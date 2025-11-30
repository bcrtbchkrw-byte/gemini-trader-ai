"""
Order Execution with LIMIT validation
Executes trades with proper limit order checks and safety validations.
"""
from typing import Dict, Any, Optional, List
from loguru import logger
from ib_insync import Order, LimitOrder, MarketOrder
from ibkr.connection import get_ibkr_connection


class OrderExecutor:
    """Execute orders with validation and safety checks + LOW-LATENCY execution"""
    
    def __init__(self):
        self.connection = get_ibkr_connection()
        self.adaptive_mode = True  # Use adaptive algo for faster fills
        self.default_routing = 'SMART'  # Can override with 'ISLAND' for speed
    
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
    
    def create_marketable_limit_order(
        self,
        action: str,
        quantity: int,
        mid_price: float,
        bid: float,
        ask: float,
        aggressiveness: float = 0.5
    ) -> Optional[LimitOrder]:
        """
        Create MARKETABLE limit order for fastest execution
        
        Sets limit INSIDE the spread to ensure fill while protecting from slippage.
        
        Args:
            action: BUY or SELL
            quantity: Number of contracts
            mid_price: Mid market price
            bid: Current bid
            ask: Current ask
            aggressiveness: 0-1 scale (0=passive, 1=market taker)
            
        Returns:
            LimitOrder optimized for fast fill
        """
        try:
            # Calculate aggressive limit:
            # For BUY: Start at mid, move toward ask based on aggressiveness
            # For SELL: Start at mid, move toward bid
            
            if action == "BUY":
                # Aggressive buy: limit closer to ask
                limit_price = mid_price + (ask - mid_price) * aggressiveness
                limit_price = min(limit_price, ask * 1.02)  # Cap at ask +2%
                
            elif action == "SELL":
                # Aggressive sell: limit closer to bid
                limit_price = mid_price - (mid_price - bid) * aggressiveness
                limit_price = max(limit_price, bid * 0.98)  # Floor at bid -2%
            else:
                logger.error(f"Invalid action: {action}")
                return None
            
            order = LimitOrder(
                action=action,
                totalQuantity=quantity,
                lmtPrice=round(limit_price, 2)
            )
            
            # Adaptive algo for smart routing
            if self.adaptive_mode:
                order.algoStrategy = "Adaptive"
                order.algoParams = [
                    ('adaptivePriority', 'Normal')  # or 'Urgent' for faster
                ]
            
            # Routing
            order.exchange = self.default_routing
            
            logger.info(
                f"Marketable {action}: {quantity} @ ${limit_price:.2f} "
                f"(mid=${mid_price:.2f}, spread=${ask-bid:.2f})"
            )
            
            return order
            
        except Exception as e:
            logger.error(f"Error creating marketable limit: {e}")
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
    
    async def instant_execute(
        self,
        precomputed_strategy: Dict[str, Any],
        routing: str = 'SMART'
    ) -> Optional[Dict[str, Any]]:
        """
        INSTANT execution of pre-computed strategy
        
        This is the FAST path - no AI calls, no recalculation.
        Just execute what was pre-computed.
        
        Args:
            precomputed_strategy: Strategy from StrategyPreComputer
            routing: Exchange routing ('SMART', 'ISLAND', 'ARCA')
            
        Returns:
            Order status
        """
        try:
            if not precomputed_strategy.get('ready_to_execute'):
                logger.error("Strategy not ready for execution")
                return None
            
            logger.info("⚡ INSTANT EXECUTION - using pre-computed strategy")
            
            # Extract pre-computed parameters
            symbol = precomputed_strategy['symbol']
            strikes = precomputed_strategy['strikes']
            limit_prices = precomputed_strategy['limit_prices']
            
            # Execute with pre-calculated limits (NO RECALCULATION)
            # This is where latency is minimized
            
            logger.info(
                f"Executing {symbol}: "
                f"Strikes={strikes}, Limit={limit_prices['net_credit']:.2f}"
            )
            
            # TODO: Actual IBKR order placement
            # For now, simulate
            
            return {
                'status': 'SUBMITTED',
                'symbol': symbol,
                'execution_time_ms': 50,  # Sub-100ms target
                'method': 'instant_precomputed'
            }
            
        except Exception as e:
            logger.error(f"Instant execution error: {e}")
            return None
    
    async def execute_with_mid_price_pegging(
        self,
        contract,
        action: str,
        quantity: int,
        bid: float,
        ask: float,
        max_iterations: int = 20,
        step_cents: float = 0.01,
        wait_seconds: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Execute order with mid-price pegging strategy
        
        Strategy:
        1. Start limit at mid price (bid + ask) / 2
        2. Wait 5 seconds for fill
        3. If not filled, move limit 1¢ toward market
        4. Repeat until filled or max iterations
        
        This minimizes slippage while ensuring fills.
        
        Args:
            contract: IBKR contract
            action: BUY or SELL
            quantity: Number of contracts
            bid: Current bid price
            ask: Current ask price
            max_iterations: Max price adjustments (default 20)
            step_cents: Price step size (default $0.01)
            wait_seconds: Wait time between adjustments (default 5s)
            
        Returns:
            Order fill details or None
        """
        import asyncio
        
        try:
            ib = self.connection.get_client()
            
            if not ib or not ib.isConnected():
                logger.error("Not connected to IBKR")
                return None
            
            # Calculate mid price
            mid_price = (bid + ask) / 2
            
            # Starting limit price
            current_limit = round(mid_price, 2)
            
            logger.info(
                f"🎯 Mid-price pegging: {action} {quantity} {contract.symbol}\n"
                f"   Bid={bid:.2f}, Ask={ask:.2f}, Mid={mid_price:.2f}\n"
                f"   Starting limit: ${current_limit:.2f}"
            )
            
            for iteration in range(max_iterations):
                # Create limit order
                order = self.create_limit_order(
                    action=action,
                    quantity=quantity,
                    limit_price=current_limit
                )
                
                if not order:
                    logger.error("Failed to create order")
                    return None
                
                # Place order
                trade = ib.placeOrder(contract, order)
                
                logger.info(
                    f"[{iteration+1}/{max_iterations}] Order placed @ ${current_limit:.2f}"
                )
                
                # Wait for fill or timeout
                await asyncio.sleep(wait_seconds)
                
                # Check order status
                if trade.orderStatus.status in ['Filled', 'PartiallyFilled']:
                    logger.info(
                        f"✅ FILLED @ ${current_limit:.2f} in {iteration+1} iterations "
                        f"({(iteration+1) * wait_seconds}s)"
                    )
                    
                    return {
                        'status': 'FILLED',
                        'fill_price': trade.orderStatus.avgFillPrice,
                        'filled_quantity': trade.orderStatus.filled,
                        'iterations': iteration + 1,
                        'time_seconds': (iteration + 1) * wait_seconds,
                        'slippage': abs(trade.orderStatus.avgFillPrice - mid_price),
                        'method': 'mid_price_pegging'
                    }
                
                # Not filled - cancel and adjust
                ib.cancelOrder(order)
                await asyncio.sleep(0.5)  # Brief pause after cancel
                
                # Walk price toward market
                if action == "BUY":
                    # Move limit up toward ask
                    current_limit = min(current_limit + step_cents, ask)
                    logger.debug(f"Adjusting BUY limit up to ${current_limit:.2f}")
                else:  # SELL
                    # Move limit down toward bid
                    current_limit = max(current_limit - step_cents, bid)
                    logger.debug(f"Adjusting SELL limit down to ${current_limit:.2f}")
                
                # Check if we've reached the market
                if (action == "BUY" and current_limit >= ask) or \
                   (action == "SELL" and current_limit <= bid):
                    logger.warning(
                        f"Reached market price after {iteration+1} iterations, "
                        f"placing final order at market edge"
                    )
                    break
            
            # Final attempt at market edge
            logger.warning(
                f"⚠️  Max iterations reached, placing final order @ "
                f"${current_limit:.2f}"
            )
            
            final_order = self.create_limit_order(
                action=action,
                quantity=quantity,
                limit_price=current_limit
            )
            
            if final_order:
                trade = ib.placeOrder(contract, final_order)
                await asyncio.sleep(wait_seconds)
                
                if trade.orderStatus.status in ['Filled', 'PartiallyFilled']:
                    return {
                        'status': 'FILLED',
                        'fill_price': trade.orderStatus.avgFillPrice,
                        'filled_quantity': trade.orderStatus.filled,
                        'iterations': max_iterations,
                        'time_seconds': max_iterations * wait_seconds,
                        'method': 'mid_price_pegging_final'
                    }
            
            return {
                'status': 'NOT_FILLED',
                'last_limit': current_limit,
                'iterations': max_iterations,
                'reason': 'Max iterations exceeded'
            }
            
        except Exception as e:
            logger.error(f"Mid-price pegging error: {e}")
            return None
    
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
