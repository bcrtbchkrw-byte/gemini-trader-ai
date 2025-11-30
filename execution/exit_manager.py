"""
Exit Manager - Position Tracking & Auto-Exit Logic
Tracks open positions and triggers exits based on profit targets, stop-loss, or time.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from loguru import logger
from data.database import get_database


class Position:
    """Represents an open position"""
    
    def __init__(
        self,
        position_id: int,
        symbol: str,
        strategy: str,
        entry_date: datetime,
        expiration: datetime,
        contracts: int,
        entry_credit: float,
        max_risk: float,
        legs: List[Dict[str, Any]]
    ):
        self.position_id = position_id
        self.symbol = symbol
        self.strategy = strategy
        self.entry_date = entry_date
        self.expiration = expiration
        self.contracts = contracts
        self.entry_credit = entry_credit
        self.max_risk = max_risk
        self.legs = legs
        
        # Calculate targets
        self.profit_target = entry_credit * 0.5  # 50% of max profit
        self.stop_loss = entry_credit * 2.5  # 2.5x credit
        self.time_exit_dte = 7  # Close at 7 DTE
    
    @property
    def days_to_expiration(self) -> int:
        """Calculate days to expiration"""
        return (self.expiration - datetime.now()).days
    
    @property
    def days_in_trade(self) -> int:
        """Days since entry"""
        return (datetime.now() - self.entry_date).days
    
    def should_exit(self, current_price: float) -> Dict[str, Any]:
        """
        Determine if position should be exited
        
        Args:
            current_price: Current price of the spread
            
        Returns:
            Dict with exit decision and reason
        """
        # Profit target (50% max profit)
        if current_price <= self.profit_target:
            return {
                'should_exit': True,
                'reason': 'PROFIT_TARGET',
                'current_price': current_price,
                'target': self.profit_target,
                'pnl': (self.entry_credit - current_price) * self.contracts * 100
            }
        
        # Stop loss (2.5x credit)
        if current_price >= self.stop_loss:
            return {
                'should_exit': True,
                'reason': 'STOP_LOSS',
                'current_price': current_price,
                'stop': self.stop_loss,
                'pnl': (self.entry_credit - current_price) * self.contracts * 100
            }
        
        # Time-based exit (7 DTE)
        if self.days_to_expiration <= self.time_exit_dte:
            return {
                'should_exit': True,
                'reason': 'TIME_EXIT',
                'dte': self.days_to_expiration,
                'current_price': current_price,
                'pnl': (self.entry_credit - current_price) * self.contracts * 100
            }
        
        # Hold position
        return {
            'should_exit': False,
            'reason': 'HOLD',
            'current_price': current_price,
            'profit_distance': (current_price - self.profit_target) / self.entry_credit,
            'dte': self.days_to_expiration
        }


class ExitManager:
    """Manages position exits based on rules"""
    
    def __init__(self):
        self.db = None
    
    async def initialize(self):
        """Initialize database connection"""
        self.db = await get_database()
        await self._create_tables()
    
    async def _create_tables(self):
        """Create positions tables if they don't exist"""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                strategy TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                expiration TEXT NOT NULL,
                contracts INTEGER NOT NULL,
                entry_credit REAL NOT NULL,
                max_risk REAL NOT NULL,
                status TEXT DEFAULT 'OPEN',
                exit_date TEXT,
                exit_price REAL,
                exit_reason TEXT,
                pnl REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS position_legs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER NOT NULL,
                contract_symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                strike REAL NOT NULL,
                option_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                FOREIGN KEY (position_id) REFERENCES positions(id)
            )
        """)
        
        logger.info("Position tracking tables created")
    
    async def open_position(
        self,
        symbol: str,
        strategy: str,
        expiration: datetime,
        contracts: int,
        entry_credit: float,
        max_risk: float,
        legs: List[Dict[str, Any]]
    ) -> int:
        """
        Record new position
        
        Args:
            symbol: Stock symbol
            strategy: Strategy name (e.g., IRON_CONDOR)
            expiration: Expiration date
            contracts: Number of contracts
            entry_credit: Credit received per contract
            max_risk: Max risk per contract
            legs: List of leg details
            
        Returns:
            Position ID
        """
        try:
            # Insert position
            cursor = await self.db.execute(
                """
                INSERT INTO positions 
                (symbol, strategy, entry_date, expiration, contracts, entry_credit, max_risk, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN')
                """,
                (
                    symbol,
                    strategy,
                    datetime.now().isoformat(),
                    expiration.isoformat(),
                    contracts,
                    entry_credit,
                    max_risk
                )
            )
            
            await self.db.commit()
            position_id = cursor.lastrowid
            
            # Insert legs
            for leg in legs:
                await self.db.execute(
                    """
                    INSERT INTO position_legs
                    (position_id, contract_symbol, action, strike, option_type, quantity, entry_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        position_id,
                        leg['symbol'],
                        leg['action'],
                        leg['strike'],
                        leg['option_type'],
                        leg['quantity'],
                        leg['price']
                    )
                )
            
            await self.db.commit()
            
            logger.info(
                f"✅ Position opened: {symbol} {strategy} "
                f"({contracts} contracts @ ${entry_credit:.2f})"
            )
            
            return position_id
            
        except Exception as e:
            logger.error(f"Error opening position: {e}")
            return -1
    
    async def close_position(
        self,
        position_id: int,
        exit_price: float,
        exit_reason: str
    ) -> bool:
        """
        Close position and record exit
        
        Args:
            position_id: Position ID
            exit_price: Exit price per contract
            exit_reason: Reason for exit
            
        Returns:
            True if successful
        """
        try:
            # Get position details
            cursor = await self.db.execute(
                "SELECT entry_credit, contracts FROM positions WHERE id = ?",
                (position_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                logger.error(f"Position {position_id} not found")
                return False
            
            entry_credit, contracts = row
            
            # Calculate P/L
            pnl = (entry_credit - exit_price) * contracts * 100
                UPDATE positions
                SET status = 'CLOSED',
                    exit_date = ?,
                    exit_price = ?,
                    exit_reason = ?,
                    pnl = ?
                WHERE id = ?
                """,
                (
                    datetime.now().isoformat(),
                    exit_price,
                    exit_reason,
                    pnl,
                    position_id
                )
            )
            
            await self.db.commit()
            
            logger.info(
                f"✅ Position {position_id} closed: {exit_reason} | "
                f"P/L: ${pnl:.2f}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False
    
    async def place_closing_order(
        self,
        position: Dict[str, Any],
        reason: str = "Manual Exit"
    ) -> Optional[Dict[str, Any]]:
        """
        Place atomic closing order for position
        
        CRITICAL: Uses IBKR BAG/Combo orders for multi-leg positions
        to prevent leg risk (partial fills).
        
        Args:
            position: Position to close
            reason: Exit reason
            
        Returns:
            Order result or None
        """
        try:
            ib = self.ibkr.get_client()
            
            if not ib or not ib.isConnected():
                logger.error("Not connected to IBKR for closing")
                return None
            
            symbol = position['symbol']
            strategy = position['strategy']
            
            logger.info(
                f"🔒 Closing position: {symbol} {strategy}\n"
                f"   Reason: {reason}\n"
                f"   Method: ATOMIC COMBO ORDER (BAG)"
            )
            
            # Get position legs from database
            legs = await self._get_position_legs(position['id'])
            
            if not legs:
                logger.error(f"No legs found for position {position['id']}")
                return None
            
            # Create CLOSING combo order (atomic execution)
            combo_order = await self._create_closing_combo_order(
                symbol=symbol,
                legs=legs,
                strategy=strategy
            )
            
            if not combo_order:
                logger.error("Failed to create combo closing order")
                return None
            
            # Execute atomic combo order
            logger.info(f"Submitting ATOMIC combo closing order for {symbol}...")
            
            trade = ib.placeOrder(combo_order['contract'], combo_order['order'])
            
            # Wait for fill
            await asyncio.sleep(2)
            
            status = trade.orderStatus.status
            
            if status in ['Filled', 'PartiallyFilled']:
                logger.info(
                    f"✅ Position closed: {symbol}\n"
                    f"   Fill Price: ${trade.orderStatus.avgFillPrice:.2f}\n"
                    f"   Execution: ATOMIC (all legs together)"
                )
                
                # Update position in database
                await self._mark_position_closed(
                    position_id=position['id'],
                    exit_price=trade.orderStatus.avgFillPrice,
                    exit_reason=reason
                )
                
                return {
                    'status': 'FILLED',
                    'symbol': symbol,
                    'fill_price': trade.orderStatus.avgFillPrice,
                    'execution_type': 'ATOMIC_COMBO',
                    'reason': reason
                }
            else:
                logger.warning(f"Closing order not filled: {status}")
                return {
                    'status': status,
                    'symbol': symbol
                }
            
        except Exception as e:
            logger.error(f"Error placing closing order: {e}")
            return None
    
    async def _create_closing_combo_order(
        self,
        symbol: str,
        legs: List[Dict[str, Any]],
        strategy: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create atomic BAG order for closing multi-leg position
        
        BAG = Basket/Combo instrument in IBKR
        All legs execute together or not at all.
        
        Args:
            symbol: Underlying symbol
            legs: Position legs to close
            strategy: Strategy type
            
        Returns:
            Dict with contract and order, or None
        """
        try:
            from ib_insync import Contract, Order, ComboLeg
            
            ib = self.ibkr.get_client()
            
            # Create BAG contract
            bag = Contract()
            bag.symbol = symbol
            bag.secType = 'BAG'
            bag.currency = 'USD'
            bag.exchange = 'SMART'
            
            # Add legs to BAG (reverse of opening positions)
            combo_legs = []
            total_quantity = 0
            
            for leg in legs:
                combo_leg = ComboLeg()
                combo_leg.conId = leg['contract_id']
                
                # REVERSE the action (BUY → SELL, SELL → BUY)
                if leg['action'] == 'BUY':
                    combo_leg.action = 'SELL'  # Close long position
                elif leg['action'] == 'SELL':
                    combo_leg.action = 'BUY'   # Close short position
                
                combo_leg.ratio = 1
                combo_leg.exchange = 'SMART'
                
                combo_legs.append(combo_leg)
                total_quantity = abs(leg['quantity'])
            
            bag.comboLegs = combo_legs
            
            # Qualify the BAG contract
            qualified = await ib.qualifyContractsAsync(bag)
            
            if not qualified:
                logger.error("Could not qualify BAG contract for closing")
                return None
            
            bag = qualified[0]
            
            # Create MARKET order for closing (want immediate execution)
            # Alternative: Limit order at mid-price
            order = Order()
            order.action = 'BUY' if strategy in ['IRON_CONDOR', 'CREDIT_SPREAD'] else 'SELL'
            order.totalQuantity = total_quantity
            order.orderType = 'MKT'  # Market for fast close
            order.transmit = True
            
            logger.info(
                f"Created ATOMIC BAG closing order:\n"
                f"  Symbol: {symbol}\n"
                f"  Legs: {len(combo_legs)}\n"
                f"  Quantity: {total_quantity}\n"
                f"  Order Type: MARKET (atomic execution)"
            )
            
            return {
                'contract': bag,
                'order': order
            }
            
        except Exception as e:
            logger.error(f"Error creating combo closing order: {e}")
            return None
    
    async def _get_position_legs(self, position_id: int) -> List[Dict[str, Any]]:
        """
        Get all open positions
        
        Returns:
            List of Position objects
        """
        try:
            cursor = await self.db.execute(
                """
                SELECT contract_symbol, action, strike, option_type, quantity, entry_price
                FROM position_legs
                WHERE position_id = ?
                """,
                (position_id,)
            )
            rows = await cursor.fetchall()
            
            legs = [
                {
                    'symbol': l[0],
                    'action': l[1],
                    'strike': l[2],
                    'option_type': l[3],
                    'quantity': l[4],
                    'price': l[5]
                }
                for l in rows
            ]
            return legs
        except Exception as e:
            logger.error(f"Error getting position legs for {position_id}: {e}")
            return []
    
    async def get_open_positions(self) -> List[Position]:
        """
        Get all open positions
        
        Returns:
            List of Position objects
        """
        try:
            cursor = await self.db.execute(
                """
                SELECT id, symbol, strategy, entry_date, expiration, 
                       contracts, entry_credit, max_risk
                FROM positions
                WHERE status = 'OPEN'
                ORDER BY entry_date DESC
                """
            )
            
            rows = await cursor.fetchall()
            positions = []
            
            for row in rows:
                # Get legs for this position
                legs_cursor = await self.db.execute(
                    """
                    SELECT contract_symbol, action, strike, option_type, quantity, entry_price
                    FROM position_legs
                    WHERE position_id = ?
                    """,
                    (row[0],)
                )
                legs_rows = await legs_cursor.fetchall()
                
                legs = [
                    {
                        'symbol': l[0],
                        'action': l[1],
                        'strike': l[2],
                        'option_type': l[3],
                        'quantity': l[4],
                        'price': l[5]
                    }
                    for l in legs_rows
                ]
                
                position = Position(
                    position_id=row[0],
                    symbol=row[1],
                    strategy=row[2],
                    entry_date=datetime.fromisoformat(row[3]),
                    expiration=datetime.fromisoformat(row[4]),
                    contracts=row[5],
                    entry_credit=row[6],
                    max_risk=row[7],
                    legs=legs
                )
                
                positions.append(position)
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting open positions: {e}")
            return []
    
    async def monitor_exits(self) -> List[Dict[str, Any]]:
        """
        Check all open positions for exit signals
        
        Returns:
            List of positions that should be exited
        """
        positions = await self.get_open_positions()
        exit_signals = []
        
        for position in positions:
            # TODO: Fetch current price from IBKR
            # For now, skip actual price check
            logger.info(
                f"Monitoring {position.symbol}: DTE={position.days_to_expiration}, "
                f"Days in trade={position.days_in_trade}"
            )
            
            # Check time-based exit
            if position.days_to_expiration <= position.time_exit_dte:
                exit_signals.append({
                    'position': position,
                    'reason': 'TIME_EXIT',
                    'dte': position.days_to_expiration
                })
        
        return exit_signals


# Singleton instance
_exit_manager: Optional[ExitManager] = None


def get_exit_manager() -> ExitManager:
    """Get or create singleton exit manager"""
    global _exit_manager
    if _exit_manager is None:
        _exit_manager = ExitManager()
    return _exit_manager
