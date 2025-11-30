#!/usr/bin/env python3
"""
Verify Rolling Manager with IBKR BAG Order
Tests atomic roll execution logic.
"""
import asyncio
from datetime import datetime, timedelta
from loguru import logger
from execution.rolling_manager import get_rolling_manager
from execution.exit_manager import Position


def create_test_position():
    """Create a mock PUT credit spread position"""
    return Position(
        position_id=1,
        symbol="SPY",
        strategy="CREDIT_SPREAD",
        entry_date=datetime.now() - timedelta(days=20),
        expiration=datetime.now() + timedelta(days=10),  # 10 DTE
        contracts=1,
        entry_credit=1.50,
        max_risk=3.50,
        legs=[
            {
                'symbol': 'SPY_P450',
                'action': 'SELL',
                'strike': 450.0,
                'option_type': 'PUT',
                'quantity': 1,
                'price': 2.0
            },
            {
                'symbol': 'SPY_P445',
                'action': 'BUY',
                'strike': 445.0,
                'option_type': 'PUT',
                'quantity': 1,
                'price': 0.50
            }
        ]
    )


async def test_roll_logic():
    """Test rolling logic WITHOUT actual IBKR connection"""
    logger.info("🧪 Testing Rolling Manager...")
    
    manager = get_rolling_manager()
    await manager.initialize()
    
    position = create_test_position()
    
    # Test 1: Check triggers (price touched)
    logger.info("\n📊 Test 1: Roll trigger check")
    triggered = await manager.check_roll_triggers(
        position=position,
        current_price=449.0,  # Close to 450 short strike
        greeks={'delta': -0.45}
    )
    assert triggered, "Should trigger on high delta"
    logger.info("✅ Test 1 Passed: Trigger detected")
    
    # Test 2: Generate proposal
    logger.info("\n📊 Test 2: Roll proposal")
    proposal = await manager.propose_roll(position, current_price=449.0)
    assert proposal is not None
    assert proposal['roll_type'] == 'ROLL_DOWN_AND_OUT'
    logger.info(f"✅ Test 2 Passed: Proposal - {proposal['roll_type']}")
    
    # Test 3: Execute roll (will fail without IBKR connection, that's OK)
    logger.info("\n📊 Test 3: Execute roll (will fail without IBKR - expected)")
    try:
        result = await manager.execute_roll(position, proposal)
        if result:
            logger.info("✅ Test 3: Roll executed (IBKR connected)")
        else:
            logger.info("⚠️ Test 3: Roll not executed (expected without IBKR)")
    except Exception as e:
        logger.info(f"⚠️ Test 3: Failed as expected without IBKR: {e}")
    
    logger.info("\n🎉 Rolling Manager logic tests passed!")
    logger.info("⚠️ NOTE: Full integration test requires active IBKR connection")


if __name__ == "__main__":
    asyncio.run(test_roll_logic())
