# Watchdog Setup - Quick Guide

## 🚀 Automated Setup (Recommended)

```bash
cd /home/jakub/.gemini/antigravity/scratch/gemini-trader-ai
./setup_watchdog.sh
```

This script will:
1. ✅ Set executable permissions
2. ✅ Create log directories
3. ✅ Add cron job (every minute)
4. ✅ Install systemd service
5. ✅ Test watchdog

## 📋 Manual Setup

### 1. Set Permissions
```bash
chmod +x watchdog.sh
chmod +x watchdog.py
```

### 2. Create Log Directory
```bash
sudo mkdir -p /var/log
sudo touch /var/log/gemini-watchdog.log
sudo chown $USER:$USER /var/log/gemini-watchdog.log
```

### 3. Add to Cron
```bash
crontab -e

# Add this line at the end:
*/1 * * * * /home/jakub/.gemini/antigravity/scratch/gemini-trader-ai/watchdog.sh >> /var/log/gemini-watchdog.log 2>&1
```

**Cron syntax:**
- `*/1` = Every 1 minute
- `* * * *` = Every hour, day, month, day of week
- `>> /var/log/...` = Append output to log
- `2>&1` = Redirect errors to same log

### 4. Install Systemd Service
```bash
sudo cp gemini-trader.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gemini-trader
sudo systemctl start gemini-trader
```

## ✅ Verification

### Check Cron Job
```bash
crontab -l | grep watchdog
# Should show:
# */1 * * * * /home/jakub/.gemini/antigravity/scratch/gemini-trader-ai/watchdog.sh ...
```

### Test Watchdog Manually
```bash
./watchdog.sh
# Should output health checks
```

### View Watchdog Logs
```bash
tail -f /var/log/gemini-watchdog.log
```

Expected output:
```
[2024-11-30 22:00:01] === Watchdog check started ===
[2024-11-30 22:00:01] [OK] Service gemini-trader is active
[2024-11-30 22:00:01] [OK] Log file is fresh (45s old)
[2024-11-30 22:00:01] [OK] Process appears responsive (23 recent entries)
[2024-11-30 22:00:01] [OK] All health checks passed
[2024-11-30 22:00:01] === Watchdog check completed ===
```

### Check Service Status
```bash
sudo systemctl status gemini-trader
```

## 🔧 Troubleshooting

### Watchdog Not Running
```bash
# Check cron is running
sudo systemctl status cron

# Restart cron
sudo systemctl restart cron

# Check cron logs
grep CRON /var/log/syslog | tail
```

### Service Not Starting
```bash
# Check service logs
journalctl -u gemini-trader -n 50

# Check permissions
ls -la watchdog.sh watchdog.py
# Should show: -rwxr-xr-x (executable)
```

### Watchdog Keeps Restarting Bot
```bash
# Check why health checks fail
tail -f /var/log/gemini-watchdog.log

# Check bot logs
tail -f logs/gemini_trader.log

# Temporarily disable watchdog
crontab -e  # Comment out watchdog line
```

## 📊 Monitoring

### Real-time Watch
```bash
# Terminal 1: Watchdog logs
watch -n 5 'tail -20 /var/log/gemini-watchdog.log'

# Terminal 2: Bot logs  
tail -f logs/gemini_trader.log

# Terminal 3: Service status
watch -n 5 'systemctl status gemini-trader'
```

### Daily Summary
```bash
# Count health checks today
grep "Watchdog check" /var/log/gemini-watchdog.log | wc -l

# Count restarts today
grep "Attempting to restart" /var/log/gemini-watchdog.log | wc -l

# Last restart
grep "Service.*restarted" /var/log/gemini-watchdog.log | tail -1
```

## 🎯 Raspberry Pi Specific

### Auto-start on Boot
```bash
# Enable service
sudo systemctl enable gemini-trader

# Enable cron on boot (usually already enabled)
sudo systemctl enable cron
```

### Resource Monitoring
```bash
# Watch memory/CPU
htop -p $(pgrep -f "python.*main.py")

# Watchdog overhead
# Bash: ~1MB RAM, <1% CPU
# Python: ~20MB RAM, <1% CPU
```

### Power Management
```bash
# Prevent sleep during trading hours
sudo systemctl mask sleep.target suspend.target

# Re-enable sleep
sudo systemctl unmask sleep.target suspend.target
```

## ✅ Status Check Commands

```bash
# All-in-one status
echo "=== Watchdog Status ==="
crontab -l | grep watchdog
echo ""
echo "=== Service Status ==="
systemctl status gemini-trader --no-pager
echo ""
echo "=== Recent Watchdog Logs ==="
tail -10 /var/log/gemini-watchdog.log
```

---

**Setup complete! Watchdog is monitoring your bot every minute.** 🎯
