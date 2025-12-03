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
    
    def extract_exit_features(
        self,
        position_data: Dict[str, Any],
        current_price: float,
        market_data: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """
        Extract features for exit decision ML model
        
        Args:
            position_data: Dict with position info (entry_credit, entry_date, etc.)
            current_price: Current spread/position price
            market_data: Current market conditions
            
        Returns:
            Feature vector for exit strategy model
        """
        features = []
        
        # === P/L FEATURES ===
        entry_credit = position_data.get('entry_credit', 1.0)
        max_risk = position_data.get('max_risk', entry_credit)
        
        # Current P/L
        current_pnl = (entry_credit - current_price) * position_data.get('contracts', 1) * 100
        pnl_ratio = current_pnl / (max_risk * 100) if max_risk > 0 else 0
        features.append(pnl_ratio)
        
        # === TIME FEATURES ===
        entry_date = position_data.get('entry_date')
        expiration = position_data.get('expiration')
        
        if isinstance(entry_date, str):
            from datetime import datetime
            entry_date = datetime.fromisoformat(entry_date)
        if isinstance(expiration, str):
            from datetime import datetime
            expiration = datetime.fromisoformat(expiration)
        
        now = datetime.now()
        days_in_trade = (now - entry_date).days if entry_date else 0
        dte = (expiration - now).days if expiration else 30
        
        total_duration = (expiration - entry_date).days if (entry_date and expiration) else 45
        time_ratio = days_in_trade / total_duration if total_duration > 0 else 0.5
        
        features.extend([days_in_trade, dte, time_ratio])
        
        # === VIX / VOLATILITY FEATURES ===
        vix_entry = position_data.get('vix_entry', 15.0)
        vix_current = market_data.get('vix', 15.0) if market_data else 15.0
        vix_change = vix_current - vix_entry
        
        features.extend([vix_current, vix_entry, vix_change])
        
        # === GREEKS EVOLUTION ===
        # Delta drift (how much delta has changed)
        delta_entry = position_data.get('delta_entry', 0.0)
        delta_current = market_data.get('delta_current', delta_entry) if market_data else delta_entry
        delta_drift = abs(delta_current - delta_entry)
        features.append(delta_drift)
        
        # Theta realization (actual vs expected)
        theta_expected = position_data.get('theta_entry', 0.0)
        theta_days = days_in_trade if days_in_trade > 0 else 1
        expected_theta_decay = theta_expected * theta_days
        
        actual_pnl_from_theta = current_pnl if expected_theta_decay != 0 else 0
        theta_realization = actual_pnl_from_theta / abs(expected_theta_decay) if abs(expected_theta_decay) > 0.01 else 1.0
        theta_realization = np.clip(theta_realization, 0, 3)  # Clamp extremes
        features.append(theta_realization)
        
        # === VOLATILITY TREND ===
        # Is IV rising or falling?
        iv_entry = position_data.get('iv_entry', 0.3)
        iv_current = market_data.get('iv_current', iv_entry) if market_data else iv_entry
        volatility_trend = iv_current - iv_entry
        features.append(volatility_trend)
        
        # === MARKET REGIME ===
        # Use RegimeClassifier if available
        regime_score = 2.0  # Default: NEUTRAL
        
        if market_data and 'regime' in market_data:
            regime_map = {
                'BULL_TRENDING': 0,
                'BEAR_TRENDING': 1,
                'HIGH_VOL_NEUTRAL': 2,
                'LOW_VOL_NEUTRAL': 3,
                'EXTREME_STRESS': 4
            }
            regime_score = regime_map.get(market_data['regime'], 2)
        
        features.append(regime_score)
        
        # === PROFIT VELOCITY ===
        # Rate of P/L change (useful for trailing decisions)
        highest_profit = position_data.get('highest_profit_seen', current_pnl)
        profit_velocity = (current_pnl - (highest_profit * 0.9)) / days_in_trade if days_in_trade > 0 else 0
        features.append(profit_velocity)
        
        return np.array(features, dtype=np.float32)
    
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
