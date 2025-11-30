#!/usr/bin/env python3
"""
Verify Circuit Breaker
Tests daily loss and consecutive loss triggers.
"""
import asyncio
import os
from datetime import datetime, timedelta
from loguru import logger
import aiosqlite
from risk.circuit_breaker import get_circuit_breaker
from data.database import get_database

# Mock environment for testing
os.environ['GEMINI_API_KEY'] = 'test_key'
os.environ['ANTHROPIC_API_KEY'] = 'test_key'

async def test_circuit_breaker():
    logger.info("🧪 Testing Circuit Breaker Logic...")
    
    # Initialize
    db = await get_database()
    
    breaker = get_circuit_breaker(
        daily_max_loss_pct=5.0,
        consecutive_loss_limit=3,
        account_size=10000.0
    )
    await breaker.initialize()
    
    # Test 1: Safe daily loss
    logger.info("\n📊 Test 1: Safe daily loss")
    triggered = await breaker.check_daily_loss(-200.0)  # -2% (safe)
    assert not triggered, "Should NOT trigger on -2% loss"
    logger.info("✅ Test 1 Passed: No trigger on safe loss")
    
    # Test 2: Daily max loss breach
    logger.info("\n📊 Test 2: Daily max loss breach")
    triggered = await breaker.check_daily_loss(-600.0)  # -6% (breach)
    assert triggered, "Should trigger on -6% loss"
    assert breaker.is_trading_halted(), "Trading should be halted"
    logger.info("✅ Test 2 Passed: Triggered on -6% loss")
    
    # Reset for next test
    await breaker.reset_circuit_breaker(reason="Test reset")
    assert not breaker.is_trading_halted(), "Should be reset"
    logger.info("✅ Reset successful")
    
    # Test 3: Consecutive losses
    logger.info("\n📊 Test 3: Consecutive losses")
    
    # Insert 3 losing trades
    async with aiosqlite.connect(db.db_path) as conn:
        for i in range(3):
            await conn.execute("""
                INSERT INTO trades 
                (symbol, strategy, status, realized_pnl, close_timestamp)
                VALUES (?, ?, 'CLOSED', ?, ?)
            """, (f"TEST{i}", "TEST", -50.0, datetime.now().isoformat()))
        await conn.commit()
    
    triggered = await breaker.check_consecutive_losses()
    assert triggered, "Should trigger on 3 consecutive losses"
    assert breaker.is_trading_halted(), "Trading should be halted"
    logger.info("✅ Test 3 Passed: Triggered on 3 consecutive losses")
    
    # Check halt info
    halt_info = breaker.get_halt_info()
    logger.info(f"\n📋 Halt Info: {halt_info}")
    assert halt_info is not None
    assert halt_info['reason'] == 'CONSECUTIVE_LOSSES'
    
    logger.info("\n🎉 All Circuit Breaker tests passed!")

if __name__ == "__main__":
    asyncio.run(test_circuit_breaker())
