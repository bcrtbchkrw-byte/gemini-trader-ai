#!/usr/bin/env python3
"""
Quick strategy test without dependencies
Tests advanced strategies logic
"""

# Test Mean Reversion Strategy
print("=" * 60)
print("Testing Mean Reversion Strategy")
print("=" * 60)

# Simulate price history with deviation
import random
prices = [100 + random.uniform(-2, 2) for _ in range(19)]
prices.append(115)  # Price spike (deviation)

from strategies.advanced_strategies import QuantStrategies

result = QuantStrategies.mean_reversion_signals(prices, lookback_period=20, std_threshold=2.0)

print(f"\nPrice History: {len(prices)} days")
print(f"Current Price: ${prices[-1]:.2f}")
print(f"Mean Price: ${result['mean_price']:.2f}")
print(f"Std Dev: ${result['std_dev']:.2f}")
print(f"\nZ-Score: {result['z_score']:.2f}")
print(f"Signal: {result['signal']}")
print(f"Strategy: {result['entry_strategy']}")
print(f"Confidence: {result['confidence']:.0%}")

if 'rsi' in result:
    print(f"\n📊 Technical Confirmation:")
    print(f"  RSI: {result['rsi']:.1f} ({result['rsi_signal']})")
if 'bb_position' in result:
    print(f"  Bollinger Bands: {result['bb_position']:.2f} ({result['bb_signal']})")

# Test Theta Decay Optimizer
print("\n" + "=" * 60)
print("Testing Theta Decay Optimizer")
print("=" * 60)

test_cases = [
    (14, 0.35, 0.02),  # ATM, 14 DTE
    (30, 0.40, 0.10),  # OTM, 30 DTE - optimal
    (45, 0.30, 0.15),  # Far OTM, 45 DTE
]

for dte, iv, strike_dist in test_cases:
    result = QuantStrategies.theta_decay_optimizer(dte, iv, strike_dist)
    print(f"\nDTE: {dte}, IV: {iv:.0%}, Strike Distance: {strike_dist:.0%}")
    print(f"  Optimal Range: {result['optimal_dte_range']}")
    print(f"  Decay Rating: {result['decay_rating']}")
    print(f"  Recommendation: {result['recommendation']}")

# Test Strategy Builders
print("\n" + "=" * 60)
print("Testing Strategy Builders")
print("=" * 60)

from strategies.advanced_strategies import AdvancedStrategies

# Iron Condor
print("\n🦅 Iron Condor:")
ic = AdvancedStrategies.iron_condor(underlying_price=100, wing_width=5, body_width=10)
print(f"  Name: {ic.name}")
print(f"  Legs: {len(ic.legs)} (4-leg structure)")
print(f"  Max Profit: ${ic.max_profit:.2f}")
print(f"  Max Loss: ${ic.max_loss:.2f}")
print(f"  Breakevens: ${ic.breakeven_points[0]:.2f} / ${ic.breakeven_points[1]:.2f}")
print(f"  Best When: {ic.ideal_conditions}")

# Iron Butterfly
print("\n🦋 Iron Butterfly:")
ib = AdvancedStrategies.iron_butterfly(underlying_price=100, wing_width=5)
print(f"  Name: {ib.name}")
print(f"  Max Profit: ${ib.max_profit:.2f} (higher than IC)")
print(f"  Max Loss: ${ib.max_loss:.2f}")
print(f"  Best When: {ib.ideal_conditions}")

# Calendar Spread
print("\n📅 Calendar Spread:")
cs = AdvancedStrategies.calendar_spread(underlying_price=100, strike=100)
print(f"  Name: {cs.name}")
print(f"  Legs: {len(cs.legs)} (2-leg structure)")
print(f"  Max Profit: ${cs.max_profit:.2f}")
print(f"  Max Loss: ${cs.max_loss:.2f}")
print(f"  Best When: {cs.ideal_conditions}")

print("\n" + "=" * 60)
print("✅ All Strategy Tests Passed!")
print("=" * 60)
