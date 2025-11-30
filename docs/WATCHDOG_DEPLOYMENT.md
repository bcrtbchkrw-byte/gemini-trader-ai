# Watchdog & Production Deployment

## 🎯 Problem

Python scripts can freeze:
- Socket timeouts
- IBKR connection hangs
- Memory leaks
- Deadlocks

**Result:** Bot stops trading but "looks" like it's running ⚠️

## ✅ Solution: Watchdog Monitor

External monitoring script that:
1. Checks if logs are updating
2. Checks if process is responsive
3. Restarts service if frozen

## 📊 Implementation

### 1. Bash Watchdog (Simple)

**Script:** `watchdog.sh`

**Health Checks:**
```bash
# 1. Service running?
systemctl is-active gemini-trader

# 2. Log file fresh? (< 5 min old)
log_age=$(stat -c %Y gemini_trader.log)
if [ $age > 300 ]; then restart; fi

# 3. Recent activity in logs?
tail -n 100 gemini_trader.log | grep -c "VIX\|Update"
```

**Restart Logic:**
```bash
systemctl stop gemini-trader
pkill -9 -f "python.*main.py"  # Force kill
systemctl start gemini-trader
```

### 2. Python Watchdog (Advanced)

**Script:** `watchdog.py`

**Features:**
- Rate limiting (max 3 restarts/hour)
- Sophisticated log analysis
- Alert notifications
- Restart history

**Usage:**
```python
watchdog = ServiceWatchdog()
watchdog.run_health_check()
# Returns: True if healthy, False if restarted
```

## ⚙️ Setup

### 1. Install Systemd Service

```bash
# Copy service file
sudo cp gemini-trader.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service (auto-start on boot)
sudo systemctl enable gemini-trader

# Start service
sudo systemctl start gemini-trader

# Check status
sudo systemctl status gemini-trader
```

### 2. Setup Watchdog Cron

**Bash version (every minute):**
```bash
# Edit crontab
crontab -e

# Add line:
*/1 * * * * /home/jakub/.gemini/antigravity/scratch/gemini-trader-ai/watchdog.sh
```

**Python version (every minute):**
```bash
*/1 * * * * /usr/bin/python3 /home/jakub/.gemini/antigravity/scratch/gemini-trader-ai/watchdog.py
```

### 3. Make Scripts Executable

```bash
chmod +x watchdog.sh
chmod +x watchdog.py
```

### 4. Create Log Directory

```bash
mkdir -p logs
sudo touch /var/log/gemini-watchdog.log
sudo chown jakub:jakub /var/log/gemini-watchdog.log
```

## 🎯 Health Check Details

### Check 1: Service Running
```bash
systemctl is-active gemini-trader
# Returns: active/inactive/failed
```

**Why:** Catches crashes, killed processes

### Check 2: Log Freshness
```bash
# Check if log modified in last 5 minutes
log_age=$(( $(date +%s) - $(stat -c %Y gemini_trader.log) ))
if [ $log_age -gt 300 ]; then
    # STALE - process frozen!
fi
```

**Why:** Catches hung processes (not crashed, but frozen)

### Check 3: Recent Activity
```bash
# Look for expected log patterns
tail -n 100 gemini_trader.log | grep -c "VIX\|Position\|Update"
```

**Why:** Confirms process is actually doing work

## 📈 Restart Strategy

### Rate Limiting
```python
max_restarts_per_hour = 3

# If restarted 3+ times in 1 hour:
# → STOP auto-restart
# → Alert for manual intervention
```

**Why:** Prevents restart loops if fundamental issue

### Restart Sequence
```
1. Stop service (graceful)
   ↓
2. Wait 2s
   ↓
3. Force kill (backup)
   ↓
4. Wait 1s
   ↓
5. Start service
   ↓
6. Verify started
```

## 🚨 Alerting

### Email (Optional)
```bash
# In watchdog.sh
export ALERT_EMAIL="your@email.com"

# Sends email on restart:
echo "Bot restarted at $(date)" | mail -s "Gemini Trader Alert" $ALERT_EMAIL
```

### Telegram (Advanced)
```python
# In watchdog.py
def send_telegram_alert(message):
    import requests
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(url, data={'chat_id': chat_id, 'text': message})
```

## 📊 Monitoring Logs

### Watchdog Logs
```bash
# View watchdog activity
tail -f /var/log/gemini-watchdog.log

# Output:
[2024-11-30 21:00:01] === Watchdog check started ===
[2024-11-30 21:00:01] [OK] Service gemini-trader is active
[2024-11-30 21:00:01] [OK] Log file is fresh (45s old)
[2024-11-30 21:00:01] [OK] Process appears responsive (23 recent entries)
[2024-11-30 21:00:01] [OK] All health checks passed
```

### Bot Logs
```bash
# View bot activity
tail -f logs/gemini_trader.log
```

## 🎯 Raspberry Pi Considerations

### Resource Limits (in systemd)
```ini
[Service]
MemoryMax=1G      # Max 1GB RAM
CPUQuota=80%      # Max 80% CPU
```

**Why:** Prevent bot from overwhelming Pi

### Auto-start on Boot
```bash
sudo systemctl enable gemini-trader
```

**Why:** Survives power outages/reboots

### Watchdog at Boot
```bash
# Add to /etc/rc.local (before 'exit 0')
/home/jakub/.gemini/antigravity/scratch/gemini-trader-ai/watchdog.sh &
```

## ✅ Testing

### 1. Test Freeze Detection
```bash
# Manually stop bot (simulates freeze)
sudo systemctl stop gemini-trader

# Wait 1 minute
# Watchdog should detect and restart
```

### 2. Test Log Staleness
```bash
# Run bot, then prevent log updates
chmod 000 logs/gemini_trader.log

# Wait 6 minutes
# Watchdog should detect stale log and restart
```

### 3. Test Rate Limiting
```bash
# Repeatedly kill bot
for i in {1..5}; do
    sudo systemctl stop gemini-trader
    sleep 70  # Wait for watchdog
done

# After 3 restarts, watchdog should stop auto-restarting
```

## 📋 Checklist

- [ ] Install systemd service
- [ ] Enable auto-start
- [ ] Setup watchdog cron
- [ ] Test freeze detection
- [ ] Configure alerts (optional)
- [ ] Monitor logs for 24h
- [ ] Document restart events

---

**Status:** Production-ready ✅  
**Frequency:** Every 1 minute  
**Impact:** Prevents frozen bot disasters 🎯
