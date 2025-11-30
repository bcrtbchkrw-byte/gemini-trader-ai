"""
Gemini Trader AI - Main Entry Point
AI-powered options trading system for IBKR with Gemini and Claude integration.
"""
import asyncio
from loguru import logger
from config import get_config, reload_config
from data.logger import setup_logger
from data.database import get_database
from ibkr.connection import get_ibkr_connection
from analysis.vix_monitor import get_vix_monitor
from ai.gemini_client import get_gemini_client
from ai.claude_client import get_claude_client


class GeminiTraderAI:
    """Main trading system orchestrator"""
    
    def __init__(self):
        self.config = get_config()
        self.db = None
        self.ibkr = None
        self.vix_monitor = None
        self.gemini = None
        self.claude = None
        self.running = False
    
    async def initialize(self):
        """Initialize all system components"""
        logger.info("=" * 60)
        logger.info("Gemini Trader AI - Initialization")
        logger.info("=" * 60)
        
        # Initialize database
        logger.info("Initializing database...")
        self.db = await get_database()
        
        # Initialize IBKR connection
        logger.info("Connecting to IBKR...")
        self.ibkr = get_ibkr_connection()
        connected = await self.ibkr.connect()
        
        if not connected:
            logger.error("Failed to connect to IBKR. Please ensure TWS/IB Gateway is running.")
            return False
        
        # CRITICAL: Reconcile positions after restart
        logger.info("\n🔄 Reconciling positions with IBKR portfolio...")
        from data.position_reconciler import get_position_reconciler
        
        reconciler = get_position_reconciler(self.db, self.ibkr)
        reconciliation_report = await reconciler.reconcile_positions()
        
        if not reconciliation_report.get('success'):
            logger.error("Position reconciliation failed - proceeding with caution")
        else:
            closed_externally = len(reconciliation_report.get('closed_externally', []))
            if closed_externally > 0:
                logger.warning(
                    f"⚠️  Found {closed_externally} positions closed externally! "
                    f"DB updated."
                )
        
        # Initialize components
        self.vix_monitor = get_vix_monitor()
        self.gemini = get_gemini_client()
        self.claude = get_claude_client()
        
        # Fetch account balance from IBKR API
        logger.info("Fetching account balance from IBKR...")
        account_balance = await self.ibkr.get_account_balance()
        if account_balance:
            self.config.trading.update_account_size(account_balance)
            logger.info(f"Account balance updated: ${account_balance:.2f}")
        else:
            logger.warning("Could not fetch account balance from IBKR API")
        
        # Initial VIX update
        logger.info("Fetching initial VIX value...")
        await self.vix_monitor.update()
        
        logger.info("=" * 60)
        logger.info("✅ Initialization complete")
        logger.info("=" * 60)
        
        # Display current status
        self._display_status()
        
        return True
    
    def _display_status(self):
        """Display current system status"""
        vix = self.vix_monitor.get_current_vix()
        regime = self.vix_monitor.get_current_regime()
        regime_desc = self.vix_monitor.get_regime_description()
        
        logger.info("\n" + "=" * 60)
        logger.info("CURRENT MARKET STATUS")
        logger.info("=" * 60)
        logger.info(regime_desc)
        
        if self.vix_monitor.is_trading_allowed():
            strategies = self.vix_monitor.get_preferred_strategies()
            logger.info(f"Preferred strategies: {', '.join(strategies)}")
        else:
            logger.warning("🛑 TRADING BLOCKED - VIX in PANIC mode")
        
        logger.info("=" * 60)
        account_size_str = f"${self.config.trading.account_size:.2f}" if self.config.trading.account_size else "Not fetched yet"
        logger.info(f"Account Size: {account_size_str}")
        logger.info(f"Max Risk Per Trade: ${self.config.trading.max_risk_per_trade:.2f}")
        logger.info(f"Max Allocation: {self.config.trading.max_allocation_percent:.0f}%")
        logger.info(f"Paper Trading: {self.config.safety.paper_trading}")
        logger.info(f"Auto Execute: {self.config.safety.auto_execute}")
        logger.info("=" * 60 + "\n")
    
    async def run_screening_pipeline(self):
        """
        Execute 3-Phase Screening Pipeline
        
        Phase 1: Local pre-check (price, liquidity, IV rank) → ~10 candidates
        Phase 2: Gemini batch analysis with news → 2-3 winners
        Phase 3: IBKR Greeks + Claude strategy → executable trades
        """
        try:
            from analysis.news_fetcher import get_news_fetcher
            from ibkr.data_fetcher import get_data_fetcher
            
            logger.info("\n" + "=" * 60)
            logger.info("🚀 STARTING 3-PHASE SCREENING PIPELINE")
            logger.info("=" * 60 + "\n")
            
            # Get current market regime
            await self.vix_monitor.update()
            vix = self.vix_monitor.get_current_vix()
            regime = self.vix_monitor.get_current_regime()
            
            # =============================================================
            # PHASE 1: PRE-CHECK (Local - Free)
            # =============================================================
            logger.info("📊 PHASE 1: Stock Pre-Check")
            logger.info("-" * 60)
            
            screener = get_stock_screener()
            criteria = ScreeningCriteria(
                min_price=20,
                max_price=300,
                min_daily_volume=1_000_000,
                vix_regime=regime
            )
            
            candidates = await screener.screen(criteria=criteria, max_results=10)
            
            if not candidates:
                logger.warning("❌ No candidates passed Phase 1 filters")
                return []
            
            logger.info(f"✅ Phase 1 Complete: {len(candidates)} candidates selected\n")
            
            # =============================================================
            # PHASE 1.5: EARNINGS FILTER (Filter BEFORE expensive AI calls)
            # =============================================================
            logger.info("=" * 60)
            logger.info("📅 PHASE 1.5: EARNINGS BLACKOUT FILTER")
            logger.info("=" * 60)
            
            from analysis.earnings_checker import get_earnings_checker
            
            earnings_checker = get_earnings_checker()
            symbols = [c['symbol'] for c in candidates]
            
            # Filter out symbols in earnings blackout window
            safe_symbols = await earnings_checker.filter_safe_symbols(symbols)
            
            filtered_candidates = [
                c for c in candidates
                if c['symbol'] in safe_symbols
            ]
            
            blacklisted_count = len(candidates) - len(filtered_candidates)
            
            if blacklisted_count > 0:
                blacklisted_symbols = [
                    c['symbol'] for c in candidates
                    if c['symbol'] not in safe_symbols
                ]
                logger.warning(
                    f"⚠️  Filtered {blacklisted_count} stocks in earnings blackout: "
                    f"{', '.join(blacklisted_symbols)}"
                )
            
            logger.info(f"✅ {len(filtered_candidates)} stocks passed earnings filter\n")
            
            if not filtered_candidates:
                logger.warning("No stocks passed earnings filter - pipeline stopped")
                return []
            
            # Use filtered candidates for Gemini analysis
            candidates = filtered_candidates
            
            # =============================================================
            # PHASE 2: GEMINI FUNDAMENTAL ANALYSIS
            # =============================================================
            logger.info("🤖 PHASE 2: Gemini Fundamental Analysis + News")
            logger.info("-" * 60)
            
            # Fetch news for all candidates
            news_fetcher = get_news_fetcher()
            news_context = await news_fetcher.fetch_batch(
                [c['symbol'] for c in candidates]
            )
            
            # Gemini batch analysis
            gemini_result = await self.gemini.batch_analyze_with_news(
                candidates=candidates,
                news_context=news_context,
                vix=vix
            )
            
            if not gemini_result['success']:
                logger.error(f"❌ Phase 2 failed: {gemini_result.get('error')}")
                return []
            
            top_picks = gemini_result['top_picks'][:3]  # Max 3
            
            if not top_picks:
                logger.warning("❌ No stocks passed Phase 2 analysis")
                return []
            
            logger.info(f"✅ Phase 2 Complete: {len(top_picks)} winners selected")
            logger.info(f"🎯 Top Picks: {', '.join(top_picks)}\n")
            
            # =============================================================
            # PHASE 3: CLAUDE PRECISION STRIKE
            # =============================================================
            logger.info("🎯 PHASE 3: Claude Strategy + IBKR Greeks")
            logger.info("-" * 60)
            logger.info("Connecting to IBKR for winners only...\n")
            
            # Initialize IBKR connection (if not already connected)
            if not self.ibkr:
                self.ibkr = get_ibkr_connection()
            
            if not self.ibkr.is_connected():
                connected = await self.ibkr.connect()
                if not connected:
                    logger.error("❌ Failed to connect to IBKR for Phase 3")
                    return []
                
                # Fetch account balance
                account_balance = await self.ibkr.get_account_balance()
                if account_balance:
                    self.config.trading.update_account_size(account_balance)
            
            # Analyze each winner
            data_fetcher = get_data_fetcher()
            recommendations = []
            
            for symbol in top_picks:
                logger.info(f"📈 Analyzing {symbol}...")
                
                try:
                    # Fetch real Greeks from IBKR
                    options_data = await data_fetcher.get_options_with_greeks(
                        symbol=symbol,
                        min_dte=30,
                        max_dte=45,
                        min_delta=0.15,
                        max_delta=0.25
                    )
                    
                    if not options_data:
                        logger.warning(f"   ⚠️  No suitable options found for {symbol}")
                        continue
                    
                    # Prepare stock data for Claude
                    stock_data = {
                        'symbol': symbol,
                        'price': options_data[0].get('stock_price', 0),
                        'iv_rank': options_data[0].get('iv_rank', 50),
                        'volume': options_data[0].get('volume', 0),
                        'sector': 'Unknown'  # TODO: Fetch from data_fetcher
                    }
                    
                    # Use first option's Greeks (or aggregate if multiple)
                    greeks_data = {
                        'delta': options_data[0].get('delta', 0),
                        'gamma': options_data[0].get('gamma', 0),
                        'theta': options_data[0].get('theta', 0),
                        'vega': options_data[0].get('vega', 0),
                        'vanna': options_data[0].get('vanna', 0),
                        'impl_vol': options_data[0].get('impliedVolatility', 0),
                    }
                    
                    # Claude strategy analysis with confidence scoring
                    claude_result = await self.claude.analyze_strategy(
                        stock_data=stock_data,
                        options_data=greeks_data,
                        strategy_type="CREDIT_SPREAD"  # Or detect from options_data
                    )
                    
                    # Extract confidence and decision
                    confidence = claude_result.get('confidence_score', 0)
                    decision = claude_result.get('decision', 'REJECT')
                    approved = claude_result.get('approved', False)
                    
                    # Log result with confidence
                    confidence_emoji = "🔥" if confidence >= 9 else "⚠️" if confidence >= 7 else "❌"
                    logger.info(
                        f"   {confidence_emoji} Confidence: {confidence}/10 - {decision}"
                    )
                    
                    if approved:
                        logger.info(f"   ✅ APPROVED - High conviction trade\n")
                        recommendations.append({
                            'symbol': symbol,
                            'verdict': 'SCHVÁLENO',
                            'confidence': confidence,
                            'recommendation': claude_result,
                            'options_data': options_data
                        })
                    else:
                        reason = claude_result.get('reasoning', 'Low confidence')
                        logger.info(f"   ❌ REJECTED - {reason}\n")
                        
                except Exception as e:
                    logger.error(f"   ❌ Error analyzing {symbol}: {e}\n")
                    continue
            
            # =============================================================
            # SUMMARY
            # =============================================================
            logger.info("=" * 60)
            logger.info("✅ 3-PHASE PIPELINE COMPLETE")
            logger.info("=" * 60)
            logger.info(f"Phase 1 (Pre-check):     {len(candidates) + blacklisted_count} candidates")
            logger.info(f"Phase 1.5 (Earnings):    {blacklisted_count} filtered (blackout)")
            logger.info(f"Phase 2 (Gemini):        {len(top_picks)} winners")
            logger.info(f"Phase 3 (Claude):        {len(recommendations)} strategies")
            logger.info("=" * 60 + "\n")
            
            # Display approved trades with confidence scores
            approved = [r for r in recommendations if r['verdict'] == 'SCHVÁLENO']
            if approved:
                logger.info(f"✅ {len(approved)} APPROVED TRADES (Confidence >= 9/10):")
                for rec in approved:
                    conf = rec.get('confidence', 0)
                    strat = rec['recommendation'].get('strategy', 'N/A')
                    logger.info(f"   🎯 {rec['symbol']} - {strat} (Confidence: {conf}/10)")
                logger.info("")
            else:
                logger.info("⚠️  No trades approved by Claude (all below 9/10 confidence threshold)")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            return []
    
    async def run_analysis_demo(self, symbol: str = "SPY"):
        """
        Run a demonstration analysis on a symbol
        
        Args:
            symbol: Symbol to analyze
        """
        logger.info(f"\n{'=' * 60}")
        logger.info(f"RUNNING DEMO ANALYSIS: {symbol}")
        logger.info(f"{'=' * 60}\n")
        
        try:
            # Get current stock price
            from ibkr.data_fetcher import get_data_fetcher
            data_fetcher = get_data_fetcher()
            
            price = await data_fetcher.get_stock_price(symbol)
            if not price:
                logger.error(f"Could not fetch price for {symbol}")
                return
            
            # Update VIX
            await self.vix_monitor.update()
            vix = self.vix_monitor.get_current_vix()
            regime = self.vix_monitor.get_current_regime()
            
            # Run Gemini fundamental analysis
            logger.info(f"\n📊 Step 1: Gemini Fundamental Analysis")
            logger.info("-" * 60)
            
            gemini_result = await self.gemini.analyze_fundamental(
                symbol=symbol,
                current_price=price,
                vix=vix
            )
            
            if gemini_result['success']:
                analysis = gemini_result['analysis']
                logger.info(f"Fundamental Score: {analysis.get('fundamental_score', 'N/A')}/10")
                logger.info(f"Sentiment: {analysis.get('sentiment', 'N/A')}")
                logger.info(f"Recommendation: {analysis.get('recommendation', 'N/A')}")
            
            # Get options with Greeks
            logger.info(f"\n📈 Step 2: Fetching Options Data")
            logger.info("-" * 60)
            
            options_data = await data_fetcher.get_options_with_greeks(
                symbol=symbol,
                min_dte=30,
                max_dte=45,
                min_delta=0.15,
                max_delta=0.25
            )
            
            if options_data:
                logger.info(f"Found {len(options_data)} suitable options")
                
                # Run Claude Greeks analysis
                logger.info(f"\n🤖 Step 3: Claude Greeks Analysis")
                logger.info("-" * 60)
                
                claude_result = await self.claude.analyze_greeks_and_recommend(
                    symbol=symbol,
                    options_data=options_data,
                    vix=vix,
                    regime=regime
                )
                
                if claude_result['success']:
                    recommendation = claude_result['recommendation']
                    logger.info(f"\nVerdict: {recommendation['verdict']}")
                    logger.info(f"Strategy: {recommendation.get('strategy', 'N/A')}")
                
            else:
                logger.warning("No suitable options found for analysis")
            
            logger.info(f"\n{'=' * 60}")
            logger.info("DEMO ANALYSIS COMPLETE")
            logger.info(f"{'=' * 60}\n")
            
        except Exception as e:
            logger.error(f"Error in demo analysis: {e}")
    
    async def shutdown(self):
        """Gracefully shutdown the system"""
        logger.info("\n" + "=" * 60)
        logger.info("Shutting down Gemini Trader AI...")
        logger.info("=" * 60)
        
        if self.ibkr:
            await self.ibkr.disconnect()
        
        logger.info("✅ Shutdown complete")
        logger.info("=" * 60 + "\n")


