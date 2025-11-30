"""
Enhanced VIX Monitor - Complete implementation with term structure
"""
from typing import Optional, Dict, Any
from loguru import logger
from datetime import datetime


class VIXMonitor:
    """Monitor VIX + term structure for comprehensive regime detection"""
    
    def __init__(self):
        self.current_vix = None
        self.current_vix3m = None
        self.vix_ratio = None
        self.term_structure = None
        self.last_update = None
    
    async def update(self, ibkr_connection=None) -> bool:
        """Update VIX spot and VIX3M"""
        try:
            if ibkr_connection:
                vix = await self._fetch_vix_from_ibkr(ibkr_connection)
                vix3m = await self._fetch_vix3m_from_ibkr(ibkr_connection)
                
                if vix:
                    self.current_vix = vix
                if vix3m:
                    self.current_vix3m = vix3m
            
            if self.current_vix and self.current_vix3m:
                self._calculate_term_structure()
            
            self.last_update = datetime.now()
            
            regime = self.get_current_regime()
            logger.info(
                f"VIX: Spot={self.current_vix:.2f}, 3M={self.current_vix3m:.2f}, "
                f"Ratio={self.vix_ratio:.3f}, Structure={self.term_structure}, "
                f"Regime={regime}"
            )
            
            return True
        except Exception as e:
            logger.error(f"VIX update error: {e}")
            return False
    
    def _calculate_term_structure(self):
        """Calculate VIX/VIX3M ratio and structure"""
        self.vix_ratio = self.current_vix / self.current_vix3m
        
        if self.vix_ratio > 1.0:
            self.term_structure = 'BACKWARDATION'
        else:
            self.term_structure = 'CONTANGO'
    
    async def _fetch_vix_from_ibkr(self, ibkr_connection) -> Optional[float]:
        """Fetch VIX spot from IBKR"""
        try:
            from ibkr.data_fetcher import get_data_fetcher
            fetcher = get_data_fetcher()
            vix = await fetcher.get_vix()
            return vix
        except Exception as e:
            logger.error(f"Error fetching VIX: {e}")
            return None
    
    async def _fetch_vix3m_from_ibkr(self, ibkr_connection) -> Optional[float]:
        """Fetch VIX3M from IBKR"""
        try:
            from ib_insync import Index
            ib = ibkr_connection.get_client()
            
            vix3m = Index('VIX3M', 'CBOE')
            await ib.qualifyContractsAsync(vix3m)
            
            ticker = ib.reqMktData(vix3m, '', False, False)
            await ib.sleep(1)
            
            value = ticker.last if ticker.last > 0 else ticker.close
            ib.cancelMktData(vix3m)
            
            return value
        except Exception as e:
            logger.debug(f"VIX3M fetch error: {e}")
            return None
    
    def get_current_regime(self) -> str:
        """Get enhanced market regime"""
        if not self.current_vix:
            return 'UNKNOWN'
        
        vix = self.current_vix
        ratio = self.vix_ratio or 0.95
        
        # EXTREME: High VIX + Backwardation
        if vix >= 40 and ratio > 1.1:
            return 'EXTREME_STRESS'
        
        # HIGH_VOL + Backwardation = Severe stress
        if vix >= 30:
            if ratio > 1.05:
                return 'HIGH_VOL_BACKWARDATION'
            return 'HIGH_VOL'
        
        # ELEVATED + Backwardation = Warning
        if vix >= 20:
            if ratio > 1.0:
                return 'ELEVATED_BACKWARDATION'
            return 'ELEVATED'
        
        # NORMAL
        if vix >= 15:
            return 'NORMAL'
        
        # LOW_VOL
        return 'LOW_VOL'
    
    def should_trade_short_vega(self) -> Dict[str, Any]:
        """
        Determine if short vega strategies are safe
        
        Returns:
            Dict with recommendation and reasoning
        """
        regime = self.get_current_regime()
        
        # NEVER trade short vega in backwardation
        if 'BACKWARDATION' in regime or 'EXTREME' in regime:
            return {
                'allowed': False,
                'reason': f'Market in {regime} - avoid short vega',
                'vix': self.current_vix,
                'ratio': self.vix_ratio,
                'structure': self.term_structure
            }
        
        # Caution in HIGH_VOL even with contango
        if regime == 'HIGH_VOL':
            return {
                'allowed': True,
                'caution': True,
                'reason': 'High VIX - use shorter DTE (<21 days)',
                'max_dte': 21
            }
        
        # Normal conditions - OK
        return {
            'allowed': True,
            'caution': False,
            'reason': f'Normal conditions ({regime})',
            'max_dte': 45
        }
    
    def get_recommended_dte(self) -> int:
        """Get recommended DTE based on term structure"""
        regime = self.get_current_regime()
        
        if 'BACKWARDATION' in regime or 'EXTREME' in regime:
            return 0  # Don't trade
        
        if regime == 'HIGH_VOL':
            return 21  # Short DTE only
        
        if regime == 'ELEVATED':
            return 30
        
        return 45  # Normal DTE


_vix_monitor: Optional[VIXMonitor] = None


def get_vix_monitor() -> VIXMonitor:
    """Get singleton VIX monitor"""
    global _vix_monitor
    if _vix_monitor is None:
        _vix_monitor = VIXMonitor()
    return _vix_monitor
