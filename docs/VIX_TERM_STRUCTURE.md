# VIX Term Structure Analysis

## 🎯 Enhanced Regime Detection

**Before:** Spot VIX only
```python
if VIX > 30:
    regime = "HIGH_VOL"
```

**After:** VIX + Term Structure
```python
vix_ratio = VIX / VIX3M
if VIX > 30 and vix_ratio > 1.05:
    regime = "HIGH_VOL_BACKWARDATION"  # EXTREME STRESS!
```

## 📊 Term Structure Concepts

### Contango (Normal)
```
VIX < VIX3M
Ratio < 1.0

Example:
VIX:   18
VIX3M: 20
Ratio: 0.90 (CONTANGO)

Meaning: Market expects volatility to rise
Status: NORMAL conditions
Action: ✅ Short vega OK
```

### Backwardation (Stress)
```
VIX > VIX3M
Ratio > 1.0

Example:
VIX:   35
VIX3M: 28
Ratio: 1.25 (BACKWARDATION!)

Meaning: Current panic > future expectations
Status: EXTREME STRESS
Action: ❌ AVOID short vega!
```

## ⚡ Enhanced Regimes

### 1. Normal Contango
```
VIX: 15-20
Ratio: 0.90-0.95
Structure: CONTANGO

Trading:
✅ Short vega: YES
📅 Max DTE: 45 days
💡 Strategy: Iron Condors, Credit Spreads
```

### 2. Elevated Contango
```
VIX: 20-30
Ratio: 0.95-1.0
Structure: CONTANGO

Trading:
✅ Short vega: YES (caution)
📅 Max DTE: 30 days
💡 Strategy: Tighter strikes, smaller size
```

### 3. High Vol Contango
```
VIX: 30-40
Ratio: 0.95-1.0
Structure: CONTANGO

Trading:
⚠️ Short vega: CAUTION
📅 Max DTE: 21 days (short DTE only)
💡 Strategy: Weekly spreads, tight management
```

### 4. Backwardation (ANY VIX)
```
VIX: ANY
Ratio: > 1.0
Structure: BACKWARDATION

Trading:
❌ Short vega: NO
📅 Max DTE: 0 (don't enter)
💡 Strategy: WAIT or Long vega only
```

### 5. Extreme Backwardation
```
VIX: > 40
Ratio: > 1.1
Structure: SEVERE BACKWARDATION

Trading:
❌ Short vega: ABSOLUTELY NOT
📅 Max DTE: 0
💡 Strategy: Cash or long volatility
⚠️ Example: 2008 crisis, COVID March 2020
```

## 🎯 Implementation

### VIX Monitor Enhanced

```python
from analysis.vix_monitor_enhanced import get_vix_monitor

monitor = get_vix_monitor()

# Update with term structure
await monitor.update(ibkr_connection)

# Get regime
regime = monitor.get_current_regime()
# Returns: 'NORMAL', 'ELEVATED', 'HIGH_VOL',
#          'ELEVATED_BACKWARDATION', 'HIGH_VOL_BACKWARDATION',
#          'EXTREME_STRESS'

# Check if short vega allowed
decision = monitor.should_trade_short_vega()
if decision['allowed']:
    max_dte = decision.get('max_dte', 45)
    # Trade with max DTE
else:
    # Skip trading
```

### Trading Decision Logic

```python
# Before entering Iron Condor
vega_check = monitor.should_trade_short_vega()

if not vega_check['allowed']:
    logger.warning(
        f"⚠️ Short vega NOT allowed: {vega_check['reason']}\n"
        f"   VIX: {vega_check['vix']:.2f}\n"
        f"   Ratio: {vega_check['ratio']:.3f}\n"
        f"   Structure: {vega_check['structure']}"
    )
    return  # SKIP TRADE

# If allowed, use recommended DTE
max_dte = monitor.get_recommended_dte()
logger.info(f"Max DTE for current regime: {max_dte} days")
```

## 📈 Historical Examples

### COVID Crash (March 2020)
```
Date: March 16, 2020
VIX: 82.69
VIX3M: ~60
Ratio: 1.38 (EXTREME BACKWARDATION)

Regime: EXTREME_STRESS
Action: ❌ NO short vega
Result: VIX dropped 50% in weeks
        Short vega = disaster
```

### Normal Bull Market (2021)
```
VIX: 16
VIX3M: 18
Ratio: 0.89 (CONTANGO)

Regime: NORMAL
Action: ✅ Short vega OK
Result: Consistent premium decay
```

### 2022 Ukraine Invasion
```
VIX: 38
VIX3M: 32
Ratio: 1.19 (BACKWARDATION)

Regime: HIGH_VOL_BACKWARDATION
Action: ❌ Avoid short vega
Result: Whipsaw volatility
```

## ⚙️ Configuration

### Regime Thresholds

```python
regimes = {
    'NORMAL': {
        'vix_max': 20,
        'ratio_max': 1.0
    },
    'ELEVATED': {
        'vix_max': 30,
        'ratio_max': 1.05
    },
    'BACKWARDATION': {
        'ratio_min': 1.0  # Any ratio > 1.0
    }
}
```

### DTE Recommendations

```python
dte_by_regime = {
    'NORMAL': 45,
    'ELEVATED': 30,
    'HIGH_VOL': 21,
    'BACKWARDATION': 0  # Don't trade
}
```

## 🚨 Critical Warnings

### Never Ignore Backwardation
```
Even if VIX is "only" 25:
  If ratio > 1.0 → BACKWARDATION
  → Market is in PANIC mode
  → Avoid short vega!
```

### Term Structure > Spot VIX
```
VIX = 20 (seems normal)
Ratio = 1.15 (backwardation!)

→ Trust the ratio!
→ Market is stressed
→ Don't trade short vega
```

## ✅ Best Practices

1. **Check BOTH metrics**
   - VIX level
   - VIX/VIX3M ratio

2. **Backwardation = RED FLAG**
   - Always skip short vega
   - No exceptions

3. **Use shorter DTE in stress**
   - High VIX + contango = 21 DTE max
   - Normal = 45 DTE OK

4. **Log term structure**
   ```
   VIX: Spot=25, 3M=23, Ratio=1.09 (BACKWARDATION)
   → Decision: Skip short vega
   ```

---

**Status:** Production-ready ✅  
**Impact:** Prevents catastrophic entries  
**Key metric:** VIX/VIX3M ratio 🎯
