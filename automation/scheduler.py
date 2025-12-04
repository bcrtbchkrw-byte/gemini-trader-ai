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
from analysis.shadow_tracker import get_shadow_tracker


class TradingScheduler:
    """Schedule trading activities to minimize AI token usage"""
    
    def __init__(self):
        # self.premarket_scanner = get_premarket_scanner() # Missing file
        self.screener = get_stock_screener()
        self.gemini = get_gemini_client()
        self.shadow_tracker = get_shadow_tracker()
        self.running = False
    
    async def run_scheduled_scan(self):
        """
        Run scheduled scan + analysis
        """
        logger.info("=" * 60)
        logger.info("🕐 SCHEDULED SCAN STARTED")
        logger.info("=" * 60)
        
        try:
            # Step 1: Scan for candidates
            logger.info("\n📊 Running market scan...")
            candidates = await self.screener.screen(max_candidates=15)
            
            if not candidates:
                logger.warning("No candidates found")
                return
            
            logger.info(f"\n✅ Found {len(candidates)} candidates:")
            for i, c in enumerate(candidates[:5], 1):
                logger.info(f"  {i}. {c['symbol']}: IV Rank {c.get('iv_rank', 0)}, Score: {c.get('score', 0)}")
            
            # Step 2: Run Phase 1-2 on top picks
            logger.info("\n🤖 Running AI analysis on top picks...")
            
            # Use existing screening pipeline
            from analysis.news_fetcher import get_news_fetcher
            from analysis.vix_monitor import get_vix_monitor
            
            news_fetcher = get_news_fetcher()
            vix_monitor = get_vix_monitor()
            
            await vix_monitor.update()
            vix = vix_monitor.get_current_vix()
            
            top_symbols = [c['symbol'] for c in candidates[:10]]
            
            # Fetch news
            news_context = await news_fetcher.fetch_batch(top_symbols)
            
            # Prepare candidate data
            candidate_data = [
                {
                    'symbol': c['symbol'],
                    'price': c.get('price', 0),
                    'iv_rank': c.get('iv_rank', 50),
                    'sector': c.get('sector', 'Unknown')
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
    
    async def run_weekly_loss_analysis(self):
        """
        Run weekly analysis of ALL losing trades
        
        Analyzes all losses from the past week (no limit)
        """
        try:
            logger.info("🔍 Starting Weekly Loss Analysis...")
            
            from analysis.loss_analyzer import get_loss_analyzer
            from notifications.telegram_notifier import get_telegram_notifier
            
            analyzer = get_loss_analyzer()
            
            # Analyze ALL losses from past 7 days
            # max_analyses=20 prevents excessive Claude API costs if many losses
            report = await analyzer.analyze_recent_losses(
                days=7,
                max_analyses=20
            )
            
            # Send report via Telegram
            telegram = get_telegram_notifier()
            await telegram.send_message(
                f"📉 *WEEKLY LOSS ANALYSIS*\n\n{report[:3000]}",  # Truncate if too long
                parse_mode='Markdown'
            )
            
            logger.info("✅ Weekly loss analysis completed and sent.")
            
        except Exception as e:
            logger.error(f"Error in weekly loss analysis: {e}")
            
    async def run_premarket_scan(self):
        """Run premarket scan"""
        # This method is currently empty as the logic is within run_scheduled_scan
        # It can be populated if a dedicated premarket scan trigger is needed.
        pass

    def _get_scan_interval(self, current_time: time) -> int:
        """
        Get scan interval in minutes based on market hours
        
        Schedule:
        - 09:30 - 10:30: Every 15 min (High Opportunity)
        - 10:30 - 11:00: Every 30 min (Transition)
        - 11:00 - 14:30: Every 60 min (Lunch Lull)
        - 14:30 - 16:00: Every 30 min (Closing Prep)
        - Other: 60 min
        """
        # Convert to minutes for easier comparison
        current_min = current_time.hour * 60 + current_time.minute
        
        t_930 = 9 * 60 + 30
        t_1030 = 10 * 60 + 30
        t_1100 = 11 * 60
        t_1430 = 14 * 60 + 30
        t_1600 = 16 * 60
        
        if t_930 <= current_min < t_1030:
            return 15
        elif t_1030 <= current_min < t_1100:
            return 30
        elif t_1100 <= current_min < t_1430:
            return 60
        elif t_1430 <= current_min < t_1600:
            return 30
        else:
            return 60

    async def run_scheduler_loop(self):
        """
        Main scheduler loop with dynamic intervals (US/Eastern Time)
        """
        from utils.market_time import MarketTime, initialize_market_time
        
        # Sync time on startup
        await initialize_market_time()
        
        logger.info("🕐 Scheduler started with DYNAMIC INTERVALS (US/Eastern Time)")
        self.running = True
        
        # Times are now timezone-aware (US/Eastern)
        # We use time objects, but comparisons will be done against MarketTime.get_now().time()
        scheduled_times = {
            'premarket_scan': time(8, 45),
            'shadow_eval': time(16, 15), # After market close
        }
        
        last_run = {
            'scan': datetime.min.replace(tzinfo=pytz.timezone('US/Eastern')),
            'premarket': datetime.min.replace(tzinfo=pytz.timezone('US/Eastern')),
            'shadow': datetime.min.replace(tzinfo=pytz.timezone('US/Eastern'))
        }
        
        while self.running:
            try:
                # Get current MARKET time (US/Eastern)
                now = MarketTime.get_now()
                current_time = now.time()
                
                # 1. Fixed Time Tasks
                # Premarket Scan (8:45)
                if (current_time >= scheduled_times['premarket_scan'] and
                    last_run['premarket'].date() != now.date()):
                    
                    logger.info("\n🔔 Premarket scan time!")
                    await self.run_scheduled_scan()
                    last_run['premarket'] = now
                
                # Shadow Trade Evaluation (16:15)
                if (current_time >= scheduled_times['shadow_eval'] and
                    last_run['shadow'].date() != now.date()):
                    
                    logger.info("\n🔔 Shadow trade evaluation time!")
                    await self.shadow_tracker.run_daily_evaluation()
                    last_run['shadow'] = now
                
                # 2. Dynamic Interval Tasks (Market Hours Scan)
                # Only run between 9:30 and 16:00
                market_open = time(9, 30)
                market_close = time(16, 0)
                
                if market_open <= current_time <= market_close:
                    interval_minutes = self._get_scan_interval(current_time)
                    time_since_last = (now - last_run['scan']).total_seconds() / 60
                    
                    if time_since_last >= interval_minutes:
                        logger.info(f"\n🔔 Scheduled Scan (Interval: {interval_minutes}m)")
                        await self.run_scheduled_scan()
                        last_run['scan'] = now
                
                # Sleep for 1 minute to check again
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(60)
    
    async def cleanup_stale_orders_loop(self):
        """
        Periodically cancel orders older than TTL threshold
        
        Runs every cleanup_interval_minutes during market hours
        """
        from ibkr.order_manager import get_order_manager
        from config import get_config
        
        config = get_config()
        order_manager = get_order_manager()
        
        ttl_minutes = config.order_ttl.ttl_minutes
        cleanup_interval = config.order_ttl.cleanup_interval_minutes
        
        logger.info(
            f"🗑️ Order TTL cleanup enabled: cancel orders older than {ttl_minutes} min, "
            f"checking every {cleanup_interval} min"
        )
        
        while self.running:
            try:
                # Only run during market hours
                now = datetime.now().time()
                market_open = time(9, 30)
                market_close = time(16, 0)
                
                if market_open <= now <= market_close:
                    logger.debug("🔍 Running stale order cleanup...")
                    cancelled = await order_manager.cancel_stale_orders(ttl_minutes)
                    
                    if cancelled > 0:
                        logger.warning(f"🗑️ Cancelled {cancelled} stale order(s)")
                
                # Wait for next cleanup interval
                await asyncio.sleep(cleanup_interval * 60)
                
            except Exception as e:
                logger.error(f"Error in order cleanup: {e}")
                await asyncio.sleep(60)  # Wait 1 min before retry


# Singleton
_scheduler: Optional[TradingScheduler] = None


def get_trading_scheduler() -> TradingScheduler:
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
