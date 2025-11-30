#!/bin/bash
# Quick setup script for testing

echo "🔧 Setting up Gemini Trader AI for testing..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Setup complete!"
echo ""
echo "To run tests:"
echo "  source venv/bin/activate"
echo "  python test_pipeline.py"
echo ""
echo "To run full pipeline:"
echo "  source venv/bin/activate"
echo "  python main.py"
