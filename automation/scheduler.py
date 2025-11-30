#!/usr/bin/env python3
"""
Trading Scheduler - Automated premarket scan and analysis
Runs premarket scanner and AI analysis on schedule.
"""
from typing import Dict, Any, Optional
from loguru import logger
from datetime import datetime, time
import asyncio
import os

from analysis.stock_screener_ibkr import get_stock_screener  # IBKR native scanner
from ai.gemini_client import get_gemini_client


class TradingScheduler:
    """Schedule trading activities to minimize AI token usage"""
    
    def __init__(self):
        self.premarket_scanner = get_premarket_scanner()
        self.screener = get_stock_screener()
        self.gemini = get_gemini_client()
        self.running = False
    
    async def run_scheduled_scan(self):
        """
        Run scheduled premarket scan + analysis
        
        Workflow:
        1. 8:45 AM: Premarket scan (find movers)
        2. 9:00 AM: Run Phase 1-2 on cached candidates
        3. Cache results for rest of day
        """
        logger.info("=" * 60)
        logger.info("🕐 SCHEDULED SCAN STARTED")
        logger.info("=" * 60)
        
        try:
            # Step 1: Premarket scan (if time is right)
            if self.premarket_scanner.should_run_scan():
                logger.info("\n📊 Running premarket scan...")
                candidates = await self.premarket_scanner.scan_premarket(max_candidates=15)
                
                if not candidates:
                    logger.warning("No premarket candidates found")
                    return
                
                logger.info(f"\n✅ Found {len(candidates)} premarket movers:")
                for i, c in enumerate(candidates[:5], 1):
                    logger.info(
                        f"  {i}. {c['symbol']}: Gap {c['gap_pct']:+.1f}%, "
                        f"Volume {c['volume_ratio']:.1f}x, Score: {c['score']}"
                    )
            
            # Step 2: Get cached candidates
            candidates = self.premarket_scanner.get_cached_candidates()
            
            if not candidates:
                logger.warning("No cached candidates - run premarket scan first")
                return
            
            # Step 3: Run Phase 1-2 on top picks (no IBKR yet = no cost)
            logger.info("\n🤖 Running AI analysis on top picks...")
            
            top_symbols = [c['symbol'] for c in candidates[:10]]
            
            # Use existing screening pipeline
            from analysis.news_fetcher import get_news_fetcher
            from analysis.vix_monitor import get_vix_monitor
            
            news_fetcher = get_news_fetcher()
            vix_monitor = get_vix_monitor()
            
            await vix_monitor.update()
            vix = vix_monitor.get_current_vix()
            
            # Fetch news
            news_context = await news_fetcher.fetch_batch(top_symbols)
            
            # Prepare candidate data
            candidate_data = [
                {
                    'symbol': c['symbol'],
                    'price': c['current_price'],
                    'iv_rank': 50,  # Would use real IV calculator here
                    'sector': c['sector']
                }
                for c in candidates[:10]
            ]
            
            # Gemini batch analysis
            analysis = await self.gemini.batch_analyze_with_news(
                candidates=candidate_data,
                news_context=news_context,
                vix=vix
            )
            
            if analysis['success']:
                logger.info(f"\n✅ Analysis complete: {len(analysis['top_picks'])} top picks")
                logger.info(f"🎯 Winners: {', '.join(analysis['top_picks'])}")
                
                # Save to cache for Phase 3 later
                self._save_analysis_cache(analysis)
            else:
                logger.error("Analysis failed")
            
            logger.info("\n" + "=" * 60)
            logger.info("✅ SCHEDULED SCAN COMPLETE")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Scheduled scan error: {e}", exc_info=True)
    
    def _save_analysis_cache(self, analysis: dict):
        """Save analysis results to cache"""
        try:
            import json
            import os
            
            os.makedirs('data', exist_ok=True)
            
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'analysis': analysis
            }
            
            with open('data/analysis_cache.json', 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            logger.info("Analysis cached for later use")
            
        except Exception as e:
            logger.error(f"Error caching analysis: {e}")
    
    async def run_scheduler_loop(self):
        """
        Main scheduler loop
        
        Schedule:
        - 8:45 AM: Premarket scan
        - 9:00 AM: Full analysis (Phase 1-2)
        - Then check cache every hour for Phase 3 opportunities
        """
        logger.info("🕐 Scheduler started")
        self.running = True
        
        scheduled_times = {
            'premarket_scan': time(8, 45),
            'full_analysis': time(9, 0),
        }
        
        last_run = {}
        
        while self.running:
            try:
                now = datetime.now()
                current_time = now.time()
                
                # Check premarket scan
                if (current_time >= scheduled_times['premarket_scan'] and
                    last_run.get('premarket_scan', datetime.min).date() != now.date()):
                    
                    logger.info("\n🔔 Premarket scan time!")
                    await self.run_scheduled_scan()
                    last_run['premarket_scan'] = now
                
                # Sleep for 5 minutes
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(60)
    
    def stop(self):
        """Stop scheduler"""
        self.running = False
        logger.info("Scheduler stopped")


# Singleton
_scheduler: Optional[TradingScheduler] = None


def get_scheduler() -> TradingScheduler:
    """Get or create singleton scheduler"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TradingScheduler()
    return _scheduler


if __name__ == "__main__":
    """Run scheduler as standalone script"""
    from data.logger import setup_logger
    
    setup_logger()
    
    scheduler = get_scheduler()
    
    try:
        asyncio.run(scheduler.run_scheduler_loop())
    except KeyboardInterrupt:
        logger.info("\nScheduler stopped by user")
