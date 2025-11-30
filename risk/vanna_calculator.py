"""
Precise Vanna Calculator using Black-Scholes
Provides accurate second-order Greek calculation for risk management.
"""
from typing import Optional
import numpy as np
from scipy.stats import norm
from loguru import logger


class VannaCalculator:
    """Calculate Vanna using analytical Black-Scholes formula"""
    
    def __init__(self, risk_free_rate: float = 0.045):
        """
        Initialize Vanna calculator
        
        Args:
            risk_free_rate: Risk-free rate (default 4.5%)
        """
        self.risk_free_rate = risk_free_rate
    
    def calculate_vanna(
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
            
            # Calculate d1 and d2
            d1 = (np.log(S / K) + (self.risk_free_rate + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            # Black-Scholes Vanna formula
            # Vanna = -φ(d1) × d2 / (S × σ × √T)
            # Where φ is standard normal PDF
            
            phi_d1 = norm.pdf(d1)  # Standard normal PDF
            
            vanna = -(phi_d1 * d2) / (S * sigma * np.sqrt(T))
            
            # Vanna can also be expressed as:
            # Vanna = Vega/S × d2/(σ√T)
            
            logger.debug(
                f"Vanna: S={S:.2f}, K={K:.2f}, T={T:.3f}y, σ={sigma:.2%}, "
                f"d1={d1:.3f}, d2={d2:.3f}, Vanna={vanna:.6f}"
            )
            
            return vanna
            
        except Exception as e:
            logger.error(f"Error calculating Vanna: {e}")
            return None
    
    def calculate_vanna_from_vega(
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
            
            # Calculate d2
            d1 = (np.log(S / K) + (self.risk_free_rate + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            # Vanna from Vega
            vanna = (vega / S) * (d2 / (sigma * np.sqrt(T)))
            
            return vanna
            
        except Exception as e:
            logger.error(f"Error calculating Vanna from Vega: {e}")
            return None
    
    def calculate_vanna_numerical(
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
            
            # Calculate Delta at current IV
            delta_1 = self._calculate_delta(S, K, T, sigma, option_type)
            
            # Calculate Delta at IV + d_sigma
            delta_2 = self._calculate_delta(S, K, T, sigma + d_sigma, option_type)
            
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
    
    def _calculate_delta(
        self,
        S: float,
        K: float,
        T: float,
        sigma: float,
        option_type: str
    ) -> float:
        """Calculate Black-Scholes Delta"""
        d1 = (np.log(S / K) + (self.risk_free_rate + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        
        if option_type.lower() == 'call':
            return norm.cdf(d1)
        else:  # put
            return norm.cdf(d1) - 1


# Singleton
_vanna_calculator: Optional[VannaCalculator] = None


def get_vanna_calculator(risk_free_rate: float = 0.045) -> VannaCalculator:
    """Get or create singleton Vanna calculator"""
    global _vanna_calculator
    if _vanna_calculator is None:
        _vanna_calculator = VannaCalculator(risk_free_rate)
    return _vanna_calculator
