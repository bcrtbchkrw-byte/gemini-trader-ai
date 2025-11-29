"""
Credit Spread Strategies
Builders for credit spreads (Iron Condor, Vertical Credit Spreads).
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from loguru import logger
from config import get_config
from ibkr.data_fetcher import get_data_fetcher
from risk.greeks_validator import get_greeks_validator
from risk.position_sizer import get_position_sizer
from analysis.liquidity_checker import get_liquidity_checker


class CreditSpreadBuilder:
    """Build credit spread strategies"""
    
    def __init__(self):
        self.config = get_config()
        self.data_fetcher = get_data_fetcher()
        self.greeks_validator = get_greeks_validator()
        self.position_sizer = get_position_sizer()
        self.liquidity_checker = get_liquidity_checker()
    
    async def build_vertical_credit_spread(
        self,
        symbol: str,
        right: str,  # 'C' or 'P'
        current_price: float,
        min_dte: int = 30,
        max_dte: int = 45,
        spread_width: float = 5.0
    ) -> Optional[Dict[str, Any]]:
        """
        Build a vertical credit spread
        
        Args:
            symbol: Stock ticker
            right: 'C' for call, 'P' for put
            current_price: Current stock price
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration
            spread_width: Width of spread in dollars
            
        Returns:
            Dict with spread details or None if no valid spread found
        """
        try:
            logger.info(
                f"Building vertical {right} credit spread for {symbol} "
                f"(DTE: {min_dte}-{max_dte}, Width: ${spread_width})"
            )
            
            # Get options with appropriate Delta
            options = await self.data_fetcher.get_options_with_greeks(
                symbol=symbol,
                min_dte=min_dte,
                max_dte=max_dte,
                min_delta=self.config.greeks.credit_spread_min_delta,
                max_delta=self.config.greeks.credit_spread_max_delta
            )
            
            if not options:
                logger.warning(f"No suitable options found for {symbol}")
                return None
            
            # Find best combination
            best_spread = None
            best_score = 0
            
            for short_option in options:
                # Skip if wrong side
                if short_option['right'] != right:
                    continue
                
                # Validate Greeks for short leg
                validation = await self.greeks_validator.validate_credit_spread(short_option)
                if not validation['passed']:
                    logger.debug(
                        f"Skipping {short_option['strike']}{right}: "
                        f"Greeks validation failed - {', '.join(validation['issues'])}"
                    )
                    continue
                
                # Find long leg (further OTM)
                if right == 'C':
                    long_strike = short_option['strike'] + spread_width
                else:  # Put
                    long_strike = short_option['strike'] - spread_width
                
                # Find matching long option
                long_option = next(
                    (opt for opt in options 
                     if opt['strike'] == long_strike 
                     and opt['right'] == right
                     and opt['expiration'] == short_option['expiration']),
                    None
                )
                
                if not long_option:
                    continue
                
                # Check liquidity for both legs
                # Note: contract objects would need to be created here in production
                # For now, basic check on bid/ask
                if short_option['bid'] <= 0 or short_option['ask'] <= 0:
                    continue
                if long_option['bid'] <= 0 or long_option['ask'] <= 0:
                    continue
                
                # Calculate credit
                credit = (short_option['bid'] + short_option['ask']) / 2 - \
                        (long_option['bid'] + long_option['ask']) / 2
                
                if credit <= 0:
                    continue
                
                # Calculate position size
                sizing = self.position_sizer.calculate_max_contracts(
                    spread_width=spread_width,
                    credit_received=credit
                )
                
                if sizing['max_contracts'] < 1:
                    logger.debug(f"Position sizing rejected spread at {short_option['strike']}")
                    continue
                
                # Score this spread (higher credit = better)
                score = credit * sizing['max_contracts']
                
                if score > best_score:
                    best_score = score
                    best_spread = {
                        'symbol': symbol,
                        'type': f'vertical_{right.lower()}_credit',
                        'short_leg': short_option,
                        'long_leg': long_option,
                        'spread_width': spread_width,
                        'credit': credit,
                        'max_contracts': sizing['max_contracts'],
                        'max_profit': credit * sizing['max_contracts'] * 100,
                        'max_loss': (spread_width - credit) * sizing['max_contracts'] * 100,
                        'position_sizing': sizing
                    }
            
            if best_spread:
                logger.info(
                    f"✅ Found vertical {right} credit spread:\n"
                    f"  Short: {best_spread['short_leg']['strike']}\n"
                    f"  Long: {best_spread['long_leg']['strike']}\n"
                    f"  Credit: ${best_spread['credit']:.2f}\n"
                    f"  Max Contracts: {best_spread['max_contracts']}\n"
                    f"  Max Profit: ${best_spread['max_profit']:.2f}\n"
                    f"  Max Loss: ${best_spread['max_loss']:.2f}"
                )
                return best_spread
            else:
                logger.warning(f"No valid credit spread found for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error building vertical credit spread: {e}")
            return None
    
    async def build_iron_condor(
        self,
        symbol: str,
        current_price: float,
        min_dte: int = 30,
        max_dte: int = 45,
        spread_width: float = 5.0,
        wing_distance: float = 10.0
    ) -> Optional[Dict[str, Any]]:
        """
        Build an iron condor (OTM call spread + OTM put spread)
        
        Args:
            symbol: Stock ticker
            current_price: Current stock price
            min_dte: Min days to expiration
            max_dte: Max days to expiration
            spread_width: Width of each spread
            wing_distance: Distance from current price to short strikes
            
        Returns:
            Iron condor details or None
        """
        try:
            logger.info(
                f"Building Iron Condor for {symbol} @ ${current_price:.2f}\n"
                f"  DTE: {min_dte}-{max_dte}, Width: ${spread_width}, "
                f"Wing Distance: ${wing_distance}"
            )
            
            # Build call credit spread (above current price)
            call_spread = await self.build_vertical_credit_spread(
                symbol=symbol,
                right='C',
                current_price=current_price,
                min_dte=min_dte,
                max_dte=max_dte,
                spread_width=spread_width
            )
            
            # Build put credit spread (below current price)
            put_spread = await self.build_vertical_credit_spread(
                symbol=symbol,
                right='P',
                current_price=current_price,
                min_dte=min_dte,
                max_dte=max_dte,
                spread_width=spread_width
            )
            
            if not call_spread or not put_spread:
                logger.warning("Could not build both sides of iron condor")
                return None
            
            # Verify expirations match
            if call_spread['short_leg']['expiration'] != put_spread['short_leg']['expiration']:
                logger.warning("Expirations don't match between call and put spreads")
                return None
            
            # Calculate total credit and risk
            total_credit = call_spread['credit'] + put_spread['credit']
            
            # Use minimum of both spreads for position sizing
            max_contracts = min(
                call_spread['max_contracts'],
                put_spread['max_contracts']
            )
            
            max_profit = total_credit * max_contracts * 100
            max_loss = (spread_width - total_credit) * max_contracts * 100
            
            iron_condor = {
                'symbol': symbol,
                'type': 'iron_condor',
                'call_spread': call_spread,
                'put_spread': put_spread,
                'expiration': call_spread['short_leg']['expiration'],
                'total_credit': total_credit,
                'max_contracts': max_contracts,
                'max_profit': max_profit,
                'max_loss': max_loss,
                'strikes': {
                    'call_short': call_spread['short_leg']['strike'],
                    'call_long': call_spread['long_leg']['strike'],
                    'put_short': put_spread['short_leg']['strike'],
                    'put_long': put_spread['long_leg']['strike']
                }
            }
            
            logger.info(
                f"✅ Iron Condor built:\n"
                f"  Call: {iron_condor['strikes']['call_short']}/{iron_condor['strikes']['call_long']}\n"
                f"  Put: {iron_condor['strikes']['put_short']}/{iron_condor['strikes']['put_long']}\n"
                f"  Total Credit: ${total_credit:.2f}\n"
                f"  Max Contracts: {max_contracts}\n"
                f"  Max Profit: ${max_profit:.2f}\n"
                f"  Max Loss: ${max_loss:.2f}"
            )
            
            return iron_condor
            
        except Exception as e:
            logger.error(f"Error building iron condor: {e}")
            return None


# Singleton instance
_credit_spread_builder: Optional[CreditSpreadBuilder] = None


def get_credit_spread_builder() -> CreditSpreadBuilder:
    """Get or create singleton credit spread builder"""
    global _credit_spread_builder
    if _credit_spread_builder is None:
        _credit_spread_builder = CreditSpreadBuilder()
    return _credit_spread_builder
