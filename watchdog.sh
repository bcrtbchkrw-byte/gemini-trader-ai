#!/bin/bash
#
# Gemini Trader AI Watchdog
# Monitors the trading bot and restarts it if frozen/crashed
#
# Usage: Run via cron every minute
# */1 * * * * /path/to/watchdog.sh

set -euo pipefail

# Configuration
LOG_FILE="${LOG_FILE:-/home/jakub/.gemini/antigravity/scratch/gemini-trader-ai/logs/gemini_trader.log}"
PID_FILE="${PID_FILE:-/tmp/gemini_trader.pid}"
MAX_LOG_AGE_SECONDS=300  # 5 minutes
SERVICE_NAME="gemini-trader"  # systemd service name
ALERT_EMAIL="${ALERT_EMAIL:-}"  # Optional email for alerts

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a /var/log/gemini-watchdog.log
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a /var/log/gemini-watchdog.log
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a /var/log/gemini-watchdog.log
}

success() {
    echo -e "${GREEN}[OK]${NC} $1" | tee -a /var/log/gemini-watchdog.log
}

# Send alert (email or other notification)
send_alert() {
    local subject="$1"
    local message="$2"
    
    log "ALERT: $subject - $message"
    
    # Email notification (if configured)
    if [ -n "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "$subject" "$ALERT_EMAIL" 2>/dev/null || true
    fi
    
    # Could add Telegram/Slack notification here
}

# Check if log file exists
check_log_exists() {
    if [ ! -f "$LOG_FILE" ]; then
        warn "Log file not found: $LOG_FILE"
        return 1
    fi
    return 0
}

# Check log freshness (has it been updated recently?)
check_log_freshness() {
    if ! check_log_exists; then
        return 1
    fi
    
    local current_time=$(date +%s)
    local log_mtime=$(stat -c %Y "$LOG_FILE" 2>/dev/null || echo 0)
    local age=$((current_time - log_mtime))
    
    if [ $age -gt $MAX_LOG_AGE_SECONDS ]; then
        warn "Log file is stale (${age}s old, max ${MAX_LOG_AGE_SECONDS}s)"
        return 1
    fi
    
    success "Log file is fresh (${age}s old)"
    return 0
}

# Check if process is running
check_process_running() {
    # Check systemd service status
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        success "Service $SERVICE_NAME is active"
        return 0
    else
        warn "Service $SERVICE_NAME is not active"
        return 1
    fi
}

# Check if process is responsive (not hung)
check_process_responsive() {
    # Check if there are recent "heartbeat" entries in log
    if ! check_log_exists; then
        return 1
    fi
    
    # Look for recent activity patterns (e.g., "VIX Update", "Position check")
    local recent_activity=$(tail -n 100 "$LOG_FILE" | grep -c "VIX\|Position\|Update" || echo 0)
    
    if [ $recent_activity -gt 0 ]; then
        success "Process appears responsive ($recent_activity recent log entries)"
        return 0
    else
        warn "Process may be hung (no recent activity in logs)"
        return 1
    fi
}

# Restart the service
restart_service() {
    log "Attempting to restart $SERVICE_NAME..."
    
    # Stop first (force if needed)
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    sleep 2
    
    # Kill any remaining processes (backup)
    pkill -9 -f "python.*main.py" 2>/dev/null || true
    sleep 1
    
    # Start service
    if systemctl start "$SERVICE_NAME"; then
        success "Service $SERVICE_NAME restarted successfully"
        send_alert "Gemini Trader Restarted" "Watchdog detected issue and restarted the service"
        return 0
    else
        error "Failed to restart service $SERVICE_NAME"
        send_alert "Gemini Trader Restart FAILED" "Watchdog could not restart the service!"
        return 1
    fi
}

# Main watchdog logic
main() {
    log "=== Watchdog check started ==="
    
    local needs_restart=0
    
    # Check 1: Is service running?
    if ! check_process_running; then
        error "Service is not running"
        needs_restart=1
    fi
    
    # Check 2: Is log file being updated?
    if ! check_log_freshness; then
        error "Log file is stale or missing"
        needs_restart=1
    fi
    
    # Check 3: Is process responsive?
    if ! check_process_responsive; then
        warn "Process may be hung"
        needs_restart=1
    fi
    
    # Restart if needed
    if [ $needs_restart -eq 1 ]; then
        warn "Health checks failed - restarting service"
        restart_service
    else
        success "All health checks passed"
    fi
    
    log "=== Watchdog check completed ==="
}

# Run main function
main "$@"
