"""
Phase 9: FastAPI Research Endpoints

Provides REST API for research workflow:
- POST /api/v1/research - Start research
- GET /api/v1/research/{research_id} - Get research status
- GET /api/v1/research/{research_id}/sources - Get sources
- GET /api/v1/research/{research_id}/tools - Get tool calls
- GET /api/v1/research/{research_id}/claims - Get claims
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.schemas.common import ErrorResponse, SuccessResponse
from app.schemas.research import (
    ResearchCreateRequest,
    ResearchResponse,
    ResearchStatusResponse,
    SourceListResponse,
    ToolCallListResponse,
    ClaimListResponse,
)
from app.services.research_service import ResearchService
from app.repositories.research_repository import ResearchRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.tool_call_repository import ToolCallRepository
from app.repositories.claim_repository import ClaimRepository
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["research"])


@router.post(
    "/research",
    response_model=ResearchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start new research",
    responses={
        201: {"description": "Research started successfully"},
        400: {"description": "Invalid request", "model": ErrorResponse},
    },
)
async def start_research(
    request: ResearchCreateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> ResearchResponse:
    """
    Start a new research task.

    Args:
        request: Research creation request with question and optional max_steps
        session: Database session

    Returns:
        ResearchResponse with research_id and status

    Raises:
        HTTPException: If validation fails
    """
    try:
        if not request.question or not request.question.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty",
            )

        if len(request.question) > 500:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question too long (max 500 characters)",
            )

        # Create research run in database
        repo = ResearchRepository(session)
        research = await repo.create(
            question=request.question,
            max_steps=request.max_steps or 8,
        )

        await session.commit()

        logger.info(
            f"Research started: {research.id}",
            extra={
                "research_id": research.id,
                "question": request.question[:50],
            },
        )

        # Kick off the LangGraph agent in the background. It opens its own
        # DB session (see ResearchService.run_research) so it is safe to run
        # after this request's session/response cycle completes.
        research_service = ResearchService()
        background_tasks.add_task(
            research_service.run_research,
            research.id,
            research.question,
            research.max_steps,
        )

        return ResearchResponse(
            research_id=str(research.id),
            question=research.question,
            status=research.status,
            max_steps=research.max_steps,
            created_at=research.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting research: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start research",
        )


@router.get(
    "/research/{research_id}",
    response_model=ResearchStatusResponse,
    summary="Get research status",
    responses={
        200: {"description": "Research status retrieved"},
        404: {"description": "Research not found", "model": ErrorResponse},
    },
)
async def get_research(
    research_id: int,
    session: AsyncSession = Depends(get_session),
) -> ResearchStatusResponse:
    """
    Get the status and details of a research task.

    Args:
        research_id: Research ID
        session: Database session

    Returns:
        ResearchStatusResponse with complete status

    Raises:
        HTTPException: If research not found
    """
    try:
        repo = ResearchRepository(session)
        research = await repo.get(research_id)

        if not research:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research {research_id} not found",
            )

        return ResearchStatusResponse(
            research_id=str(research.id),
            question=research.question,
            status=research.status,
            max_steps=research.max_steps,
            steps_used=research.steps_used,
            final_answer=research.final_answer,
            created_at=research.created_at.isoformat(),
            completed_at=research.completed_at.isoformat() if research.completed_at else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving research: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve research",
        )


@router.get(
    "/research/{research_id}/sources",
    response_model=SourceListResponse,
    summary="Get research sources",
    responses={
        200: {"description": "Sources retrieved"},
        404: {"description": "Research not found", "model": ErrorResponse},
    },
)
async def get_research_sources(
    research_id: int,
    session: AsyncSession = Depends(get_session),
) -> SourceListResponse:
    """
    Get all sources used in a research task.

    Args:
        research_id: Research ID
        session: Database session

    Returns:
        SourceListResponse with list of sources

    Raises:
        HTTPException: If research not found
    """
    try:
        repo_research = ResearchRepository(session)
        research = await repo_research.get(research_id)

        if not research:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research {research_id} not found",
            )

        repo_source = SourceRepository(session)
        sources = await repo_source.get_by_research(research_id)

        return SourceListResponse(
            research_id=str(research_id),
            total_sources=len(sources),
            sources=[
                {
                    "source_id": s.source_id,
                    "url": s.url,
                    "title": s.title,
                    "domain": s.domain,
                    "fetch_status": s.fetch_status,
                    "word_count": s.word_count,
                    "fetched_at": s.fetched_at.isoformat() if s.fetched_at else None,
                }
                for s in sources
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving sources: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sources",
        )


@router.get(
    "/research/{research_id}/tools",
    response_model=ToolCallListResponse,
    summary="Get tool calls",
    responses={
        200: {"description": "Tool calls retrieved"},
        404: {"description": "Research not found", "model": ErrorResponse},
    },
)
async def get_research_tools(
    research_id: int,
    session: AsyncSession = Depends(get_session),
) -> ToolCallListResponse:
    """
    Get all tool calls executed in a research task.

    Args:
        research_id: Research ID
        session: Database session

    Returns:
        ToolCallListResponse with list of tool calls

    Raises:
        HTTPException: If research not found
    """
    try:
        repo_research = ResearchRepository(session)
        research = await repo_research.get(research_id)

        if not research:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research {research_id} not found",
            )

        repo_tool = ToolCallRepository(session)
        tool_calls = await repo_tool.get_by_research(research_id)

        return ToolCallListResponse(
            research_id=str(research_id),
            total_calls=len(tool_calls),
            tool_calls=[
                {
                    "step_number": tc.step_number,
                    "tool_name": tc.tool_name,
                    "status": tc.status,
                    "input": tc.input_data,
                    "output": tc.output_data,
                    "created_at": tc.created_at.isoformat(),
                }
                for tc in tool_calls
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving tool calls: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tool calls",
        )


@router.get(
    "/research/{research_id}/claims",
    response_model=ClaimListResponse,
    summary="Get claims and citations",
    responses={
        200: {"description": "Claims retrieved"},
        404: {"description": "Research not found", "model": ErrorResponse},
    },
)
async def get_research_claims(
    research_id: int,
    session: AsyncSession = Depends(get_session),
) -> ClaimListResponse:
    """
    Get all claims and citations for a research task.

    Args:
        research_id: Research ID
        session: Database session

    Returns:
        ClaimListResponse with list of claims and citations

    Raises:
        HTTPException: If research not found
    """
    try:
        repo_research = ResearchRepository(session)
        research = await repo_research.get(research_id)

        if not research:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research {research_id} not found",
            )

        # Get claims (eagerly loaded with their citations to avoid lazy-load
        # errors under async SQLAlchemy).
        claim_repo = ClaimRepository(session)
        claims = await claim_repo.get_by_research(research_id)

        claims_data = []
        for claim in claims:
            claim_sources = []
            for cs in claim.claim_sources:
                claim_sources.append({
                    "source_id": cs.source.source_id if cs.source else None,
                    "url": cs.source.url if cs.source else None,
                    "title": cs.source.title if cs.source else None,
                    "citation_number": cs.citation_number,
                    "confidence": cs.confidence,
                    "evidence": cs.evidence,
                })

            claims_data.append({
                "claim_id": claim.id,
                "claim_text": claim.claim_text,
                "citations": claim_sources,
            })

        return ClaimListResponse(
            research_id=str(research_id),
            total_claims=len(claims_data),
            claims=claims_data,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving claims: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve claims",
        )
