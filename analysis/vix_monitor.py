"""
VIX Monitor
Continuous VIX monitoring and regime classification.
"""
from typing import Optional
from datetime import datetime
from loguru import logger
from config import get_config
from ibkr.data_fetcher import get_data_fetcher


class VIXMonitor:
    """Monitor VIX and classify market regime"""
    
    def __init__(self):
        self.config = get_config().vix_regimes
        self.data_fetcher = get_data_fetcher()
        self._current_vix: Optional[float] = None
        self._current_regime: Optional[str] = None
        self._last_update: Optional[datetime] = None
    
    async def update(self) -> bool:
        """
        Fetch latest VIX value and update regime
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            vix_value = await self.data_fetcher.get_vix()
            
            if vix_value is None:
                logger.warning("Failed to fetch VIX value")
                return False
            
            old_regime = self._current_regime
            self._current_vix = vix_value
            self._current_regime = self.config.get_regime(vix_value)
            self._last_update = datetime.now()
            
            # Log regime changes
            if old_regime and old_regime != self._current_regime:
                logger.warning(
                    f"⚠️ VIX REGIME CHANGE: {old_regime} → {self._current_regime} (VIX: {vix_value:.2f})"
                )
            else:
                logger.info(f"VIX: {vix_value:.2f} | Regime: {self._current_regime}")
            
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
