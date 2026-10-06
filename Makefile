.PHONY: env start start-all stop status logs health ingest test test-e2e test-live lint format eval clean

env:            ## generate .env with random secrets (never overwrites)
	bash scripts/make-env.sh

start:          ## core stack: API, Postgres, OpenSearch, Redis, Airflow
	docker compose up -d --build

start-all:      ## core stack plus Langfuse tracing
	docker compose --profile tracing up -d --build

stop:
	docker compose --profile tracing --profile bot --profile tools down

status:
	docker compose --profile tracing --profile bot ps

logs:
	docker compose logs -f --tail 100 api

health:
	curl -s http://localhost:8000/api/v1/health | python3 -m json.tool

ingest:         ## run the ingestion DAG now
	docker compose exec airflow airflow dags trigger driver_ops_ingestion

test:
	uv run pytest -q

test-e2e:       ## browser tests of the chat UI, mocked API (no services needed)
	uv run pytest tests/e2e -m "e2e and not live" -q

test-live:      ## browser tests against the real running stack
	uv run pytest tests/e2e -m live -q

lint:
	uv run ruff check . && uv run mypy src

format:
	uv run ruff check --fix . && uv run ruff format .

eval:           ## acceptance test against the running stack (what drivers get)
	uv run python evals/run_eval.py --mode agentic

clean:          ## stop and DELETE all data volumes
	docker compose --profile tracing --profile bot --profile tools down -v
