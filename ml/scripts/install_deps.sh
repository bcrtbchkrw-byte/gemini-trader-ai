#!/bin/bash
#
# Install ML dependencies for training pipeline
#

echo "Installing ML training dependencies..."

# Check if venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: No virtual environment detected"
    echo "Consider activating venv first: source venv/bin/activate"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install ML requirements
echo ""
echo "📦 Installing xgboost, scikit-learn, joblib..."
pip install -r requirements_ml.txt

# Verify installation
echo ""
echo "✓ Verifying installation..."
python -m ml.scripts.verify_setup

echo ""
echo "Setup complete! Next steps:"
echo "1. Start IBKR TWS/Gateway"
echo "2. Run: python -m ml.scripts.prepare_ml_training_pipeline"
