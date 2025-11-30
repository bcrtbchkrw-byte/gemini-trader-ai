"""
Order Execution with LIMIT validation
Executes trades with proper limit order checks and safety validations.
"""
from typing import Dict, Any, Optional, List
from loguru import logger
from ib_insync import Order, LimitOrder, MarketOrder
from ibkr.connection import get_ibkr_connection


class OrderExecutor:
    """Execute orders with validation and safety checks"""
    
    def __init__(self):
        self.connection = get_ibkr_connection()
    
    def create_limit_order(
        self,
        action: str,
        quantity: int,
        limit_price: float,
        safety_margin: float = 0.05
    ) -> Optional[LimitOrder]:
        """
        Create limit order with validation
        
        Args:
            action: BUY or SELL
            quantity: Number of contracts
            limit_price: Limit price
            safety_margin: Safety margin for limit (5% default)
            
        Returns:
            LimitOrder or None if invalid
        """
        try:
            if limit_price <= 0:
                logger.error("Invalid limit price: must be > 0")
                return None
            
            if quantity <= 0:
                logger.error("Invalid quantity: must be > 0")
                return None
            
            if action not in ["BUY", "SELL"]:
                logger.error(f"Invalid action: {action}")
                return None
            
            # Create limit order
            order = LimitOrder(
                action=action,
                totalQuantity=quantity,
                lmtPrice=round(limit_price, 2)  # Round to 2 decimals
            )
            
            # Add safety properties
            order.outsideRth = False  # Only during regular hours
            order.tif = 'DAY'  # Day order
            
            logger.info(
                f"Created {action} limit order: {quantity} @ ${limit_price:.2f}"
            )
            
            return order
            
        except Exception as e:
            logger.error(f"Error creating limit order: {e}")
            return None
    
    def validate_limit_price(
        self,
        limit_price: float,
        market_price: float,
        action: str,
        max_slippage: float = 0.10
    ) -> bool:
        """
        Validate limit price is reasonable vs market
        
        Args:
            limit_price: Proposed limit price
            market_price: Current market price
            action: BUY or SELL
            max_slippage: Max allowed slippage (10% default)
            
        Returns:
            True if valid
        """
        if not market_price or market_price <= 0:
            logger.warning("Market price not available, skipping validation")
            return True
        
        # Calculate slippage
        if action == "BUY":
            # Buying limit should be >= market (you pay market or better)
            slippage = (limit_price - market_price) / market_price
            if slippage < -max_slippage:
                logger.error(
                    f"BUY limit ${limit_price:.2f} too far below market ${market_price:.2f} "
                    f"(slippage: {slippage:.1%})"
                )
                return False
                
        elif action == "SELL":
            # Selling limit should be <= market (you sell at market or better)
            slippage = (market_price - limit_price) / market_price
            if slippage < -max_slippage:
                logger.error(
                    f"SELL limit ${limit_price:.2f} too far above market ${market_price:.2f} "
                    f"(slippage: {slippage:.1%})"
                )
                return False
        
        logger.info(f"✅ Limit price validated: ${limit_price:.2f} vs market ${market_price:.2f}")
        return True
    
    async def execute_spread_order(
        self,
        spread_legs: List[Dict[str, Any]],
        limit_price: float,
        validate: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Execute multi-leg spread order with validation
        
        Args:
            spread_legs: List of leg dicts with contract, action, quantity
            limit_price: Net credit/debit limit
            validate: Whether to validate before execution
            
        Returns:
            Order status dict or None
        """
        try:
            ib = self.connection.get_client()
            
            if not ib or not ib.isConnected():
                logger.error("Not connected to IBKR")
                return None
            
            # Validation checks
            if validate:
                if len(spread_legs) < 2:
                    logger.error("Spread must have at least 2 legs")
                    return None
                
                if limit_price <= 0:
                    logger.error("Limit price must be positive")
                    return None
            
            # TODO: Implement combo order placement
            # This requires creating ComboLegs and placing via ib.placeOrder()
            logger.warning("Multi-leg spread execution not yet implemented")
            logger.info(f"Would execute {len(spread_legs)}-leg spread @ ${limit_price:.2f}")
            
            return {
                'status': 'NOT_IMPLEMENTED',
                'legs': len(spread_legs),
                'limit_price': limit_price
            }
            
        except Exception as e:
            logger.error(f"Error executing spread order: {e}")
            return None


# Singleton instance
_order_executor: Optional[OrderExecutor] = None


def get_order_executor() -> OrderExecutor:
    """Get or create singleton order executor"""
    global _order_executor
    if _order_executor is None:
        _order_executor = OrderExecutor()
    return _order_executor
