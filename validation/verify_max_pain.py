import asyncio
from ibkr.data_fetcher import get_data_fetcher
from analysis.max_pain import get_max_pain_calculator
from loguru import logger
from data.logger import setup_logger

async def main():
    setup_logger()
    
    logger.info("=" * 60)
    logger.info("🔮 Verifying Max Pain Calculation")
    logger.info("=" * 60)
    
    fetcher = get_data_fetcher()
    
    try:
        # Connect
        logger.info("Connecting to IBKR...")
        connected = await fetcher.connection.connect()
        if not connected:
            logger.error("Failed to connect")
            return
            
        symbol = "SPY"
        
        # Get chain to find expiration
        logger.info(f"Fetching chain for {symbol}...")
        contracts = await fetcher.get_options_chain(symbol)
        
        if not contracts:
            logger.error("No contracts found")
            return
            
        # Pick an expiration ~30-45 days out
        from datetime import datetime
        today = datetime.now()
        target_exp = None
        
        # Find unique expirations
        expirations = sorted(list(set(c.lastTradeDateOrContractMonth for c in contracts)))
        
        for exp in expirations:
            exp_date = datetime.strptime(exp, '%Y%m%d')
            dte = (exp_date - today).days
            if dte >= 30:
                target_exp = exp
                break
        
        if not target_exp:
            target_exp = expirations[0]
            
        logger.info(f"Target Expiration: {target_exp}")
        
        # Fetch OI
        logger.info("Fetching Open Interest...")
        chain_oi = await fetcher.get_chain_open_interest(symbol, target_exp)
        
        if not chain_oi:
            logger.error("Failed to fetch OI")
            return
            
        logger.info(f"Fetched OI for {len(chain_oi)} strikes")
        
        # Calculate Max Pain
        calc = get_max_pain_calculator()
        max_pain = calc.calculate_max_pain(chain_oi)
        
        logger.info(f"✅ Max Pain for {symbol} (Exp: {target_exp}): ${max_pain:.2f}")
        
        # Get current price for comparison
        price = await fetcher.get_stock_price(symbol)
        if price:
            diff = max_pain - price
            logger.info(f"Current Price: ${price:.2f}")
            logger.info(f"Difference: ${diff:.2f} ({diff/price:.1%})")
            
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await fetcher.connection.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
