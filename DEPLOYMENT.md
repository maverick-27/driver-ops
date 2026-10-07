# Deployment Guide

## Local Development

```bash
docker compose up -d
make ingest
make health
uv run python ui_server.py
```

Visit http://127.0.0.1:7861

## Cloud Deployment

### AWS EC2
1. Launch Ubuntu 22.04 LTS, t3.large (4 vCPU, 8GB RAM)
2. SSH in and clone repo
3. Install Docker, uv, Ollama
4. Start: `docker compose up -d && make ingest`
5. Expose UI via nginx reverse proxy on port 80/443

### DigitalOcean Droplet
Similar to AWS; use DigitalOcean App Platform for managed PostgreSQL + OpenSearch if preferred.

## Monitoring

- Health: `curl https://trucking-compliance.ca/api/v1/health`
- Logs: `docker compose logs -f api`
- Scaling: Add caching layer (Redis/CDN) if >100 req/sec

## Backup & Recovery

- Postgres: Use `pg_dump` daily
- OpenSearch: Snapshot to S3 daily

## Pre-Flight Checklist

```bash
make health-check
make test
make lint
```

All green? Ready to deploy.
