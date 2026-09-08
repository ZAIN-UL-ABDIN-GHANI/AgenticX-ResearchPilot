# Example Run Generator (dev tooling)

`generate_examples.py` and `render_examples.py` were used to produce the
three example run documents in `examples/*.md`. They run the **real**
FastAPI app, LangGraph agent, and citation validator end-to-end via
`httpx`'s ASGI transport, with only the three tools' external network calls
(Google Search / page fetch / Gemini) replaced by realistic canned
responses — since this can be run without any real API keys or network
access, unlike the actual production system.

To regenerate the examples yourself (e.g. after modifying the agent):

```bash
cd backend
python3 ../examples/generator/generate_examples.py   # writes /tmp/example_runs.json
python3 ../examples/generator/render_examples.py      # writes examples/EXAMPLE_*.md
```

These scripts are not part of the shipped application — they're a
reproducibility aid for the example documentation only.
