"""
Vanna Calculator - Precise second-order Greek calculation
Uses Black-Scholes analytical formula with DYNAMIC risk-free rate.
"""
from typing import Optional
import numpy as np
from scipy.stats import norm
from loguru import logger


class VannaCalculator:
    """
    Calculate Vanna (∂²V/∂S∂σ) using Black-Scholes
    
    Vanna measures sensitivity of Delta to changes in volatility.
    Critical for stress testing options strategies.
    
    Now uses DYNAMIC risk-free rate from IBKR Treasury yields.
    """
    
    def __init__(self, risk_free_rate: Optional[float] = None, ibkr_connection=None):
        """
        Initialize Vanna calculator
        
        Args:
            risk_free_rate: Risk-free rate (e.g., 0.045 = 4.5%)
                           If None, will fetch dynamically from IBKR
            ibkr_connection: IBKR connection for fetching Treasury yields
        """
        self.ibkr_connection = ibkr_connection
        
        if risk_free_rate is not None:
            # User-provided rate (static)
            self.risk_free_rate = risk_free_rate
            self.use_dynamic_rate = False
            logger.debug(f"VannaCalculator: Using static rate {risk_free_rate:.4f}")
        else:
            # Will fetch dynamically from IBKR
            self.risk_free_rate = None  # Fetched on demand
            self.use_dynamic_rate = True
            logger.debug("VannaCalculator: Will fetch dynamic rate from IBKR")
    
    async def calculate_vanna(
        self,
        S: float,
        K: float,
        T: float,
        sigma: float,
        option_type: str = 'call'
    ) -> Optional[float]:
        """
        Calculate Vanna using Black-Scholes analytical formula
        
        Vanna = ∂²V/∂S∂σ = (Vega/S) × (d₂/(σ√T))
        
        Uses DYNAMIC risk-free rate from IBKR if not specified.
        
        Args:
            S: Underlying price
            K: Strike price
            T: Time to expiration (years)
            sigma: Implied volatility (decimal, e.g. 0.25 for 25%)
            option_type: 'call' or 'put' (Vanna is same for both)
            
        Returns:
            Vanna value
        """
        try:
            if T <= 0 or sigma <= 0 or S <= 0:
                return None
            
            # Get risk-free rate (dynamic if enabled)
            r = await self._get_risk_free_rate()
            
            # Calculate d1 and d2
            d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            # Black-Scholes Vanna formula
            # Vanna = -φ(d1) × d2 / (S × σ × √T)
            # Where φ is standard normal PDF
            
            phi_d1 = norm.pdf(d1)  # Standard normal PDF
            
            vanna = -(phi_d1 * d2) / (S * sigma * np.sqrt(T))
            
            logger.debug(
                f"Vanna: S={S:.2f}, K={K:.2f}, T={T:.3f}y, σ={sigma:.2%}, "
                f"d1={d1:.3f}, d2={d2:.3f}, Vanna={vanna:.6f}"
            )
            
            return vanna
            
        except Exception as e:
            logger.error(f"Error calculating Vanna: {e}")
            return None
    
    async def _get_risk_free_rate(self) -> float:
        """
        Get risk-free rate (dynamic or static)
        
        Returns:
            Risk-free rate as decimal (e.g., 0.045)
        """
        if not self.use_dynamic_rate:
            # Use static rate
            return self.risk_free_rate
        
        # Fetch dynamic rate from IBKR
        if self.risk_free_rate is None:  # Not cached yet
            from data.risk_free_rate_fetcher import get_current_risk_free_rate
            
            try:
                rate = await get_current_risk_free_rate(self.ibkr_connection)
                self.risk_free_rate = rate  # Cache for this instance
                logger.info(f"📊 VannaCalculator: Using dynamic rate {rate:.4f} ({rate*100:.2f}%)")
                return rate
            except Exception as e:
                logger.warning(f"Failed to fetch dynamic rate: {e}, using fallback 4.5%")
                return 0.045  # Fallback
        
        return self.risk_free_rate
    
    async def calculate_vanna_from_vega(
        self,
        vega: float,
        S: float,
        K: float,
        T: float,
        sigma: float
    ) -> Optional[float]:
        """
        Calculate Vanna from Vega using relationship
        
        Vanna = Vega/S × d₂/(σ√T)
        
        Args:
            vega: Option Vega
            S: Underlying price
            K: Strike price
            T: Time to expiration
            sigma: Implied volatility
            
        Returns:
            Vanna value
        """
        try:
            if T <= 0 or sigma <= 0 or S <= 0:
                return None
            
            # Get risk-free rate
            r = await self._get_risk_free_rate()
            
            # Calculate d2
            d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            # Vanna from Vega
            vanna = (vega / S) * (d2 / (sigma * np.sqrt(T)))
            
            return vanna
            
        except Exception as e:
            logger.error(f"Error calculating Vanna from Vega: {e}")
            return None
    
    async def calculate_vanna_numerical(
        self,
        S: float,
        K: float,
        T: float,
        sigma: float,
        option_type: str = 'call',
        d_sigma: float = 0.01
    ) -> Optional[float]:
        """
        Calculate Vanna using numerical finite difference
        
        Vanna ≈ [Delta(σ + Δσ) - Delta(σ)] / Δσ
        
        Args:
            S: Underlying price
            K: Strike price  
            T: Time to expiration
            sigma: Implied volatility
            option_type: 'call' or 'put'
            d_sigma: IV increment (default 1% = 0.01)
            
        Returns:
            Vanna value (numerical approximation)
        """
        try:
            if T <= 0 or sigma <= 0 or S <= 0:
                return None
            
            # Get risk-free rate
            r = await self._get_risk_free_rate()
            
            # Calculate Delta at current IV
            delta_1 = await self._calculate_delta(S, K, T, sigma, option_type, r)
            
            # Calculate Delta at IV + d_sigma
            delta_2 = await self._calculate_delta(S, K, T, sigma + d_sigma, option_type, r)
            
            # Vanna = ∂Delta/∂σ
            vanna = (delta_2 - delta_1) / d_sigma
            
            logger.debug(
                f"Vanna (numerical): Δ@σ={delta_1:.4f}, "
                f"Δ@σ+{d_sigma}={delta_2:.4f}, Vanna={vanna:.6f}"
            )
            
            return vanna
            
        except Exception as e:
            logger.error(f"Error calculating numerical Vanna: {e}")
            return None
    
    async def _calculate_delta(
        self,
        S: float,
        K: float,
        T: float,
        sigma: float,
        option_type: str,
        r: Optional[float] = None
    ) -> float:
        """Calculate Black-Scholes Delta"""
        if r is None:
            r = await self._get_risk_free_rate()
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        
        if option_type.lower() == 'call':
            return norm.cdf(d1)
        else:  # put
            return norm.cdf(d1) - 1


# Singleton
_vanna_calculator: Optional[VannaCalculator] = None


def get_vanna_calculator(risk_free_rate: Optional[float] = None, ibkr_connection=None) -> VannaCalculator:
    """
    Get or create singleton Vanna calculator
    
    Args:
        risk_free_rate: Static rate (optional). If None, uses dynamic IBKR rate.
        ibkr_connection: IBKR connection for fetching Treasury yields
        
    Returns:
        VannaCalculator instance
    """
    global _vanna_calculator
    if _vanna_calculator is None:
        _vanna_calculator = VannaCalculator(risk_free_rate, ibkr_connection)
    return _vanna_calculator
