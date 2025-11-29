"""
Earnings Calendar Checker
Checks for upcoming earnings to avoid high-risk periods.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import requests
from loguru import logger
from config import get_config


class EarningsChecker:
    """Check for upcoming earnings announcements"""
    
    def __init__(self):
        self.config = get_config().safety
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def check_earnings_proximity(
        self,
        symbol: str,
        expiration_date: datetime
    ) -> Dict[str, Any]:
        """
        Check if there's an earnings announcement before expiration
        
        Args:
            symbol: Stock ticker
            expiration_date: Option expiration date
            
        Returns:
            Dict with earnings info and safety status
        """
        try:
            # Check cache first
            if symbol in self._cache:
                cached_data = self._cache[symbol]
                if cached_data['timestamp'] > datetime.now() - timedelta(hours=1):
                    return self._evaluate_safety(cached_data, expiration_date)
            
            # Fetch earnings date
            earnings_date = self._fetch_earnings_date(symbol)
            
            if earnings_date:
                self._cache[symbol] = {
                    'earnings_date': earnings_date,
                    'timestamp': datetime.now()
                }
                return self._evaluate_safety(self._cache[symbol], expiration_date)
            else:
                # No earnings data available - proceed with caution
                return {
                    'safe': True,
                    'earnings_date': None,
                    'days_to_earnings': None,
                    'warning': 'No earnings data available - proceed with caution'
                }
                
        except Exception as e:
            logger.error(f"Error checking earnings for {symbol}: {e}")
            return {
                'safe': False,
                'earnings_date': None,
                'days_to_earnings': None,
                'error': str(e)
            }
    
    def _fetch_earnings_date(self, symbol: str) -> Optional[datetime]:
        """
        Fetch next earnings date for symbol
        
        This is a simplified implementation. In production, you would use:
        - Yahoo Finance API
        - Alpha Vantage
        - Earnings Whispers API
        - IBKR's own earnings data
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Next earnings date or None
        """
        try:
            # Using Yahoo Finance as a free option
            # Note: This may require additional libraries like yfinance
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            calendar = ticker.calendar
            
            if calendar is not None and 'Earnings Date' in calendar:
                earnings_date_str = calendar['Earnings Date'][0]
                if isinstance(earnings_date_str, str):
                    earnings_date = datetime.strptime(earnings_date_str, '%Y-%m-%d')
                else:
                    earnings_date = earnings_date_str
                
                logger.info(f"Next earnings for {symbol}: {earnings_date.strftime('%Y-%m-%d')}")
                return earnings_date
            
            return None
            
        except ImportError:
            logger.warning("yfinance not installed. Install with: pip install yfinance")
            return None
        except Exception as e:
            logger.warning(f"Could not fetch earnings date for {symbol}: {e}")
            return None
    
    def _evaluate_safety(
        self,
        cached_data: Dict[str, Any],
        expiration_date: datetime
    ) -> Dict[str, Any]:
        """Evaluate if trade is safe based on earnings proximity"""
        earnings_date = cached_data['earnings_date']
        
        if not earnings_date:
            return {
                'safe': True,
                'earnings_date': None,
                'days_to_earnings': None,
                'warning': 'No earnings data'
            }
        
        now = datetime.now()
        hours_to_earnings = (earnings_date - now).total_seconds() / 3600
        days_to_earnings = hours_to_earnings / 24
        
        # Check if earnings is before expiration and within blackout window
        if earnings_date < expiration_date:
            if hours_to_earnings < self.config.earnings_blackout_hours:
                return {
                    'safe': False,
                    'earnings_date': earnings_date,
                    'days_to_earnings': days_to_earnings,
                    'reason': f'Earnings in {days_to_earnings:.1f} days (< {self.config.earnings_blackout_hours/24:.0f} day blackout)'
                }
        
        return {
            'safe': True,
            'earnings_date': earnings_date,
            'days_to_earnings': days_to_earnings,
            'message': f'Earnings in {days_to_earnings:.1f} days - Safe to trade'
        }
    
    def is_safe_for_credit_spread(
        self,
        symbol: str,
        expiration_date: datetime,
        short_strike: float,
        current_price: float,
        expected_move: Optional[float] = None
    ) -> bool:
        """
        Check if credit spread is safe considering earnings
        
        Args:
            symbol: Stock ticker
            expiration_date: Option expiration
            short_strike: Short strike price
            current_price: Current stock price
            expected_move: Expected move from options pricing
            
        Returns:
            bool: True if safe to trade
        """
        earnings_check = self.check_earnings_proximity(symbol, expiration_date)
        
        if not earnings_check['safe']:
            logger.warning(f"⚠️ Earnings risk for {symbol}: {earnings_check['reason']}")
            
            # If we have expected move data, we can allow OTM positions
            if expected_move:
                distance_to_short = abs(short_strike - current_price)
                if distance_to_short > expected_move:
                    logger.info(
                        f"✅ Short strike ${short_strike} is outside expected move "
                        f"({distance_to_short:.2f} > {expected_move:.2f}), allowing trade despite earnings"
                    )
                    return True
            
            return False
        
        return True


# Singleton instance
_earnings_checker: Optional[EarningsChecker] = None


def get_earnings_checker() -> EarningsChecker:
    """Get or create singleton earnings checker instance"""
    global _earnings_checker
    if _earnings_checker is None:
        _earnings_checker = EarningsChecker()
    return _earnings_checker
