#!/bin/bash
#
# Setup cron job for monthly ML retraining
# Run this script once to configure automatic monthly retraining
#

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "🤖 Setting up monthly ML retraining cron job..."
echo "Project directory: $PROJECT_DIR"

# Check if venv exists
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "⚠️  Warning: Virtual environment not found at $PROJECT_DIR/venv"
    echo "Make sure to activate venv before running cron job"
fi

# Create cron job entry
CRON_CMD="0 2 1 * * cd $PROJECT_DIR && $PROJECT_DIR/venv/bin/python -m ml.scripts.monthly_retrain >> $PROJECT_DIR/logs/monthly_retrain.log 2>&1"

echo ""
echo "Cron job to be added:"
echo "$CRON_CMD"
echo ""
echo "This will run:"
echo "  - Monthly on the 1st day at 2:00 AM"
echo "  - Fetch last month's data"
echo "  - Append to existing data (accumulation)"
echo "  - Retrain both ML models"
echo "  - Log output to logs/monthly_retrain.log"
echo ""

read -p "Add this cron job? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]
then
    # Add to crontab
    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
    
    echo "✅ Cron job added successfully!"
    echo ""
    echo "To verify:"
    echo "  crontab -l"
    echo ""
    echo "To remove later:"
    echo "  crontab -e"
    echo ""
    echo "To test manually:"
    echo "  python -m ml.scripts.monthly_retrain"
    
    # Create logs directory if it doesn't exist
    mkdir -p "$PROJECT_DIR/logs"
    echo "✅ Logs directory created: $PROJECT_DIR/logs"
else
    echo "❌ Cron job not added."
    echo ""
    echo "To add manually, run:"
    echo "  crontab -e"
    echo ""
    echo "And add this line:"
    echo "$CRON_CMD"
fi
