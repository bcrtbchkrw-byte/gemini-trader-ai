"""
Verify IBKR Market Data Type
Checks if the connected IBKR session is receiving Real-Time or Delayed data.
"""
import asyncio
import sys
from ib_insync import IB, Stock
from loguru import logger
from config import get_config

# Map market data types to human-readable strings
MARKET_DATA_TYPES = {
    1: "Real-Time",
    2: "Frozen",
    3: "Delayed",
    4: "Delayed Frozen"
}

async def verify_market_data():
    logger.info("=" * 60)
    logger.info("🔍 Verifying IBKR Market Data Connection")
    logger.info("=" * 60)
    
    config = get_config()
    ib = IB()
    
    try:
        logger.info(f"Connecting to {config.ibkr.host}:{config.ibkr.port} (Client ID: {config.ibkr.client_id})...")
        await ib.connectAsync(
            config.ibkr.host,
            config.ibkr.port,
            clientId=config.ibkr.client_id
        )
        logger.info("✅ Connected to IBKR")
        
        # Request Real-Time Data explicitly (Type 1)
        ib.reqMarketDataType(1)
        logger.info("Requested Market Data Type: 1 (Real-Time)")
        
        # Create contract for SPY (highly liquid, should have data)
        spy = Stock('SPY', 'SMART', 'USD')
        await ib.qualifyContractsAsync(spy)
        
        logger.info(f"Requesting market data for {spy.symbol}...")
        ticker = ib.reqMktData(spy, '', False, False)
        
        # Wait for data to arrive (up to 5 seconds)
        logger.info("Waiting for data...")
        for i in range(10):
            await asyncio.sleep(0.5)
            if ticker.marketDataType != 0: # 0 is initial/unknown
                break
        
        # Report results
        data_type = ticker.marketDataType
        type_str = MARKET_DATA_TYPES.get(data_type, f"Unknown ({data_type})")
        
        logger.info("-" * 60)
        logger.info(f"📊 Market Data Status for {spy.symbol}:")
        logger.info(f"   Market Data Type: {data_type} -> {type_str}")
        
        if data_type == 1:
            logger.info("✅ SUCCESS: You are receiving LIVE Real-Time data.")
        elif data_type == 3:
            logger.warning("⚠️  WARNING: You are receiving DELAYED data.")
            logger.warning("   This usually means you do not have active market data subscriptions")
            logger.warning("   for US Stocks/Options on your IBKR account.")
        elif data_type == 4:
             logger.warning("⚠️  WARNING: You are receiving DELAYED FROZEN data.")
        else:
            logger.warning(f"⚠️  Unexpected data type: {type_str}")
            
        logger.info("-" * 60)
        
        # Also check price to ensure it's not stale
        if ticker.last:
            logger.info(f"   Last Price: ${ticker.last:.2f}")
        elif ticker.close:
             logger.info(f"   Close Price: ${ticker.close:.2f}")
        
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Verification failed: {e}")
    finally:
        if ib.isConnected():
            ib.disconnect()
            logger.info("Disconnected")

if __name__ == "__main__":
    # Setup simple logging
    logger.remove()
    logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")
    
    asyncio.run(verify_market_data())
