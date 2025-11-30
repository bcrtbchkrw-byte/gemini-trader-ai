"""
Bid-Ask Spread Validation
Checks options liquidity before trading.
"""
from typing import Dict, Any, Optional
from loguru import logger


class SpreadValidator:
    """
    Validate bid-ask spread quality
    
    Wide spreads indicate:
    - Poor liquidity
    - Stale/bad data
    - Market maker issues
    """
    
    def __init__(
        self,
        max_spread_pct: float = 0.20,  # 20% default
        max_spread_dollars: float = 0.50,  # $0.50 default
        min_bid: float = 0.05  # Minimum bid to consider
    ):
        """
        Initialize spread validator
        
        Args:
            max_spread_pct: Max spread as % of mid price (0.20 = 20%)
            max_spread_dollars: Max absolute spread in dollars
            min_bid: Minimum bid price to consider valid
        """
        self.max_spread_pct = max_spread_pct
        self.max_spread_dollars = max_spread_dollars
        self.min_bid = min_bid
    
    def validate_option_spread(
        self,
        bid: float,
        ask: float,
        symbol: str = "",
        strike: float = 0
    ) -> Dict[str, Any]:
        """
        Validate bid-ask spread quality
        
        Args:
            bid: Bid price
            ask: Ask price
            symbol: Option symbol (for logging)
            strike: Strike price (for logging)
            
        Returns:
            Dict with validation result
        """
        # Check minimum bid
        if bid < self.min_bid:
            return {
                'valid': False,
                'reason': f'Bid too low ({bid:.2f} < {self.min_bid:.2f})',
                'bid': bid,
                'ask': ask,
                'action': 'SKIP'
            }
        
        # Check for invalid data
        if bid <= 0 or ask <= 0:
            return {
                'valid': False,
                'reason': f'Invalid prices (bid={bid:.2f}, ask={ask:.2f})',
                'bid': bid,
                'ask': ask,
                'action': 'SKIP'
            }
        
        # Check bid > ask (data error)
        if bid > ask:
            return {
                'valid': False,
                'reason': f'Bid > Ask ({bid:.2f} > {ask:.2f}) - data error',
                'bid': bid,
                'ask': ask,
                'action': 'SKIP'
            }
        
        # Calculate mid and spread
        mid = (bid + ask) / 2
        spread_dollars = ask - bid
        spread_pct = spread_dollars / mid if mid > 0 else float('inf')
        
        # Check percentage spread
        if spread_pct > self.max_spread_pct:
            return {
                'valid': False,
                'reason': f'Spread too wide ({spread_pct:.1%} > {self.max_spread_pct:.1%})',
                'bid': bid,
                'ask': ask,
                'mid': mid,
                'spread_pct': spread_pct,
                'spread_dollars': spread_dollars,
                'action': 'SKIP'
            }
        
        # Check absolute spread
        if spread_dollars > self.max_spread_dollars:
            return {
                'valid': False,
                'reason': f'Spread too wide (${spread_dollars:.2f} > ${self.max_spread_dollars:.2f})',
                'bid': bid,
                'ask': ask,
                'mid': mid,
                'spread_pct': spread_pct,
                'spread_dollars': spread_dollars,
                'action': 'SKIP'
            }
        
        # Valid spread
        logger.debug(
            f"Spread OK: {symbol} {strike} - "
            f"Bid={bid:.2f}, Ask={ask:.2f}, Mid={mid:.2f}, "
            f"Spread={spread_pct:.1%} (${spread_dollars:.2f})"
        )
        
        return {
            'valid': True,
            'reason': 'Spread acceptable',
            'bid': bid,
            'ask': ask,
            'mid': mid,
            'spread_pct': spread_pct,
            'spread_dollars': spread_dollars,
            'action': 'PROCEED'
        }
    
    def validate_options_chain(
        self,
        options: list,
        required_valid: int = 2
    ) -> Dict[str, Any]:
        """
        Validate multiple options from chain
        
        Args:
            options: List of option dicts with 'bid' and 'ask'
            required_valid: Minimum valid options needed
            
        Returns:
            Dict with validation result
        """
        valid_options = []
        invalid_options = []
        
        for opt in options:
            result = self.validate_option_spread(
                bid=opt.get('bid', 0),
                ask=opt.get('ask', 0),
                symbol=opt.get('symbol', ''),
                strike=opt.get('strike', 0)
            )
            
            if result['valid']:
                valid_options.append({
                    'option': opt,
                    'validation': result
                })
            else:
                invalid_options.append({
                    'option': opt,
                    'validation': result
                })
        
        sufficient = len(valid_options) >= required_valid
        
        return {
            'valid': sufficient,
            'valid_count': len(valid_options),
            'invalid_count': len(invalid_options),
            'required': required_valid,
            'valid_options': valid_options,
            'invalid_options': invalid_options
        }


# Singleton
_spread_validator: Optional['SpreadValidator'] = None


def get_spread_validator(
    max_spread_pct: float = 0.20,
    max_spread_dollars: float = 0.50
) -> SpreadValidator:
    """Get or create singleton spread validator"""
    global _spread_validator
    if _spread_validator is None:
        _spread_validator = SpreadValidator(
            max_spread_pct=max_spread_pct,
            max_spread_dollars=max_spread_dollars
        )
    return _spread_validator
