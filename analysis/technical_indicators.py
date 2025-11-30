"""
Technical Analysis Indicators
Using pandas_ta for advanced market analysis.
"""
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from loguru import logger

try:
    import pandas_ta as ta
    PANDAS_TA_AVAILABLE = True
except ImportError:
    PANDAS_TA_AVAILABLE = False
    logger.warning("pandas_ta not installed - technical indicators unavailable")


class TechnicalIndicators:
    """Technical analysis indicators for market analysis"""
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """
        Calculate RSI (Relative Strength Index)
        
        Args:
            prices: Historical prices
            period: RSI period (default 14)
            
        Returns:
            Current RSI value (0-100)
        """
        if not PANDAS_TA_AVAILABLE or len(prices) < period + 1:
            return None
        
        df = pd.DataFrame({'close': prices})
        rsi = ta.rsi(df['close'], length=period)
        return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
    
    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Optional[Dict[str, float]]:
        """
        Calculate Bollinger Bands
        
        Args:
            prices: Historical prices
            period: Period for moving average
            std_dev: Standard deviations for bands
            
        Returns:
            Dict with upper, middle, lower bands and current position
        """
        if not PANDAS_TA_AVAILABLE or len(prices) < period:
            return None
        
        df = pd.DataFrame({'close': prices})
        bbands = ta.bbands(df['close'], length=period, std=std_dev)
        
        if bbands is None:
            return None
        
        current_price = prices[-1]
        upper = float(bbands[f'BBU_{period}_{std_dev}'].iloc[-1])
        middle = float(bbands[f'BBM_{period}_{std_dev}'].iloc[-1])
        lower = float(bbands[f'BBL_{period}_{std_dev}'].iloc[-1])
        
        # Calculate position within bands (0-1)
        band_width = upper - lower
        position = (current_price - lower) / band_width if band_width > 0 else 0.5
        
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower,
            'width': band_width,
            'position': position,  # 0 = at lower, 0.5 = at middle, 1 = at upper
            'signal': 'OVERSOLD' if position < 0.2 else 'OVERBOUGHT' if position > 0.8 else 'NEUTRAL'
        }
    
    @staticmethod
    def calculate_macd(
        prices: List[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Optional[Dict[str, float]]:
        """
        Calculate MACD (Moving Average Convergence Divergence)
        
        Args:
            prices: Historical prices
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period
            
        Returns:
            Dict with MACD line, signal line, and histogram
        """
        if not PANDAS_TA_AVAILABLE or len(prices) < slow + signal:
            return None
        
        df = pd.DataFrame({'close': prices})
        macd = ta.macd(df['close'], fast=fast, slow=slow, signal=signal)
        
        if macd is None:
            return None
        
        macd_line = float(macd[f'MACD_{fast}_{slow}_{signal}'].iloc[-1])
        signal_line = float(macd[f'MACDs_{fast}_{slow}_{signal}'].iloc[-1])
        histogram = float(macd[f'MACDh_{fast}_{slow}_{signal}'].iloc[-1])
        
        # Determine trend
        if macd_line > signal_line and histogram > 0:
            trend = 'BULLISH'
        elif macd_line < signal_line and histogram < 0:
            trend = 'BEARISH'
        else:
            trend = 'NEUTRAL'
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram,
            'trend': trend,
            'crossover': abs(macd_line - signal_line) < 0.1  # Recent crossover
        }
    
    @staticmethod
    def calculate_atr(
        high: List[float],
        low: List[float],
        close: List[float],
        period: int = 14
    ) -> Optional[float]:
        """
        Calculate ATR (Average True Range) for volatility
        
        Args:
            high: Historical highs
            low: Historical lows
            close: Historical closes
            period: ATR period
            
        Returns:
            Current ATR value
        """
        if not PANDAS_TA_AVAILABLE or len(close) < period + 1:
            return None
        
        df = pd.DataFrame({
            'high': high,
            'low': low,
            'close': close
        })
        
        atr = ta.atr(df['high'], df['low'], df['close'], length=period)
        return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else None
    
    @staticmethod
    def get_comprehensive_analysis(
        prices: List[float],
        high: Optional[List[float]] = None,
        low: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive technical analysis
        
        Args:
            prices: Historical close prices
            high: Historical highs (optional)
            low: Historical lows (optional)
            
        Returns:
            Dict with all indicators
        """
        if not PANDAS_TA_AVAILABLE:
            return {'error': 'pandas_ta not available'}
        
        analysis = {
            'rsi': TechnicalIndicators.calculate_rsi(prices),
            'bbands': TechnicalIndicators.calculate_bollinger_bands(prices),
            'macd': TechnicalIndicators.calculate_macd(prices),
        }
        
        # Add ATR if OHLC data available
        if high is not None and low is not None:
            analysis['atr'] = TechnicalIndicators.calculate_atr(high, low, prices)
        
        # Generate overall signal
        signals = []
        
        # RSI signals
        if analysis['rsi']:
            if analysis['rsi'] < 30:
                signals.append('RSI_OVERSOLD')
            elif analysis['rsi'] > 70:
                signals.append('RSI_OVERBOUGHT')
        
        # Bollinger Bands signals
        if analysis['bbands']:
            signals.append(f"BB_{analysis['bbands']['signal']}")
        
        # MACD signals
        if analysis['macd']:
            signals.append(f"MACD_{analysis['macd']['trend']}")
        
        analysis['signals'] = signals
        analysis['overall_signal'] = 'BULLISH' if 'MACD_BULLISH' in signals else \
                                    'BEARISH' if 'MACD_BEARISH' in signals else 'NEUTRAL'
        
        return analysis


# Singleton instance
_technical_indicators: Optional[TechnicalIndicators] = None


def get_technical_indicators() -> TechnicalIndicators:
    """Get or create singleton technical indicators instance"""
    global _technical_indicators
    if _technical_indicators is None:
        _technical_indicators = TechnicalIndicators()
    return _technical_indicators
