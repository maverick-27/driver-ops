# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Driver Ops: a RAG agent for a trucking company. Drivers ask compliance and company-procedure questions (via Telegram, or the local chat UI) and get short answers citing source documents. It only answers trucking compliance and company procedures and refuses everything else. When company policy and regulation both apply, answers give both and label which is which. The corpus is `corpus/regulations/` (R01–R18, HTML and PDF, official Canadian/US/Ontario sources listed in `manifest.csv`, fetched by `fetch_corpus.sh`) and `corpus/company/` (C01–C06, fictional "Maple Freight Inc." markdown policies).

## Commands

Python 3.12, managed with `uv`.

```bash
make env          # generate .env with random secrets (never overwrites)
make start        # docker compose: api, postgres, opensearch, redis, airflow
make start-all    # plus Langfuse tracing (profile "tracing")
make ingest       # trigger the Airflow DAG driver_ops_ingestion
make health       # curl /api/v1/health
make test         # uv run pytest -q
make lint         # ruff check . && mypy src
make format       # ruff --fix + ruff format
make eval         # uv run python evals/run_eval.py --mode agentic
uv run pytest tests/unit/test_x.py::test_name   # single test
uv run python ui_server.py                      # chat UI at http://127.0.0.1:7861 (proxies to API on :8000)
```

Compose profiles: `tracing` (Langfuse), `bot` (Telegram bot: `python -m src.services.telegram.bot`), `tools` (OpenSearch Dashboards). The LLM and embeddings run on **Ollama on the host** (not in Compose); containers reach it at `host.docker.internal:11434`. Defaults: `gemma3:4b`, embeddings `bge-m3`.

Eval modes: `uv run python evals/run_eval.py --mode bm25|hybrid|ask|agentic` (staged retrieval -> plain RAG -> agent). Questions live in `evals/questions.yaml` (derived from `questions.md`, which holds the release thresholds); results are written to `evals/results/<mode>.md/.json` and the script exits 1 if a threshold is missed. Automatic checks do not verify regulation numbers; read answers against the cited section. `evals/deepeval_eval.py` needs the `eval` dependency group.

## Architecture

- **API** (`src/main.py`, FastAPI): the lifespan builds every client once per Uvicorn worker and stores them on `app.state` (`dependencies.py` exposes them to routers). OpenSearch, embeddings and Redis are optional/degrade gracefully (embeddings missing -> BM25 only; Redis missing -> no caching). Routers: `ping` (health), `hybrid_search`, `ask` (plain RAG), `agentic_ask` (`/api/v1/ask-agentic` and `/stream` SSE).
- **Agent** (`src/services/agents/agentic_rag.py`): a LangGraph compiled once and reused. Flow: `guardrail` -> (`out_of_scope` | `retrieve` -> `grade_documents` -> `generate_answer` | `rewrite_query` -> back to `retrieve` | `not_found`). Nodes are in `agents/nodes/`; prompts in `agents/prompts.py`; limits (top_k, `max_retrieval_attempts`, `guardrail_threshold`) in `agents/config.py` and overridable per request.
- **Retrieval** (`src/services/opensearch/`, `retrieval.py`): hybrid BM25 + vector search; index config in `index_config_hybrid.py`. `citations.py` extracts/sanitizes citations and builds follow-up retrieval queries; `rag.py` has cache keys and cited-source helpers.
- **Ingestion** (`airflow/dags/driver_ops_ingestion/`): daily DAG setup -> fetch_and_parse -> index -> report. Reprocesses the whole corpus but only re-parses changed files; trigger with `{"force_reparse": true}` or `{"force_reindex": true}` after changing the parser, chunker or embedding model. Parsers live in `src/services/parser/` (`docling_pdf.py` for PDFs, `html.py`, `markdown.py`); Docling is installed only in the Airflow image (`ingest` dependency group), not the API image.
- **Persistence**: Postgres (SQLAlchemy models/repositories for document metadata), OpenSearch (chunks), Redis (response cache), Langfuse (optional tracing).
- **Clients** follow a `factory.py` pattern (`make_*_client()`) in each `src/services/<name>/` package.
- **Telegram bot** (`src/services/telegram/`): talks to the API over HTTP; access restricted to `TELEGRAM__ALLOWED_USER_IDS` (empty = nobody).
- `ui_server.py` + `ui/index.html`: standalone chat page that adds the API key server-side so it never reaches the browser.

## Conventions and gotchas

- Nested settings use a **double underscore** in env vars (`REDIS__PASSWORD`); a single underscore is silently ignored. See `.env.example`.
- Ruff line length 130 (E501 ignored), rules E,F,I,B,UP; mypy `check_untyped_defs`. pytest runs with `asyncio_mode = "auto"` and `pythonpath = ["."]`.
- Always use `uv` to run the server and any Python (`uv run ...`, `uv sync`, `uv add`); never call `pip` directly.
- `.env` holds real secrets; never print or commit it.
