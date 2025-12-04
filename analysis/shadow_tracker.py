"""
Shadow Tracker
Tracks and evaluates rejected trades to determine if the rejection was a "Good Reject" or "Missed Opportunity".
"""
import asyncio
from typing import Dict, Any, List
from loguru import logger
from datetime import datetime, timedelta

from data.database import get_database
from ibkr.connection import get_ibkr_connection
from ibkr.data_fetcher import get_data_fetcher

class ShadowTracker:
    """
    Tracks rejected trades (Shadow Trades) and evaluates their hypothetical performance.
    """
    
    def __init__(self):
        self.db = None
        self.ibkr = None
        self.data_fetcher = None
        
    async def initialize(self):
        """Initialize dependencies"""
        self.db = await get_database()
        self.ibkr = get_ibkr_connection()
        
        # Ensure IBKR is connected
        if not self.ibkr.is_connected():
            await self.ibkr.connect()
            
        self.data_fetcher = get_data_fetcher()
        
    async def run_daily_evaluation(self):
        """
        Run daily evaluation of all pending shadow trades.
        Should be run once per day (e.g., after market close).
        """
        logger.info("=" * 60)
        logger.info("🕵️ STARTING SHADOW TRADE EVALUATION")
        logger.info("=" * 60)
        
        if not self.db:
            await self.initialize()
            
        pending_trades = await self.db.get_pending_shadow_trades()
        
        if not pending_trades:
            logger.info("No pending shadow trades to evaluate.")
            return
            
        logger.info(f"Found {len(pending_trades)} pending shadow trades.")
        
        for trade in pending_trades:
            await self._evaluate_trade(trade)
            
        logger.info("Shadow trade evaluation complete.")
        
    async def _evaluate_trade(self, trade: Dict[str, Any]):
        """Evaluate a single shadow trade"""
        symbol = trade['symbol']
        trade_id = trade['id']
        expiration_str = trade['expiration']
        
        logger.info(f"Evaluating Shadow Trade #{trade_id}: {symbol} {trade['strategy']}")
        
        try:
            # Parse expiration
            expiration_date = datetime.strptime(expiration_str, "%Y%m%d").date()
            today = datetime.now().date()
            
            # Check if expired
            is_expired = today >= expiration_date
            
            # Get current price of the underlying
            current_price = await self.data_fetcher.get_stock_price(symbol)
            if not current_price:
                logger.warning(f"Could not fetch price for {symbol}, skipping.")
                return

            # Calculate hypothetical PnL
            # Simplified logic for Credit Spreads:
            # If expired:
            #   - If OTM (safe): Profit = Credit Received
            #   - If ITM (unsafe): Loss = (Strike diff - Credit) * 100 * contracts (assuming max loss)
            # If not expired:
            #   - Mark to market (requires option prices, which is expensive/complex to fetch historically)
            #   - For MVP, we only evaluate at expiration or if stop loss would have been hit (simulated)
            
            if is_expired:
                await self._finalize_expired_trade(trade, current_price)
            else:
                # Optional: Check for early stop loss / take profit
                # For now, just log current status
                logger.info(f"   Still active. Current Price: ${current_price:.2f}")
                
        except Exception as e:
            logger.error(f"Error evaluating trade {trade_id}: {e}")

    async def _finalize_expired_trade(self, trade: Dict[str, Any], final_price: float):
        """Finalize a trade that has reached expiration"""
        short_strike = trade['short_strike']
        long_strike = trade['long_strike']
        credit = trade['credit_received']
        strategy = trade['strategy']
        
        pnl = 0.0
        outcome = "NEUTRAL"
        
        if strategy == "CREDIT_SPREAD":
            # Assume Bull Put Spread for simplicity (or check option type)
            # If Put: OTM if Price > Short Strike
            # If Call: OTM if Price < Short Strike
            
            option_type = trade.get('option_type', 'PUT') # Default to PUT if missing
            
            is_itm = False
            if option_type == 'PUT':
                is_itm = final_price < short_strike
            else: # CALL
                is_itm = final_price > short_strike
                
            if not is_itm:
                # Full Profit
                pnl = credit * 100 # Per contract
                outcome = "MISSED_OPPORTUNITY" # We rejected a winner
                logger.info(f"   ✅ Expired OTM (Winner). We missed ${pnl:.2f}")
            else:
                # Max Loss (simplified)
                width = abs(short_strike - long_strike)
                loss = (width - credit) * 100
                pnl = -loss
                outcome = "GOOD_REJECT" # We rejected a loser
                logger.info(f"   ❌ Expired ITM (Loser). Saved ${loss:.2f}")
        
        # Update DB
        await self.db.update_shadow_outcome(
            trade_id=trade['id'],
            outcome=outcome,
            final_pnl=pnl,
            notes=f"Expired at ${final_price:.2f}"
        )

# Singleton
_tracker = None

def get_shadow_tracker():
    global _tracker
    if _tracker is None:
        _tracker = ShadowTracker()
    return _tracker
