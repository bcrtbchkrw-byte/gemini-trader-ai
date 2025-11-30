#!/bin/bash
#
# Watchdog Setup Script
# Automates watchdog installation and cron setup
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Gemini Trader Watchdog Setup ===${NC}\n"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$SCRIPT_DIR"

echo "Project directory: $PROJECT_DIR"

# 1. Set executable permissions
echo -e "\n${YELLOW}Step 1: Setting executable permissions...${NC}"
chmod +x "$PROJECT_DIR/watchdog.sh"
chmod +x "$PROJECT_DIR/watchdog.py"
echo -e "${GREEN}✅ Permissions set${NC}"

# 2. Create log directory
echo -e "\n${YELLOW}Step 2: Creating log directories...${NC}"
sudo mkdir -p /var/log
sudo touch /var/log/gemini-watchdog.log
sudo chown $USER:$USER /var/log/gemini-watchdog.log
echo -e "${GREEN}✅ Log directory ready${NC}"

# 3. Setup cron job
echo -e "\n${YELLOW}Step 3: Setting up cron job...${NC}"

CRON_LINE="*/1 * * * * $PROJECT_DIR/watchdog.sh >> /var/log/gemini-watchdog.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "watchdog.sh"; then
    echo -e "${YELLOW}⚠️  Watchdog cron job already exists${NC}"
    echo "Current cron jobs:"
    crontab -l | grep watchdog || true
else
    # Add to crontab
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    echo -e "${GREEN}✅ Cron job added${NC}"
fi

# 4. Install systemd service
echo -e "\n${YELLOW}Step 4: Installing systemd service...${NC}"

if [ -f "$PROJECT_DIR/gemini-trader.service" ]; then
    sudo cp "$PROJECT_DIR/gemini-trader.service" /etc/systemd/system/
    sudo systemctl daemon-reload
    echo -e "${GREEN}✅ Systemd service installed${NC}"
    
    # Ask if user wants to enable
    read -p "Enable service to start on boot? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemctl enable gemini-trader
        echo -e "${GREEN}✅ Service enabled${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  gemini-trader.service not found, skipping${NC}"
fi

# 5. Test watchdog
echo -e "\n${YELLOW}Step 5: Testing watchdog...${NC}"
echo "Running watchdog test..."
"$PROJECT_DIR/watchdog.sh"
echo -e "${GREEN}✅ Watchdog test complete${NC}"

# Summary
echo -e "\n${GREEN}=== Setup Complete ===${NC}"
echo -e "\n${YELLOW}Cron job installed:${NC}"
echo "  $CRON_LINE"
echo -e "\n${YELLOW}Logs:${NC}"
echo "  Watchdog: /var/log/gemini-watchdog.log"
echo "  Bot: $PROJECT_DIR/logs/gemini_trader.log"
echo -e "\n${YELLOW}Commands:${NC}"
echo "  Start service:   sudo systemctl start gemini-trader"
echo "  Stop service:    sudo systemctl stop gemini-trader"
echo "  Service status:  sudo systemctl status gemini-trader"
echo "  View cron jobs:  crontab -l"
echo "  View watchdog:   tail -f /var/log/gemini-watchdog.log"
echo -e "\n${GREEN}Watchdog will check bot health every minute!${NC}"
