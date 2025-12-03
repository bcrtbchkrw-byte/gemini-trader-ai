#!/bin/bash
# Setup Cron Job for Monthly ML Retraining

echo "=========================================="
echo "Monthly ML Retraining - Cron Setup"
echo "=========================================="
echo ""

# Get project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "📂 Project directory: $PROJECT_DIR"
echo ""

# Create cron job entry
CRON_CMD="0 2 1 * * cd $PROJECT_DIR && $PROJECT_DIR/venv/bin/python -m ml.scripts.monthly_retrain >> $PROJECT_DIR/logs/monthly_retrain.log 2>&1"

echo "📅 Cron job to be added:"
echo "   $CRON_CMD"
echo ""
echo "This will run on the 1st of each month at 2:00 AM"
echo ""

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "monthly_retrain"; then
    echo "⚠️  Warning: A monthly_retrain cron job already exists!"
    echo ""
    echo "Current crontab:"
    crontab -l | grep monthly_retrain
    echo ""
    read -p "Do you want to replace it? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Aborted"
        exit 1
    fi
    
    # Remove old entry
    crontab -l | grep -v monthly_retrain | crontab -
    echo "🗑️  Removed old cron job"
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

echo "✅ Cron job added successfully!"
echo ""
echo "=========================================="
echo "Verification"
echo "=========================================="
echo ""
echo "Current crontab:"
crontab -l | grep monthly_retrain
echo ""
echo "Log file will be: $PROJECT_DIR/logs/monthly_retrain.log"
echo ""
echo "To check cron logs:"
echo "  grep CRON /var/log/syslog"
echo ""
echo "To test manually:"
echo "  cd $PROJECT_DIR"
echo "  python -m ml.scripts.monthly_retrain"
echo ""
echo "=========================================="
echo "✅ Setup complete!"
echo "=========================================="
