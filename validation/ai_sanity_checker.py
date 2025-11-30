"""
AI Sanity Checker - Validation Layer
Validates AI recommendations against real market data to catch hallucinations.
"""
from typing import Dict, Any, List, Optional
from loguru import logger


class AISanityChecker:
    """
    Validates AI-generated trade recommendations to catch:
    - Hallucinated strike prices ($500 for $50 stock)
    - Invalid strategy logic (short > long)
    - Unreasonable Greeks (delta 0.80)
    """
    
    def __init__(
        self,
        max_strike_deviation_pct: float = 20.0,
        delta_range: tuple = (0.10, 0.40),
        max_vega: float = 1.0,
        dte_range: tuple = (30, 60)
    ):
        """
        Initialize sanity checker
        
        Args:
            max_strike_deviation_pct: Max % strike can deviate from current price
            delta_range: Valid delta range (min, max)
            max_vega: Maximum vega exposure
            dte_range: Valid DTE range (min, max)
        """
        self.max_strike_deviation_pct = max_strike_deviation_pct
        self.delta_range = delta_range
        self.max_vega = max_vega
        self.dte_range = dte_range
    
    def validate_recommendation(
        self,
        recommendation: Dict[str, Any],
        options_data: List[Dict[str, Any]],
        current_price: float
    ) -> Dict[str, Any]:
        """
        Validate AI recommendation against real market data
        
        Args:
            recommendation: AI-generated recommendation
            options_data: Actual option chain data from IBKR
            current_price: Current stock price
            
        Returns:
            Dict with 'valid': bool and 'errors': List[str]
        """
        errors = []
        
        # Extract strikes from recommendation
        short_strike = recommendation.get('short_strike')
        long_strike = recommendation.get('long_strike')
        strategy = recommendation.get('strategy', 'UNKNOWN')
        
        # 1. Validate strike prices exist and are reasonable
        if short_strike:
            strike_errors = self.check_strike_validity(
                strike=short_strike,
                options_data=options_data,
                current_price=current_price,
                label="Short"
            )
            errors.extend(strike_errors)
        
        if long_strike:
            strike_errors = self.check_strike_validity(
                strike=long_strike,
                options_data=options_data,
                current_price=current_price,
                label="Long"
            )
            errors.extend(strike_errors)
        
        # 2. Validate strategy logic
        if short_strike and long_strike:
            logic_errors = self.check_strategy_logic(
                strategy=strategy,
                short_strike=short_strike,
                long_strike=long_strike,
                option_type=recommendation.get('option_type', 'CALL')
            )
            errors.extend(logic_errors)
        
        # 3. Validate Greeks (if provided)
        greeks = recommendation.get('greeks', {})
        if greeks:
            greeks_errors = self.check_greeks_sanity(greeks)
            errors.extend(greeks_errors)
        
        # 4. Validate expiration (if provided)
        dte = recommendation.get('dte')
        if dte:
            dte_errors = self.check_dte_validity(dte)
            errors.extend(dte_errors)
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            logger.error(
                f"❌ AI SANITY CHECK FAILED for {recommendation.get('symbol', 'UNKNOWN')}:\n"
                + "\n".join(f"   - {err}" for err in errors)
            )
        else:
            logger.info(f"✅ AI sanity check passed for {recommendation.get('symbol', 'UNKNOWN')}")
        
        return {
            'valid': is_valid,
            'errors': errors,
            'recommendation': recommendation
        }
    
    def check_strike_validity(
        self,
        strike: float,
        options_data: List[Dict[str, Any]],
        current_price: float,
        label: str = "Strike"
    ) -> List[str]:
        """
        Check if strike price is valid
        
        Args:
            strike: Proposed strike price
            options_data: Option chain from IBKR
            current_price: Current stock price
            label: Label for error messages
            
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # 1. Check if strike exists in option chain
        available_strikes = set(opt.get('strike') for opt in options_data if opt.get('strike'))
        
        if strike not in available_strikes:
            errors.append(
                f"{label} strike ${strike:.2f} NOT FOUND in option chain. "
                f"Available: {sorted(list(available_strikes)[:5])}..."
            )
        
        # 2. Check if strike is within reasonable range of current price
        deviation_pct = abs(strike - current_price) / current_price * 100
        
        if deviation_pct > self.max_strike_deviation_pct:
            errors.append(
                f"{label} strike ${strike:.2f} is {deviation_pct:.1f}% from current price "
                f"${current_price:.2f} (max {self.max_strike_deviation_pct}%)"
            )
        
        return errors
    
    def check_strategy_logic(
        self,
        strategy: str,
        short_strike: float,
        long_strike: float,
        option_type: str = 'CALL'
    ) -> List[str]:
        """
        Validate strategy logic (spread configuration)
        
        Args:
            strategy: Strategy type (CREDIT_SPREAD, DEBIT_SPREAD, etc.)
            short_strike: Short leg strike
            long_strike: Long leg strike
            option_type: CALL or PUT
            
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        if strategy == 'CREDIT_SPREAD':
            if option_type == 'CALL':
                # Call credit spread: short < long (sell lower, buy higher)
                if short_strike >= long_strike:
                    errors.append(
                        f"Invalid CALL credit spread: short strike ${short_strike} >= "
                        f"long strike ${long_strike}. Should be short < long."
                    )
            elif option_type == 'PUT':
                # Put credit spread: short > long (sell higher, buy lower)
                if short_strike <= long_strike:
                    errors.append(
                        f"Invalid PUT credit spread: short strike ${short_strike} <= "
                        f"long strike ${long_strike}. Should be short > long."
                    )
        
        elif strategy == 'DEBIT_SPREAD':
            if option_type == 'CALL':
                # Call debit spread: long < short (buy lower, sell higher)
                if long_strike >= short_strike:
                    errors.append(
                        f"Invalid CALL debit spread: long strike ${long_strike} >= "
                        f"short strike ${short_strike}. Should be long < short."
                    )
            elif option_type == 'PUT':
                # Put debit spread: long > short (buy higher, sell lower)
                if long_strike <= short_strike:
                    errors.append(
                        f"Invalid PUT debit spread: long strike ${long_strike} <= "
                        f"short strike ${short_strike}. Should be long > short."
                    )
        
        # Width validation (spread shouldn't be too narrow or too wide)
        width = abs(long_strike - short_strike)
        if width < 1.0:
            errors.append(f"Spread too narrow: ${width:.2f} (min $1.00)")
        
        return errors
    
    def check_greeks_sanity(self, greeks: Dict[str, float]) -> List[str]:
        """
        Validate Greeks are in reasonable ranges
        
        Args:
            greeks: Dict with delta, gamma, theta, vega, etc.
            
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # Delta validation (for short options, typically 0.10-0.40)
        delta = abs(greeks.get('delta', 0))
        if delta < self.delta_range[0] or delta > self.delta_range[1]:
            errors.append(
                f"Delta {delta:.2f} out of range "
                f"[{self.delta_range[0]}, {self.delta_range[1]}]"
            )
        
        # Vega validation (high vega = too much vol risk)
        vega = abs(greeks.get('vega', 0))
        if vega > self.max_vega:
            errors.append(f"Vega {vega:.2f} exceeds max {self.max_vega}")
        
        # Theta validation (for selling options, theta should be positive)
        theta = greeks.get('theta', 0)
        if theta < 0:
            errors.append(f"Theta {theta:.2f} is negative (should be positive for selling)")
        
        return errors
    
    def check_dte_validity(self, dte: int) -> List[str]:
        """
        Validate DTE (Days To Expiration) is in reasonable range
        
        Args:
            dte: Days to expiration
            
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        if dte < self.dte_range[0]:
            errors.append(f"DTE {dte} too short (min {self.dte_range[0]})")
        elif dte > self.dte_range[1]:
            errors.append(f"DTE {dte} too long (max {self.dte_range[1]})")
        
        return errors


# Singleton
_sanity_checker: Optional[AISanityChecker] = None


def get_sanity_checker(
    max_strike_deviation_pct: float = 20.0,
    delta_range: tuple = (0.10, 0.40),
    max_vega: float = 1.0
) -> AISanityChecker:
    """Get or create singleton sanity checker"""
    global _sanity_checker
    if _sanity_checker is None:
        _sanity_checker = AISanityChecker(
            max_strike_deviation_pct=max_strike_deviation_pct,
            delta_range=delta_range,
            max_vega=max_vega
        )
    return _sanity_checker
