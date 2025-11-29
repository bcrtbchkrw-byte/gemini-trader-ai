"""
Liquidity Checker
Validates option liquidity to avoid slippage and illiquid trades.
"""
from typing import Optional, Dict, Any
from ib_insync import Contract
from loguru import logger
from config import get_config
from ibkr.data_fetcher import get_data_fetcher


class LiquidityChecker:
    """Check option liquidity before trading"""
    
    def __init__(self):
        self.config = get_config().liquidity
        self.data_fetcher = get_data_fetcher()
    
    async def check_liquidity(self, contract: Contract) -> Dict[str, Any]:
        """
        Check if contract meets liquidity requirements
        
        Args:
            contract: Option contract to check
            
        Returns:
            Dict with liquidity metrics and pass/fail status
        """
        try:
            # Get option data including bid/ask and volume
            greeks_data = await self.data_fetcher.get_option_greeks(contract)
            
            if not greeks_data:
                return {
                    'passed': False,
                    'reason': 'Unable to fetch contract data',
                    'bid_ask_spread': None,
                    'volume': None,
                    'open_interest': None
                }
            
            bid = greeks_data.get('bid', 0)
            ask = greeks_data.get('ask', 0)
            volume = greeks_data.get('volume', 0)
            open_interest = greeks_data.get('open_interest', 0)
            
            # Calculate bid-ask spread
            if bid > 0 and ask > 0:
                spread = ask - bid
                mid_price = (bid + ask) / 2
                spread_percent = (spread / mid_price * 100) if mid_price > 0 else 100
            else:
                return {
                    'passed': False,
                    'reason': 'No valid bid/ask quotes',
                    'bid_ask_spread': None,
                    'volume': volume,
                    'open_interest': open_interest
                }
            
            # Check bid-ask spread
            spread_check_passed = spread <= self.config.max_bid_ask_spread or spread_percent <= 2.0
            
            # Check volume/OI ratio if OI exists
            if open_interest > 0:
                volume_oi_ratio = (volume / open_interest * 100)
                volume_check_passed = volume_oi_ratio >= self.config.min_volume_oi_ratio
            else:
                volume_oi_ratio = 0
                volume_check_passed = False  # Require some open interest
            
            # Overall pass
            passed = spread_check_passed and volume_check_passed
            
            result = {
                'passed': passed,
                'bid_ask_spread': spread,
                'spread_percent': spread_percent,
                'volume': volume,
                'open_interest': open_interest,
                'volume_oi_ratio': volume_oi_ratio,
                'reason': self._get_failure_reason(
                    spread_check_passed,
                    volume_check_passed,
                    spread,
                    spread_percent,
                    volume_oi_ratio
                )
            }
            
            if passed:
                logger.info(
                    f"✅ Liquidity check PASSED for {contract.symbol} {contract.strike}{contract.right}: "
                    f"Spread=${spread:.3f} ({spread_percent:.1f}%), Vol/OI={volume_oi_ratio:.1f}%"
                )
            else:
                logger.warning(
                    f"❌ Liquidity check FAILED for {contract.symbol} {contract.strike}{contract.right}: "
                    f"{result['reason']}"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking liquidity: {e}")
            return {
                'passed': False,
                'reason': f'Error: {str(e)}',
                'bid_ask_spread': None,
                'volume': None,
                'open_interest': None
            }
    
    def _get_failure_reason(
        self,
        spread_check:bool,
        volume_check: bool,
        spread: float,
        spread_percent: float,
        volume_oi_ratio: float
    ) -> Optional[str]:
        """Generate human-readable failure reason"""
        if spread_check and volume_check:
            return None  # Passed
        
        reasons = []
        
        if not spread_check:
            reasons.append(
                f"Bid-Ask spread too wide (${spread:.3f}, {spread_percent:.1f}% > max {self.config.max_bid_ask_spread})"
            )
        
        if not volume_check:
            reasons.append(
                f"Insufficient volume/OI ratio ({volume_oi_ratio:.1f}% < min {self.config.min_volume_oi_ratio}%)"
            )
        
        return"; ".join(reasons)
    
    async def check_spread_liquidity(self, short_leg: Contract, long_leg: Contract) -> bool:
        """
        Check liquidity for both legs of a spread
        
        Args:
            short_leg: Short option contract
            long_leg: Long option contract
            
        Returns:
            bool: True if both legs pass liquidity check
        """
        short_check = await self.check_liquidity(short_leg)
        long_check = await self.check_liquidity(long_leg)
        
        if short_check['passed'] and long_check['passed']:
            logger.info("✅ Both spread legs pass liquidity check")
            return True
        else:
            logger.warning("❌ Spread liquidity check failed")
            if not short_check['passed']:
                logger.warning(f"Short leg failed: {short_check['reason']}")
            if not long_check['passed']:
                logger.warning(f"Long leg failed: {long_check['reason']}")
            return False


# Singleton instance
_liquidity_checker: Optional[LiquidityChecker] = None


def get_liquidity_checker() -> LiquidityChecker:
    """Get or create singleton liquidity checker instance"""
    global _liquidity_checker
    if _liquidity_checker is None:
        _liquidity_checker = LiquidityChecker()
    return _liquidity_checker
