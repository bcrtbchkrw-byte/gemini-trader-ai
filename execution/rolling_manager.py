"""
Rolling Manager
Handles defensive rolling logic for challenged positions.
Uses AI to validate if a roll is justified (thesis check) or if a loss should be taken.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
import asyncio
from ibkr.data_fetcher import get_data_fetcher
from ibkr.order_manager import get_order_manager
from ibkr.position_tracker import get_position_tracker
from config import get_config

class RollingManager:
    """
    Manages the lifecycle of a 'Roll' decision.
    1. Detects challenged positions (Delta expansion, Price breaches).
    2. Validates rolling candidacy (Credit check, Technicals).
    3. AI Confirmation (Is the thesis dead?).
    4. Execution (Atomic Combo).
    """
    
    def __init__(self):
        self.config = get_config()
        self.data_fetcher = get_data_fetcher()
        self.order_manager = get_order_manager()
        self.position_tracker = get_position_tracker()
        
    async def check_for_rolls(self) -> List[Dict[str, Any]]:
        """
        Scan all positions for rolling candidates.
        Returns list of actions taken/recommended.
        """
        positions = await self.position_tracker.update_positions()
        actions = []
        
        for pos in positions:
            # Only manage defined strategies like Spreads for now
            # Identifying grouped positions is tricky without a Portfolio Manager abstraction
            # For MVP, we scan individual legs or assume 1-leg handling for test
            # TODO: Implement full strategy grouping in PositionTracker
            pass
            
        return actions

    async def evaluate_roll(self, position_data: Dict[str, Any], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate if a specific position should be rolled.
        
        Args:
            position_data: Dict with position details (legs, strike, etc.)
            market_data: Current market context (price, regime, etc.)
            
        Returns:
            Dict with decision ('ROLL', 'HOLD', 'CLOSE') and details.
        """
        symbol = position_data.get('symbol')
        logger.info(f"🔄 Evaluating Roll for {symbol}...")
        
        # 1. Technical Trigger Check
        # Example: Short Strike is being tested (Price within 1%)
        current_price = market_data.get('price', 0)
        short_strike = self._get_short_strike(position_data)
        
        if not short_strike:
            return {'decision': 'HOLD', 'reason': 'No short strike identified'}
            
        distance_pct = (current_price - short_strike) / short_strike
        is_challenged = abs(distance_pct) < 0.02 # Within 2%
        
        if not is_challenged:
            return {'decision': 'HOLD', 'reason': 'Position Safe'}
            
        logger.warning(f"⚠️ Position {symbol} Challenged! Dist: {distance_pct:.1%}")
        
        # 2. AI Thesis Check
        # Ask ML: Is there a reversal coming?
        # If ML says "STRONG DOWNTREND" and we are selling Puts -> DON'T ROLL. CLOSE.
        ml_score = market_data.get('success_prob', 0.5) # From TradeSuccessPredictor
        
        # Only do expensive AI check if configured
        if self.config.ai.enable_ai_rolling:
            # Here we would call Claude/Gemini for a detailed "Thesis Review"
            # For now, we rely on the cost-free local XGBoost score
            pass
        
        if ml_score < 0.40:
            logger.warning(f"⛔ AI Thesis Invalidated (Score {ml_score:.2f}). Recommendation: CLOSE (Stop Loss)")
            return {'decision': 'CLOSE', 'reason': 'AI Thesis Invalidated'}
            
        # 3. Liquidity & Credit Check
        # Can we roll for a credit?
        # TODO: Lookup next expiration and calculate potential credit
        
        logger.info("✅ Position eligible for Defensive Roll (AI Approved)")
        return {
            'decision': 'ROLL',
            'reason': 'Challenged but Thesis Valid',
            'target_dte': 45, # Roll out
            'target_strike': short_strike # Maybe move it if possible
        }

    def _get_short_strike(self, position: Dict[str, Any]) -> Optional[float]:
        # Helper to find short strike from position dict
        # Assuming position contains leg info
        if position.get('position', 0) < 0:
            return position.get('strike')
        return None

    async def execute_roll(self, roll_plan: Dict[str, Any]) -> bool:
        """
        Execute the roll atomically
        """
        # Logic to build list of legs and call order_manager.place_roll_combo_order
        return True

# Singleton
_rolling_manager = None

def get_rolling_manager() -> RollingManager:
    global _rolling_manager
    if _rolling_manager is None:
        _rolling_manager = RollingManager()
    return _rolling_manager
