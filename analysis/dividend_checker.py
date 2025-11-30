"""
Dividend Risk Checker
Prevents early assignment risk on short call positions before ex-dividend dates.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
import asyncio


class DividendChecker:
    """
    Check for upcoming dividends and enforce blackout windows.
    
    Prevents trading short calls when ex-dividend date is within blackout window.
    This protects against early assignment and unexpected short stock positions.
    """
    
    def __init__(self, blackout_days: int = 5, auto_exit_enabled: bool = True):
        """
        Initialize dividend checker
        
        Args:
            blackout_days: Days before ex-div to start blackout
            auto_exit_enabled: Whether to auto-exit positions before ex-div
        """
        self.blackout_days = blackout_days
        self.auto_exit_enabled = auto_exit_enabled
        self._dividend_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_expiry: Dict[str, datetime] = {}
    
    async def get_next_dividend(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get next dividend information for symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with ex_date, amount, etc. or None if no dividend
        """
        # Check cache first (expires after 1 day)
        if symbol in self._dividend_cache:
            if symbol in self._cache_expiry and datetime.now() < self._cache_expiry[symbol]:
                return self._dividend_cache[symbol]
        
        try:
            # Use yfinance for dividend data
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            
            # Get dividend history
            dividends = ticker.dividends
            
            if dividends.empty:
                logger.debug(f"No dividend history for {symbol}")
                self._dividend_cache[symbol] = None
                self._cache_expiry[symbol] = datetime.now() + timedelta(days=1)
                return None
            
            # Get calendar (includes upcoming ex-dividend if available)
            calendar = ticker.calendar
            
            if calendar and 'Ex-Dividend Date' in calendar:
                ex_date_str = calendar['Ex-Dividend Date']
                
                # Parse ex-dividend date
                if isinstance(ex_date_str, str):
                    ex_date = datetime.strptime(ex_date_str, '%Y-%m-%d')
                elif hasattr(ex_date_str, 'to_pydatetime'):
                    # pandas Timestamp
                    ex_date = ex_date_str.to_pydatetime()
                else:
                    # datetime.date -> convert to datetime
                    ex_date = datetime.combine(ex_date_str, datetime.min.time())
                
                # Only return if in future
                if ex_date.date() > datetime.now().date():
                    # Get last dividend amount as estimate
                    last_dividend = dividends.iloc[-1]
                    
                    dividend_info = {
                        'ex_date': ex_date,
                        'amount': float(last_dividend),
                        'days_until': (ex_date.date() - datetime.now().date()).days
                    }
                    
                    # Cache result
                    self._dividend_cache[symbol] = dividend_info
                    self._cache_expiry[symbol] = datetime.now() + timedelta(days=1)
                    
                    logger.debug(
                        f"Dividend found for {symbol}: "
                        f"${dividend_info['amount']:.2f} on {ex_date.date()}"
                    )
                    
                    return dividend_info
            
            # No upcoming dividend found
            self._dividend_cache[symbol] = None
            self._cache_expiry[symbol] = datetime.now() + timedelta(days=1)
            return None
            
        except Exception as e:
            logger.warning(f"Error fetching dividend for {symbol}: {e}")
            return None
    
    async def check_dividend_risk(self, symbol: str) -> Dict[str, Any]:
        """
        Check if symbol has dividend risk in blackout window
        
        Args:
            symbol: Stock symbol
            
        Returns:
            {
                'has_dividend': bool,
                'ex_date': datetime or None,
                'days_until': int or None,
                'dividend_amount': float or None,
                'in_blackout': bool
            }
        """
        dividend_info = await self.get_next_dividend(symbol)
        
        if not dividend_info:
            return {
                'has_dividend': False,
                'ex_date': None,
                'days_until': None,
                'dividend_amount': None,
                'in_blackout': False
            }
        
        days_until = dividend_info['days_until']
        in_blackout = days_until <= self.blackout_days
        
        return {
            'has_dividend': True,
            'ex_date': dividend_info['ex_date'],
            'days_until': days_until,
            'dividend_amount': dividend_info['amount'],
            'in_blackout': in_blackout
        }
    
    async def should_avoid_symbol(self, symbol: str, strategy: str) -> bool:
        """
        Determine if symbol should be avoided due to dividend risk
        
        Only applies to strategies with SHORT CALLS:
        - Credit spreads (call side)
        - Iron condors (call side)
        - Covered calls
        - Short calls
        
        PUT-only strategies are SAFE!
        
        Args:
            symbol: Stock symbol
            strategy: Strategy type
            
        Returns:
            True if should avoid (in blackout with short calls)
        """
        # Check if strategy involves short calls
        strategy_upper = strategy.upper()
        has_short_call = any(keyword in strategy_upper for keyword in [
            'CALL',
            'CONDOR',
            'IRON',
            'COVERED'
        ])
        
        # PUT-only strategies are safe
        if 'PUT' in strategy_upper and 'CALL' not in strategy_upper:
            has_short_call = False
        
        if not has_short_call:
            logger.debug(f"{symbol}: No short call risk in {strategy}")
            return False
        
        # Check dividend
        risk_info = await self.check_dividend_risk(symbol)
        
        if risk_info['in_blackout']:
            logger.warning(
                f"⚠️ DIVIDEND BLACKOUT: {symbol}\n"
                f"   Strategy: {strategy}\n"
                f"   Ex-Date: {risk_info['ex_date'].date()}\n"
                f"   Days Until: {risk_info['days_until']}\n"
                f"   Dividend: ${risk_info['dividend_amount']:.2f}\n"
                f"   🚫 SHORT CALLS NOT ALLOWED"
            )
            return True
        
        return False
    
    async def batch_check_symbols(self, symbols: list, strategy: str) -> list:
        """
        Check multiple symbols for dividend risk
        
        Args:
            symbols: List of symbols to check
            strategy: Strategy type
            
        Returns:
            List of symbols that passed dividend check
        """
        tasks = [self.should_avoid_symbol(sym, strategy) for sym in symbols]
        results = await asyncio.gather(*tasks)
        
        # Filter out symbols in blackout
        safe_symbols = [
            sym for sym, should_avoid in zip(symbols, results)
            if not should_avoid
        ]
        
        filtered_count = len(symbols) - len(safe_symbols)
        if filtered_count > 0:
            logger.info(f"🗑️ Filtered {filtered_count} symbols due to dividend blackout")
        
        return safe_symbols


# Singleton
_dividend_checker: Optional[DividendChecker] = None


def get_dividend_checker(
    blackout_days: int = 5,
    auto_exit_enabled: bool = True
) -> DividendChecker:
    """Get or create singleton dividend checker"""
    global _dividend_checker
    if _dividend_checker is None:
        _dividend_checker = DividendChecker(blackout_days, auto_exit_enabled)
    return _dividend_checker
