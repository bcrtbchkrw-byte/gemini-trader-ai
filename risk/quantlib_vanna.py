"""
QuantLib Vanna Calculator
Calculates Vanna for American Options using QuantLib and numerical differentiation.
"""
import QuantLib as ql
from typing import Optional
from loguru import logger
import datetime

class QuantLibVannaCalculator:
    """
    Calculates Vanna for American Options using QuantLib.
    
    Since QuantLib doesn't provide analytical Vanna for American options,
    we use numerical differentiation of Delta:
    Vanna ≈ (Delta(σ + h) - Delta(σ - h)) / (2 * h)
    """
    
    def __init__(self):
        self.calendar = ql.UnitedStates(ql.UnitedStates.NYSE)
        self.day_counter = ql.Actual365Fixed()
        
    def calculate_vanna(
        self,
        S: float,
        K: float,
        T: float,
        sigma: float,
        r: float,
        option_type: str = 'call',
        div_yield: float = 0.0
    ) -> Optional[float]:
        """
        Calculate Vanna for American Option
        
        Args:
            S: Underlying price
            K: Strike price
            T: Time to expiration (years)
            sigma: Implied volatility (decimal)
            r: Risk-free rate (decimal)
            option_type: 'call' or 'put'
            div_yield: Dividend yield (decimal)
            
        Returns:
            Vanna value
        """
        try:
            if T <= 0 or sigma <= 0 or S <= 0:
                return None
                
            # Setup Date
            today = ql.Date.todaysDate()
            ql.Settings.instance().evaluationDate = today
            
            # Maturity Date
            # Convert T (years) to days
            days_to_exp = int(T * 365)
            maturity_date = today + days_to_exp
            
            # Option Type
            opt_type = ql.Option.Call if option_type.lower() == 'call' else ql.Option.Put
            
            # Payoff & Exercise
            payoff = ql.PlainVanillaPayoff(opt_type, K)
            exercise = ql.AmericanExercise(today, maturity_date)
            
            # Market Data Handles
            spot_handle = ql.QuoteHandle(ql.SimpleQuote(S))
            rate_handle = ql.YieldTermStructureHandle(
                ql.FlatForward(today, r, self.day_counter)
            )
            div_handle = ql.YieldTermStructureHandle(
                ql.FlatForward(today, div_yield, self.day_counter)
            )
            
            # Volatility Quote (we will modify this for numerical diff)
            vol_quote = ql.SimpleQuote(sigma)
            vol_handle = ql.BlackVolTermStructureHandle(
                ql.BlackConstantVol(today, self.calendar, ql.QuoteHandle(vol_quote), self.day_counter)
            )
            
            # BS Process
            process = ql.BlackScholesMertonProcess(
                spot_handle, div_handle, rate_handle, vol_handle
            )
            
            # Create Option
            option = ql.VanillaOption(payoff, exercise)
            
            # Pricing Engine - Binomial for American
            # Steps = 801 is a good balance for accuracy/speed
            steps = 801
            engine = ql.BinomialVanillaEngine(process, "crr", steps)
            option.setPricingEngine(engine)
            
            # Numerical Differentiation Parameters
            h = 0.001  # Volatility step (0.1%)
            
            # 1. Calculate Delta at sigma + h
            vol_quote.setValue(sigma + h)
            delta_plus = option.delta()
            
            # 2. Calculate Delta at sigma - h
            vol_quote.setValue(sigma - h)
            delta_minus = option.delta()
            
            # 3. Vanna = (Delta+ - Delta-) / (2h)
            vanna = (delta_plus - delta_minus) / (2 * h)
            
            logger.debug(
                f"QL Vanna: S={S:.2f}, K={K:.2f}, T={T:.3f}, σ={sigma:.2%}, "
                f"Δ+={delta_plus:.4f}, Δ-={delta_minus:.4f}, Vanna={vanna:.6f}"
            )
            
            return vanna
            
        except Exception as e:
            logger.error(f"Error calculating QuantLib Vanna: {e}")
            return None

# Singleton
_ql_vanna_calculator = None

def get_quantlib_vanna_calculator() -> QuantLibVannaCalculator:
    global _ql_vanna_calculator
    if _ql_vanna_calculator is None:
        _ql_vanna_calculator = QuantLibVannaCalculator()
    return _ql_vanna_calculator
