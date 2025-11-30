#!/bin/bash
# Run Gemini Trader AI with scheduler

echo "🚀 Gemini Trader AI - Scheduler Mode"
echo "===================================="
echo ""

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Check .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found!"
    echo "Creating from .env.example..."
    cp .env.example .env
    echo "✅ Please edit .env with your API keys"
    exit 1
fi

# Run scheduler
echo "Starting scheduler daemon..."
echo "Press Ctrl+C to stop"
echo ""

python main.py --scheduler
