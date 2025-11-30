"""
Rolling Manager - Defensive Strategy Logic
Handles rolling of losing positions to extend duration and adjust strikes.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger
from data.database import get_database
from execution.exit_manager import get_exit_manager, Position


class RollingManager:
    """
    Manages defensive rolling of positions.
    
    Trigger:
    - Price touches short strike
    - Delta > 0.40 (approx)
    
    Action:
    - Roll out in time (next monthly or +30 days)
    - Adjust tested strike to be OTM again (e.g., 30 delta)
    - Aim for Net Credit or minimal Debit
    """
    
    def __init__(self):
        self.db = None
        self.exit_manager = get_exit_manager()
        
    async def initialize(self):
        """Initialize dependencies"""
        self.db = await get_database()
        
    async def check_roll_triggers(
        self,
        position: Position,
        current_price: float,
        greeks: Dict[str, float]
    ) -> bool:
        """
        Check if position needs rolling
        
        Args:
            position: Open position
            current_price: Current underlying price
            greeks: Current greeks of the short leg(s)
            
        Returns:
            True if roll is triggered
        """
        # 1. Check if price touches short strike
        # Find short legs
        short_legs = [l for l in position.legs if l['action'] == 'SELL']
        
        for leg in short_legs:
            strike = leg['strike']
            option_type = leg['option_type']
            
            # Call touched? (Price >= Strike)
            if option_type == 'CALL' and current_price >= strike:
                logger.warning(f"🚨 ROLL TRIGGER: {position.symbol} Call strike ${strike} touched (Price: ${current_price})")
                return True
                
            # Put touched? (Price <= Strike)
            if option_type == 'PUT' and current_price <= strike:
                logger.warning(f"🚨 ROLL TRIGGER: {position.symbol} Put strike ${strike} touched (Price: ${current_price})")
                return True
        
        # 2. Check Delta (if available)
        # We assume 'greeks' contains the worst delta of short legs
        delta = abs(greeks.get('delta', 0))
        if delta > 0.40:
            logger.warning(f"🚨 ROLL TRIGGER: {position.symbol} Delta {delta:.2f} > 0.40")
            return True
            
        return False

    async def propose_roll(
        self,
        position: Position,
        current_price: float
    ) -> Optional[Dict[str, Any]]:
        """
        Propose a defensive roll for the position
        
        Args:
            position: Position to roll
            current_price: Current underlying price
            
        Returns:
            Dict with roll details (new expiration, new strikes)
        """
        try:
            # 1. Determine new expiration (Roll out ~30 days)
            current_exp = position.expiration
            new_exp = current_exp + timedelta(days=30)
            
            # Adjust to Friday? (Simplified: just add 30 days for now)
            # In production, find next monthly expiration
            
            # 2. Determine new strikes
            # We want to move the TESTED side further OTM
            # Keep the UNTESTED side same or tighten (to collect more credit)
            
            new_legs = []
            roll_type = "UNKNOWN"
            
            short_legs = [l for l in position.legs if l['action'] == 'SELL']
            
            # Identify tested side
            tested_leg = None
            for leg in short_legs:
                if leg['option_type'] == 'CALL' and current_price >= leg['strike'] * 0.98: # Close to strike
                    tested_leg = leg
                    roll_type = "ROLL_UP_AND_OUT" # Call tested -> Move up
                elif leg['option_type'] == 'PUT' and current_price <= leg['strike'] * 1.02:
                    tested_leg = leg
                    roll_type = "ROLL_DOWN_AND_OUT" # Put tested -> Move down
            
            if not tested_leg:
                logger.info(f"No specific leg tested for {position.symbol}, suggesting standard Roll Out")
                roll_type = "ROLL_OUT"
            
            # Construct proposal
            proposal = {
                'original_position_id': position.position_id,
                'symbol': position.symbol,
                'roll_type': roll_type,
                'current_expiration': current_exp.strftime('%Y-%m-%d'),
                'new_expiration': new_exp.strftime('%Y-%m-%d'),
                'strategy': position.strategy,
                'reason': f"Defensive roll: {roll_type}"
            }
            
            logger.info(f"📋 Proposed Roll for {position.symbol}: {roll_type} to {new_exp.date()}")
            return proposal
            
        except Exception as e:
            logger.error(f"Error proposing roll: {e}")
            return None

    async def execute_roll(
        self,
        position: Position,
        proposal: Dict[str, Any]
    ) -> bool:
        """
        Execute the roll ATOMICALLY using IBKR BAG order
        
        This places a single order that simultaneously:
        1. Closes the old position (BUY to close short, SELL to close long)
        2. Opens the new position (SELL new short, BUY new long)
        
        Args:
            position: Current position
            proposal: Roll proposal
            
        Returns:
            True if successful
        """
        logger.info(f"🔄 EXECUTING ATOMIC ROLL for {position.symbol}...")
        
        try:
            # Get original legs
            short_legs = [l for l in position.legs if l['action'] == 'SELL']
            long_legs = [l for l in position.legs if l['action'] == 'BUY']
            
            if not short_legs or not long_legs:
                logger.error("❌ Cannot roll: position must have both short and long legs")
                return False
            
            short_leg = short_legs[0]
            long_leg = long_legs[0]
            
            # Calculate current width
            width = abs(long_leg['strike'] - short_leg['strike'])
            
            # Determine new strikes based on roll type
            if proposal['roll_type'] == 'ROLL_UP_AND_OUT':
                # Move call strikes up (tested side is calls)
                new_short_strike = short_leg['strike'] + width  # Move up one width
                new_long_strike = new_short_strike + width
            elif proposal['roll_type'] == 'ROLL_DOWN_AND_OUT':
                # Move put strikes down (tested side is puts)
                new_short_strike = short_leg['strike'] - width  # Move down one width
                new_long_strike = new_short_strike - width
            else:
                # Standard roll out - keep strikes same
                new_short_strike = short_leg['strike']
                new_long_strike = long_leg['strike']
            
            # Get IBKR connection
            from ibkr.connection import get_ibkr_connection
            from ib_insync import Contract, ComboLeg, LimitOrder, Option
            
            ibkr = get_ibkr_connection()
            ib = ibkr.get_client()
            
            if not ib or not ibkr.is_connected():
                logger.error("❌ Not connected to IBKR")
                return False
            
            # Create option contracts for OLD position (to close)
            old_short = Option(
                position.symbol,
                position.expiration.strftime('%Y%m%d'),
                short_leg['strike'],
                short_leg['option_type'][0],  # 'C' or 'P'
                'SMART'
            )
            old_long = Option(
                position.symbol,
                position.expiration.strftime('%Y%m%d'),
                long_leg['strike'],
                long_leg['option_type'][0],
                'SMART'
            )
            
            # Create option contracts for NEW position (to open)
            new_exp_date = datetime.strptime(proposal['new_expiration'], '%Y-%m-%d').strftime('%Y%m%d')
            new_short = Option(
                position.symbol,
                new_exp_date,
                new_short_strike,
                short_leg['option_type'][0],
                'SMART'
            )
            new_long = Option(
                position.symbol,
                new_exp_date,
                new_long_strike,
                long_leg['option_type'][0],
                'SMART'
            )
            
            # Qualify all contracts
            logger.info("📋 Qualifying option contracts...")
            await ib.qualifyContractsAsync(old_short, old_long, new_short, new_long)
            
            # Create BAG order with 4 legs
            bag = Contract()
            bag.symbol = position.symbol
            bag.secType = 'BAG'
            bag.currency = 'USD'
            bag.exchange = 'SMART'
            
            # Legs: Close old + Open new
            bag.comboLegs = [
                # Close old position (reverse of original)
                ComboLeg(conId=old_short.conId, ratio=1, action='BUY', exchange='SMART'),   # BUY to close short
                ComboLeg(conId=old_long.conId, ratio=1, action='SELL', exchange='SMART'),  # SELL to close long
                # Open new position
                ComboLeg(conId=new_short.conId, ratio=1, action='SELL', exchange='SMART'), # SELL new short
                ComboLeg(conId=new_long.conId, ratio=1, action='BUY', exchange='SMART'),   # BUY new long
            ]
            
            # Calculate limit price (aim for small credit or break-even)
            # For now, set to -0.05 (willing to pay $5 to roll if needed)
            roll_limit = -0.05
            
            # Create limit order
            order = LimitOrder(
                action='BUY',  # BUY the combo
                totalQuantity=position.contracts,
                lmtPrice=roll_limit,
                tif='DAY',
                orderType='LMT'
            )
            
            logger.info(
                f"📤 Placing ATOMIC ROLL order:\n"
                f"   Close OLD: {short_leg['strike']}/{long_leg['strike']} exp {position.expiration.date()}\n"
                f"   Open NEW: {new_short_strike}/{new_long_strike} exp {proposal['new_expiration']}\n"
                f"   Limit: ${roll_limit:.2f} (per spread)\n"
                f"   Contracts: {position.contracts}"
            )
            
            # Place order
            trade = ib.placeOrder(bag, order)
            
            logger.info(f"✅ ROLL order placed. Order ID: {trade.order.orderId}")
            logger.info(f"   Status: {trade.orderStatus.status}")
            
            # Wait for fill (with timeout)
            import asyncio
            for _ in range(30):  # 30 seconds timeout
                await asyncio.sleep(1)
                if trade.orderStatus.status in ['Filled', 'Cancelled']:
                    break
            
            if trade.orderStatus.status == 'Filled':
                logger.info(f"🎉 ROLL EXECUTED for {position.symbol}!")
                logger.info(f"   Fill price: ${trade.orderStatus.avgFillPrice:.2f}")
                
                # TODO: Update database with new position
                # - Mark old position as ROLLED
                # - Create new position entry
                
                return True
            else:
                logger.warning(f"⏱️ Roll order not filled yet. Status: {trade.orderStatus.status}")
                logger.warning(f"   Monitor order ID: {trade.order.orderId}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error executing roll: {e}")
            logger.critical(
                f"🚨 CRITICAL ERROR during roll execution!\n"
                f"   Symbol: {position.symbol}\n"
                f"   Error: {str(e)}\n"
                f"   Manual intervention required!"
            )
            return False


# Singleton
_rolling_manager: Optional[RollingManager] = None


def get_rolling_manager() -> RollingManager:
    """Get or create singleton rolling manager"""
    global _rolling_manager
    if _rolling_manager is None:
        _rolling_manager = RollingManager()
    return _rolling_manager
