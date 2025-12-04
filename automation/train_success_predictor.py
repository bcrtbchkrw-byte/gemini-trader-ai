"""
Train Trade Success Predictor
Script to train the Gatekeeper model on Real and Shadow trades.
"""
import asyncio
import aiosqlite
import pandas as pd
import numpy as np
from loguru import logger
from data.database import get_database
from ml.trade_success_predictor import get_success_predictor

async def train_predictor():
    logger.info("🧠 Starting Trade Success Predictor Training...")
    
    db = await get_database()
    predictor = get_success_predictor()
    
    # 1. Fetch Real Trades
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        
        # Real Trades
        async with conn.execute("""
            SELECT * FROM trades 
            WHERE status = 'CLOSED'
        """) as cursor:
            real_rows = await cursor.fetchall()
            real_data = [dict(row) for row in real_rows]
            
        # Shadow Trades
        async with conn.execute("""
            SELECT * FROM shadow_trades 
            WHERE status = 'EVALUATED' 
            AND outcome IN ('GOOD_REJECT', 'MISSED_OPPORTUNITY')
        """) as cursor:
            shadow_rows = await cursor.fetchall()
            shadow_data = [dict(row) for row in shadow_rows]
            
    logger.info(f"📚 Found {len(real_data)} real trades and {len(shadow_data)} shadow trades.")
    
    if not real_data and not shadow_data:
        logger.warning("⚠️ No data to train on.")
        return

    # 2. Unify Data
    training_rows = []
    
    # Process Real Trades
    for t in real_data:
        # Determine success (Profit > 0)
        # User definition: > 50% max profit. But for now let's say PnL > 0.
        is_successful = t.get('realized_pnl', 0) > 0
        
        row = {
            'vix': t.get('vix_at_entry', 0),
            'market_regime_val': 0, # TODO: Map regime string to int if needed
            'vix_term_structure_ratio': 1.0, # Missing in old data
            'rsi': 50, # Missing
            'distance_to_sma200': 0, # Missing
            'iv_rank': 50, # Missing
            'beta': 1.0,
            'delta': 0.20, # Estimate if missing
            'dte': 45, # Estimate
            'pot_probability': 0.5,
            'day_of_week': 0, # TODO: Parse timestamp
            'is_successful': is_successful
        }
        training_rows.append(row)
        
    # Process Shadow Trades
    for t in shadow_data:
        # Success = Missed Opportunity (We should have taken it)
        is_successful = t.get('outcome') == 'MISSED_OPPORTUNITY'
        
        row = {
            'vix': t.get('vix', 0),
            'market_regime_val': 0,
            'vix_term_structure_ratio': 1.0, # Missing
            'rsi': 50, # Missing
            'distance_to_sma200': 0, # Missing
            'iv_rank': t.get('iv_rank', 50),
            'beta': 1.0,
            'delta': t.get('delta', 0.20),
            'dte': 45, # Estimate from expiration
            'pot_probability': 0.5,
            'day_of_week': 0,
            'is_successful': is_successful
        }
        training_rows.append(row)
        
    # 3. Train
    df = pd.DataFrame(training_rows)
    predictor.train(df)
    
    logger.info("🎉 Gatekeeper training complete!")

if __name__ == "__main__":
    asyncio.run(train_predictor())
