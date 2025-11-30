#!/usr/bin/env python3
"""
Test the 3-Phase Screening Pipeline
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from analysis.stock_screener import get_stock_screener, ScreeningCriteria
from analysis.news_fetcher import get_news_fetcher
from ai.gemini_client import get_gemini_client


async def test_phase1():
    """Test Phase 1: Stock Screener"""
    logger.info("=" * 60)
    logger.info("PHASE 1: Stock Screener Test")
    logger.info("=" * 60)
    
    screener = get_stock_screener()
    criteria = ScreeningCriteria(
        min_price=20,
        max_price=300,
        min_daily_volume=1_000_000,
        vix_regime="NORMAL"
    )
    
    candidates = await screener.screen(criteria=criteria, max_results=10)
    
    logger.info(f"\n✅ Phase 1 Results: {len(candidates)} candidates")
    for candidate in candidates:
        logger.info(
            f"  {candidate['symbol']:6} | "
            f"Price: ${candidate['price']:6.2f} | "
            f"IV: {candidate['iv_rank']:5.1f} | "
            f"Score: {candidate['score']:5.2f}"
        )
    logger.info("")
    
    return candidates


async def test_phase2(candidates):
    """Test Phase 2: News + Gemini Analysis"""
    logger.info("=" * 60)
    logger.info("PHASE 2: Gemini Batch Analysis Test")
    logger.info("=" * 60)
    
    # Fetch news
    news_fetcher = get_news_fetcher()
    news_context = await news_fetcher.fetch_batch(
        [c['symbol'] for c in candidates]
    )
    
    # Gemini batch analysis
    gemini = get_gemini_client()
    result = await gemini.batch_analyze_with_news(
        candidates=candidates,
        news_context=news_context,
        vix=18.5
    )
    
    if result['success']:
        logger.info(f"\n✅ Phase 2 Results:")
        for stock in result['ranked_stocks']:
            logger.info(
                f"  {stock['symbol']:6} | "
                f"Score: {stock['fundamental_score']}/10 | "
                f"Sentiment: {stock['news_sentiment']:8} | "
                f"{stock['recommendation']}"
            )
        logger.info(f"\n🎯 Top Picks: {', '.join(result['top_picks'])}")
        logger.info("")
        return result['top_picks']
    else:
        logger.error(f"Phase 2 failed: {result.get('error')}")
        return []


async def main():
    """Run full pipeline test"""
    try:
        # Phase 1
        candidates = await test_phase1()
        
        if not candidates:
            logger.error("No candidates from Phase 1")
            return
        
        # Phase 2
        top_picks = await test_phase2(candidates)
        
        if not top_picks:
            logger.error("No top picks from Phase 2")
            return
        
        logger.info("=" * 60)
        logger.info("✅ PIPELINE TEST COMPLETE")
        logger.info(f"   Phase 1: {len(candidates)} candidates")
        logger.info(f"   Phase 2: {len(top_picks)} winners")
        logger.info("=" * 60)
        
        # Phase 3 would connect to IBKR and run Claude analysis
        logger.info("\n💡 Phase 3 (Claude + IBKR Greeks) - requires IBKR connection")
        logger.info("   Run main.py to test full pipeline")
        
    except KeyboardInterrupt:
        logger.info("\n\nTest interrupted by user")
    except Exception as e:
        logger.error(f"\n\nTest failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
