#!/usr/bin/env bash
set -euo pipefail

airflow db migrate

airflow users create \
  --username "${AIRFLOW_ADMIN_USER}" --password "${AIRFLOW_ADMIN_PASSWORD}" \
  --firstname Driver --lastname Ops --role Admin --email admin@example.invalid || true

airflow webserver --port 8080 &
exec airflow scheduler
