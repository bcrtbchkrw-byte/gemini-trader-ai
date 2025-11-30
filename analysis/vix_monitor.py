"""
VIX Monitor - Market Regime Detection with ML Integration
Monitors VIX and uses ML for regime classification with rule-based fallback.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger
from config import get_config
from ibkr.data_fetcher import get_data_fetcher


class VIXMonitor:
    """
    Monitor VIX and classify market regime
    
    🤖 ML-Enhanced: Uses XGBoost RegimeClassifier when available
    📊 Fallback: Uses simple VIX threshold rules
    """
    
    def __init__(self):
        self.current_vix: Optional[float] = None
        self.current_vix3m: Optional[float] = None
        self.vix_ratio: Optional[float] = None  # VIX / VIX3M
        self.term_structure: Optional[str] = None  # 'CONTANGO' or 'BACKWARDATION'
        self._current_regime: Optional[str] = None
        self._last_update: Optional[datetime] = None
        self.history = []
        
        # ML Integration
        self.use_ml = True  # Toggle ML vs rule-based
        self.ml_classifier = None
        self.feature_engineer = None
        
        # Try to load ML components
        try:
            from ml.regime_classifier import get_regime_classifier
            from ml.feature_engineering import get_feature_engineer
            
            self.ml_classifier = get_regime_classifier()
            self.feature_engineer = get_feature_engineer()
            
            logger.info("✅ VIXMonitor: ML components loaded")
        except Exception as e:
            logger.warning(f"⚠️ VIXMonitor: ML components unavailable - {e}")
            logger.info("   Using rule-based regime detection")
            self.use_ml = False
        
        # Enhanced regime thresholds (example, adjust as needed)
        self.regimes = {
            'LOW_VOL': {'vix_max': 15, 'ratio_max': 0.95},
            'NORMAL': {'vix_max': 20, 'ratio_max': 1.0},
            'ELEVATED': {'vix_max': 30, 'ratio_max': 1.05},
            'HIGH_VOL': {'vix_max': 40, 'ratio_max': 1.1},
            'EXTREME': {'vix_min': 40, 'ratio_min': 1.1}
        }
    
    async def update(self):
        """Fetch latest VIX value"""
        try:
            # Fetch VIX from yfinance
            import yfinance as yf
            vix_ticker = yf.Ticker("^VIX")
            vix_data = vix_ticker.history(period="5d")
            
            if not vix_data.empty:
                self.current_vix = vix_data['Close'].iloc[-1]
                self._last_update = datetime.now() # Changed from self.last_update to self._last_update
                self.history.append({
                    'timestamp': self._last_update, # Changed from self.last_update to self._last_update
                    'value': self.current_vix
                })
                logger.info(f"📊 VIX updated: {self.current_vix:.2f}")
            else:
                logger.warning("No VIX data available")
                
        except Exception as e:
            logger.error(f"Error updating VIX: {e}")


# Singleton
_vix_monitor: Optional[VIXMonitor] = None


def get_vix_monitor() -> VIXMonitor:
    """Get or create singleton VIX monitor"""
    global _vix_monitor
    if _vix_monitor is None:
        _vix_monitor = VIXMonitor()
    return _vix_monitor

    def _calculate_term_structure(self):
        """Calculates VIX ratio and term structure type."""
        if self.current_vix and self.current_vix3m and self.current_vix3m != 0:
            self.vix_ratio = self.current_vix / self.current_vix3m
            self.term_structure = 'CONTANGO' if self.vix_ratio < 1.0 else 'BACKWARDATION'
        else:
            self.vix_ratio = None
            self.term_structure = None

    def _determine_enhanced_regime(self) -> str:
        """
        Determines the market regime based on VIX spot and term structure,
        with an option to use ML prediction.
        """
        if self.current_vix is None or self.vix_ratio is None:
            return "UNKNOWN"

        # 🤖 TRY ML PREDICTION FIRST
        if self.use_ml:
            try:
                # Extract features from current market state
                # Assuming 'SPY' as a proxy for market features, adjust as needed
                features = self.feature_engineer.extract_features(
                    symbol='SPY',
                    lookback_days=30
                )
                
                if features is not None:
                    # Get ML prediction
                    ml_regime = self.ml_classifier.predict_regime(features)
                    
                    logger.info(
                        f"🤖 ML Regime Prediction: {ml_regime} "
                        f"(VIX: {self.current_vix:.2f}, Ratio: {self.vix_ratio:.3f})"
                    )
                    return ml_regime
                else:
                    logger.warning("ML features extraction failed - using rule-based fallback")
                    
            except Exception as e:
                logger.warning(f"ML prediction failed: {e} - using rule-based fallback")

        # 📊 FALLBACK: Rule-based regime (original logic, adapted for VIX/VIX3M)
        if self.current_vix >= self.regimes['EXTREME']['vix_min'] and \
           self.vix_ratio >= self.regimes['EXTREME']['ratio_min']:
            return "EXTREME"
        elif self.current_vix >= self.regimes['HIGH_VOL']['vix_max'] and \
             self.vix_ratio >= self.regimes['HIGH_VOL']['ratio_max']:
            return "HIGH_VOL"
        elif self.current_vix >= self.regimes['ELEVATED']['vix_max'] and \
             self.vix_ratio >= self.regimes['ELEVATED']['ratio_max']:
            return "ELEVATED"
        elif self.current_vix >= self.regimes['NORMAL']['vix_max'] and \
             self.vix_ratio >= self.regimes['NORMAL']['ratio_max']:
            return "NORMAL"
        elif self.current_vix <= self.regimes['LOW_VOL']['vix_max'] and \
             self.vix_ratio <= self.regimes['LOW_VOL']['ratio_max']:
            return "LOW_VOL"
        else:
            return "NORMAL" # Default or catch-all

    def get_current_vix(self) -> Optional[float]:
        """Get current VIX value"""
        return self.current_vix
    
    def get_current_regime(self) -> Optional[str]:
        """Get current market regime"""
        return self._current_regime
    
    def is_trading_allowed(self) -> bool:
        """
        Check if new credit positions are allowed based on VIX regime
        
        Returns:
            bool: True if trading allowed, False if in PANIC mode
        """
        # Assuming "EXTREME" or "HIGH_VOL" might be considered "PANIC" for trading restrictions
        if self._current_regime in ["EXTREME", "HIGH_VOL"]: # Adjusted from "PANIC"
            logger.warning(f"🛑 TRADING BLOCKED: VIX in {self._current_regime} mode")
            return False
        return True
    
    def get_preferred_strategies(self) -> list:
        """
        Get list of preferred strategies based on current VIX regime
        
        Returns:
            List of strategy names
        """
        if not self._current_regime:
            logger.warning("VIX regime not set, cannot determine strategies")
            return []
        
        strategy_map = {
            "PANIC": [],  # No new positions
            "HIGH_VOL": ["iron_condor", "vertical_credit_spread"],
            "NORMAL": ["iron_condor", "vertical_credit_spread"],
            "LOW_VOL": ["vertical_debit_spread", "calendar_spread"]
        }
        
        strategies = strategy_map.get(self._current_regime, [])
        logger.info(f"Preferred strategies for {self._current_regime}: {strategies}")
        return strategies
    
    def get_regime_description(self) -> str:
        """Get human-readable regime description"""
        if not self._current_regime or not self._current_vix:
            return "Unknown (VIX data not available)"
        
        descriptions = {
            "PANIC": f"🛑 PANIC MODE (VIX {self._current_vix:.2f} > 30) - HARD STOP on new credit positions",
            "HIGH_VOL": f"✅ HIGH VOLATILITY (VIX {self._current_vix:.2f}) - Ideal for Credit Spreads",
            "NORMAL": f"⚠️ NORMAL VOLATILITY (VIX {self._current_vix:.2f}) - Selective Credit Spreads",
            "LOW_VOL": f"💤 LOW VOLATILITY (VIX {self._current_vix:.2f}) - Prefer Debit/Calendar Spreads"
        }
        
        return descriptions.get(self._current_regime, f"VIX {self._current_vix:.2f}")


# Singleton instance
_vix_monitor: Optional[VIXMonitor] = None


def get_vix_monitor() -> VIXMonitor:
    """Get or create singleton VIX monitor instance"""
    global _vix_monitor
    if _vix_monitor is None:
        _vix_monitor = VIXMonitor()
    return _vix_monitor
