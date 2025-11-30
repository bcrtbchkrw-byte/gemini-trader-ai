"""
SQLite Database Manager
Handles all database operations for trade logging and analytics.
"""
import aiosqlite
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger


class Database:
    """SQLite database manager for trade data"""
    
    def __init__(self, db_path: str = "data/trading.db"):
        self.db_path = db_path
        self._ensure_db_dir()
    
    def _ensure_db_dir(self):
        """Ensure database directory exists"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self):
        """Create database tables if they don't exist"""
        async with aiosqlite.connect(self.db_path) as db:
            # Trades table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    direction TEXT,
                    short_strike REAL,
                    long_strike REAL,
                    expiration TEXT,
                    num_contracts INTEGER,
                    credit_received REAL,
                    debit_paid REAL,
                    max_profit REAL,
                    max_loss REAL,
                    status TEXT DEFAULT 'OPEN',
                    close_timestamp DATETIME,
                    close_price REAL,
                    realized_pnl REAL,
                    vix_at_entry REAL,
                    regime_at_entry TEXT,
                    notes TEXT
                )
            """)
            
            # Positions table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    entry_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expiration TEXT,
                    num_contracts INTEGER,
                    credit_received REAL,
                    max_risk REAL,
                    status TEXT DEFAULT 'OPEN',
                    close_timestamp DATETIME,
                    close_price REAL,
                    realized_pnl REAL,
                    notes TEXT,
                    rolled_from_position_id INTEGER,
                    FOREIGN KEY (rolled_from_position_id) REFERENCES positions(id)
                )
            """)
            
            # Position legs (for multi-leg strategies)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS position_legs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    position_id INTEGER NOT NULL,
                    leg_type TEXT,
                    option_type TEXT,
                    strike REAL,
                    expiration TEXT,
                    quantity INTEGER,
                    action TEXT,
                    FOREIGN KEY (position_id) REFERENCES positions(id)
                )
            """)
            
            # PnL history table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pnl_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL UNIQUE,
                    daily_pnl REAL,
                    cumulative_pnl REAL,
                    account_value REAL,
                    num_trades INTEGER,
                    win_rate REAL
                )
            """)
            
            # AI decisions table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ai_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    ai_model TEXT NOT NULL,
                    decision_type TEXT,
                    recommendation TEXT,
                    confidence_score REAL,
                    reasoning TEXT,
                    vix REAL,
                    regime TEXT
                )
            """)
            
            # Market data snapshots
            await db.execute("""
                CREATE TABLE IF NOT EXISTS market_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    vix REAL,
                    regime TEXT,
                    spx_price REAL,
                    notes TEXT
                )
            """)
            
            await db.commit()
            logger.info("Database initialized successfully")
    
    async def log_trade(self, trade_data: Dict[str, Any]) -> int:
        """
        Log a new trade
        
        Args:
            trade_data: Dict with trade information
            
        Returns:
            Trade ID
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO trades (
                    symbol, strategy, direction, short_strike, long_strike,
                    expiration, num_contracts, credit_received, debit_paid,
                    max_profit, max_loss, vix_at_entry, regime_at_entry, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_data.get('symbol'),
                trade_data.get('strategy'),
                trade_data.get('direction'),
                trade_data.get('short_strike'),
                trade_data.get('long_strike'),
                trade_data.get('expiration'),
                trade_data.get('num_contracts'),
                trade_data.get('credit_received'),
                trade_data.get('debit_paid'),
                trade_data.get('max_profit'),
                trade_data.get('max_loss'),
                trade_data.get('vix_at_entry'),
                trade_data.get('regime_at_entry'),
                trade_data.get('notes')
            ))
            
            await db.commit()
            trade_id = cursor.lastrowid
            logger.info(f"Trade logged with ID: {trade_id}")
            return trade_id
    
    async def update_position(
        self,
        trade_id: int,
        current_price: float,
        current_pnl: float,
        greeks: Optional[Dict[str, float]] = None
    ):
        """Update position with current market data"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE positions
                SET current_price = ?,
                    current_pnl = ?,
                    delta = ?,
                    theta = ?,
                    vega = ?,
                    last_update = CURRENT_TIMESTAMP
                WHERE trade_id = ?
            """, (
                current_price,
                current_pnl,
                greeks.get('delta') if greeks else None,
                greeks.get('theta') if greeks else None,
                greeks.get('vega') if greeks else None,
                trade_id
            ))
            await db.commit()
    
    async def close_trade(
        self,
        trade_id: int,
        close_price: float,
        realized_pnl: float
    ):
        """Mark trade as closed"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE trades
                SET status = 'CLOSED',
                    close_timestamp = CURRENT_TIMESTAMP,
                    close_price = ?,
                    realized_pnl = ?
                WHERE id = ?
            """, (close_price, realized_pnl, trade_id))
            await db.commit()
            logger.info(f"Trade {trade_id} closed with P&L: ${realized_pnl:.2f}")
    
    async def log_ai_decision(self, decision_data: Dict[str, Any]):
        """Log AI decision for audit trail"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO ai_decisions (
                    symbol, ai_model, decision_type, recommendation,
                    confidence_score, reasoning, vix, regime
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                decision_data.get('symbol'),
                decision_data.get('ai_model'),
                decision_data.get('decision_type'),
                decision_data.get('recommendation'),
                decision_data.get('confidence_score'),
                decision_data.get('reasoning'),
                decision_data.get('vix'),
                decision_data.get('regime')
            ))
            await db.commit()
    
    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM trades WHERE status = 'OPEN'
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_trade_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get trade history"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if symbol:
                query = "SELECT * FROM trades WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?"
                params = (symbol, limit)
            else:
                query = "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?"
                params = (limit,)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_losing_trades(
        self,
        limit: int = 10,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get recent losing trades for analysis
        
        Args:
            limit: Max number of trades to return
            days: Lookback period in days
            
        Returns:
            List of losing trades
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            query = """
                SELECT * FROM trades 
                WHERE status = 'CLOSED' 
                AND realized_pnl < 0
                AND close_timestamp >= date('now', ?)
                ORDER BY realized_pnl ASC
                LIMIT ?
            """
            
            async with db.execute(query, (f'-{days} days', limit)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]


# Singleton instance
_database: Optional[Database] = None


async def get_database() -> Database:
    """Get or create singleton database instance"""
    global _database
    if _database is None:
        _database = Database()
        await _database.initialize()
    return _database
