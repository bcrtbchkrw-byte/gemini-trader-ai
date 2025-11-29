"""
Strategy Selector
Selects appropriate strategy based on VIX regime and market conditions.
"""
from typing import Dict, Any, Optional
from loguru import logger
from analysis.vix_monitor import get_vix_monitor
from strategies.credit_spreads import get_credit_spread_builder
from strategies.debit_spreads import get_debit_spread_builder
from ai.gemini_client import get_gemini_client
from ai.claude_client import get_claude_client


class StrategySelector:
    """Select and build appropriate trading strategy based on market conditions"""
    
    def __init__(self):
        self.vix_monitor = get_vix_monitor()
        self.credit_builder = get_credit_spread_builder()
        self.debit_builder = get_debit_spread_builder()
        self.gemini = get_gemini_client()
        self.claude = get_claude_client()
    
    async def select_strategy(
        self,
        symbol: str,
        current_price: float
    ) -> Optional[Dict[str, Any]]:
        """
        Select and build best strategy for current market conditions
        
        Args:
            symbol: Stock ticker
            current_price: Current stock price
            
        Returns:
            Strategy details or None
        """
        try:
            # Update VIX
            await self.vix_monitor.update()
            
            vix = self.vix_monitor.get_current_vix()
            regime = self.vix_monitor.get_current_regime()
            
            logger.info(
                f"\n{'='*60}\n"
                f"STRATEGY SELECTION FOR {symbol}\n"
                f"{'='*60}\n"
                f"VIX: {vix:.2f}, Regime: {regime}\n"
                f"Current Price: ${current_price:.2f}\n"
                f"{'='*60}"
            )
            
            # Check if trading allowed
            if not self.vix_monitor.is_trading_allowed():
                logger.warning("🛑 Trading blocked - VIX in PANIC mode")
                return None
            
            # Step 1: Gemini Fundamental Analysis
            logger.info("\n📊 Step 1: Gemini Fundamental Analysis")
            logger.info("-" * 60)
            
            gemini_result = await self.gemini.analyze_fundamental(
                symbol=symbol,
                current_price=current_price,
                vix=vix
            )
            
            if not gemini_result['success']:
                logger.error("Gemini analysis failed")
                return None
            
            fundamental_recommendation = gemini_result['analysis'].get('recommendation', 'AVOID')
            
            logger.info(f"Gemini Recommendation: {fundamental_recommendation}")
            
            if fundamental_recommendation == 'AVOID':
                logger.warning("⚠️ Gemini recommends AVOID - skipping strategy selection")
                return None
            
            # Step 2: Build Strategy Based on Regime
            logger.info("\n📈 Step 2: Building Strategy")
            logger.info("-" * 60)
            
            strategy = None
            
            if regime == "HIGH_VOL":
                # High VIX - prefer credit spreads
                logger.info("High volatility - building credit spreads")
                
                # Try Iron Condor first
                strategy = await self.credit_builder.build_iron_condor(
                    symbol=symbol,
                    current_price=current_price
                )
                
                # If Iron Condor fails, try single credit spread
                if not strategy:
                    logger.info("Iron Condor failed, trying vertical credit spread")
                    
                    # Choose call or put based on sentiment
                    sentiment = gemini_result['analysis'].get('sentiment', 'NEUTRAL')
                    right = 'P' if sentiment == 'BULLISH' else 'C'
                    
                    strategy = await self.credit_builder.build_vertical_credit_spread(
                        symbol=symbol,
                        right=right,
                        current_price=current_price
                    )
                    
            elif regime == "NORMAL":
                # Normal VIX - selective credit spreads
                logger.info("Normal volatility - selective credit spreads")
                
                sentiment = gemini_result['analysis'].get('sentiment', 'NEUTRAL')
                right = 'P' if sentiment == 'BULLISH' else 'C'
                
                strategy = await self.credit_builder.build_vertical_credit_spread(
                    symbol=symbol,
                    right=right,
                    current_price=current_price
                )
                
            elif regime == "LOW_VOL":
                # Low VIX - prefer debit spreads
                logger.info("Low volatility - building debit spreads")
                
                sentiment = gemini_result['analysis'].get('sentiment', 'NEUTRAL')
                
                if sentiment == 'BULLISH':
                    right = 'C'  # Call debit spread
                elif sentiment == 'BEARISH':
                    right = 'P'  # Put debit spread
                else:
                    # Neutral - skip or try small credit
                    logger.info("Neutral sentiment in low VIX - skipping trade")
                    return None
                
                strategy = await self.debit_builder.build_vertical_debit_spread(
                    symbol=symbol,
                    right=right,
                    current_price=current_price
                )
            
            if not strategy:
                logger.warning("No suitable strategy found")
                return None
            
            # Step 3: Claude Greeks Validation
            logger.info("\n🤖 Step 3: Claude Greeks Validation")
            logger.info("-" * 60)
            
            # Prepare options data for Claude
            options_data = []
            
            if strategy['type'] == 'iron_condor':
                options_data = [
                    strategy['call_spread']['short_leg'],
                    strategy['call_spread']['long_leg'],
                    strategy['put_spread']['short_leg'],
                    strategy['put_spread']['long_leg']
                ]
            else:
                options_data = [
                    strategy.get('short_leg') or strategy.get('long_leg'),
                ]
            
            claude_result = await self.claude.analyze_greeks_and_recommend(
                symbol=symbol,
                options_data=options_data,
                vix=vix,
                regime=regime
            )
            
            if not claude_result['success']:
                logger.error("Claude analysis failed")
                return None
            
            verdict = claude_result['recommendation']['verdict']
            
            logger.info(f"Claude Verdict: {verdict}")
            
            if verdict != 'SCHVÁLENO':
                logger.warning(f"❌ Claude rejected strategy: {verdict}")
                return None
            
            # Final strategy with all validations passed
            strategy['gemini_analysis'] = gemini_result['analysis']
            strategy['claude_recommendation'] = claude_result['recommendation']
            strategy['vix'] = vix
            strategy['regime'] = regime
            
            logger.info(
                f"\n{'='*60}\n"
                f"✅ STRATEGY SELECTED: {strategy['type'].upper()}\n"
                f"{'='*60}\n"
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"Error in strategy selection: {e}")
            return None
    
    async def get_strategy_recommendation(
        self,
        symbol: str,
        current_price: float
    ) -> Dict[str, Any]:
        """
        Get strategy recommendation without building full strategy
        
        Args:
            symbol: Stock ticker
            current_price: Current price
            
        Returns:
            Recommendation dict
        """
        try:
            await self.vix_monitor.update()
            
            vix = self.vix_monitor.get_current_vix()
            regime = self.vix_monitor.get_current_regime()
            
            preferred_strategies = self.vix_monitor.get_preferred_strategies()
            
            return {
                'symbol': symbol,
                'price': current_price,
                'vix': vix,
                'regime': regime,
                'trading_allowed': self.vix_monitor.is_trading_allowed(),
                'preferred_strategies': preferred_strategies,
                'regime_description': self.vix_monitor.get_regime_description()
            }
            
        except Exception as e:
            logger.error(f"Error getting strategy recommendation: {e}")
            return {}


# Singleton instance
_strategy_selector: Optional[StrategySelector] = None


def get_strategy_selector() -> StrategySelector:
    """Get or create singleton strategy selector"""
    global _strategy_selector
    if _strategy_selector is None:
        _strategy_selector = StrategySelector()
    return _strategy_selector
