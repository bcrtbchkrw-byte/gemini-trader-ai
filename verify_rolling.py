#!/usr/bin/env python3
"""
Verify Rolling Strategy
Tests trigger logic and roll proposal generation.
"""
import asyncio
import os
from datetime import datetime, timedelta
from loguru import logger
from execution.rolling_manager import get_rolling_manager
from execution.exit_manager import Position

# Mock Position
def create_mock_position(symbol="TEST", strike=100, option_type="PUT"):
    return Position(
        position_id=1,
        symbol=symbol,
        strategy="CREDIT_SPREAD",
        entry_date=datetime.now() - timedelta(days=10),
        expiration=datetime.now() + timedelta(days=20),
        contracts=1,
        entry_credit=1.0,
        max_risk=4.0,
        legs=[
            {
                'symbol': f"{symbol}_P{strike}",
                'action': 'SELL',
                'strike': strike,
                'option_type': option_type,
                'quantity': 1,
                'price': 1.0
            }
        ]
    )

async def test_rolling_logic():
    logger.info("🧪 Testing Rolling Strategy Logic...")
    
    manager = get_rolling_manager()
    await manager.initialize()
    
    # Test 1: No Trigger (Safe)
    pos = create_mock_position(strike=100, option_type="PUT")
    triggered = await manager.check_roll_triggers(
        position=pos,
        current_price=105.0,  # Safe (above put strike)
        greeks={'delta': -0.20}
    )
    assert not triggered, "Should NOT trigger when safe"
    logger.info("✅ Test 1 Passed: No trigger when safe")
    
    # Test 2: Price Touch Trigger
    triggered = await manager.check_roll_triggers(
        position=pos,
        current_price=99.0,   # Touched (below put strike)
        greeks={'delta': -0.45}
    )
    assert triggered, "Should trigger on price touch"
    logger.info("✅ Test 2 Passed: Triggered on price touch")
    
    # Test 3: Delta Trigger
    triggered = await manager.check_roll_triggers(
        position=pos,
        current_price=102.0,  # Safe price
        greeks={'delta': -0.45} # High delta
    )
    assert triggered, "Should trigger on high delta"
    logger.info("✅ Test 3 Passed: Triggered on high delta")
    
    # Test 4: Roll Proposal
    proposal = await manager.propose_roll(pos, current_price=99.0)
    assert proposal is not None
    assert proposal['roll_type'] == "ROLL_DOWN_AND_OUT"
    logger.info(f"✅ Test 4 Passed: Proposal generated - {proposal['roll_type']}")
    
    logger.info("\n🎉 All Rolling Strategy tests passed!")

if __name__ == "__main__":
    asyncio.run(test_rolling_logic())
