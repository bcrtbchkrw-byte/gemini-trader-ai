"""
IBKR Order Manager
Handles order execution for spreads and single options.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from ib_insync import IB, Order, Contract, Option, Trade, LimitOrder
from loguru import logger
from ibkr.connection import get_ibkr_connection
from data.logger import get_trade_logger


class OrderManager:
    """Manage order placement and execution"""
    
    def __init__(self):
        self.connection = get_ibkr_connection()
        self.trade_logger = get_trade_logger()
        self._active_orders: Dict[int, Trade] = {}
        self._order_timestamps: Dict[int, datetime] = {}  # Track when orders were placed
    
    def _get_client(self) -> IB:
        """Get IBKR client with connection check"""
        if not self.connection.is_connected():
            raise RuntimeError("Not connected to IBKR")
        return self.connection.get_client()
    
    async def place_vertical_spread(
        self,
        symbol: str,
        expiration: str,
        short_strike: float,
        long_strike: float,
        right: str,  # 'C' or 'P'
        is_credit: bool,
        num_contracts: int,
        limit_price: float,
        exchange: str = "SMART"
    ) -> Optional[Dict[str, Any]]:
        """
        Place vertical spread order (credit or debit)
        
        Args:
            symbol: Stock symbol
            expiration: Expiration date (YYYYMMDD)
            short_strike: Short leg strike
            long_strike: Long leg strike  
            right: 'C' for call, 'P' for put
            is_credit: True for credit spread, False for debit
            num_contracts: Number of contracts
            limit_price: Limit price for the spread
            exchange: Exchange to route to
            
        Returns:
            Dict with order details or None if failed
        """
        try:
            ib = self._get_client()
            
            # Create option contracts
            short_option = Option(symbol, expiration, short_strike, right, exchange)
            long_option = Option(symbol, expiration, long_strike, right, exchange)
            
            # Qualify contracts
            await ib.qualifyContractsAsync(short_option, long_option)
            
            logger.info(
                f"Placing vertical {right} spread: "
                f"Sell {short_strike} / Buy {long_strike}, "
                f"Exp: {expiration}, Qty: {num_contracts}, "
                f"Limit: ${limit_price:.2f}"
            )
            
            # Create combo order (spread)
            combo = Contract()
            combo.symbol = symbol
            combo.secType = "BAG"
            combo.currency = "USD"
            combo.exchange = exchange
            
            # Define legs
            from ib_insync import ComboLeg
            
            leg1 = ComboLeg()
            leg1.conId = short_option.conId
            leg1.ratio = 1
            leg1.action = "SELL"  # Short leg
            leg1.exchange = exchange
            
            leg2 = ComboLeg()
            leg2.conId = long_option.conId
            leg2.ratio = 1
            leg2.action = "BUY"  # Long leg (protection)
            leg2.exchange = exchange
            
            combo.comboLegs = [leg1, leg2]
            
            # Create limit order
            order = LimitOrder(
                action="BUY" if is_credit else "SELL",  # BUY spread = collect credit
                totalQuantity=num_contracts,
                lmtPrice=limit_price,
                tif="GTC",  # Good-Till-Cancelled
                orderType="LMT"
            )
            
            # Place order
            trade = ib.placeOrder(combo, order)
            
            # Store trade and timestamp
            self._active_orders[trade.order.orderId] = trade
            self._order_timestamps[trade.order.orderId] = datetime.now()
            
            # Log trade
            self.trade_logger.info(
                f"SPREAD ORDER PLACED - ID: {trade.order.orderId}\n"
                f"Symbol: {symbol}, Type: {'Credit' if is_credit else 'Debit'}\n"
                f"Short: {short_strike}{right}, Long: {long_strike}{right}\n"
                f"Expiration: {expiration}, Contracts: {num_contracts}\n"
                f"Limit Price: ${limit_price:.2f}"
            )
            
            logger.info(f"✅ Order placed successfully. Order ID: {trade.order.orderId}")
            
            return {
                'order_id': trade.order.orderId,
                'symbol': symbol,
                'type': 'credit_spread' if is_credit else 'debit_spread',
                'short_strike': short_strike,
                'long_strike': long_strike,
                'right': right,
                'expiration': expiration,
                'num_contracts': num_contracts,
                'limit_price': limit_price,
                'status': trade.orderStatus.status,
                'trade': trade
            }
            
        except Exception as e:
            logger.error(f"Error placing vertical spread: {e}")
            return None
    
    async def place_iron_condor(
        self,
        symbol: str,
        expiration: str,
        call_short_strike: float,
        call_long_strike: float,
        put_short_strike: float,
        put_long_strike: float,
        num_contracts: int,
        limit_price: float,
        exchange: str = "SMART"
    ) -> Optional[Dict[str, Any]]:
        """
        Place iron condor (credit spread on both sides)
        
        Args:
            symbol: Stock symbol
            expiration: Expiration date
            call_short_strike: Short call strike
            call_long_strike: Long call strike (higher)
            put_short_strike: Short put strike
            put_long_strike: Long put strike (lower)
            num_contracts: Number of contracts
            limit_price: Total credit to collect
            exchange: Exchange
            
        Returns:
            Order details or None
        """
        try:
            ib = self._get_client()
            
            # Create all 4 option contracts
            call_short = Option(symbol, expiration, call_short_strike, 'C', exchange)
            call_long = Option(symbol, expiration, call_long_strike, 'C', exchange)
            put_short = Option(symbol, expiration, put_short_strike, 'P', exchange)
            put_long = Option(symbol, expiration, put_long_strike, 'P', exchange)
            
            # Qualify all contracts
            await ib.qualifyContractsAsync(call_short, call_long, put_short, put_long)
            
            logger.info(
                f"Placing Iron Condor on {symbol}:\n"
                f"  Call spread: Sell {call_short_strike} / Buy {call_long_strike}\n"
                f"  Put spread: Sell {put_short_strike} / Buy {put_long_strike}\n"
                f"  Contracts: {num_contracts}, Credit: ${limit_price:.2f}"
            )
            
            # Create combo
            combo = Contract()
            combo.symbol = symbol
            combo.secType = "BAG"
            combo.currency = "USD"
            combo.exchange = exchange
            
            from ib_insync import ComboLeg
            
            # 4 legs
            legs = [
                ComboLeg(conId=call_short.conId, ratio=1, action="SELL", exchange=exchange),
                ComboLeg(conId=call_long.conId, ratio=1, action="BUY", exchange=exchange),
                ComboLeg(conId=put_short.conId, ratio=1, action="SELL", exchange=exchange),
                ComboLeg(conId=put_long.conId, ratio=1, action="BUY", exchange=exchange),
            ]
            
            combo.comboLegs = legs
            
            # Limit order
            order = LimitOrder(
                action="BUY",  # BUY the spread = collect credit
                totalQuantity=num_contracts,
                lmtPrice=limit_price,
                tif="GTC",
                orderType="LMT"
            )
            
            # Place order
            trade = ib.placeOrder(combo, order)
            self._active_orders[trade.order.orderId] = trade
            self._order_timestamps[trade.order.orderId] = datetime.now()
            
            self.trade_logger.info(
                f"IRON CONDOR PLACED - ID: {trade.order.orderId}\n"
                f"Symbol: {symbol}, Exp: {expiration}\n"
                f"Call: {call_short_strike}/{call_long_strike}\n"
                f"Put: {put_short_strike}/{put_long_strike}\n"
                f"Contracts: {num_contracts}, Credit: ${limit_price:.2f}"
            )
            
            logger.info(f"✅ Iron Condor placed. Order ID: {trade.order.orderId}")
            
            return {
                'order_id': trade.order.orderId,
                'symbol': symbol,
                'type': 'iron_condor',
                'expiration': expiration,
                'num_contracts': num_contracts,
                'limit_price': limit_price,
                'status': trade.orderStatus.status,
                'trade': trade
            }
            
        except Exception as e:
            logger.error(f"Error placing iron condor: {e}")
            return None
    
    async def get_order_status(self, order_id: int) -> Optional[Dict[str, Any]]:
        """Get status of an order"""
        try:
            if order_id in self._active_orders:
                trade = self._active_orders[order_id]
                
                return {
                    'order_id': order_id,
                    'status': trade.orderStatus.status,
                    'filled': trade.orderStatus.filled,
                    'remaining': trade.orderStatus.remaining,
                    'avg_fill_price': trade.orderStatus.avgFillPrice,
                    'last_fill_price': trade.orderStatus.lastFillPrice
                }
            else:
                logger.warning(f"Order ID {order_id} not found in active orders")
                return None
                
        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            return None
    
    async def cancel_order(self, order_id: int) -> bool:
        """Cancel an order"""
        try:
            if order_id not in self._active_orders:
                logger.warning(f"Order ID {order_id} not found")
                return False
            
            ib = self._get_client()
            trade = self._active_orders[order_id]
            
            ib.cancelOrder(trade.order)
            logger.info(f"Order {order_id} cancellation requested")
            
            self.trade_logger.info(f"ORDER CANCELLED - ID: {order_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False
    
    async def place_closing_order(
        self,
        original_order_id: int,
        closing_price: float
    ) -> Optional[Dict[str, Any]]:
        """
        Place order to close an existing position
        
        Args:
            original_order_id: ID of original opening order
            closing_price: Price to close at
            
        Returns:
            Closing order details
        """
        try:
            if original_order_id not in self._active_orders:
                logger.error(f"Original order {original_order_id} not found")
                return None
            
            ib = self._get_client()
            original_trade = self._active_orders[original_order_id]
            
            # Create closing order (reverse of opening)
            closing_order = LimitOrder(
                action="SELL" if original_trade.order.action == "BUY" else "BUY",
                totalQuantity=original_trade.order.totalQuantity,
                lmtPrice=closing_price,
                tif="GTC",
                orderType="LMT"
            )
            
            # Place closing order
            closing_trade = ib.placeOrder(original_trade.contract, closing_order)
            self._active_orders[closing_trade.order.orderId] = closing_trade
            self._order_timestamps[closing_trade.order.orderId] = datetime.now()
            
            logger.info(
                f"Closing order placed for original order {original_order_id}. "
                f"New order ID: {closing_trade.order.orderId}, Price: ${closing_price:.2f}"
            )
            
            self.trade_logger.info(
                f"CLOSING ORDER - ID: {closing_trade.order.orderId}\n"
                f"Original Order: {original_order_id}\n"
                f"Closing Price: ${closing_price:.2f}"
            )
            
            return {
                'order_id': closing_trade.order.orderId,
                'original_order_id': original_order_id,
                'closing_price': closing_price,
                'status': closing_trade.orderStatus.status,
                'trade': closing_trade
            }
            
        except Exception as e:
            logger.error(f"Error placing closing order: {e}")
            return None
    
    async def get_open_orders(self) -> List[Dict[str, Any]]:
        """
        Get all currently open orders
        
        Returns:
            List of open order details
        """
        try:
            ib = self._get_client()
            open_trades = ib.openOrders()
            
            orders = []
            for trade in open_trades:
                order_id = trade.order.orderId
                age_minutes = None
                
                if order_id in self._order_timestamps:
                    age_seconds = (datetime.now() - self._order_timestamps[order_id]).total_seconds()
                    age_minutes = age_seconds / 60
                
                orders.append({
                    'order_id': order_id,
                    'symbol': trade.contract.symbol if hasattr(trade.contract, 'symbol') else 'N/A',
                    'status': trade.orderStatus.status,
                    'action': trade.order.action,
                    'quantity': trade.order.totalQuantity,
                    'limit_price': trade.order.lmtPrice if hasattr(trade.order, 'lmtPrice') else None,
                    'age_minutes': age_minutes,
                    'placed_at': self._order_timestamps.get(order_id)
                })
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []
    
    async def cancel_stale_orders(self, max_age_minutes: int = 30) -> int:
        """
        Cancel orders older than max_age_minutes
        
        Args:
            max_age_minutes: Maximum age in minutes before cancelling
            
        Returns:
            Number of orders cancelled
        """
        try:
            ib = self._get_client()
            open_trades = ib.openOrders()
            cancelled_count = 0
            
            logger.info(f"🔍 Checking for stale orders (TTL: {max_age_minutes} min)...")
            
            for trade in open_trades:
                order_id = trade.order.orderId
                
                # Check if we have timestamp for this order
                if order_id not in self._order_timestamps:
                    # Order placed before tracking started, assume it's old
                    logger.warning(f"Order {order_id} has no timestamp - cancelling as precaution")
                    await self.cancel_order(order_id)
                    cancelled_count += 1
                    continue
                
                # Calculate age
                age_seconds = (datetime.now() - self._order_timestamps[order_id]).total_seconds()
                age_minutes = age_seconds / 60
                
                # Cancel if too old
                if age_minutes > max_age_minutes:
                    symbol = trade.contract.symbol if hasattr(trade.contract, 'symbol') else 'N/A'
                    logger.warning(
                        f"🗑️ Cancelling STALE order {order_id} for {symbol}\n"
                        f"   Age: {age_minutes:.1f} minutes (max: {max_age_minutes})"
                    )
                    
                    await self.cancel_order(order_id)
                    cancelled_count += 1
                    
                    # Remove from tracking
                    if order_id in self._order_timestamps:
                        del self._order_timestamps[order_id]
            
            if cancelled_count > 0:
                logger.warning(f"✅ Cancelled {cancelled_count} stale order(s)")
            else:
                logger.info("✓ No stale orders found")
            
            return cancelled_count
            
        except Exception as e:
            logger.error(f"Error cancelling stale orders: {e}")
            return 0


# Singleton instance
_order_manager: Optional[OrderManager] = None


def get_order_manager() -> OrderManager:
    """Get or create singleton order manager instance"""
    global _order_manager
    if _order_manager is None:
        _order_manager = OrderManager()
    return _order_manager
