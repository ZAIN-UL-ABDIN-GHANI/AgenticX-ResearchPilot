# Example 2 — What are the main differences between LangGraph and traditional LLM chains?

> **Note on how this example was produced:** this is real output from the actual system (`POST /api/v1/research` -> the real LangGraph agent -> the real citation validator -> the real database), captured via `backend/generate_examples.py`. Because this sandboxed environment has no live network access to the Google Search/Gemini APIs, the network calls made by the three tools (`web_search`, `fetch_page`, `summarize`) were substituted with realistic, fixed responses so the example is reproducible -- everything downstream of those calls (agent routing, step counting, citation validation, database persistence, and the API responses below) is the real, unmodified system.

## Request

```http
POST /api/v1/research
Content-Type: application/json

{
  "question": "What are the main differences between LangGraph and traditional LLM chains?",
  "max_steps": 8
}
```

## Agent Execution Trace

**Steps used:** 6 / 8   |   **Final status:** `completed`

| Step | Tool | Status | Detail |
|---|---|---|---|
| 1 | `web_search` | success | query: "What are the main differences between LangGraph and traditional LLM chains?" → 2 result(s) |
| 2 | `fetch_page` | success | SRC-001: 84 words fetched |
| 3 | `fetch_page` | success | SRC-002: 72 words fetched |
| 4 | `summarize` | success | SRC-001: "LangGraph models workflows as explicit state graphs with cycles, unlike traditional linear chains" |
| 5 | `summarize` | success | SRC-002: "LangGraph supports cycles between nodes and can enforce a hard step limit inside the routing node to guarantee termination" |

## Sources Discovered

| Source ID | Title | Domain | Fetch Status | Words |
|---|---|---|---|---|
| SRC-001 | LangGraph: Building Stateful, Multi-Actor LLM Applications | langchain-ai.github.io | success | 84 |
| SRC-002 | Cyclic Graphs vs Directed Acyclic Chains in LLM Orchestration | blog.langchain.dev | success | 72 |

## Claims and Citations

**Claim 3:** LangGraph models workflows as explicit state graphs with cycles, unlike traditional linear chains.

- **[1]** LangGraph: Building Stateful, Multi-Actor LLM Applications — https://langchain-ai.github.io/langgraph/ (confidence: 90%)
  > _Evidence:_ "Traditional LLM chains compose steps as a linear (or simple branching) sequence with no built-in support for cycles. LangGraph instead models a workfl"

**Claim 4:** LangGraph supports cycles between nodes and can enforce a hard step limit inside the routing node to guarantee termination.

- **[2]** Cyclic Graphs vs Directed Acyclic Chains in LLM Orchestration — https://blog.langchain.dev/langgraph-vs-chains (confidence: 90%)
  > _Evidence:_ "A classic LLM chain is a directed acyclic graph (DAG) of steps executed once each. Many agentic behaviors, however, require revisiting the same decisi"

## Final Answer (as returned by `GET /api/v1/research/{id}`)

```
LangGraph models workflows as explicit state graphs with cycles, unlike traditional linear chains [1] LangGraph supports cycles between nodes and can enforce a hard step limit inside the routing node to guarantee termination [2]

## Sources

[1] LangGraph: Building Stateful, Multi-Actor LLM Applications
    Domain: langchain-ai.github.io
    URL: https://langchain-ai.github.io/langgraph/

[2] Cyclic Graphs vs Directed Acyclic Chains in LLM Orchestration
    Domain: blog.langchain.dev
    URL: https://blog.langchain.dev/langgraph-vs-chains


```

## What This Demonstrates

- A comparative question still resolves to two independently cited claims, one per source, rather than a single unattributed summary -- the citation validator matches each generated sentence to its own evidence, not just the first available source.
- Total steps used (6) is well under the `max_steps` budget (8), showing the agent finishes as soon as it runs out of useful work to do, rather than always consuming the full budget.
