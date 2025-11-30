"""
Advanced Options Strategies
Implementation of sophisticated multi-leg strategies.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class StrategyLeg:
    """Single option leg in a strategy"""
    action: str  # BUY or SELL
    strike: float
    option_type: str  # CALL or PUT
    quantity: int
    expiration: str


@dataclass
class StrategyDefinition:
    """Complete strategy definition"""
    name: str
    legs: List[StrategyLeg]
    max_profit: float
    max_loss: float
    breakeven_points: List[float]
    ideal_conditions: Dict[str, Any]


class AdvancedStrategies:
    """Builder for advanced options strategies"""
    
    @staticmethod
    def iron_condor(
        underlying_price: float,
        wing_width: float = 5.0,
        body_width: float = 10.0,
        expiration: str = "30DTE"
    ) -> StrategyDefinition:
        """
        Iron Condor: Sell OTM call spread + sell OTM put spread
        
        Best for: High IV, range-bound market, theta decay
        Max Profit: Net credit received
        Max Loss: Width of widest spread - credit
        
        Args:
            underlying_price: Current stock price
            wing_width: Width of each spread (e.g., 5 points)
            body_width: Distance from price to short strikes
            expiration: Expiration date
            
        Returns:
            Strategy definition
        """
        # Calculate strikes
        short_call = underlying_price + body_width
        long_call = short_call + wing_width
        short_put = underlying_price - body_width
        long_put = short_put - wing_width
        
        legs = [
            # Call spread (sell lower, buy higher)
            StrategyLeg("SELL", short_call, "CALL", 1, expiration),
            StrategyLeg("BUY", long_call, "CALL", 1, expiration),
            # Put spread (sell higher, buy lower)
            StrategyLeg("SELL", short_put, "PUT", 1, expiration),
            StrategyLeg("BUY", long_put, "PUT", 1, expiration),
        ]
        
        # Estimate P/L (simplified - real would use Greeks)
        estimated_credit = wing_width * 0.3  # Rough estimate
        max_profit = estimated_credit
        max_loss = wing_width - estimated_credit
        
        return StrategyDefinition(
            name="IRON_CONDOR",
            legs=legs,
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven_points=[short_put - estimated_credit, short_call + estimated_credit],
            ideal_conditions={
                "iv_rank": "high",
                "expected_move": "low",
                "market_outlook": "neutral",
                "theta_decay": "positive"
            }
        )
    
    @staticmethod
    def iron_butterfly(
        underlying_price: float,
        wing_width: float = 5.0,
        expiration: str = "30DTE"
    ) -> StrategyDefinition:
        """
        Iron Butterfly: ATM short straddle + OTM long strangle
        
        Best for: Very high IV, expect stock to stay near current price
        Higher credit than Iron Condor but narrower profit zone
        
        Args:
            underlying_price: Current stock price
            wing_width: Distance to protective wings
            expiration: Expiration date
            
        Returns:
            Strategy definition
        """
        atm_strike = round(underlying_price)
        upper_wing = atm_strike + wing_width
        lower_wing = atm_strike - wing_width
        
        legs = [
            # ATM short straddle
            StrategyLeg("SELL", atm_strike, "CALL", 1, expiration),
            StrategyLeg("SELL", atm_strike, "PUT", 1, expiration),
            # OTM long strangle (protection)
            StrategyLeg("BUY", upper_wing, "CALL", 1, expiration),
            StrategyLeg("BUY", lower_wing, "PUT", 1, expiration),
        ]
        
        estimated_credit = wing_width * 0.4
        max_profit = estimated_credit
        max_loss = wing_width - estimated_credit
        
        return StrategyDefinition(
            name="IRON_BUTTERFLY",
            legs=legs,
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven_points=[atm_strike - estimated_credit, atm_strike + estimated_credit],
            ideal_conditions={
                "iv_rank": "very_high",
                "expected_move": "minimal",
                "market_outlook": "pin_at_strike",
                "theta_decay": "maximum"
            }
        )
    
    @staticmethod
    def calendar_spread(
        underlying_price: float,
        strike: Optional[float] = None,
        near_expiration: str = "30DTE",
        far_expiration: str = "60DTE",
        option_type: str = "CALL"
    ) -> StrategyDefinition:
        """
        Calendar Spread (Time Spread): Sell near-term, buy far-term
        
        Best for: Profit from theta decay differential
        Near-term decays faster than far-term
        
        Args:
            underlying_price: Current stock price
            strike: Strike price (default: ATM)
            near_expiration: Near-term expiration
            far_expiration: Far-term expiration
            option_type: CALL or PUT
            
        Returns:
            Strategy definition
        """
        if strike is None:
            strike = round(underlying_price)
        
        legs = [
            StrategyLeg("SELL", strike, option_type, 1, near_expiration),
            StrategyLeg("BUY", strike, option_type, 1, far_expiration),
        ]
        
        # Calendar spreads profit from time decay differential
        estimated_cost = 2.0  # Net debit
        max_profit = 3.0  # When near-term expires worthless
        max_loss = estimated_cost
        
        return StrategyDefinition(
            name="CALENDAR_SPREAD",
            legs=legs,
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven_points=[strike],
            ideal_conditions={
                "iv_rank": "low_to_medium",
                "expected_move": "minimal",
                "market_outlook": "neutral",
                "volatility_outlook": "increasing"
            }
        )


class QuantStrategies:
    """Quantitative trading strategies inspired by Renaissance Technologies"""
    
    @staticmethod
    def mean_reversion_signals(
        price_history: List[float],
        lookback_period: int = 20,
        std_threshold: float = 2.0
    ) -> Dict[str, Any]:
        """
        Mean Reversion Strategy (Jim Simons style) + Technical Indicators
        
        Combines statistical mean reversion with RSI and Bollinger Bands
        for stronger confirmation signals.
        
        Args:
            price_history: Historical prices
            lookback_period: Period for calculating mean
            std_threshold: Standard deviations for signal
            
        Returns:
            Signal dict with entry/exit levels
        """
        import numpy as np
        
        if len(price_history) < lookback_period:
            return {"signal": "INSUFFICIENT_DATA"}
        
        recent_prices = price_history[-lookback_period:]
        mean_price = np.mean(recent_prices)
        std_price = np.std(recent_prices)
        current_price = price_history[-1]
        
        # Z-score (statistical signal)
        z_score = (current_price - mean_price) / std_price if std_price > 0 else 0
        
        # Try to get technical indicators for confirmation
        try:
            import pandas as pd
            import pandas_ta as ta
            
            df = pd.DataFrame({'close': price_history})
            
            # RSI for overbought/oversold confirmation
            rsi = ta.rsi(df['close'], length=14)
            current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
            
            # Bollinger Bands for volatility context
            bbands = ta.bbands(df['close'], length=20, std=2.0)
            if bbands is not None:
                bb_upper = float(bbands['BBU_20_2.0'].iloc[-1])
                bb_lower = float(bbands['BBL_20_2.0'].iloc[-1])
                bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) if bb_upper > bb_lower else 0.5
            else:
                bb_position = None
            
        except ImportError:
            current_rsi = None
            bb_position = None
        
        # Signal generation with technical confirmation
        signal = "NEUTRAL"
        entry_strategy = None
        confidence = 0.0
        
        if z_score > std_threshold:
            # Price too high - potential reversion down
            base_confidence = min(abs(z_score) / std_threshold, 1.0)
            
            # Confirm with RSI (overbought?)
            rsi_confirm = current_rsi > 70 if current_rsi else False
            bb_confirm = bb_position > 0.8 if bb_position else False
            
            if rsi_confirm or bb_confirm:
                signal = "SELL_REVERSION_CONFIRMED"
                confidence = min(base_confidence + 0.3, 1.0)
            else:
                signal = "SELL_REVERSION"
                confidence = base_confidence
            
            entry_strategy = "SELL_CALL_SPREAD"
            
        elif z_score < -std_threshold:
            # Price too low - potential reversion up
            base_confidence = min(abs(z_score) / std_threshold, 1.0)
            
            # Confirm with RSI (oversold?)
            rsi_confirm = current_rsi < 30 if current_rsi else False
            bb_confirm = bb_position < 0.2 if bb_position else False
            
            if rsi_confirm or bb_confirm:
                signal = "BUY_REVERSION_CONFIRMED"
                confidence = min(base_confidence + 0.3, 1.0)
            else:
                signal = "BUY_REVERSION"
                confidence = base_confidence
            
            entry_strategy = "SELL_PUT_SPREAD"
        
        result = {
            "signal": signal,
            "z_score": round(z_score, 2),
            "mean_price": round(mean_price, 2),
            "current_price": current_price,
            "std_dev": round(std_price, 2),
            "entry_strategy": entry_strategy,
            "confidence": round(confidence, 2)
        }
        
        # Add technical indicators if available
        if current_rsi is not None:
            result["rsi"] = round(current_rsi, 1)
            result["rsi_signal"] = "OVERBOUGHT" if current_rsi > 70 else "OVERSOLD" if current_rsi < 30 else "NEUTRAL"
        
        if bb_position is not None:
            result["bb_position"] = round(bb_position, 2)
            result["bb_signal"] = "UPPER" if bb_position > 0.8 else "LOWER" if bb_position < 0.2 else "MIDDLE"
        
        return result
    
    @staticmethod
    def theta_decay_optimizer(
        days_to_expiration: int,
        implied_volatility: float,
        strike_distance: float
    ) -> Dict[str, Any]:
        """
        Theta Decay Strategy: Optimize for maximum time decay
        
        Theta accelerates as expiration approaches, especially
        in final 30 days for ATM options.
        
        Args:
            days_to_expiration: DTE
            implied_volatility: IV as decimal
            strike_distance: How far OTM (as %)
            
        Returns:
            Optimization metrics
        """
        # Theta decay curve is non-linear
        # Maximum decay in 20-35 DTE range for far OTM
        # ATM options decay fastest in final 7-14 days
        
        if strike_distance < 0.05:  # ATM
            optimal_dte_range = (14, 21)
            decay_rating = "MAXIMUM" if 14 <= days_to_expiration <= 21 else "MODERATE"
        elif strike_distance < 0.15:  # Near OTM
            optimal_dte_range = (21, 35)
            decay_rating = "HIGH" if 21 <= days_to_expiration <= 35 else "MODERATE"
        else:  # Far OTM
            optimal_dte_range = (30, 45)
            decay_rating = "MODERATE" if 30 <= days_to_expiration <= 45 else "LOW"
        
        # IV affects theta - higher IV = higher theta
        iv_multiplier = 1 + (implied_volatility - 0.3)  # Baseline IV = 30%
        
        return {
            "optimal_dte_range": optimal_dte_range,
            "current_dte": days_to_expiration,
            "decay_rating": decay_rating,
            "iv_adjusted_theta": iv_multiplier,
            "recommendation": "ENTER" if decay_rating in ["HIGH", "MAXIMUM"] else "WAIT"
        }


# Strategies registry
STRATEGY_BUILDERS = {
    "IRON_CONDOR": AdvancedStrategies.iron_condor,
    "IRON_BUTTERFLY": AdvancedStrategies.iron_butterfly,
    "CALENDAR_SPREAD": AdvancedStrategies.calendar_spread,
}

QUANT_STRATEGIES = {
    "MEAN_REVERSION": QuantStrategies.mean_reversion_signals,
    "THETA_DECAY": QuantStrategies.theta_decay_optimizer,
}
