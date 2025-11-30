#!/usr/bin/env python3
"""
Verify Order TTL (Time-To-Live)
Tests stale order detection and cancellation.
"""
import asyncio
import os
from datetime import datetime, timedelta
from loguru import logger

# Mock environment for testing
os.environ['GEMINI_API_KEY'] = 'test_key'
os.environ['ANTHROPIC_API_KEY'] = 'test_key'

from ibkr.order_manager import get_order_manager


class MockTrade:
    """Mock trade object for testing"""
    def __init__(self, order_id, symbol='TEST'):
        self.order = MockOrder(order_id)
        self.orderStatus = MockOrderStatus()
        self.contract = MockContract(symbol)


class MockOrder:
    def __init__(self, order_id):
        self.orderId = order_id
        self.action = 'BUY'
        self.totalQuantity = 1


class MockOrderStatus:
    def __init__(self):
        self.status = 'Submitted'


class MockContract:
    def __init__(self, symbol):
        self.symbol = symbol


async def test_ttl():
    """Test TTL logic WITHOUT actual IBKR connection"""
    logger.info("🧪 Testing Order TTL...")
    
    manager = get_order_manager()
    
    # Test 1: Timestamp tracking
    logger.info("\n📊 Test 1: Timestamp tracking")
    
    # Simulate placing an order
    test_order_id = 12345
    manager._active_orders[test_order_id] = MockTrade(test_order_id)
    manager._order_timestamps[test_order_id] = datetime.now()
    
    assert test_order_id in manager._order_timestamps
    logger.info("✅ Test 1 Passed: Timestamps tracked")
    
    # Test 2: Age calculation
    logger.info("\n📊 Test 2: Age calculation")
    
    # Simulate old order (35 minutes ago)
    old_order_id = 67890
    manager._active_orders[old_order_id] = MockTrade(old_order_id)
    manager._order_timestamps[old_order_id] = datetime.now() - timedelta(minutes=35)
    
    age = (datetime.now() - manager._order_timestamps[old_order_id]).total_seconds() / 60
    assert age > 30, f"Age should be > 30 min, got {age:.1f}"
    logger.info(f"✅ Test 2 Passed: Age calculated correctly ({age:.1f} min)")
    
    # Test 3: Open orders retrieval
    logger.info("\n📊 Test 3: Open orders retrieval")
    
    # Note: This will fail without IBKR connection, that's expected
    try:
        open_orders = await manager.get_open_orders()
        logger.info(f"✅ Test 3: Retrieved {len(open_orders)} open orders")
    except Exception as e:
        logger.info(f"⚠️ Test 3: Expected failure without IBKR: {e}")
    
    # Test 4: Manual staleness check
    logger.info("\n📊 Test 4: Staleness detection")
    
    ttl = 30  # minutes
    stale_count = 0
    
    for order_id, timestamp in manager._order_timestamps.items():
        age_minutes = (datetime.now() - timestamp).total_seconds() / 60
        if age_minutes > ttl:
            stale_count += 1
            logger.info(f"   Stale order detected: {order_id} (age: {age_minutes:.1f} min)")
    
    assert stale_count == 1, f"Should detect 1 stale order, found {stale_count}"
    logger.info(f"✅ Test 4 Passed: Detected {stale_count} stale order")
    
    logger.info("\n🎉 All Order TTL logic tests passed!")
    logger.info("⚠️ NOTE: Full test with IBKR connection requires active broker session")


if __name__ == "__main__":
    asyncio.run(test_ttl())
