"""
VIX Monitor - Enhanced Market Regime Detection
Monitors VIX spot + term structure (VIX/VIX3M) for comprehensive regime analysis.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger
from config import get_config
from ibkr.data_fetcher import get_data_fetcher


class VIXMonitor:
    """
    Monitor VIX and term structure for market regime detection
    
    Term structure features:
    - VIX/VIX3M ratio
    - Contango vs Backwardation
    - Stress level classification
    """
    
    def __init__(self):
        self.config = get_config().vix_regimes # Keep this for now, might be replaced by new regime logic
        self.data_fetcher = get_data_fetcher()
        
        self.current_vix: Optional[float] = None
        self.current_vix3m: Optional[float] = None
        self.vix_ratio: Optional[float] = None  # VIX / VIX3M
        self.term_structure: Optional[str] = None  # 'CONTANGO' or 'BACKWARDATION'
        self._current_regime: Optional[str] = None # Renamed from _current_regime to match new structure
        self._last_update: Optional[datetime] = None # Renamed from _last_update to match new structure
        
        # Enhanced regime thresholds (example, adjust as needed)
        self.regimes = {
            'LOW_VOL': {'vix_max': 15, 'ratio_max': 0.95},
            'NORMAL': {'vix_max': 20, 'ratio_max': 1.0},
            'ELEVATED': {'vix_max': 30, 'ratio_max': 1.05},
            'HIGH_VOL': {'vix_max': 40, 'ratio_max': 1.1},
            'EXTREME': {'vix_min': 40, 'ratio_min': 1.1}
        }
    
    async def update(self) -> bool:
        """
        Fetch latest VIX value and update regime
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            vix_value = await self.data_fetcher.get_vix()
            vix3m_value = await self.data_fetcher.get_vix3m() # Assuming a new method for VIX3M
            
            if vix_value is None or vix3m_value is None:
                logger.warning("Failed to fetch VIX or VIX3M value")
                return False
            
            old_regime = self._current_regime
            self.current_vix = vix_value
            self.current_vix3m = vix3m_value
            
            self._calculate_term_structure() # Calculate ratio and term structure
            self._current_regime = self._determine_enhanced_regime() # Determine regime based on new logic
            self._last_update = datetime.now()
            
            # Log regime changes
            if old_regime and old_regime != self._current_regime:
                logger.warning(
                    f"⚠️ VIX REGIME CHANGE: {old_regime} → {self._current_regime} "
                    f"(VIX: {self.current_vix:.2f}, VIX3M: {self.current_vix3m:.2f}, Ratio: {self.vix_ratio:.3f})"
                )
            else:
                logger.info(
                    f"VIX Update: Spot={self.current_vix:.2f}, "
                    f"3M={self.current_vix3m:.2f}, "
                    f"Ratio={self.vix_ratio:.3f}, "
                    f"Structure={self.term_structure}, "
                    f"Regime={self._current_regime}"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating VIX: {e}")
            return False
    
    def get_current_vix(self) -> Optional[float]:
        """Get current VIX value"""
        return self._current_vix
    
    def get_current_regime(self) -> Optional[str]:
        """Get current market regime"""
        return self._current_regime
    
    def is_trading_allowed(self) -> bool:
        """
        Check if new credit positions are allowed based on VIX regime
        
        Returns:
            bool: True if trading allowed, False if in PANIC mode
        """
        if self._current_regime == "PANIC":
            logger.warning("🛑 TRADING BLOCKED: VIX in PANIC mode (>30)")
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
