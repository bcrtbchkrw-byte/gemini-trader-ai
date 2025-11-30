"""
IV Rank Calculator - Real Implied Volatility Rank
Calculates actual IV percentile rank using historical data.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
from loguru import logger


class IVCalculator:
    """Calculate real IV rank from historical data"""
    
    def __init__(self, cache_ttl: int = 3600):
        self.cache = {}
        self.cache_ttl = cache_ttl  # 1 hour default
    
    def get_iv_rank(self, symbol: str, lookback_days: int = 252) -> Optional[float]:
        """
        Calculate IV rank (percentile over lookback period)
        
        Args:
            symbol: Stock ticker
            lookback_days: Lookback period (default 252 = 1 year)
            
        Returns:
            IV rank (0-100) or None
        """
        # Check cache
        cache_key = f"{symbol}_{lookback_days}"
        if cache_key in self.cache:
            cached_time, cached_value = self.cache[cache_key]
            if (datetime.now() - cached_time).seconds < self.cache_ttl:
                logger.debug(f"IV rank cache hit for {symbol}")
                return cached_value
        
        try:
            import yfinance as yf
            
            # Fetch historical data
            ticker = yf.Ticker(symbol)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)
            
            hist = ticker.history(start=start_date, end=end_date)
            
            if len(hist) < 20:
                logger.warning(f"Insufficient data for {symbol} IV rank")
                return None
            
            # Calculate historical volatility (annualized)
            returns = hist['Close'].pct_change().dropna()
            historical_vol = returns.rolling(window=20).std() * (252 ** 0.5) * 100
            
            if historical_vol.empty:
                return None
            
            current_hv = historical_vol.iloc[-1]
            
            # Calculate percentile rank
            iv_rank = (historical_vol < current_hv).sum() / len(historical_vol) * 100
            
            # Cache result
            self.cache[cache_key] = (datetime.now(), iv_rank)
            
            logger.info(f"{symbol} IV Rank: {iv_rank:.1f}% (Current HV: {current_hv:.1f}%)")
            
            return float(iv_rank)
            
        except Exception as e:
            logger.error(f"Error calculating IV rank for {symbol}: {e}")
            return None
    
    def get_iv_details(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed IV statistics
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Dict with IV stats or None
        """
        try:
            import yfinance as yf
            import numpy as np
            
            ticker = yf.Ticker(symbol)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=252)
            
            hist = ticker.history(start=start_date, end=end_date)
            
            if len(hist) < 20:
                return None
            
            # Calculate historical volatility
            returns = hist['Close'].pct_change().dropna()
            hv_series = returns.rolling(window=20).std() * (252 ** 0.5) * 100
            
            current_hv = hv_series.iloc[-1]
            
            return {
                'symbol': symbol,
                'current_hv': round(current_hv, 2),
                'hv_mean': round(hv_series.mean(), 2),
                'hv_std': round(hv_series.std(), 2),
                'hv_min': round(hv_series.min(), 2),
                'hv_max': round(hv_series.max(), 2),
                'iv_rank': round(self.get_iv_rank(symbol) or 0, 1),
                'high_iv': current_hv > hv_series.mean() + hv_series.std(),
                'low_iv': current_hv < hv_series.mean() - hv_series.std()
            }
            
        except Exception as e:
            logger.error(f"Error getting IV details for {symbol}: {e}")
            return None
    
    def clear_cache(self):
        """Clear IV rank cache"""
        self.cache = {}
        logger.info("IV rank cache cleared")


# Singleton instance
_iv_calculator: Optional[IVCalculator] = None


def get_iv_calculator() -> IVCalculator:
    """Get or create singleton IV calculator"""
    global _iv_calculator
    if _iv_calculator is None:
        _iv_calculator = IVCalculator()
    return _iv_calculator
