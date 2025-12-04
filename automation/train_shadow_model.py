"""
Train Shadow Model
Script to train the Rejection Model on evaluated shadow trades.
"""
import asyncio
import aiosqlite
import pandas as pd
from loguru import logger
from data.database import get_database
from ml.rejection_model import get_rejection_model

async def train_model():
    logger.info("🧠 Starting Rejection Model Training...")
    
    db = await get_database()
    model = get_rejection_model()
    
    # Fetch evaluated shadow trades
    # We need trades that have an outcome (GOOD_REJECT or MISSED_OPPORTUNITY)
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("""
            SELECT * FROM shadow_trades 
            WHERE status = 'EVALUATED' 
            AND outcome IN ('GOOD_REJECT', 'MISSED_OPPORTUNITY')
        """) as cursor:
            rows = await cursor.fetchall()
            data = [dict(row) for row in rows]
            
    if not data:
        logger.warning("⚠️ No evaluated shadow trades found. Cannot train model.")
        return
        
    logger.info(f"📚 Found {len(data)} training records.")
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Ensure all feature columns exist (for backward compatibility with old records)
    feature_cols = ['vix', 'delta', 'gamma', 'theta', 'vega', 'iv_rank']
    for col in feature_cols:
        if col not in df.columns:
            logger.warning(f"Column {col} missing in training data. Filling with 0.")
            df[col] = 0.0
            
    # Train
    model.train(df)
    
    logger.info("🎉 Training complete!")

if __name__ == "__main__":
    import aiosqlite
    asyncio.run(train_model())
