"""
Exit Manager
Automatically manages take profit and stop loss exits.
"""
from typing import Dict, Any, Optional
import asyncio
from loguru import logger
from config import get_config
from ibkr.position_tracker import get_position_tracker
from ibkr.order_manager import get_order_manager
from data.database import get_database
from data.logger import get_trade_logger


class ExitManager:
    """Manage automatic exits for positions"""
    
    def __init__(self):
        self.config = get_config()
        self.position_tracker = get_position_tracker()
        self.order_manager = get_order_manager()
        self.trade_logger = get_trade_logger()
        self._monitoring = False
        self._exit_rules: Dict[int, Dict[str, Any]] = {}
    
    def set_exit_rules(
        self,
        order_id: int,
        take_profit_price: float,
        stop_loss_price: float,
        max_profit: float,
        max_loss: float
    ):
        """
        Set exit rules for a position
        
        Args:
            order_id: Original order ID
            take_profit_price: Price to take profit
            stop_loss_price: Price to stop loss
            max_profit: Maximum profit ($)
            max_loss: Maximum loss ($)
        """
        self._exit_rules[order_id] = {
            'take_profit_price': take_profit_price,
            'stop_loss_price': stop_loss_price,
            'max_profit': max_profit,
            'max_loss': max_loss,
            'enabled': True
        }
        
        logger.info(
            f"Exit rules set for order {order_id}: "
            f"TP=${take_profit_price:.2f}, SL=${stop_loss_price:.2f}"
        )
    
    async def place_bracket_orders(
        self,
        order_id: int,
        entry_price: float,
        num_contracts: int
    ) -> Dict[str, Any]:
        """
        Place GTC bracket orders (TP and SL) after entry fill
        
        Args:
            order_id: Original entry order ID
            entry_price: Filled entry price
            num_contracts: Number of contracts
            
        Returns:
            Dict with TP and SL order IDs
        """
        try:
            if order_id not in self._exit_rules:
                logger.error(f"No exit rules found for order {order_id}")
                return {}
            
            rules = self._exit_rules[order_id]
            
            # Calculate actual TP and SL prices based on entry
            # For credit spreads: we sold at entry_price, want to buy back cheaper
            tp_price = rules['take_profit_price']  # 50% of credit
            sl_price = rules['stop_loss_price']    # 2.5x credit
            
            logger.info(
                f"Placing bracket orders for order {order_id}:\n"
                f"  Entry: ${entry_price:.2f}\n"
                f"  TP: ${tp_price:.2f}\n"
                f"  SL: ${sl_price:.2f}"
            )
            
            # Place TP order
            tp_order = await self.order_manager.place_closing_order(
                original_order_id=order_id,
                closing_price=tp_price
            )
            
            # Place SL order
            sl_order = await self.order_manager.place_closing_order(
                original_order_id=order_id,
                closing_price=sl_price
            )
            
            result = {
                'take_profit_order': tp_order,
                'stop_loss_order': sl_order
            }
            
            if tp_order and sl_order:
                logger.info(
                    f"✅ Bracket orders placed: "
                    f"TP Order #{tp_order['order_id']}, "
                    f"SL Order #{sl_order['order_id']}"
                )
                
                self.trade_logger.info(
                    f"BRACKET ORDERS PLACED\n"
                    f"Entry Order: {order_id}\n"
                    f"TP Order: {tp_order['order_id']} @ ${tp_price:.2f}\n"
                    f"SL Order: {sl_order['order_id']} @ ${sl_price:.2f}"
                )
            else:
                logger.error("Failed to place bracket orders")
            
            return result
            
        except Exception as e:
            logger.error(f"Error placing bracket orders: {e}")
            return {}
    
    async def monitor_exits(self, check_interval: int = 30):
        """
        Monitor positions and execute exits when conditions met
        
        Args:
            check_interval: How often to check (seconds)
        """
        self._monitoring = True
        logger.info(f"Exit monitoring started (interval: {check_interval}s)")
        
        try:
            while self._monitoring:
                # Get all open positions
                positions = await self.position_tracker.get_all_positions()
                
                for position in positions:
                    # Find matching exit rules
                    # This is simplified - in production you'd need better position ID tracking
                    for order_id, rules in self._exit_rules.items():
                        if not rules.get('enabled', True):
                            continue
                        
                        # Check exit conditions
                        exit_check = await self.position_tracker.check_exit_conditions(
                            position_data=position,
                            take_profit_price=rules.get('take_profit_price'),
                            stop_loss_price=rules.get('stop_loss_price')
                        )
                        
                        if exit_check['should_exit']:
                            logger.warning(
                                f"⚠️ EXIT SIGNAL: {exit_check['reason']}\n"
                                f"Position: {position['symbol']}, "
                                f"P&L: ${exit_check['unrealized_pnl']:.2f}"
                            )
                            
                            # Execute exit (in auto mode)
                            if self.config.safety.auto_execute:
                                await self._execute_exit(order_id, exit_check, position)
                            else:
                                logger.info("Auto-execute disabled. Manual action required.")
                
                await asyncio.sleep(check_interval)
                
        except Exception as e:
            logger.error(f"Error in exit monitoring: {e}")
            self._monitoring = False
    
    async def _execute_exit(
        self,
        order_id: int,
        exit_check: Dict[str, Any],
        position: Dict[str, Any]
    ):
        """Execute exit order"""
        try:
            logger.info(f"Executing exit for order {order_id}...")
            
            # Place closing order at current market price
            closing_order = await self.order_manager.place_closing_order(
                original_order_id=order_id,
                closing_price=exit_check['current_price']
            )
            
            if closing_order:
                self.trade_logger.info(
                    f"AUTO EXIT EXECUTED\n"
                    f"Reason: {exit_check['reason']}\n"
                    f"Order ID: {closing_order['order_id']}\n"
                    f"Price: ${exit_check['current_price']:.2f}\n"
                    f"P&L: ${exit_check['unrealized_pnl']:.2f}"
                )
                
                # Disable further monitoring for this position
                if order_id in self._exit_rules:
                    self._exit_rules[order_id]['enabled'] = False
                
                logger.info(f"✅ Exit executed for order {order_id}")
            else:
                logger.error(f"Failed to execute exit for order {order_id}")
                
        except Exception as e:
            logger.error(f"Error executing exit: {e}")
    
    def stop_monitoring(self):
        """Stop exit monitoring"""
        self._monitoring = False
        logger.info("Exit monitoring stopped")
    
    async def manual_exit(
        self,
        order_id: int,
        reason: str = "Manual close"
    ) -> bool:
        """
        Manually close a position
        
        Args:
            order_id: Order ID to close
            reason: Reason for closing
            
        Returns:
            bool: True if successful
        """
        try:
            logger.info(f"Manual exit requested for order {order_id}: {reason}")
            
            # Get current position
            positions = await self.position_tracker.get_all_positions()
            
            # Find matching position (simplified - needs better matching in production)
            for position in positions:
                # Place closing order at market
                closing_order = await self.order_manager.place_closing_order(
                    original_order_id=order_id,
                    closing_price=position['market_price']
                )
                
                if closing_order:
                    self.trade_logger.info(
                        f"MANUAL EXIT\n"
                        f"Order: {order_id}\n"
                        f"Reason: {reason}\n"
                        f"Closing Order: {closing_order['order_id']}"
                    )
                    
                    # Disable auto monitoring
                    if order_id in self._exit_rules:
                        self._exit_rules[order_id]['enabled'] = False
                    
                    return True
            
            logger.warning(f"Could not find position for order {order_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error in manual exit: {e}")
            return False


# Singleton instance
_exit_manager: Optional[ExitManager] = None


def get_exit_manager() -> ExitManager:
    """Get or create singleton exit manager instance"""
    global _exit_manager
    if _exit_manager is None:
        _exit_manager = ExitManager()
    return _exit_manager
