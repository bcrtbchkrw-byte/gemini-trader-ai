"""
Risk-Free Rate Fetcher - Dynamic Treasury Yield from IBKR
Fetches current US Treasury rates for accurate Black-Scholes calculations.
"""
from typing import Optional
from loguru import logger
from datetime import datetime, timedelta
import os


class RiskFreeRateFetcher:
    """Fetch current risk-free rate (US Treasury yield) from IBKR"""
    
    def __init__(self, ibkr_connection=None):
        self.ibkr = ibkr_connection
        self.cached_rate = None
        self.cache_timestamp = None
        self.cache_ttl = 3600  # 1 hour cache
        
        # Fallback from environment
        self.fallback_rate = float(os.getenv('RISK_FREE_RATE', '0.045'))
    
    async def get_risk_free_rate(self) -> float:
        """
        Get current risk-free rate
        
        Priority:
        1. Cache (if < 1 hour old)
        2. IBKR Treasury yield
        3. Environment variable (.env)
        4. Default (4.5%)
        
        Returns:
            Risk-free rate (e.g., 0.045 = 4.5%)
        """
        # Check cache
        if self._is_cache_valid():
            logger.debug(f"Using cached risk-free rate: {self.cached_rate:.4f}")
            return self.cached_rate
        
        # Try IBKR
        rate = await self._fetch_from_ibkr()
        
        if rate is not None:
            self._update_cache(rate)
            logger.info(f"✅ Risk-free rate from IBKR: {rate:.4f} ({rate*100:.2f}%)")
            return rate
        
        # Fallback to env/default
        logger.warning(
            f"Could not fetch rate from IBKR, using fallback: {self.fallback_rate:.4f}"
        )
        return self.fallback_rate
    
    async def _fetch_from_ibkr(self) -> Optional[float]:
        """
        Fetch US Treasury 3-month yield from IBKR
        
        Returns:
            Rate as decimal (e.g., 0.045 = 4.5%) or None if failed
        """
        if not self.ibkr:
            logger.debug("No IBKR connection for rate fetching")
            return None
        
        try:
            ib = self.ibkr.get_client()
            
            if not ib or not ib.isConnected():
                logger.debug("IBKR not connected for rate fetch")
                return None
            
            # Request US 3-Month Treasury Bill
            from ib_insync import Bond
            
            # US Treasury Bill contract
            # CUSIP for 3-month T-Bill (changes quarterly)
            # Using generic yield fetch
            tbill = Bond()
            tbill.secIdType = 'CUSIP'
            tbill.secId = '912796XD9'  # Example CUSIP (update quarterly)
            tbill.exchange = 'SMART'
            tbill.currency = 'USD'
            
            # Qualify contract
            contracts = await ib.qualifyContractsAsync(tbill)
            
            if not contracts:
                logger.debug("Could not qualify T-Bill contract")
                return self._fetch_alternative_rate()
            
            # Get market data
            ticker = ib.reqMktData(contracts[0], '', False, False)
            await ib.sleep(2)
            
            # Get yield
            # T-Bill yield is typically in ticker.last or custom field
            if ticker.last and ticker.last > 0:
                # Yield is typically in percentage, convert to decimal
                yield_pct = ticker.last
                rate = yield_pct / 100.0
                
                ib.cancelMktData(contracts[0])
                
                # Sanity check (0.5% to 10%)
                if 0.005 <= rate <= 0.10:
                    return rate
                else:
                    logger.warning(f"Rate {rate:.4f} outside expected range")
                    return None
            
            ib.cancelMktData(contracts[0])
            return None
            
        except Exception as e:
            logger.debug(f"Error fetching rate from IBKR: {e}")
            return self._fetch_alternative_rate()
    
    def _fetch_alternative_rate(self) -> Optional[float]:
        """
        Alternative: Fetch from public API
        
        Uses Treasury.gov or FRED API as backup
        """
        try:
            import requests
            
            # Try FRED API (Federal Reserve Economic Data)
            # Requires API key, not always available
            
            # For now, return None to use fallback
            logger.debug("Alternative rate fetch not implemented")
            return None
            
        except Exception as e:
            logger.debug(f"Alternative rate fetch failed: {e}")
            return None
    
    def _is_cache_valid(self) -> bool:
        """Check if cached rate is still valid"""
        if self.cached_rate is None or self.cache_timestamp is None:
            return False
        
        age = (datetime.now() - self.cache_timestamp).seconds
        return age < self.cache_ttl
    
    def _update_cache(self, rate: float):
        """Update rate cache"""
        self.cached_rate = rate
        self.cache_timestamp = datetime.now()
        logger.debug(f"Cached risk-free rate: {rate:.4f}")
    
    def set_manual_rate(self, rate: float):
        """
        Manually set risk-free rate
        
        Useful for testing or when IBKR unavailable
        
        Args:
            rate: Risk-free rate as decimal (e.g., 0.045)
        """
        if not 0.001 <= rate <= 0.15:
            logger.error(f"Invalid rate {rate:.4f}, must be 0.1%-15%")
            return
        
        self._update_cache(rate)
        logger.info(f"Manual risk-free rate set: {rate:.4f} ({rate*100:.2f}%)")


# Singleton
_rate_fetcher: Optional[RiskFreeRateFetcher] = None


def get_risk_free_rate_fetcher(ibkr_connection=None) -> RiskFreeRateFetcher:
    """Get or create risk-free rate fetcher"""
    global _rate_fetcher
    if _rate_fetcher is None:
        _rate_fetcher = RiskFreeRateFetcher(ibkr_connection)
    return _rate_fetcher


async def get_current_risk_free_rate(ibkr_connection=None) -> float:
    """
    Convenience function to get current rate
    
    Args:
        ibkr_connection: IBKR connection (optional)
        
    Returns:
        Current risk-free rate
    """
    fetcher = get_risk_free_rate_fetcher(ibkr_connection)
    return await fetcher.get_risk_free_rate()
