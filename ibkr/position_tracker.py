"""
Position Tracker
Monitors open positions and their P&L in real-time.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
from ib_insync import IB, Contract, Portfolio
from loguru import logger
from ibkr.connection import get_ibkr_connection
from data.database import get_database


class PositionTracker:
    """Track and monitor open positions"""
    
    def __init__(self):
        self.connection = get_ibkr_connection()
        self._positions: Dict[str, Dict[str, Any]] = {}
        self._monitoring = False
    
    def _get_client(self) -> IB:
        """Get IBKR client with connection check"""
        if not self.connection.is_connected():
            raise RuntimeError("Not connected to IBKR")
        return self.connection.get_client()
    
    async def update_positions(self) -> List[Dict[str, Any]]:
        """
        Fetch current positions from IBKR
        
        Returns:
            List of position dicts
        """
        try:
            ib = self._get_client()
            
            # Get portfolio positions
            portfolio_items = ib.portfolio()
            
            positions = []
            
            for item in portfolio_items:
                if item.position == 0:
                    continue  # Skip closed positions
                
                position_data = {
                    'symbol': item.contract.symbol,
                    'contract_type': item.contract.secType,
                    'position': item.position,
                    'market_price': item.marketPrice,
                    'market_value': item.marketValue,
                    'average_cost': item.averageCost,
                    'unrealized_pnl': item.unrealizedPNL,
                    'realized_pnl': item.realizedPNL,
                    'contract': item.contract,
                    'last_update': datetime.now()
                }
                
                # For options, add strike and expiration
                if item.contract.secType == 'OPT':
                    position_data['strike'] = item.contract.strike
                    position_data['right'] = item.contract.right
                    position_data['expiration'] = item.contract.lastTradeDateOrContractMonth
                
                # Store in cache
                position_key = self._get_position_key(item.contract)
                self._positions[position_key] = position_data
                positions.append(position_data)
                
                logger.debug(
                    f"Position: {item.contract.symbol} {item.contract.secType} "
                    f"Qty: {item.position}, P&L: ${item.unrealizedPNL:.2f}"
                )
            
            logger.info(f"Updated {len(positions)} positions")
            return positions
            
        except Exception as e:
            logger.error(f"Error updating positions: {e}")
            return []
    
    def _get_position_key(self, contract: Contract) -> str:
        """Generate unique key for position"""
        if contract.secType == 'OPT':
            return f"{contract.symbol}_{contract.lastTradeDateOrContractMonth}_{contract.strike}_{contract.right}"
        else:
            return f"{contract.symbol}_{contract.secType}"
    
    async def get_position(self, contract: Contract) -> Optional[Dict[str, Any]]:
        """Get specific position"""
        position_key = self._get_position_key(contract)
        return self._positions.get(position_key)
    
    async def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get all cached positions"""
        return list(self._positions.values())
    
    async def get_total_pnl(self) -> Dict[str, float]:
        """
        Calculate total P&L across all positions
        
        Returns:
            Dict with unrealized and realized PnL
        """
        try:
            await self.update_positions()
            
            total_unrealized = sum(
                pos.get('unrealized_pnl', 0) 
                for pos in self._positions.values()
            )
            
            total_realized = sum(
                pos.get('realized_pnl', 0)
                for pos in self._positions.values()
            )
            
            return {
                'unrealized_pnl': total_unrealized,
                'realized_pnl': total_realized,
                'total_pnl': total_unrealized + total_realized
            }
            
        except Exception as e:
            logger.error(f"Error calculating total P&L: {e}")
            return {
                'unrealized_pnl': 0,
                'realized_pnl': 0,
                'total_pnl': 0
            }
    
    async def monitor_positions(self, interval: int = 60):
        """
        Start monitoring positions at regular intervals
        
        Args:
            interval: Update interval in seconds
        """
        self._monitoring = True
        logger.info(f"Starting position monitoring (interval: {interval}s)")
        
        try:
            while self._monitoring:
                await self.update_positions()
                
                # Log summary
                pnl = await self.get_total_pnl()
                logger.info(
                    f"Position Update - "
                    f"Unrealized: ${pnl['unrealized_pnl']:.2f}, "
                    f"Realized: ${pnl['realized_pnl']:.2f}, "
                    f"Total: ${pnl['total_pnl']:.2f}"
                )
                
                # Update database
                db = await get_database()
                for position in self._positions.values():
                    # Here you could update position table in database
                    pass
                
                await asyncio.sleep(interval)
                
        except Exception as e:
            logger.error(f"Error in position monitoring: {e}")
            self._monitoring = False
    
    def stop_monitoring(self):
        """Stop position monitoring"""
        self._monitoring = False
        logger.info("Position monitoring stopped")
    
    async def get_greeks_for_position(self, contract: Contract) -> Optional[Dict[str, float]]:
        """
        Get current Greeks for a position
        
        Args:
            contract: Option contract
            
        Returns:
            Dict with Greeks or None
        """
        try:
            from ibkr.data_fetcher import get_data_fetcher
            data_fetcher = get_data_fetcher()
            
            greeks_data = await data_fetcher.get_option_greeks(contract)
            
            if greeks_data:
                return {
                    'delta': greeks_data.get('delta'),
                    'gamma': greeks_data.get('gamma'),
                    'theta': greeks_data.get('theta'),
                    'vega': greeks_data.get('vega'),
                    'vanna': greeks_data.get('vanna')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching Greeks for position: {e}")
            return None
    
    async def check_exit_conditions(
        self,
        position_data: Dict[str, Any],
        take_profit_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Check if position should be exited based on TP/SL
        
        Args:
            position_data: Position data dict
            take_profit_price: Take profit price target
            stop_loss_price: Stop loss price target
            
        Returns:
            Dict with exit recommendation
        """
        try:
            current_price = position_data.get('market_price', 0)
            unrealized_pnl = position_data.get('unrealized_pnl', 0)
            
            should_exit = False
            exit_reason = None
            
            # Check take profit
            if take_profit_price and current_price <= take_profit_price:
                should_exit = True
                exit_reason = f"Take Profit hit (${current_price:.2f} <= ${take_profit_price:.2f})"
                logger.info(f"✅ {exit_reason}")
            
            # Check stop loss
            if stop_loss_price and current_price >= stop_loss_price:
                should_exit = True
                exit_reason = f"Stop Loss hit (${current_price:.2f} >= ${stop_loss_price:.2f})"
                logger.warning(f"🛑 {exit_reason}")
            
            return {
                'should_exit': should_exit,
                'reason': exit_reason,
                'current_price': current_price,
                'unrealized_pnl': unrealized_pnl,
                'position': position_data
            }
            
        except Exception as e:
            logger.error(f"Error checking exit conditions: {e}")
            return {
                'should_exit': False,
                'reason': f'Error: {str(e)}',
                'current_price': 0,
                'unrealized_pnl': 0
            }


# Singleton instance
_position_tracker: Optional[PositionTracker] = None


def get_position_tracker() -> PositionTracker:
    """Get or create singleton position tracker instance"""
    global _position_tracker
    if _position_tracker is None:
        _position_tracker = PositionTracker()
    return _position_tracker
