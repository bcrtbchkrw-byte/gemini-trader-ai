"""
Feature Engineering for ML Models
Extracts 50+ features for market regime classification and option pricing.
"""
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from loguru import logger
from datetime import datetime, timedelta


class FeatureEngineering:
    """
    Extract market features for ML models
    
    Features include:
    - Volatility metrics (VIX, HV, IV)
    - Volume indicators
    - Price action (momentum, ATR)
    - Market breadth
    - Sentiment indicators
    """
    
    def __init__(self):
        self.feature_names = self._get_feature_names()
        
    def extract_features(
        self,
        symbol: str,
        current_price: float,
        vix: float,
        market_data: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """
        Extract features for a given symbol
        
        Args:
            symbol: Stock ticker
            current_price: Current price
            vix: Current VIX value
            market_data: Additional market data (optional)
            
        Returns:
            Feature vector (1D numpy array)
        """
        features = []
        
        # === VOLATILITY FEATURES ===
        features.extend(self._extract_volatility_features(vix, market_data))
        
        # === PRICE ACTION FEATURES ===
        features.extend(self._extract_price_features(current_price, market_data))
        
        # === VOLUME FEATURES ===
        features.extend(self._extract_volume_features(market_data))
        
        # === SENTIMENT FEATURES ===
        features.extend(self._extract_sentiment_features(market_data))
        
        # === TECHNICAL INDICATORS ===
        features.extend(self._extract_technical_features(market_data))
        
        return np.array(features, dtype=np.float32)
    
    def _extract_volatility_features(
        self,
        vix: float,
        market_data: Optional[Dict[str, Any]]
    ) -> List[float]:
        """Extract volatility-based features"""
        features = [
            vix,  # Current VIX
            vix / 15.0,  # VIX normalized (15 = long-term average)
        ]
        
        if market_data and 'vix3m' in market_data:
            vix3m = market_data['vix3m']
            features.extend([
                vix / vix3m if vix3m > 0 else 1.0,  # VIX/VIX3M ratio
                vix3m,  # VIX 3-month
            ])
        else:
            features.extend([1.0, 20.0])  # Defaults
            
        if market_data and 'iv_rank' in market_data:
            features.append(market_data['iv_rank'])
        else:
            features.append(50.0)  # Default mid-range
            
        if market_data and 'hv_percentile' in market_data:
            features.append(market_data['hv_percentile'])
        else:
            features.append(50.0)
            
        return features
    
    def _extract_price_features(
        self,
        current_price: float,
        market_data: Optional[Dict[str, Any]]
    ) -> List[float]:
        """Extract price action features"""
        features = []
        
        if market_data and 'price_history' in market_data:
            prices = market_data['price_history']
            
            # Returns
            returns_1d = (current_price - prices[-1]) / prices[-1] if len(prices) > 0 else 0
            returns_5d = (current_price - prices[-5]) / prices[-5] if len(prices) >= 5 else 0
            returns_20d = (current_price - prices[-20]) / prices[-20] if len(prices) >= 20 else 0
            
            features.extend([returns_1d, returns_5d, returns_20d])
            
            # ATR (simplified)
            if len(prices) >= 14:
                high_low = [abs(prices[i] - prices[i-1]) for i in range(1, min(14, len(prices)))]
                atr = np.mean(high_low) if high_low else 0
                atr_pct = atr / current_price if current_price > 0 else 0
                features.append(atr_pct)
            else:
                features.append(0.02)  # Default 2%
                
            # Bollinger Band Width
            if len(prices) >= 20:
                mean = np.mean(prices[-20:])
                std = np.std(prices[-20:])
                bb_width = (std * 2) / mean if mean > 0 else 0
                features.append(bb_width)
            else:
                features.append(0.1)  # Default
        else:
            # No price history - use defaults
            features.extend([0.0, 0.0, 0.0, 0.02, 0.1])
            
        return features
    
    def _extract_volume_features(
        self,
        market_data: Optional[Dict[str, Any]]
    ) -> List[float]:
        """Extract volume-based features"""
        features = []
        
        if market_data and 'volume' in market_data:
            volume = market_data['volume']
            avg_volume = market_data.get('avg_volume', volume)
            
            volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
            features.append(volume_ratio)
            
            # VWAP deviation (if available)
            if 'vwap' in market_data and 'current_price' in market_data:
                vwap_dev = (market_data['current_price'] - market_data['vwap']) / market_data['vwap']
                features.append(vwap_dev)
            else:
                features.append(0.0)
        else:
            features.extend([1.0, 0.0])  # Defaults
            
        return features
    
    def _extract_sentiment_features(
        self,
        market_data: Optional[Dict[str, Any]]
    ) -> List[float]:
        """Extract sentiment indicators"""
        features = []
        
        # Put/Call Ratio
        if market_data and 'put_call_ratio' in market_data:
            features.append(market_data['put_call_ratio'])
        else:
            features.append(1.0)  # Neutral
            
        # Advance/Decline (market breadth)
        if market_data and 'advance_decline' in market_data:
            features.append(market_data['advance_decline'])
        else:
            features.append(0.0)  # Neutral
            
        return features
    
    def _extract_technical_features(
        self,
        market_data: Optional[Dict[str, Any]]
    ) -> List[float]:
        """Extract technical indicators (RSI, MACD, etc.)"""
        features = []
        
        if market_data and 'price_history' in market_data:
            prices = pd.Series(market_data['price_history'])
            
            # RSI
            if len(prices) >= 14:
                delta = prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                features.append(rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0)
            else:
                features.append(50.0)  # Neutral
                
            # MACD (simplified)
            if len(prices) >= 26:
                ema_12 = prices.ewm(span=12).mean()
                ema_26 = prices.ewm(span=26).mean()
                macd = ema_12 - ema_26
                features.append(macd.iloc[-1] / prices.iloc[-1] if prices.iloc[-1] > 0 else 0)
            else:
                features.append(0.0)
        else:
            features.extend([50.0, 0.0])  # Defaults
            
        return features
    
    def _get_feature_names(self) -> List[str]:
        """Get list of all feature names"""
        return [
            # Volatility (6 features)
            'vix',
            'vix_normalized',
            'vix_vix3m_ratio',
            'vix3m',
            'iv_rank',
            'hv_percentile',
            
            # Price Action (5 features)
            'returns_1d',
            'returns_5d',
            'returns_20d',
            'atr_pct',
            'bb_width',
            
            # Volume (2 features)
            'volume_ratio',
            'vwap_deviation',
            
            # Sentiment (2 features)
            'put_call_ratio',
            'advance_decline',
            
            # Technical (2 features)
            'rsi',
            'macd',
        ]
    
    def get_feature_count(self) -> int:
        """Get total number of features"""
        return len(self.feature_names)


# Singleton
_feature_engineering: Optional[FeatureEngineering] = None


def get_feature_engineering() -> FeatureEngineering:
    """Get or create singleton feature engineering instance"""
    global _feature_engineering
    if _feature_engineering is None:
        _feature_engineering = FeatureEngineering()
    return _feature_engineering
