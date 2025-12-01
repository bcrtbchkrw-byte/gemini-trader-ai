"""
Test Incremental Data Fetch

Quick test to verify incremental data fetching works correctly.
"""
import asyncio
from ml.historical_data_fetcher import get_historical_fetcher
from loguru import logger


async def test_incremental_fetch():
    """Test incremental fetch for one symbol"""
    logger.info("Testing incremental data fetch...")
    
    fetcher = get_historical_fetcher()
    
    # Test with SPY
    symbol = 'SPY'
    logger.info(f"\nFetching incremental data for {symbol}...")
    
    df = await fetcher.fetch_incremental_data(symbol, days=35)
    
    if not df.empty:
        logger.info(f"✅ Success!")
        logger.info(f"   Total rows: {len(df)}")
        logger.info(f"   Date range: {df['date'].min()} to {df['date'].max()}")
        logger.info(f"   Latest close: ${df.iloc[-1]['close']:.2f}")
        
        # Show last 5 rows
        logger.info("\nLast 5 rows:")
        print(df.tail(5))
    else:
        logger.error("❌ Incremental fetch failed")


if __name__ == '__main__':
    asyncio.run(test_incremental_fetch())
