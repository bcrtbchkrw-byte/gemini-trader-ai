#!/usr/bin/env python3
"""
Python Watchdog - Alternative to bash watchdog
More sophisticated health checks and monitoring.
"""
import os
import sys
import time
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Configuration
LOG_FILE = Path(os.getenv('LOG_FILE', 'logs/gemini_trader.log'))
MAX_LOG_AGE_SECONDS = int(os.getenv('MAX_LOG_AGE_SECONDS', '300'))  # 5 min
SERVICE_NAME = os.getenv('SERVICE_NAME', 'gemini-trader')
WATCHDOG_LOG = Path('/var/log/gemini-watchdog.log')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(WATCHDOG_LOG),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('watchdog')


class ServiceWatchdog:
    """Monitor and restart frozen services"""
    
    def __init__(self):
        self.restart_count = 0
        self.last_restart = None
        self.max_restarts_per_hour = 3
    
    def check_log_exists(self) -> bool:
        """Check if log file exists"""
        if not LOG_FILE.exists():
            logger.warning(f"Log file not found: {LOG_FILE}")
            return False
        return True
    
    def check_log_freshness(self) -> bool:
        """Check if log has been updated recently"""
        if not self.check_log_exists():
            return False
        
        mtime = datetime.fromtimestamp(LOG_FILE.stat().st_mtime)
        age = datetime.now() - mtime
        
        if age.total_seconds() > MAX_LOG_AGE_SECONDS:
            logger.warning(
                f"Log file is stale ({age.total_seconds():.0f}s old, "
                f"max {MAX_LOG_AGE_SECONDS}s)"
            )
            return False
        
        logger.info(f"Log file is fresh ({age.total_seconds():.0f}s old)")
        return True
    
    def check_service_running(self) -> bool:
        """Check if systemd service is active"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', SERVICE_NAME],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                logger.info(f"Service {SERVICE_NAME} is active")
                return True
            else:
                logger.warning(f"Service {SERVICE_NAME} is not active")
                return False
                
        except Exception as e:
            logger.error(f"Error checking service: {e}")
            return False
    
    def check_process_responsive(self) -> bool:
        """Check if process is responsive (has recent activity)"""
        if not self.check_log_exists():
            return False
        
        try:
            # Read last 100 lines
            with LOG_FILE.open('r') as f:
                lines = f.readlines()[-100:]
            
            # Look for activity indicators
            activity_patterns = ['VIX', 'Position', 'Update', 'Trading', 'Analysis']
            recent_activity = sum(
                1 for line in lines 
                if any(pattern in line for pattern in activity_patterns)
            )
            
            if recent_activity > 0:
                logger.info(
                    f"Process appears responsive "
                    f"({recent_activity} recent log entries)"
                )
                return True
            else:
                logger.warning("Process may be hung (no recent activity)")
                return False
                
        except Exception as e:
            logger.error(f"Error checking responsiveness: {e}")
            return False
    
    def can_restart(self) -> bool:
        """Check if we can restart (rate limiting)"""
        # Reset counter if more than 1 hour since last restart
        if self.last_restart:
            if datetime.now() - self.last_restart > timedelta(hours=1):
                self.restart_count = 0
        
        if self.restart_count >= self.max_restarts_per_hour:
            logger.error(
                f"Too many restarts ({self.restart_count}) in last hour! "
                "Manual intervention required."
            )
            return False
        
        return True
    
    def restart_service(self) -> bool:
        """Restart the systemd service"""
        if not self.can_restart():
            return False
        
        logger.warning(f"Attempting to restart {SERVICE_NAME}...")
        
        try:
            # Stop service
            subprocess.run(['systemctl', 'stop', SERVICE_NAME], timeout=10)
            time.sleep(2)
            
            # Force kill any remaining processes (backup)
            subprocess.run(
                ['pkill', '-9', '-f', 'python.*main.py'],
                timeout=5
            )
            time.sleep(1)
            
            # Start service
            result = subprocess.run(
                ['systemctl', 'start', SERVICE_NAME],
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info(f"Service {SERVICE_NAME} restarted successfully")
                self.restart_count += 1
                self.last_restart = datetime.now()
                self.send_alert(
                    "Gemini Trader Restarted",
                    f"Watchdog detected issue and restarted the service "
                    f"(restart #{self.restart_count})"
                )
                return True
            else:
                logger.error(f"Failed to restart service {SERVICE_NAME}")
                return False
                
        except Exception as e:
            logger.error(f"Error restarting service: {e}")
            return False
    
    def send_alert(self, subject: str, message: str):
        """Send alert notification"""
        logger.info(f"ALERT: {subject} - {message}")
        
        # Could add email, Telegram, Slack notifications here
        # For now, just log
    
    def run_health_check(self) -> bool:
        """Run all health checks"""
        logger.info("=== Watchdog check started ===")
        
        needs_restart = False
        
        # Check 1: Service running?
        if not self.check_service_running():
            logger.error("Service is not running")
            needs_restart = True
        
        # Check 2: Log fresh?
        if not self.check_log_freshness():
            logger.error("Log file is stale or missing")
            needs_restart = True
        
        # Check 3: Process responsive?
        if not self.check_process_responsive():
            logger.warning("Process may be hung")
            needs_restart = True
        
        # Restart if needed
        if needs_restart:
            logger.warning("Health checks failed - restarting service")
            success = self.restart_service()
        else:
            logger.info("✅ All health checks passed")
            success = True
        
        logger.info("=== Watchdog check completed ===\n")
        return success


if __name__ == '__main__':
    watchdog = ServiceWatchdog()
    watchdog.run_health_check()
