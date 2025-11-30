"""
Strategy Pre-Computer - Prepare strategies ahead of AI approval
Decouples strategy generation from execution for minimal latency.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
import asyncio


class StrategyPreComputer:
    """Pre-compute strategy parameters for fast execution"""
    
    def __init__(self):
        self.precomputed_strategies = {}
        self.cache_ttl = 300  # 5 minutes
    
    async def precompute_strategy(
        self,
        symbol: str,
        strategy_type: str,
        market_data: Dict[str, Any],
        greeks: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Pre-compute strategy BEFORE AI approval
        
        This calculates all parameters (strikes, quantities, limits)
        so execution can happen instantly after AI says "GO".
        
        Args:
            symbol: Stock symbol
            strategy_type: e.g., "IRON_CONDOR"
            market_data: Current market prices
            greeks: Option Greeks
            
        Returns:
            Pre-computed strategy ready for instant execution
        """
        try:
            logger.info(f"Pre-computing {strategy_type} for {symbol}...")
            
            # Calculate optimal strikes BEFORE AI
            strikes = await self._calculate_optimal_strikes(
                symbol, strategy_type, market_data, greeks
            )
            
            # Calculate optimal quantities
            quantities = await self._calculate_quantities(
                strategy_type, strikes, market_data
            )
            
            # Pre-calculate EXACT limit prices
            limit_prices = await self._calculate_aggressive_limits(
                strikes, market_data
            )
            
            precomputed = {
                'symbol': symbol,
                'strategy_type': strategy_type,
                'strikes': strikes,
                'quantities': quantities,
                'limit_prices': limit_prices,
                'market_snapshot': market_data,
                'computed_at': datetime.now().isoformat(),
                'ready_to_execute': True
            }
            
            # Cache for fast lookup
            cache_key = f"{symbol}_{strategy_type}"
            self.precomputed_strategies[cache_key] = precomputed
            
            logger.info(
                f"✅ Strategy pre-computed: {strategy_type} "
                f"Strikes: {strikes}, Limits: {limit_prices}"
            )
            
            return precomputed
            
        except Exception as e:
            logger.error(f"Error pre-computing strategy: {e}")
            return None
    
    async def _calculate_optimal_strikes(
        self,
        symbol: str,
        strategy_type: str,
        market_data: Dict[str, Any],
        greeks: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate optimal strikes for strategy"""
        current_price = market_data.get('price', 100)
        
        if strategy_type == "IRON_CONDOR":
            # Example: 10-wide wings, 15-wide body
            return {
                'put_short': current_price * 0.95,  # 5% OTM
                'put_long': current_price * 0.92,   # 8% OTM
                'call_short': current_price * 1.05, # 5% OTM
                'call_long': current_price * 1.08   # 8% OTM
            }
        
        elif strategy_type == "VERTICAL_PUT_SPREAD":
            return {
                'short': current_price * 0.97,  # 3% OTM
                'long': current_price * 0.94    # 6% OTM
            }
        
        elif strategy_type == "VERTICAL_CALL_SPREAD":
            return {
                'short': current_price * 1.03,
                'long': current_price * 1.06
            }
        
        return {}
    
    async def _calculate_quantities(
        self,
        strategy_type: str,
        strikes: Dict[str, float],
        market_data: Dict[str, Any]
    ) -> Dict[str, int]:
        """Calculate optimal quantities based on risk"""
        # Simplified - would integrate with position_sizer.py
        return {'contracts': 1}
    
    async def _calculate_aggressive_limits(
        self,
        strikes: Dict[str, float],
        market_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Calculate AGGRESSIVE limit prices for fast fills
        
        Offset from market to ensure execution while protecting from slippage
        """
        # Example: For credit spreads
        mid_price = 1.50  # Would calculate from actual option chain
        
        # Offset limits to ensure fill:
        # - For selling (credit): limit BELOW mid (accept less premium)
        # - For buying (debit): limit ABOVE mid (pay more)
        
        return {
            'net_credit': mid_price * 0.95,  # Accept 5% less for faster fill
            'slippage_tolerance': 0.05
        }
    
    def get_precomputed(self, symbol: str, strategy_type: str) -> Optional[Dict[str, Any]]:
        """Get pre-computed strategy from cache"""
        cache_key = f"{symbol}_{strategy_type}"
        
        if cache_key in self.precomputed_strategies:
            strategy = self.precomputed_strategies[cache_key]
            
            # Check if still valid (< 5 min old)
            computed_at = datetime.fromisoformat(strategy['computed_at'])
            age = (datetime.now() - computed_at).seconds
            
            if age < self.cache_ttl:
                logger.info(f"Using cached strategy ({age}s old)")
                return strategy
            else:
                logger.warning(f"Cached strategy expired ({age}s old)")
                del self.precomputed_strategies[cache_key]
        
        return None
    
    async def parallel_precompute_batch(
        self,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Pre-compute strategies for multiple stocks IN PARALLEL
        
        This runs BEFORE AI approval, so when AI says "GO",
        execution is instant.
        """
        logger.info(f"Pre-computing {len(candidates)} strategies in parallel...")
        
        # Create parallel tasks
        tasks = [
            self.precompute_strategy(
                symbol=cand['symbol'],
                strategy_type=cand.get('suggested_strategy', 'VERTICAL_PUT_SPREAD'),
                market_data={'price': cand.get('price', 100)},
                greeks=cand.get('greeks', {})
            )
            for cand in candidates
        ]
        
        # Execute in parallel (asyncio.gather)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out errors
        valid_results = [r for r in results if r and not isinstance(r, Exception)]
        
        logger.info(f"✅ Pre-computed {len(valid_results)}/{len(candidates)} strategies")
        
        return valid_results


# Singleton
_precomputer: Optional[StrategyPreComputer] = None


def get_strategy_precomputer() -> StrategyPreComputer:
    """Get or create singleton pre-computer"""
    global _precomputer
    if _precomputer is None:
        _precomputer = StrategyPreComputer()
    return _precomputer
