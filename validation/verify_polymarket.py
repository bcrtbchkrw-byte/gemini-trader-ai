"""
Verify Polymarket Integration
Tests fetching data from Polymarket API.
"""
import asyncio
import sys
from loguru import logger
from analysis.polymarket_client import get_polymarket_client

async def verify_polymarket():
    logger.info("=" * 60)
    logger.info("🔮 Verifying Polymarket Integration")
    logger.info("=" * 60)
    
    client = get_polymarket_client()
    
    try:
        # 1. Test Macro Context
        logger.info("\n📊 Testing Macro Context...")
        macro = await client.get_macro_context()
        if macro:
            for query, data in macro.items():
                logger.info(f"   {query}: {data.get('probability'):.1%} ({data.get('question')})")
        else:
            logger.warning("   No macro context found (API might be down or no matching markets)")
            
        # 2. Test Crypto Sentiment
        logger.info("\n₿ Testing Crypto Sentiment...")
        crypto = await client.get_crypto_sentiment()
        if crypto:
            for query, markets in crypto.items():
                logger.info(f"   {query}:")
                for m in markets:
                    logger.info(f"      - {m.get('question')}: {m.get('probability'):.1%}")
        else:
            logger.warning("   No crypto sentiment found")
            
        # 3. Test Specific Event Search
        test_query = "Trump" # High volume topic usually
        logger.info(f"\n🔍 Testing Search ('{test_query}')...")
        events = await client.get_event_probs(test_query)
        if events:
            for e in events:
                logger.info(f"   - {e.get('question')}: {e.get('probability'):.1%}")
        else:
            logger.warning(f"   No events found for '{test_query}'")
            
        logger.info("\n" + "=" * 60)
        logger.info("✅ Polymarket Verification Complete")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Verification failed: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    # Setup simple logging
    logger.remove()
    logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")
    
    asyncio.run(verify_polymarket())
