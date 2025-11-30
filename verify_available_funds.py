#!/usr/bin/env python3
"""
Verify Available Funds Integration
Tests that PositionSizer uses AvailableFunds instead of NetLiquidation.
"""
import asyncio
import os
from loguru import logger

# Mock environment
os.environ['GEMINI_API_KEY'] = 'test_key'
os.environ['ANTHROPIC_API_KEY'] = 'test_key'


class MockIBKRConnection:
    """Mock IBKR connection for testing"""
    
    def __init__(self):
        self.net_liquidation = 100000.0
        self.available_funds = 75000.0  # Less than NetLiq (positions use some)
        self.buying_power = 150000.0    # With margin
    
    async def get_account_balance(self):
        """Mock NetLiquidation"""
        return self.net_liquidation
    
    async def get_available_funds(self):
        """Mock AvailableFunds"""
        logger.info(f"💰 Mock AvailableFunds: ${self.available_funds:,.2f}")
        return self.available_funds
    
    async def get_buying_power(self):
        """Mock BuyingPower"""
        logger.info(f"💪 Mock BuyingPower: ${self.buying_power:,.2f}")
        return self.buying_power


async def test_available_funds_integration():
    """Test that PositionSizer uses AvailableFunds"""
    logger.info("🧪 Testing Available Funds Integration...")
    
    # Test 1: Position sizing with AvailableFunds
    logger.info("\n📊 Test 1: Position sizing uses AvailableFunds")
    
    from risk.position_sizer import PositionSizer
    from config import get_config
    
    config = get_config()
    mock_ibkr = MockIBKRConnection()
    
    # Create PositionSizer with mock connection
    sizer = PositionSizer(config)
    sizer.ibkr = mock_ibkr  # Inject mock
    
    # Calculate position size
    max_risk_per_contract = 500.0  # $500 max risk per contract
    result = await sizer.calculate_position_size(
        max_risk=max_risk_per_contract,
        account_risk_pct=2.0  # 2% of available funds
    )
    
    # Calculate expected
    expected_max_risk = mock_ibkr.available_funds * 0.02  # $75,000 * 2% = $1,500
    expected_contracts = int(expected_max_risk / max_risk_per_contract)  # 1500 / 500 = 3
    
    logger.info(f"\n📈 Results:")
    logger.info(f"   Available Funds: ${result.get('available_funds', 0):,.2f}")
    logger.info(f"   Contracts: {result['num_contracts']}")
    logger.info(f"   Total Risk: ${result['total_risk']:.2f}")
    logger.info(f"   % of Available: {result['account_pct']:.2f}%")
    
    # Verify uses AvailableFunds, NOT NetLiquidation
    assert result['num_contracts'] == expected_contracts, \
        f"Expected {expected_contracts} contracts, got {result['num_contracts']}"
    
    # If it used NetLiq ($100k), it would calculate 4 contracts ($2,000 max risk)
    wrong_max_risk = mock_ibkr.net_liquidation * 0.02
    wrong_contracts = int(wrong_max_risk / max_risk_per_contract)
    
    assert result['num_contracts'] != wrong_contracts, \
        f"ERROR: Using NetLiquidation instead of AvailableFunds!"
    
    logger.info("✅ Test 1 Passed: Correctly uses AvailableFunds")
    
    # Test 2: Verify difference matters
    logger.info("\n📊 Test 2: AvailableFunds vs NetLiquidation difference")
    
    difference = mock_ibkr.net_liquidation - mock_ibkr.available_funds
    logger.info(f"   NetLiq: ${mock_ibkr.net_liquidation:,.2f}")
    logger.info(f"   Available: ${mock_ibkr.available_funds:,.2f}")
    logger.info(f"   Difference: ${difference:,.2f} (tied up in positions)")
    logger.info(f"   → Using AvailableFunds prevents over-leveraging ✅")
    
    logger.info("\n🎉 All Available Funds integration tests passed!")


if __name__ == "__main__":
    asyncio.run(test_available_funds_integration())
