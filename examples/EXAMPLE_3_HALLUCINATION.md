# Example 3 — What are current techniques for reducing LLM hallucinations?

> **Note on how this example was produced:** this is real output from the actual system (`POST /api/v1/research` -> the real LangGraph agent -> the real citation validator -> the real database), captured via `backend/generate_examples.py`. Because this sandboxed environment has no live network access to the Google Search/Gemini APIs, the network calls made by the three tools (`web_search`, `fetch_page`, `summarize`) were substituted with realistic, fixed responses so the example is reproducible -- everything downstream of those calls (agent routing, step counting, citation validation, database persistence, and the API responses below) is the real, unmodified system.

## Request

```http
POST /api/v1/research
Content-Type: application/json

{
  "question": "What are current techniques for reducing LLM hallucinations?",
  "max_steps": 8
}
```

## Agent Execution Trace

**Steps used:** 8 / 8   |   **Final status:** `completed`

| Step | Tool | Status | Detail |
|---|---|---|---|
| 1 | `web_search` | success | query: "What are current techniques for reducing LLM hallucinations?" → 3 result(s) |
| 2 | `fetch_page` | success | SRC-001: 48 words fetched |
| 3 | `fetch_page` | success | SRC-002: 32 words fetched |
| 4 | `fetch_page` | success | SRC-003: 53 words fetched |
| 5 | `summarize` | success | SRC-001: "Retrieval-augmentation reduces hallucination by conditioning output on retrieved passages" |
| 6 | `summarize` | success | SRC-002: "Self-consistency reduces confidently-stated incorrect answers by sampling multiple reasoning paths and selecting the most common answer" |
| 7 | `summarize` | success | SRC-003: "Citation verification pipelines reject claims that cannot be matched to a specific retrieved source" |

## Sources Discovered

| Source ID | Title | Domain | Fetch Status | Words |
|---|---|---|---|---|
| SRC-001 | Retrieval-Augmented Generation for Knowledge-Intensive NLP | arxiv.org | success | 48 |
| SRC-002 | Self-Consistency and Verification in Language Model Reasoning | arxiv.org | success | 32 |
| SRC-003 | Citation Verification Pipelines for Generated Text | arxiv.org | success | 53 |

## Claims and Citations

**Claim 5:** Retrieval-augmentation reduces hallucination by conditioning output on retrieved passages.

- **[1]** Retrieval-Augmented Generation for Knowledge-Intensive NLP — https://arxiv.org/abs/2005.11401 (confidence: 90%)
  > _Evidence:_ "One widely used technique for reducing hallucination is retrieval-augmentation: conditioning the model's output on passages retrieved from an external"

**Claim 6:** Self-consistency reduces confidently-stated incorrect answers by sampling multiple reasoning paths and selecting the most common answer.

- **[2]** Self-Consistency and Verification in Language Model Reasoning — https://arxiv.org/abs/2203.11171 (confidence: 90%)
  > _Evidence:_ "Self-consistency methods sample multiple independent reasoning paths for the same question and select the most common final answer, which reduces the "

**Claim 7:** Citation verification pipelines reject claims that cannot be matched to a specific retrieved source.

- **[3]** Citation Verification Pipelines for Generated Text — https://arxiv.org/abs/2305.14627 (confidence: 90%)
  > _Evidence:_ "A citation verification stage checks each claim in a generated answer against the evidence it cites, and rejects or flags any claim that cannot be mat"

## Final Answer (as returned by `GET /api/v1/research/{id}`)

```
Retrieval-augmentation reduces hallucination by conditioning output on retrieved passages [1] Self-consistency reduces confidently-stated incorrect answers by sampling multiple reasoning paths and selecting the most common answer [2] Citation verification pipelines reject claims that cannot be matched to a specific retrieved source [3]

## Sources

[1] Retrieval-Augmented Generation for Knowledge-Intensive NLP
    Domain: arxiv.org
    URL: https://arxiv.org/abs/2005.11401

[2] Self-Consistency and Verification in Language Model Reasoning
    Domain: arxiv.org
    URL: https://arxiv.org/abs/2203.11171

[3] Citation Verification Pipelines for Generated Text
    Domain: arxiv.org
    URL: https://arxiv.org/abs/2305.14627


```

## What This Demonstrates

- A broader question pulled in three sources rather than two, using 8 of the 8 available steps -- right at the step budget -- and still finished cleanly with three independently cited claims, demonstrating the multi-source citation validation path (each claim must independently match its own evidence, not just "some" evidence) at a larger scale than examples 1-2.
- This scenario intentionally uses exactly `max_steps` steps to also illustrate that reaching the budget does not truncate or corrupt the answer -- the planner still finishes cleanly on the final allowed step.
