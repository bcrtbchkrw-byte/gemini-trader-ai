"""
Circuit Breaker - Trading Kill Switch
Halts trading when safety thresholds are breached to prevent catastrophic losses.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from loguru import logger
from data.database import get_database


class CircuitBreaker:
    """
    Safety mechanism to halt trading under dangerous conditions:
    
    1. Daily Max Loss: If daily loss exceeds threshold (default 5%)
    2. Consecutive Losses: If N consecutive trades are losses (default 3)
    
    Once triggered, requires MANUAL RESET to resume trading.
    """
    
    def __init__(
        self,
        daily_max_loss_pct: float = 5.0,
        consecutive_loss_limit: int = 3,
        halt_duration_hours: int = 24,
        account_size: Optional[float] = None
    ):
        """
        Initialize Circuit Breaker
        
        Args:
            daily_max_loss_pct: Max daily loss % before halting (default 5%)
            consecutive_loss_limit: Number of consecutive losses before halt (default 3)
            halt_duration_hours: Auto-reset duration (default 24h)
            account_size: Account size for calculating loss threshold
        """
        self.daily_max_loss_pct = daily_max_loss_pct
        self.consecutive_loss_limit = consecutive_loss_limit
        self.halt_duration_hours = halt_duration_hours
        self.account_size = account_size
        
        # State
        self._trading_halted = False
        self._halt_reason = None
        self._halt_triggered_at = None
        
        self.db = None
        
    async def initialize(self):
        """Initialize database connection and create tables"""
        self.db = await get_database()
        await self._create_table()
        
        # Check if there's an active halt from previous session
        await self._check_existing_halt()
        
    async def _create_table(self):
        """Create circuit_breaker_events table"""
        import aiosqlite
        async with aiosqlite.connect(self.db.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS circuit_breaker_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    triggered_at DATETIME NOT NULL,
                    reason TEXT NOT NULL,
                    threshold_value REAL,
                    reset_at DATETIME,
                    reset_by TEXT,
                    notes TEXT
                )
            """)
            await db.commit()
        logger.info("Circuit breaker table initialized")
        
    async def _check_existing_halt(self):
        """Check if there's an active halt from previous session"""
        import aiosqlite
        async with aiosqlite.connect(self.db.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT triggered_at, reason
                FROM circuit_breaker_events
                WHERE reset_at IS NULL
                ORDER BY triggered_at DESC
                LIMIT 1
            """) as cursor:
                row = await cursor.fetchone()
        
        if row:
            triggered_at_str, reason = row
            triggered_at = datetime.fromisoformat(triggered_at_str)
            
            # Check if halt has expired
            if datetime.now() - triggered_at > timedelta(hours=self.halt_duration_hours):
                logger.info(f"Auto-resetting expired halt from {triggered_at}")
                await self.reset_circuit_breaker(reset_by="AUTO", reason="Time expired")
            else:
                self._trading_halted = True
                self._halt_reason = reason
                self._halt_triggered_at = triggered_at
                logger.warning(
                    f"🛑 CIRCUIT BREAKER ACTIVE from previous session: {reason}\n"
                    f"   Triggered: {triggered_at}\n"
                    f"   Manual reset required!"
                )
    
    def update_account_size(self, size: float):
        """Update account size for loss calculations"""
        self.account_size = size
        
    async def check_daily_loss(self, current_daily_pnl: float) -> bool:
        """
        Check if daily loss exceeds threshold
        
        Args:
            current_daily_pnl: Current P&L for the day (negative = loss)
            
        Returns:
            True if threshold breached (trading should halt)
        """
        if not self.account_size:
            logger.warning("Account size not set, cannot check daily loss")
            return False
            
        max_loss = -(self.account_size * self.daily_max_loss_pct / 100)
        
        if current_daily_pnl <= max_loss:
            loss_pct = (current_daily_pnl / self.account_size) * 100
            logger.error(
                f"🚨 DAILY MAX LOSS BREACHED!\n"
                f"   Daily P&L: ${current_daily_pnl:.2f} ({loss_pct:.2f}%)\n"
                f"   Threshold: ${max_loss:.2f} ({-self.daily_max_loss_pct:.2f}%)\n"
                f"   HALTING TRADING"
            )
            await self._trigger_halt(
                reason="DAILY_MAX_LOSS",
                threshold_value=loss_pct
            )
            return True
            
        return False
    
    async def check_consecutive_losses(self) -> bool:
        """
        Check if consecutive loss limit is reached
        
        Returns:
            True if threshold breached (trading should halt)
        """
        import aiosqlite
        # Fetch last N trades
        async with aiosqlite.connect(self.db.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT realized_pnl
                FROM trades
                WHERE status = 'CLOSED' AND realized_pnl IS NOT NULL
                ORDER BY close_timestamp DESC
                LIMIT ?
            """, (self.consecutive_loss_limit,)) as cursor:
                rows = await cursor.fetchall()
        
        if len(rows) < self.consecutive_loss_limit:
            # Not enough trades yet
            return False
        
        # Check if all are losses
        consecutive_losses = all(row['realized_pnl'] < 0 for row in rows)
        
        if consecutive_losses:
            logger.error(
                f"🚨 CONSECUTIVE LOSS LIMIT BREACHED!\n"
                f"   Last {self.consecutive_loss_limit} trades all losses\n"
                f"   HALTING TRADING for {self.halt_duration_hours}h"
            )
            await self._trigger_halt(
                reason="CONSECUTIVE_LOSSES",
                threshold_value=self.consecutive_loss_limit
            )
            return True
            
        return False
    
    async def _trigger_halt(self, reason: str, threshold_value: float):
        """
        Trigger circuit breaker halt
        
        Args:
            reason: Reason for halt (DAILY_MAX_LOSS or CONSECUTIVE_LOSSES)
            threshold_value: The value that triggered the halt
        """
        self._trading_halted = True
        self._halt_reason = reason
        self._halt_triggered_at = datetime.now()
        
        # Log to database
        import aiosqlite
        async with aiosqlite.connect(self.db.db_path) as db:
            await db.execute("""
                INSERT INTO circuit_breaker_events
                (triggered_at, reason, threshold_value)
                VALUES (?, ?, ?)
            """, (self._halt_triggered_at.isoformat(), reason, threshold_value))
            await db.commit()
        
        logger.critical(
            f"🛑 CIRCUIT BREAKER TRIGGERED\n"
            f"   Reason: {reason}\n"
            f"   Value: {threshold_value}\n"
            f"   Time: {self._halt_triggered_at}\n"
            f"   === TRADING HALTED ===\n"
            f"   Manual reset required to resume."
        )
        
        # TODO: Send Telegram alert
        # await telegram.send_alert(f"🚨 CIRCUIT BREAKER: {reason}")
    
    def is_trading_halted(self) -> bool:
        """
        Check if trading is currently halted
        
        Returns:
            True if trading is halted
        """
        return self._trading_halted
    
    def get_halt_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about current halt
        
        Returns:
            Dict with halt details or None if not halted
        """
        if not self._trading_halted:
            return None
            
        return {
            'halted': True,
            'reason': self._halt_reason,
            'triggered_at': self._halt_triggered_at,
            'duration': (datetime.now() - self._halt_triggered_at).total_seconds() / 3600  # hours
        }
    
    async def reset_circuit_breaker(
        self,
        reset_by: str = "MANUAL",
        reason: str = "Admin reset"
    ) -> bool:
        """
        Reset circuit breaker (requires manual action)
        
        Args:
            reset_by: Who/what reset it (MANUAL, AUTO)
            reason: Reason for reset
            
        Returns:
            True if successful
        """
        if not self._trading_halted:
            logger.info("Circuit breaker not active, no need to reset")
            return True
            
        # Update database
        import aiosqlite
        async with aiosqlite.connect(self.db.db_path) as db:
            await db.execute("""
                UPDATE circuit_breaker_events
                SET reset_at = ?, reset_by = ?, notes = ?
                WHERE reset_at IS NULL
            """, (datetime.now().isoformat(), reset_by, reason))
            await db.commit()
        
        # Clear state
        self._trading_halted = False
        self._halt_reason = None
        self._halt_triggered_at = None
        
        logger.info(
            f"✅ Circuit breaker RESET\n"
            f"   Reset by: {reset_by}\n"
            f"   Reason: {reason}\n"
            f"   Trading RESUMED"
        )
        
        return True


# Singleton
_circuit_breaker: Optional[CircuitBreaker] = None


def get_circuit_breaker(
    daily_max_loss_pct: float = 5.0,
    consecutive_loss_limit: int = 3,
    account_size: Optional[float] = None
) -> CircuitBreaker:
    """Get or create singleton circuit breaker"""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker(
            daily_max_loss_pct=daily_max_loss_pct,
            consecutive_loss_limit=consecutive_loss_limit,
            account_size=account_size
        )
    return _circuit_breaker
