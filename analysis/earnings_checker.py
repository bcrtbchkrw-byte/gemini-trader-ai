"""
Earnings Calendar - Prevent trades near earnings
Uses IBKR fundamental data for reliable earnings dates.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger


class EarningsChecker:
    """Check earnings dates using IBKR fundamental data"""
    
    def __init__(self, blackout_hours: int = 48):
        self.blackout_hours = blackout_hours
        self.cache = {}  # Cache earnings dates
        self.data_fetcher = None  # Lazy init
    
    def _get_data_fetcher(self):
        """Lazy initialize IBKR data fetcher"""
        if self.data_fetcher is None:
            from ibkr.data_fetcher import get_data_fetcher
            self.data_fetcher = get_data_fetcher()
        return self.data_fetcher
    
    async def get_next_earnings(self, symbol: str) -> Optional[datetime]:
        """
        Get next earnings date from IBKR fundamental data
        
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
            fetcher = self._get_data_fetcher()
            
            # Use IBKR fundamental data (more reliable than yfinance)
            earnings_date = await fetcher.get_earnings_date(symbol)
            
            if earnings_date:
                # Cache result
                self.cache[symbol] = (datetime.now(), earnings_date)
                logger.info(f"{symbol} next earnings: {earnings_date.strftime('%Y-%m-%d')} (IBKR)")
                return earnings_date
            
            logger.debug(f"No earnings data for {symbol} from IBKR")
            return None
            
        except Exception as e:
            logger.warning(f"Could not fetch earnings for {symbol}: {e}")
            return None
    
    async def is_in_blackout(self, symbol: str) -> Dict[str, Any]:
        """
        Check if symbol is in earnings blackout period
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Dict with blackout status and details
        """
        try:
            earnings_date = await self.get_next_earnings(symbol)
            
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
    
    async def check_batch(self, symbols: list, delay_seconds: float = 2.0) -> Dict[str, Dict[str, Any]]:
        """
        Check earnings blackout for multiple symbols with rate limiting
        
        IBKR has strict limits on fundamental data:
        - ~60 requests per 10 minutes
        - Pacing violation error 162 if exceeded
        
        Args:
            symbols: List of stock tickers
            delay_seconds: Delay between requests (default 2s = 30 req/min, safe)
            
        Returns:
            Dict of symbol -> blackout status
        """
        import asyncio
        
        results = {}
        total = len(symbols)
        
        logger.info(f"Checking earnings for {total} symbols (throttled @ {delay_seconds}s delay)...")
        
        for i, symbol in enumerate(symbols, 1):
            # Add delay between requests to avoid pacing violations
            if i > 1:  # Skip delay on first request
                await asyncio.sleep(delay_seconds)
            
            logger.debug(f"[{i}/{total}] Checking {symbol}...")
            results[symbol] = await self.is_in_blackout(symbol)
        
        # Log summary
        blocked = [s for s, r in results.items() if r['in_blackout']]
        if blocked:
            logger.warning(f"⚠️  {len(blocked)} symbols in earnings blackout: {', '.join(blocked)}")
        else:
            logger.info(f"✅ All {len(symbols)} symbols clear of earnings")
        
        # Log rate info
        total_time = delay_seconds * (total - 1)
        logger.info(f"Batch complete: {total} symbols in {total_time:.1f}s (rate-limited)")
        
        return results
    
    async def filter_safe_symbols(self, symbols: list) -> list:
        """
        Filter symbols to only those safe to trade
        
        Args:
            symbols: List of stock tickers
            
        Returns:
            List of symbols NOT in blackout
        """
        batch_results = await self.check_batch(symbols)
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
