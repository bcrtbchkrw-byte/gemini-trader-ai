"""
Position Sizer
Calculates appropriate position sizes based on account risk limits.
"""
from typing import Dict, Any, Optional
from loguru import logger
from config import get_config


class PositionSizer:
    """Calculate position sizes within risk limits"""
    
    def __init__(self):
        self.config = get_config().trading
    
    def calculate_max_contracts(
        self,
        spread_width: float,
        credit_received: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate maximum number of contracts for a spread
        
        Args:
            spread_width: Width of the spread in dollars (e.g., $5 for 100/105 spread)
            credit_received: Credit received per contract (for credit spreads)
            
        Returns:
            Dict with position sizing information
        """
        try:
            # Max risk per contract
            if credit_received:
                # Credit spread: risk = width - credit
                risk_per_contract = (spread_width - credit_received) * 100  # x100 for contract multiplier
            else:
                # Debit spread: risk = debit paid (assumed to be spread_width for now)
                                risk_per_contract = spread_width * 100
            
            # Calculate max contracts based on max risk per trade
            if risk_per_contract > 0:
                max_contracts_by_risk = int(self.config.max_risk_per_trade / risk_per_contract)
            else:
                max_contracts_by_risk = 0
            
            # Calculate max contracts based on max position size (25% allocation)
            max_position_value = self.config.max_position_size
            if spread_width > 0:
                max_contracts_by_allocation = int(max_position_value / (spread_width * 100))
            else:
                max_contracts_by_allocation = 0
            
            # Take the minimum of both limits
            max_contracts = min(max_contracts_by_risk, max_contracts_by_allocation)
            
            # Ensure at least 1 contract if risk allows
            if max_contracts < 1 and risk_per_contract <= self.config.max_risk_per_trade:
                max_contracts = 1
                logger.warning(
                    f"⚠️ Risk ${risk_per_contract:.2f} is high but within limit. "
                    f"Allowing 1 contract."
                )
            
            total_risk = max_contracts * risk_per_contract
            total_capital_used = max_contracts * spread_width * 100
            
            result = {
                'max_contracts': max_contracts,
                'risk_per_contract': risk_per_contract,
                'total_risk': total_risk,
                'total_capital_used': total_capital_used,
                'percent_of_account': (total_capital_used / self.config.account_size) * 100,
                'within_limits': total_risk <= self.config.max_risk_per_trade
            }
            
            logger.info(
                f"Position sizing: {max_contracts} contracts, "
                f"Risk: ${total_risk:.2f} "
                f"({result['percent_of_account']:.1f}% of account)"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return {
                'max_contracts': 0,
                'risk_per_contract': 0,
                'total_risk': 0,
                'total_capital_used': 0,
                'percent_of_account': 0,
                'within_limits': False,
                'error': str(e)
            }
    
    def validate_position_size(
        self,
        num_contracts: int,
        spread_width: float,
        credit_received: Optional[float] = None
    ) -> bool:
        """
        Validate if a specific position size is within risk limits
        
        Args:
            num_contracts: Number of contracts to trade
            spread_width: Width of the spread
            credit_received: Credit received per contract
            
        Returns:
            bool: True if position size is valid
        """
        sizing = self.calculate_max_contracts(spread_width, credit_received)
        
        if num_contracts <= sizing['max_contracts']:
            logger.info(f"✅ Position size validated: {num_contracts} contracts within limits")
            return True
        else:
            logger.warning(
                f"❌ Position size too large: {num_contracts} contracts exceeds "
                f"max of {sizing['max_contracts']}"
            )
            return False
    
    def calculate_profit_targets(
        self,
        num_contracts: int,
        credit_received: float,
        spread_width: float
    ) -> Dict[str, float]:
        """
        Calculate profit and loss targets
        
        Args:
            num_contracts: Number of contracts
            credit_received: Credit received per contract
            spread_width: Width of spread
            
        Returns:
            Dict with profit/loss targets
        """
        try:
            max_profit = credit_received * num_contracts * 100
            max_loss = (spread_width - credit_received) * num_contracts * 100
            
            # Take profit at 50%
            take_profit_price = credit_received * 0.5
            take_profit_amount = max_profit * 0.5
            
            # Stop loss at 2.5x credit
            stop_loss_price = credit_received * 2.5
            stop_loss_amount = (stop_loss_price - credit_received) * num_contracts * 100
            
            result = {
                'max_profit': max_profit,
                'max_loss': max_loss,
                'take_profit_price': take_profit_price,
                'take_profit_amount': take_profit_amount,
                'stop_loss_price': stop_loss_price,
                'stop_loss_amount': stop_loss_amount,
                'risk_reward_ratio': max_profit / max_loss if max_loss > 0 else 0
            }
            
            logger.info(
                f"Profit targets: Max Profit=${max_profit:.2f}, "
                f"TP@${take_profit_price:.2f} (${take_profit_amount:.2f}), "
                f"SL@${stop_loss_price:.2f} (-${stop_loss_amount:.2f})"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating profit targets: {e}")
            return {}


# Singleton instance
_position_sizer: Optional[PositionSizer] = None


def get_position_sizer() -> PositionSizer:
    """Get or create singleton position sizer instance"""
    global _position_sizer
    if _position_sizer is None:
        _position_sizer = PositionSizer()
    return _position_sizer
