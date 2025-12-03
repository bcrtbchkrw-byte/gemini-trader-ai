"""
Max Pain Calculator
Calculates the Max Pain strike price for a given options chain.
"""
from typing import List, Dict, Any
from loguru import logger

class MaxPainCalculator:
    """
    Calculates Max Pain strike price.
    Max Pain is the strike price at which the maximum number of options expire worthless,
    causing the least amount of payout for option writers (and most pain for buyers).
    """
    
    def calculate_max_pain(self, chain_data: List[Dict[str, Any]]) -> float:
        """
        Calculate Max Pain strike from chain data
        
        Args:
            chain_data: List of dicts with keys:
                - strike: float
                - call_oi: int
                - put_oi: int
                
        Returns:
            Max Pain strike price
        """
        if not chain_data:
            return 0.0
            
        strikes = sorted(list(set(d['strike'] for d in chain_data)))
        if not strikes:
            return 0.0
            
        # Organize data by strike
        # {strike: {'call_oi': 100, 'put_oi': 50}}
        strike_data = {}
        for item in chain_data:
            s = item['strike']
            if s not in strike_data:
                strike_data[s] = {'call_oi': 0, 'put_oi': 0}
            
            strike_data[s]['call_oi'] += item.get('call_oi', 0)
            strike_data[s]['put_oi'] += item.get('put_oi', 0)
            
        # Calculate total cash value of options for each potential expiration price
        # We assume the expiration price will be one of the strikes
        min_pain = float('inf')
        max_pain_strike = 0.0
        
        for potential_price in strikes:
            total_pain = 0.0
            
            for k, data in strike_data.items():
                # Call Value: max(0, Price - Strike) * Call OI
                call_value = max(0, potential_price - k) * data['call_oi']
                
                # Put Value: max(0, Strike - Price) * Put OI
                put_value = max(0, k - potential_price) * data['put_oi']
                
                total_pain += (call_value + put_value)
                
            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = potential_price
                
        logger.info(f"Calculated Max Pain: ${max_pain_strike:.2f} (Total Value: ${min_pain:,.0f})")
        return max_pain_strike

# Singleton
_max_pain_calculator = None

def get_max_pain_calculator() -> MaxPainCalculator:
    global _max_pain_calculator
    if _max_pain_calculator is None:
        _max_pain_calculator = MaxPainCalculator()
    return _max_pain_calculator
