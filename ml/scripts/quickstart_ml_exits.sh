#!/bin/bash
# Quick Start Guide for ML Exit Strategy

echo "==================================================="
echo "ML Exit Strategy - Quick Start Guide"
echo "==================================================="
echo ""

# Check if we have historical trades
echo "Step 1: Checking for historical trades..."
python3 -c "
import asyncio
from data.database import get_database

async def check_trades():
    db = await get_database()
    cursor = await db.execute('SELECT COUNT(*) FROM positions WHERE status=\"CLOSED\"')
    count = (await cursor.fetchone())[0]
    print(f'   Found {count} closed trades in database')
    if count < 20:
        print('   ⚠️  WARNING: Recommend at least 20 trades for training')
        print('   Consider paper trading more first or using demo mode')
    else:
        print('   ✅ Sufficient data for training')
    return count

count = asyncio.run(check_trades())
" || echo "   ⚠️  Could not check database (may not exist yet)"

echo ""
echo "Step 2: Generate training data from historical trades"
echo "   Run: python -m ml.prepare_exit_training_data"
echo ""

echo "Step 3: Train the ML model"
echo "   Run: python -m ml.scripts.train_exit_model"
echo ""

echo "Step 4: Enable ML exits in .env"
echo "   Set: USE_ML_EXITS=true"
echo "   Set: TRAILING_PROFIT_ENABLED=true"
echo "   Set: TRAILING_STOP_ENABLED=true"
echo ""

echo "Step 5: Test with your next trade"
echo "   The Position class will automatically use ML predictions"
echo "   Check logs for: 'ML Exit Update'"
echo ""

echo "==================================================="
echo "Optional: Run unit tests"
echo "   python -m unittest tests.test_exit_strategy_ml -v"
echo "==================================================="