async def main():
    """Main entry point with scheduler integration"""
    import os
    trader = GeminiTraderAI()
    
    try:
        # Initialize basic components
        logger.info("Initializing Gemini Trader AI...")
        
        trader.db = await get_database()
        trader.vix_monitor = get_vix_monitor()
        trader.gemini = get_gemini_client()
        trader.claude = get_claude_client()
        
        # VIX check
        await trader.vix_monitor.update()
        logger.info(f"VIX: {trader.vix_monitor.get_current_vix():.2f}")
        logger.info(f"Regime: {trader.vix_monitor.get_current_regime()}\n")
        
        # Check if auto-premarket scan is enabled
        auto_scan = os.getenv('AUTO_PREMARKET_SCAN', 'false').lower() == 'true'
        
        if auto_scan:
            logger.info("🕐 Auto-scheduler enabled - running scheduled workflow")
            logger.info("=" * 60)
            
            from automation.scheduler import get_scheduler
            
            scheduler = get_scheduler()
            
            # Run scheduled scan (will check time and cache)
            await scheduler.run_scheduled_scan()
            
            # Ask if user wants to run continuous scheduler
            logger.info("\n" + "=" * 60)
            logger.info("Options:")
            logger.info("1. One-time scan complete (cached for today)")  
            logger.info("2. Run continuous scheduler (monitors all day)")
            logger.info("=" * 60)
            
            # For now, just do one-time scan
            # To run continuous: await scheduler.run_scheduler_loop()
            
        else:
            logger.info("Manual mode - running full pipeline")
            logger.info("=" * 60)
            
            # Run 3-Phase Screening Pipeline
            recommendations = await trader.run_screening_pipeline()
            
            if not recommendations:
                logger.warning("\n⚠️  No trades to execute from pipeline")
            else:
                logger.info(f"\n✅ Pipeline complete with {len(recommendations)} recommendations")
                
                # In production, would execute approved trades here
                approved = [r for r in recommendations if r['verdict'] == 'SCHVÁLENO']
                if approved and not trader.config.safety.auto_execute:
                    logger.info("\n💡 AUTO_EXECUTE=false - Manual approval required")
        
    except KeyboardInterrupt:
        logger.info("\n\nReceived shutdown signal...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await trader.shutdown()


async def run_scheduler_daemon():
    """Run scheduler in continuous mode (daemon)"""
    from automation.scheduler import get_scheduler
    from data.logger import setup_logger
    
    setup_logger()
    
    logger.info("=" * 60)
    logger.info("🕐 SCHEDULER DAEMON MODE")
    logger.info("=" * 60)
    logger.info("Will run:")
    logger.info("  8:45 AM - Premarket scan")
    logger.info("  9:00 AM - Full analysis")
    logger.info("  Then monitor throughout day")
    logger.info("=" * 60 + "\n")
    
    scheduler = get_scheduler()
    
    try:
        await scheduler.run_scheduler_loop()
    except KeyboardInterrupt:
        logger.info("\nScheduler stopped by user")
        scheduler.stop()


if __name__ == "__main__":
    import sys
    
    # Setup logger
    setup_logger()
    
    # Check command line args
    if len(sys.argv) > 1 and sys.argv[1] == '--scheduler':
        # Run in continuous scheduler mode
        asyncio.run(run_scheduler_daemon())
    else:
        # Standard one-time run
        asyncio.run(main())
