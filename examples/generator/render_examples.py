import json

TITLES = {
    "example_1_rag": "Example 1 — What is RAG and why is it useful for LLM applications?",
    "example_2_langgraph": "Example 2 — What are the main differences between LangGraph and traditional LLM chains?",
    "example_3_hallucination": "Example 3 — What are current techniques for reducing LLM hallucinations?",
}

d = json.load(open("/tmp/example_runs.json"))

for name, r in d.items():
    status = r["status"]
    sources = r["sources"]["sources"]
    tools = r["tools"]["tool_calls"]
    claims = r["claims"]["claims"]

    lines = []
    lines.append(f"# {TITLES[name]}\n")
    lines.append(
        "> **Note on how this example was produced:** this is real output from "
        "the actual system (`POST /api/v1/research` -> the real LangGraph agent "
        "-> the real citation validator -> the real database), captured via "
        "`backend/generate_examples.py`. Because this sandboxed environment has "
        "no live network access to the Google Search/Gemini APIs, the network "
        "calls made by the three tools (`web_search`, `fetch_page`, `summarize`) "
        "were substituted with realistic, fixed responses so the example is "
        "reproducible -- everything downstream of those calls (agent routing, "
        "step counting, citation validation, database persistence, and the API "
        "responses below) is the real, unmodified system.\n"
    )

    lines.append("## Request\n")
    lines.append("```http")
    lines.append("POST /api/v1/research")
    lines.append("Content-Type: application/json\n")
    lines.append(json.dumps({"question": status["question"], "max_steps": status["max_steps"]}, indent=2))
    lines.append("```\n")

    lines.append("## Agent Execution Trace\n")
    lines.append(f"**Steps used:** {status['steps_used']} / {status['max_steps']}   |   **Final status:** `{status['status']}`\n")
    lines.append("| Step | Tool | Status | Detail |")
    lines.append("|---|---|---|---|")
    for t in tools:
        detail = ""
        if t["tool_name"] == "web_search":
            detail = f"query: \"{t['input']['query']}\" → {t['output']['result_count']} result(s)"
        elif t["tool_name"] == "fetch_page":
            detail = f"{t['input']['source_id']}: {t['output']['word_count']} words fetched"
        elif t["tool_name"] == "summarize":
            detail = f"{t['input']['source_id']}: \"{t['output']['summary']}\""
        lines.append(f"| {t['step_number']} | `{t['tool_name']}` | {t['status']} | {detail} |")
    lines.append("")

    lines.append("## Sources Discovered\n")
    lines.append("| Source ID | Title | Domain | Fetch Status | Words |")
    lines.append("|---|---|---|---|---|")
    for s in sources:
        lines.append(f"| {s['source_id']} | {s['title']} | {s['domain']} | {s['fetch_status']} | {s['word_count']} |")
    lines.append("")

    lines.append("## Claims and Citations\n")
    for c in claims:
        lines.append(f"**Claim {c['claim_id']}:** {c['claim_text']}\n")
        for cit in c["citations"]:
            lines.append(
                f"- **[{cit['citation_number']}]** {cit['title']} — {cit['url']} "
                f"(confidence: {cit['confidence']}%)\n"
                f"  > _Evidence:_ \"{cit['evidence']}\""
            )
        lines.append("")

    lines.append("## Final Answer (as returned by `GET /api/v1/research/{id}`)\n")
    lines.append("```")
    lines.append(status["final_answer"])
    lines.append("```\n")

    lines.append("## What This Demonstrates\n")
    if name == "example_1_rag":
        lines.append(
            "- The agent selected `web_search` first, then `fetch_page` for each "
            "discovered source, then `summarize` for each successfully fetched "
            "source, before finishing -- exactly the planner routing logic "
            "described in `docs/SYSTEM_DESIGN.md` §8.\n"
            "- Both claims in the final answer trace to a distinct fetched "
            "source (SRC-001, SRC-002), each with a citation number matching "
            "the `[1]`/`[2]` markers in the answer text."
        )
    elif name == "example_2_langgraph":
        lines.append(
            "- A comparative question still resolves to two independently "
            "cited claims, one per source, rather than a single unattributed "
            "summary -- the citation validator matches each generated "
            "sentence to its own evidence, not just the first available "
            "source.\n"
            "- Total steps used (6) is well under the `max_steps` budget (8), "
            "showing the agent finishes as soon as it runs out of useful work "
            "to do, rather than always consuming the full budget."
        )
    else:
        lines.append(
            "- A broader question pulled in three sources rather than two, "
            "using 8 of the 8 available steps -- right at the step budget -- "
            "and still finished cleanly with three independently cited claims, "
            "demonstrating the multi-source citation validation path (each "
            "claim must independently match its own evidence, not just "
            "\"some\" evidence) at a larger scale than examples 1-2.\n"
            "- This scenario intentionally uses exactly `max_steps` steps to "
            "also illustrate that reaching the budget does not truncate or "
            "corrupt the answer -- the planner still finishes cleanly on the "
            "final allowed step."
        )
    lines.append("")

    out_path = f"/home/claude/build/researchpilot-ai/examples/{name.upper()}.md"
    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    print("wrote", out_path)
