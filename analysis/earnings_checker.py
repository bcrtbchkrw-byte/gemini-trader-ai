"""
Earnings Calendar - Prevent trades near earnings
Checks earnings dates and blocks trades within blackout window.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger


class EarningsChecker:
    """Check earnings dates and enforce blackout periods"""
    
    def __init__(self, blackout_hours: int = 48):
        self.blackout_hours = blackout_hours
        self.cache = {}  # Cache earnings dates
    
    def get_next_earnings(self, symbol: str) -> Optional[datetime]:
        """
        Get next earnings date for symbol
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Next earnings datetime or None
        """
        # Check cache
        if symbol in self.cache:
            cached_time, earnings_date = self.cache[symbol]
            # Cache for 24 hours
            if (datetime.now() - cached_time).seconds < 86400:
                return earnings_date
        
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            calendar = ticker.calendar
            
            if calendar is None or calendar.empty:
                logger.debug(f"No earnings calendar for {symbol}")
                return None
            
            # yfinance returns earnings date in calendar
            if 'Earnings Date' in calendar.index:
                earnings_value = calendar.loc['Earnings Date']
                
                # Handle different return types
                if isinstance(earnings_value, pd.Series):
                    # Multiple earnings dates - take first
                    earnings_date_str = earnings_value.iloc[0]
                else:
                    earnings_date_str = earnings_value
                
                # Parse earnings date
                if pd.notna(earnings_date_str):
                    earnings_date = pd.to_datetime(earnings_date_str)
                    
                    # Cache result
                    self.cache[symbol] = (datetime.now(), earnings_date)
                    
                    logger.info(f"{symbol} next earnings: {earnings_date.strftime('%Y-%m-%d')}")
                    return earnings_date
            
            return None
            
        except Exception as e:
            logger.warning(f"Could not fetch earnings for {symbol}: {e}")
            return None
    
    def is_in_blackout(self, symbol: str) -> Dict[str, Any]:
        """
        Check if symbol is in earnings blackout period
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Dict with blackout status and details
        """
        try:
            earnings_date = self.get_next_earnings(symbol)
            
            if earnings_date is None:
                return {
                    'in_blackout': False,
                    'reason': 'NO_DATA',
                    'symbol': symbol
                }
            
            now = datetime.now()
            
            # Ensure earnings_date is timezone-naive for comparison
            if earnings_date.tzinfo is not None:
                earnings_date = earnings_date.replace(tzinfo=None)
            
            time_to_earnings = earnings_date - now
            hours_to_earnings = time_to_earnings.total_seconds() / 3600
            
            # Check if within blackout window
            if 0 < hours_to_earnings <= self.blackout_hours:
                return {
                    'in_blackout': True,
                    'reason': 'EARNINGS_TOO_CLOSE',
                    'symbol': symbol,
                    'earnings_date': earnings_date.strftime('%Y-%m-%d %H:%M'),
                    'hours_until': round(hours_to_earnings, 1),
                    'blackout_hours': self.blackout_hours
                }
            
            # Earnings already passed (< 24h ago)
            if -24 < hours_to_earnings <= 0:
                return {
                    'in_blackout': True,
                    'reason': 'EARNINGS_JUST_PASSED',
                    'symbol': symbol,
                    'earnings_date': earnings_date.strftime('%Y-%m-%d %H:%M'),
                    'hours_since': round(abs(hours_to_earnings), 1)
                }
            
            # Safe to trade
            return {
                'in_blackout': False,
                'reason': 'SAFE',
                'symbol': symbol,
                'earnings_date': earnings_date.strftime('%Y-%m-%d'),
                'hours_until': round(hours_to_earnings, 1) if hours_to_earnings > 0 else None
            }
            
        except Exception as e:
            logger.error(f"Error checking blackout for {symbol}: {e}")
            return {
                'in_blackout': False,
                'reason': 'ERROR',
                'error': str(e)
            }
    
    def check_batch(self, symbols: list) -> Dict[str, Dict[str, Any]]:
        """
        Check earnings blackout for multiple symbols
        
        Args:
            symbols: List of stock tickers
            
        Returns:
            Dict of symbol -> blackout status
        """
        results = {}
        
        for symbol in symbols:
            results[symbol] = self.is_in_blackout(symbol)
        
        # Log summary
        blocked = [s for s, r in results.items() if r['in_blackout']]
        if blocked:
            logger.warning(f"⚠️  {len(blocked)} symbols in earnings blackout: {', '.join(blocked)}")
        else:
            logger.info(f"✅ All {len(symbols)} symbols clear of earnings")
        
        return results
    
    def filter_safe_symbols(self, symbols: list) -> list:
        """
        Filter symbols to only those safe to trade
        
        Args:
            symbols: List of stock tickers
            
        Returns:
            List of symbols NOT in blackout
        """
        batch_results = self.check_batch(symbols)
        safe_symbols = [
            symbol for symbol, result in batch_results.items()
            if not result['in_blackout']
        ]
        
        logger.info(f"Filtered {len(symbols)} -> {len(safe_symbols)} safe symbols")
        
        return safe_symbols


# Singleton instance
_earnings_checker: Optional[EarningsChecker] = None


def get_earnings_checker(blackout_hours: int = 48) -> EarningsChecker:
    """Get or create singleton earnings checker"""
    global _earnings_checker
    if _earnings_checker is None:
        _earnings_checker = EarningsChecker(blackout_hours)
    return _earnings_checker
