# Canadian Trucking Compliance Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-compose-2496ED.svg)](https://www.docker.com/)

A free, open-source compliance assistant for truckers across Canada. Get accurate answers about trucking regulations for any province or federal jurisdiction—in English or Punjabi.

**Features:**
- **Coverage:** All 13 Canadian jurisdictions (federal + 10 provinces + 3 territories)
- **Languages:** Ask in English or Punjabi (ਪੰਜਾਬੀ); answers in English
- **Accuracy:** Citations to official regulations and source URLs
- **Open-source:** MIT license; community-maintained
- **Free:** No login, no payments, no company data
- **Local-first:** LLM and embeddings run on [Ollama](https://ollama.com) on your machine

## Supported Languages

### UI Languages
- English (full support)
- Punjabi (ਪੰਜਾਬੀ) — Phase 1

### Query Languages
- English
- Punjabi (users can ask questions in Punjabi; answers in English)

### Document Languages
- English (all regulations)
- Punjabi translations: Phase 2 (if demand warrants)

## Corpus

| Folder | Contents |
|---|---|
| `corpus/regulations/federal/` | FMVSS, CSA, CVSA — federal standards |
| `corpus/regulations/provinces/` | All 13 jurisdictions (BC, AB, SK, MB, ON, QC, NB, NS, PE, NL, YT, NT, NU) |
| `corpus/manifest.csv` | Metadata for all ~300+ documents |

The corpus is community-maintained. See [CONTRIBUTING.md](CONTRIBUTING.md) to update regulations or suggest improvements.

## Architecture

```
Telegram bot ─┐
Chat UI ──────┼─► FastAPI ─► LangGraph agent ─► OpenSearch (BM25 + vector)
              │                 │                 Ollama (LLM, embeddings)
              │                 └─► Redis (response cache)
Airflow DAG ──► parse (Docling / HTML / Markdown) ─► chunk ─► embed ─► OpenSearch
                                 Postgres (document metadata) · Langfuse (optional tracing)
```

**Agent flow:** `guardrail` → `out_of_scope`, or `retrieve` → `grade_documents` → `generate_answer`; a poor retrieval goes through `rewrite_query` and back to `retrieve`, and ends at `not_found` once attempts run out.

**Degrades gracefully:** without embeddings it falls back to BM25 only; without Redis it skips caching.

| Path | Purpose |
|---|---|
| `src/main.py` | FastAPI app; clients are built once per worker in the lifespan |
| `src/routers/` | health, hybrid search, plain RAG `ask`, `ask-agentic` (+ SSE `/stream`) |
| `src/services/agents/` | LangGraph agent, nodes, prompts, limits |
| `src/services/opensearch/` | hybrid retrieval, index config, citations, cache keys |
| `src/services/parser/` | PDF (Docling), HTML and Markdown parsers |
| `src/services/telegram/` | Telegram bot (talks to the API over HTTP) |
| `airflow/dags/driver_ops_ingestion/` | daily ingestion DAG |
| `ui_server.py`, `ui/` | local chat page; adds the API key server-side |
| `evals/` | acceptance questions, runner and thresholds |
| `tests/` | unit, API and live browser (e2e) tests |

## Stack

Python 3.12 (managed with `uv`), FastAPI, LangGraph, OpenSearch, PostgreSQL, Redis, Airflow, Docling, Ollama (`gemma3:4b`, `bge-m3` by default), Langfuse (optional), Docker Compose.

## Quick start

Requirements: Docker, [`uv`](https://docs.astral.sh/uv/), and Ollama running on the host.

```bash
ollama pull gemma3:4b && ollama pull bge-m3

bash fetch_corpus.sh      # download the 18 regulations; check corpus/regulations/fetch_log.txt
make env                  # generate .env with random secrets (never overwrites)
make start                # api, postgres, opensearch, redis, airflow
make ingest               # run the ingestion DAG
make health               # curl /api/v1/health
```

Then ask a question:

```bash
uv run python ui_server.py   # chat UI at http://127.0.0.1:7861
```

or call `POST /api/v1/ask-agentic` on `http://127.0.0.1:8000` with your `API_KEY`.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for cloud setup (AWS, DigitalOcean, self-hosted).

## Contributing

This is a community-maintained corpus. To update regulations or suggest improvements, see [CONTRIBUTING.md](CONTRIBUTING.md).

**GitHub:** [canadian-trucking-compliance/platform](https://github.com/canadian-trucking-compliance/platform)  
**Issues:** [Report bugs or suggest regulations](https://github.com/canadian-trucking-compliance/platform/issues)

| Service | URL |
|---|---|
| API | http://127.0.0.1:8000 |
| Airflow | http://127.0.0.1:8081 |
| Langfuse (`make start-all`) | http://127.0.0.1:3001 |
| OpenSearch Dashboards (profile `tools`) | http://127.0.0.1:5601 |

Compose profiles: `tracing` (Langfuse), `bot` (Telegram), `tools` (OpenSearch Dashboards).

### Telegram bot

Set `TELEGRAM__ENABLED`, `TELEGRAM__BOT_TOKEN` and `TELEGRAM__ALLOWED_USER_IDS` in `.env`, then start the `bot` profile. Only listed user ids can use it; an empty list means nobody.

### Re-ingesting

The DAG reprocesses the whole corpus but only re-parses changed files. After changing the parser, chunker or embedding model, trigger it with `{"force_reparse": true}` or `{"force_reindex": true}`.

## Configuration

Copy `.env.example` to `.env` (or run `make env`). Nested settings use a **double underscore** (`REDIS__PASSWORD`); a single underscore is silently ignored. `.env` holds real secrets and is git-ignored.

## Development

```bash
make test     # pytest
make lint     # ruff + mypy
make format   # ruff --fix + ruff format
make test-live  # browser tests against the running stack
```

Always run Python through `uv` (`uv run ...`, `uv sync`, `uv add`).

## GitHub Actions with Claude

You can set up GitHub Actions to automate workflows using Claude Code:

```bash
/install-github-app    # Authorize Claude to access your GitHub repository
```

This allows Claude to:
- Run tests and linting on pull requests
- Deploy changes to staging or production
- Trigger ingestion DAGs on code changes
- Post review comments and status checks

To revoke access later:

```bash
gh auth logout
```

## Evaluation

`evals/questions.md` holds the acceptance questions, expected sources and release thresholds; `evals/questions.yaml` is the machine-readable version.

```bash
uv run python evals/run_eval.py --mode bm25|hybrid|ask|agentic   # make eval = agentic
```

Modes run staged: retrieval only, hybrid, plain RAG, then the full agent. Results go to `evals/results/<mode>.md`, and the script exits 1 if a threshold is missed.

| Check | Target |
|---|---|
| Retrieval hit (Q01–Q15, Q22–Q24) | ≥ 80% |
| Citations correct | 100% |
| Q16–Q18 (not in corpus) | not invented |
| Q19–Q21 (off-topic) | refused |
| Q24 (Punjabi) | handled sensibly |

The automatic checks do not verify regulation numbers, so read answers against the cited section. `evals/deepeval_eval.py` needs the `eval` dependency group.

## Disclaimer

Maple Freight Inc., its phone numbers and email addresses are fictional. The regulation documents are the real public sources; check them for currency before relying on this for real compliance decisions. Answers are not legal advice.
