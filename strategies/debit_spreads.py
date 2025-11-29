"""
Debit Spread Strategies
Builders for debit spreads (low VIX environment).
"""
from typing import Dict, Any, List, Optional
from loguru import logger
from config import get_config
from ibkr.data_fetcher import get_data_fetcher
from risk.greeks_validator import get_greeks_validator
from risk.position_sizer import get_position_sizer


class DebitSpreadBuilder:
    """Build debit spread strategies for low VIX environments"""
    
    def __init__(self):
        self.config = get_config()
        self.data_fetcher = get_data_fetcher()
        self.greeks_validator = get_greeks_validator()
        self.position_sizer = get_position_sizer()
    
    async def build_vertical_debit_spread(
        self,
        symbol: str,
        right: str,  # 'C' or 'P'
        current_price: float,
        min_dte: int = 30,
        max_dte: int = 45,
        spread_width: float = 5.0
    ) -> Optional[Dict[str, Any]]:
        """
        Build a vertical debit spread
        
        For debit spreads:
        - We BUY the closer-to-money option (higher Delta)
        - We SELL the further-from-money option (lower Delta)
        - We pay a debit (cost) upfront
        - Max profit = spread width - debit paid
        
        Args:
            symbol: Stock ticker
            right: 'C' for call, 'P' for put
            current_price: Current stock price
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration
            spread_width: Width of spread
            
        Returns:
            Debit spread details or None
        """
        try:
            logger.info(
                f"Building vertical {right} debit spread for {symbol} "
                f"(DTE: {min_dte}-{max_dte}, Width: ${spread_width})"
            )
            
            # Get ITM/ATM options (higher Delta for long leg)
            options = await self.data_fetcher.get_options_with_greeks(
                symbol=symbol,
                min_dte=min_dte,
                max_dte=max_dte,
                min_delta=self.config.greeks.debit_spread_min_delta,
                max_delta=self.config.greeks.debit_spread_max_delta
            )
            
            if not options:
                logger.warning(f"No suitable options found for {symbol}")
                return None
            
            best_spread = None
            best_score = 0
            
            for long_option in options:
                # Skip if wrong side
                if long_option['right'] != right:
                    continue
                
                # Validate Greeks for long leg
                validation = await self.greeks_validator.validate_debit_spread(long_option)
                if not validation['passed']:
                    logger.debug(
                        f"Skipping {long_option['strike']}{right}: "
                        f"Greeks validation failed"
                    )
                    continue
                
                # Find short leg (further OTM)
                if right == 'C':
                    short_strike = long_option['strike'] + spread_width
                else:  # Put
                    short_strike = long_option['strike'] - spread_width
                
                # Find matching short option
                short_option = next(
                    (opt for opt in options
                     if opt['strike'] == short_strike
                     and opt['right'] == right
                     and opt['expiration'] == long_option['expiration']),
                    None
                )
                
                if not short_option:
                    continue
                
                # Check prices available
                if long_option['ask'] <= 0 or short_option['bid'] <= 0:
                    continue
                
                # Calculate debit (cost)
                long_cost = (long_option['bid'] + long_option['ask']) / 2
                short_credit = (short_option['bid'] + short_option['ask']) / 2
                debit = long_cost - short_credit
                
                if debit <= 0 or debit >= spread_width:
                    continue
                
                # Calculate max profit
                max_profit_per_contract = (spread_width - debit) * 100
                
                # Calculate position size (debit spreads: risk = debit paid)
                sizing = self.position_sizer.calculate_max_contracts(
                    spread_width=spread_width,
                    credit_received=None  # It's a debit, not credit
                )
                
                if sizing['max_contracts'] < 1:
                    logger.debug(f"Position sizing rejected spread at {long_option['strike']}")
                    continue
                
                # Score (higher profit potential = better)
                score = max_profit_per_contract * sizing['max_contracts']
                
                if score > best_score:
                    best_score = score
                    best_spread = {
                        'symbol': symbol,
                        'type': f'vertical_{right.lower()}_debit',
                        'long_leg': long_option,
                        'short_leg': short_option,
                        'spread_width': spread_width,
                        'debit': debit,
                        'max_contracts': sizing['max_contracts'],
                        'max_profit': max_profit_per_contract * sizing['max_contracts'],
                        'max_loss': debit * sizing['max_contracts'] * 100,
                        'position_sizing': sizing
                    }
            
            if best_spread:
                logger.info(
                    f"✅ Found vertical {right} debit spread:\n"
                    f"  Long: {best_spread['long_leg']['strike']} (Buy)\n"
                    f"  Short: {best_spread['short_leg']['strike']} (Sell)\n"
                    f"  Debit: ${best_spread['debit']:.2f}\n"
                    f"  Max Contracts: {best_spread['max_contracts']}\n"
                    f"  Max Profit: ${best_spread['max_profit']:.2f}\n"
                    f"  Max Loss: ${best_spread['max_loss']:.2f}"
                )
                return best_spread
            else:
                logger.warning(f"No valid debit spread found for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error building vertical debit spread: {e}")
            return None


# Singleton instance
_debit_spread_builder: Optional[DebitSpreadBuilder] = None


def get_debit_spread_builder() -> DebitSpreadBuilder:
    """Get or create singleton debit spread builder"""
    global _debit_spread_builder
    if _debit_spread_builder is None:
        _debit_spread_builder = DebitSpreadBuilder()
    return _debit_spread_builder
