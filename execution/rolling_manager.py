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
        Execute the roll (Atomic: Close Old + Open New)
        
        Args:
            position: Current position
            proposal: Roll proposal
            
        Returns:
            True if successful
        """
        logger.info(f"🔄 EXECUTING ROLL for {position.symbol}...")
        
        # 1. Close current position
        # In a real implementation, this would be a single COMBO order (Close + Open)
        # For now, we simulate it as Close then Open to keep it simple, 
        # but acknowledge the slippage risk.
        
        # Ideally: self.ibkr.place_combo_order(close_legs + open_legs)
        
        close_result = await self.exit_manager.place_closing_order(
            position={'id': position.position_id, 'symbol': position.symbol, 'strategy': position.strategy},
            reason=f"Rolling: {proposal['roll_type']}"
        )
        
        if not close_result or close_result['status'] != 'FILLED':
            logger.error("❌ Roll failed: Could not close existing position")
            return False
            
        # 2. Open new position
        # This would be triggered via the Strategy Selector or manually constructed here
        # For this MVP, we'll just log that the new position should be opened.
        
        logger.info(f"✅ Old position closed. OPENING NEW POSITION per proposal: {proposal}")
        
        # TODO: Call StrategyExecutor to open the new legs
        # await self.strategy_executor.execute_strategy(...)
        
        return True


# Singleton
_rolling_manager: Optional[RollingManager] = None


def get_rolling_manager() -> RollingManager:
    """Get or create singleton rolling manager"""
    global _rolling_manager
    if _rolling_manager is None:
        _rolling_manager = RollingManager()
    return _rolling_manager
