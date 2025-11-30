#!/usr/bin/env python3
"""
Verify AI Sanity Checker
Tests validation logic for catching hallucinations.
"""
import asyncio
from loguru import logger
from validation.ai_sanity_checker import get_sanity_checker


def test_sanity_checker():
    logger.info("🧪 Testing AI Sanity Checker...")
    
    checker = get_sanity_checker()
    
    # Mock option chain data
    options_data = [
        {'strike': 100.0, 'delta': 0.30},
        {'strike': 105.0, 'delta': 0.25},
        {'strike': 110.0, 'delta': 0.20},
        {'strike': 95.0, 'delta': 0.35},
        {'strike': 90.0, 'delta': 0.40},
    ]
    current_price = 100.0
    
    # Test 1: Valid recommendation
    logger.info("\n📊 Test 1: Valid CALL credit spread")
    valid_rec = {
        'symbol': 'TEST',
        'strategy': 'CREDIT_SPREAD',
        'option_type': 'CALL',
        'short_strike': 105.0,
        'long_strike': 110.0,
        'dte': 45,
        'greeks': {'delta': 0.25, 'vega': 0.50, 'theta': 0.10}
    }
    
    result = checker.validate_recommendation(valid_rec, options_data, current_price)
    assert result['valid'], f"Should be valid, got errors: {result['errors']}"
    logger.info("✅ Test 1 Passed: Valid recommendation accepted")
    
    # Test 2: Hallucinated strike (not in chain)
    logger.info("\n📊 Test 2: Hallucinated strike $500")
    hallucinated_rec = {
        'symbol': 'TEST',
        'strategy': 'CREDIT_SPREAD',
        'option_type': 'CALL',
        'short_strike': 500.0,  # Hallucination!
        'long_strike': 510.0,
        'dte': 45,
        'greeks': {'delta': 0.25, 'vega': 0.50, 'theta': 0.10}
    }
    
    result = checker.validate_recommendation(hallucinated_rec, options_data, current_price)
    assert not result['valid'], "Should be invalid (strike not in chain)"
    assert any('NOT FOUND' in err for err in result['errors'])
    logger.info("✅ Test 2 Passed: Hallucinated strike rejected")
    
    # Test 3: Strike too far from current price
    logger.info("\n📊 Test 3: Strike > 20% from current price")
    far_strike_rec = {
        'symbol': 'TEST',
        'strategy': 'CREDIT_SPREAD',
        'option_type': 'CALL',
        'short_strike': 130.0,  # 30% from $100
        'long_strike': 135.0,
        'dte': 45,
        'greeks': {'delta': 0.25, 'vega': 0.50, 'theta': 0.10}
    }
    
    # Add these strikes to chain to test only distance validation
    extended_chain = options_data + [
        {'strike': 130.0, 'delta': 0.10},
        {'strike': 135.0, 'delta': 0.08}
    ]
    
    result = checker.validate_recommendation(far_strike_rec, extended_chain, current_price)
    assert not result['valid'], "Should be invalid (strike too far)"
    assert any('from current price' in err for err in result['errors'])
    logger.info("✅ Test 3 Passed: Far strike rejected")
    
    # Test 4: Invalid strategy logic (short >= long)
    logger.info("\n📊 Test 4: Invalid spread logic (short >= long)")
    invalid_logic_rec = {
        'symbol': 'TEST',
        'strategy': 'CREDIT_SPREAD',
        'option_type': 'CALL',
        'short_strike': 110.0,  # Should be < long
        'long_strike': 105.0,   # Reversed!
        'dte': 45,
        'greeks': {'delta': 0.25, 'vega': 0.50, 'theta': 0.10}
    }
    
    result = checker.validate_recommendation(invalid_logic_rec, options_data, current_price)
    assert not result['valid'], "Should be invalid (invalid spread logic)"
    assert any('short strike' in err.lower() for err in result['errors'])
    logger.info("✅ Test 4 Passed: Invalid spread logic rejected")
    
    # Test 5: Invalid Greeks (delta too high)
    logger.info("\n📊 Test 5: Invalid Greeks (delta 0.80)")
    invalid_greeks_rec = {
        'symbol': 'TEST',
        'strategy': 'CREDIT_SPREAD',
        'option_type': 'CALL',
        'short_strike': 105.0,
        'long_strike': 110.0,
        'dte': 45,
        'greeks': {'delta': 0.80, 'vega': 0.50, 'theta': 0.10}  # Delta too high!
    }
    
    result = checker.validate_recommendation(invalid_greeks_rec, options_data, current_price)
    assert not result['valid'], "Should be invalid (delta out of range)"
    assert any('Delta' in err for err in result['errors'])
    logger.info("✅ Test 5 Passed: Invalid delta rejected")
    
    logger.info("\n🎉 All AI Sanity Checker tests passed!")


if __name__ == "__main__":
    test_sanity_checker()
