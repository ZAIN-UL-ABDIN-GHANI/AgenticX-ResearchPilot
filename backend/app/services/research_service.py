"""
Research Service.

This is the missing link between the FastAPI layer and the LangGraph agent:
it runs the full agentic workflow for a research run and persists every
artifact (sources, tool calls, claims, citations, final answer) so the
GET endpoints can serve them back.

Workflow
--------
1. Build a fresh ``AgentContext`` + compiled LangGraph graph for this run.
2. ``graph.ainvoke(...)`` drives planner -> tool -> planner ... until the
   hard step limit is hit or the planner decides there's nothing left to do.
3. Synthesize a final answer from the collected evidence using Gemini,
   falling back to a safe extractive answer if Gemini is unavailable/fails.
4. Run citation validation (NO SOURCE = NO CLAIM) and persist only claims
   that are backed by a fetched source.
5. Mark the research run completed (or failed, if the agent itself raised).
"""

from typing import Any, Dict, Optional

import google.generativeai as genai

from app.agent.graph import AgentContext, build_research_graph
from app.agent.state import initial_state
from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import async_session_maker
from app.repositories.claim_repository import ClaimRepository
from app.repositories.research_repository import ResearchRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.tool_call_repository import ToolCallRepository
from app.services.citation_integration import CitationIntegrationService

logger = get_logger(__name__)


class ResearchService:
    """Coordinates end-to-end execution of a research run."""

    async def run_research(
        self, research_id: int, question: str, max_steps: int
    ) -> None:
        """Execute the full research workflow and persist the outcome.

        This is designed to be called as a background task immediately after
        the research run row is created and committed by the API layer, so
        it opens its own database session rather than reusing the request's.
        """
        async with async_session_maker() as session:
            research_repo = ResearchRepository(session)
            source_repo = SourceRepository(session)
            tool_call_repo = ToolCallRepository(session)
            claim_repo = ClaimRepository(session)
            citation_service = CitationIntegrationService()

            ctx = AgentContext(source_repo, tool_call_repo, citation_service)
            graph = build_research_graph(ctx)

            state = initial_state(question, research_id, max_steps)

            try:
                # recursion_limit guards against any LangGraph-internal
                # runaway independent of our own step_count check.
                final_state = await graph.ainvoke(
                    state, config={"recursion_limit": (max_steps * 4) + 20}
                )
                await session.commit()
            except Exception as exc:  # noqa: BLE001 - must never crash the run
                logger.error(
                    "Agent execution failed for research %s: %s",
                    research_id,
                    exc,
                    exc_info=True,
                )
                await session.rollback()
                await research_repo.fail(research_id, f"Agent execution error: {exc}")
                await session.commit()
                return

            steps_used = final_state.get("step_count", 0)

            try:
                answer_text = await self._generate_answer(question, citation_service)
            except Exception as exc:  # noqa: BLE001
                logger.error("Answer generation failed: %s", exc, exc_info=True)
                answer_text = self._extractive_fallback_answer(citation_service)

            if not answer_text or not answer_text.strip():
                # No evidence to ground an answer -> do not fabricate one.
                await research_repo.update(research_id, steps_used=steps_used)
                await research_repo.fail(
                    research_id,
                    "Insufficient evidence was gathered to produce a "
                    "supported answer within the step budget.",
                )
                await session.commit()
                return

            validation_report = citation_service.validate_answer(answer_text)
            final_answer = citation_service.build_final_answer_with_citations(
                answer_text, validation_report
            )
            citations_section = citation_service.get_citations_section(
                validation_report
            )
            if validation_report.get("fetched_sources"):
                final_answer = f"{final_answer}\n\n{citations_section}"

            await self._persist_claims(
                claim_repo, source_repo, citation_service, research_id, validation_report
            )

            await research_repo.update(research_id, steps_used=steps_used)
            await research_repo.complete(research_id, final_answer)
            await session.commit()

            logger.info(
                "Research %s completed in %s/%s steps (%s claims verified)",
                research_id,
                steps_used,
                max_steps,
                validation_report.get("verified_claims", 0),
            )

    async def _persist_claims(
        self,
        claim_repo: ClaimRepository,
        source_repo: SourceRepository,
        citation_service: CitationIntegrationService,
        research_id: int,
        validation_report: Dict[str, Any],
    ) -> None:
        """Persist only claims that passed citation validation.

        Enforces NO SOURCE = NO CLAIM at the persistence layer as a final
        safety net, in addition to the validation already performed above.
        """
        citation_number = 1
        for claim in validation_report.get("claims", []):
            if not claim.get("verified") or not claim.get("source_ids"):
                continue

            db_claim = await claim_repo.create_claim(
                research_run_id=research_id, claim_text=claim["claim_text"]
            )

            for source_id in claim["source_ids"]:
                source = await source_repo.get_by_source_id(research_id, source_id)
                if source is None or source.fetch_status != "success":
                    # Belt-and-braces: never cite a source that wasn't
                    # actually fetched successfully.
                    continue

                # Find matching evidence text/confidence for this source.
                evidence_text = None
                confidence = None
                for ev_id in claim.get("evidence_ids", []):
                    ev = citation_service.evidence_map.get(ev_id)
                    if ev and ev.get("source_id") == source_id:
                        evidence_text = ev.get("evidence") or ev.get("text")
                        confidence = ev.get("confidence")
                        break

                await claim_repo.add_citation(
                    claim_id=db_claim.id,
                    source_id=source.id,
                    evidence=evidence_text,
                    citation_number=citation_number,
                    confidence=confidence,
                )
                citation_number += 1

    async def _generate_answer(
        self, question: str, citation_service: CitationIntegrationService
    ) -> str:
        """Synthesize a final answer from collected evidence using Gemini."""
        evidence_items = list(citation_service.evidence_map.values())

        if not evidence_items:
            return ""

        evidence_block = "\n".join(
            f"- {item['text']} (source: {item['source_id']})"
            for item in evidence_items[:30]
        )

        prompt = (
            f"Question: {question}\n\n"
            "Using ONLY the evidence below, write a concise, well-organized "
            "answer in plain prose (no headings, no citation markers -- those "
            "are added separately). Do not include any claim that isn't "
            "directly supported by the evidence.\n\n"
            f"Evidence:\n{evidence_block}\n\n"
            "Answer:"
        )

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.2, "max_output_tokens": 1000},
        )
        text = (response.text or "").strip()
        return text or self._extractive_fallback_answer(citation_service)

    def _extractive_fallback_answer(
        self, citation_service: CitationIntegrationService
    ) -> str:
        """Build a safe answer directly from evidence text if Gemini fails.

        This keeps the "no evidence -> do not fabricate" guarantee even when
        the LLM call itself is unavailable, by falling back to a purely
        extractive combination of the evidence sentences already grounded in
        fetched sources.
        """
        evidence_items = list(citation_service.evidence_map.values())
        if not evidence_items:
            return ""
        sentences = [item["text"].strip().rstrip(".") + "." for item in evidence_items[:8]]
        return " ".join(sentences)
