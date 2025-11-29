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
        
        # Initialize components
        self.vix_monitor = get_vix_monitor()
        self.gemini = get_gemini_client()
        self.claude = get_claude_client()
        
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
        logger.info(f"Account Size: ${self.config.trading.account_size:.2f}")
        logger.info(f"Max Risk Per Trade: ${self.config.trading.max_risk_per_trade:.2f}")
        logger.info(f"Max Allocation: {self.config.trading.max_allocation_percent:.0f}%")
        logger.info(f"Paper Trading: {self.config.safety.paper_trading}")
        logger.info(f"Auto Execute: {self.config.safety.auto_execute}")
        logger.info("=" * 60 + "\n")
    
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
    """Main entry point"""
    trader = GeminiTraderAI()
    
    try:
        # Initialize system
        success = await trader.initialize()
        
        if not success:
            logger.error("Initialization failed. Exiting.")
            return
        
        # Check if we should run demo
        if trader.config.safety.paper_trading:
            logger.info("\n⚠️  Running in PAPER TRADING mode")
            logger.info("Demo analysis will be performed on SPY\n")
            
            # Run demo analysis
            await trader.run_analysis_demo("SPY")
        else:
            logger.info("System initialized. Ready for live trading.")
        
    except KeyboardInterrupt:
        logger.info("\nReceived shutdown signal...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        await trader.shutdown()


if __name__ == "__main__":
    # Setup logger
    setup_logger()
    
    # Run main async loop
    asyncio.run(main())
