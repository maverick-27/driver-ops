#!/usr/bin/env bash
# Writes .env from .env.example with a fresh random secret in place of every "change-me". Never overwrites.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -e .env ]; then echo ".env already exists; not overwriting"; exit 0; fi

rand() { openssl rand -hex "$1"; }
pg=$(rand 16)
while IFS= read -r line; do
  case "$line" in
    POSTGRES_PASSWORD=*) echo "POSTGRES_PASSWORD=$pg" ;;
    POSTGRES_DATABASE_URL=*) echo "POSTGRES_DATABASE_URL=postgresql+psycopg2://driver_ops:$pg@localhost:5442/driver_ops" ;;
    LANGFUSE_ENCRYPTION_KEY=*) echo "LANGFUSE_ENCRYPTION_KEY=$(rand 32)" ;;
    LANGFUSE__PUBLIC_KEY=*) echo "LANGFUSE__PUBLIC_KEY=pk-lf-$(rand 16)" ;;
    LANGFUSE__SECRET_KEY=*) echo "LANGFUSE__SECRET_KEY=sk-lf-$(rand 16)" ;;
    *=change-me) echo "${line%%=*}=$(rand 16)" ;;
    *) echo "$line" ;;
  esac
done < .env.example > .env
chmod 600 .env
echo "Wrote .env"
