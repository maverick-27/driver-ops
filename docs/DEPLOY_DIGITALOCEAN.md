# Deploy to DigitalOcean

## Quick Start (15 mins)

### 1. Create Droplet
```bash
# Option A: Via CLI
doctl compute droplet create trucking-compliance \
  --region nyc3 \
  --image ubuntu-24-04-x64 \
  --size s-2vcpu-4gb \
  --ssh-keys $(doctl compute ssh-key list --format ID --no-header)

# Option B: Via Web Console
# - Ubuntu 24.04 LTS
# - 2 vCPU, 4GB RAM ($24/month)
# - New York region (nyc3)
```

### 2. SSH into Droplet
```bash
ssh root@YOUR_DROPLET_IP
```

### 3. Install Dependencies
```bash
apt update && apt install -y \
  docker.io \
  docker-compose \
  git \
  curl

# Add current user to docker group
usermod -aG docker $USER
newgrp docker
```

### 4. Install Ollama
```bash
curl -fsSL https://ollama.ai/install.sh | sh

# Pull models
ollama pull gemma3:4b
ollama pull bge-m3

# Run in background
nohup ollama serve &
```

### 5. Clone & Deploy
```bash
git clone https://github.com/canadian-trucking-compliance/platform.git
cd platform

# Setup environment
cp .env.example .env
# Edit .env: Set ENVIRONMENT=production, SECRET_KEY, etc.

# Start services
docker compose up -d

# Run ingestion
docker compose exec api uv run python -m src.services.ingestion.run

# Verify
curl http://localhost:8000/api/v1/health
```

### 6. Setup Domain & HTTPS
```bash
# Install Caddy (auto HTTPS)
apt install -y caddy

# Create Caddyfile
cat > /etc/caddy/Caddyfile << 'EOF'
trucking-compliance.ca {
  reverse_proxy localhost:8000
}
EOF

# Start Caddy
systemctl restart caddy
```

### 7. Setup Monitoring
```bash
# View logs
docker compose logs -f api

# Monitor performance
curl http://localhost:8000/api/v1/metrics

# Set up email alerts (optional)
# Use DigitalOcean Monitoring or third-party (Sentry, DataDog)
```

## Production Checklist

- [ ] Domain DNS points to Droplet IP
- [ ] SSL certificate auto-renews (Caddy)
- [ ] Backups enabled (DigitalOcean Snapshots)
- [ ] Monitoring configured
- [ ] Database backups daily
- [ ] Rate limiting enabled
- [ ] CORS configured correctly
- [ ] API key rotation plan

## Monitoring

### Health Check
```bash
curl https://trucking-compliance.ca/api/v1/health
```

### Metrics
```bash
curl https://trucking-compliance.ca/api/v1/metrics | jq .
```

### Logs
```bash
docker compose logs -f api | grep ERROR
```

## Scaling

If traffic increases:

```bash
# Upgrade Droplet size
doctl compute droplet resize DROPLET_ID --size s-4vcpu-8gb --resize-disk

# Or add load balancer + multiple droplets
```

## Costs

- **Droplet:** $24/month (2vCPU, 4GB RAM)
- **Domain:** $12/year (Namecheap)
- **Backups:** Included
- **Bandwidth:** First 1TB free
- **Total:** ~$26/month to start

## Troubleshooting

```bash
# Ollama not responding
ps aux | grep ollama
ollama serve  # Run in foreground to debug

# Database connection issues
docker compose logs postgres

# OpenSearch issues
docker compose logs opensearch

# Check disk space
df -h

# Restart all services
docker compose restart
```

## Next Steps

1. Add monitoring dashboard (Prometheus + Grafana)
2. Setup CI/CD (GitHub Actions → Auto-deploy)
3. Add email alerts
4. Scale to multiple regions (DigitalOcean App Platform)

See [DEPLOYMENT.md](../DEPLOYMENT.md) for more details.
