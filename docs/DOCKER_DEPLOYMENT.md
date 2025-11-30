# Docker Deployment Guide

## 🐳 Full Docker Setup

### Quick Start

```bash
# 1. Build and start all services
docker-compose up -d

# 2. View logs
docker-compose logs -f trader

# 3. Stop all services
docker-compose down
```

## 📦 Services

### 1. ib-gateway (IBKR Gateway)
```yaml
- Container: ib-gateway
- Image: ghcr.io/gnzsnz/ib-gateway
- Ports: 4001, 4002, 5900
- Purpose: IBKR API connection
```

### 2. trader (Gemini Trader Bot)
```yaml
- Container: gemini-trader
- Build: From Dockerfile
- Depends: ib-gateway (waits for health check)
- Purpose: Trading bot
```

## 🔧 Configuration

### Environment Variables

All configured via `.env` file:
```bash
# IBKR
IBKR_USERNAME=your_username
IBKR_PASSWORD=your_password
IBKR_ACCOUNT=DU123456
TRADING_MODE=paper

# AI
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=...

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

### Network

Both services on shared network:
```yaml
networks:
  trading-network:
    driver: bridge
```

**Benefits:**
- `trader` connects to `ib-gateway` by hostname
- No port conflicts
- Isolated from host

## 🚀 Deployment

### Initial Setup

```bash
# 1. Clone/copy project to RPi
scp -r gemini-trader-ai/ pi@raspberrypi:~/

# 2. SSH to RPi
ssh pi@raspberrypi

# 3. Configure .env
cd gemini-trader-ai
cp .env.example .env
nano .env  # Edit credentials

# 4. Start services
docker-compose up -d

# 5. Check status
docker-compose ps
docker-compose logs -f
```

### Updates

```bash
# 1. Pull latest code
git pull  # or scp new files

# 2. Rebuild and restart
docker-compose down
docker-compose build --no-cache trader
docker-compose up -d

# 3. Verify
docker-compose logs -f trader
```

### One-Command Update

```bash
# Update everything
docker-compose pull && \
docker-compose build --no-cache && \
docker-compose up -d
```

## 📊 Monitoring

### View Logs

```bash
# All services
docker-compose logs -f

# Trader only
docker-compose logs -f trader

# Gateway only
docker-compose logs -f ib-gateway

# Last 100 lines
docker-compose logs --tail=100 trader
```

### Check Health

```bash
# Service status
docker-compose ps

# Health checks
docker inspect gemini-trader | grep -A 10 Health

# Enter container
docker exec -it gemini-trader bash
```

### Resource Usage

```bash
# Real-time stats
docker stats

# Logs size
docker system df
```

## 🔄 Dependencies

### Service Startup Order

```
1. ib-gateway starts
   ↓
2. Health check (port 4002 open)
   ↓
3. trader starts (only after gateway healthy)
   ↓
4. trader connects to ib-gateway:4002
```

### Restart Behavior

```yaml
# Gateway restarts
→ trader also restarts (depends_on)

# Manual restart
docker-compose restart trader
docker-compose restart ib-gateway  # Also restarts trader
```

## 💾 Persistence

### Volumes

```yaml
volumes:
  # Gateway data
  - ib-gateway-data:/root/Jts
  
  # Trader data
  - ./data:/app/data        # Database
  - ./logs:/app/logs        # Logs
  - ./.env:/app/.env:ro     # Config (read-only)
```

**Survives:**
- Container restarts ✅
- Container rebuilds ✅
- System reboots ✅

## 🚨 Troubleshooting

### Trader Won't Start

```bash
# Check gateway health
docker-compose ps
# Should show: ib-gateway (healthy)

# If unhealthy:
docker-compose restart ib-gateway

# Check logs
docker-compose logs ib-gateway
```

### Connection Issues

```bash
# Test connectivity
docker exec gemini-trader ping ib-gateway

# Check network
docker network inspect gemini-trader-ai_trading-network

# Restart both
docker-compose down
docker-compose up -d
```

### Out of Memory (RPi)

```yaml
# Add to docker-compose.yml under trader:
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '0.8'
```

### Logs Too Large

```bash
# Clear logs
docker-compose down
rm -rf logs/*
docker-compose up -d

# Limit log size
docker-compose.yml:
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
```

## 🔧 Development

### Local Testing

```bash
# Build image
docker-compose build trader

# Run with local code
docker-compose up trader

# Interactive mode
docker-compose run --rm trader bash
```

### Hot Reload (Development)

```yaml
# Mount code as volume for live updates
volumes:
  - .:/app
```

## ✅ Production Checklist

- [ ] `.env` configured with real credentials
- [ ] `TRADING_MODE=live` (if production)
- [ ] Telegram notifications tested
- [ ] Logs directory exists
- [ ] Auto-restart enabled (`restart: unless-stopped`)
- [ ] Health checks working
- [ ] Resource limits set (RPi)
- [ ] Backups configured

## 📱 Remote Access

### VNC to Gateway

```bash
# Connect to VNC
vncviewer raspberrypi:5900
# Password: ${VNC_PASSWORD}
```

### SSH Tunnel

```bash
# Forward ports from RPi to local
ssh -L 5900:localhost:5900 pi@raspberrypi

# Access VNC locally
vncviewer localhost:5900
```

---

**Status:** Production-ready ✅  
**Platform:** Raspberry Pi optimized  
**Update:** `docker-compose pull && up -d` 🎯
