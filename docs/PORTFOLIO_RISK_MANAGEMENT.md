# Portfolio Risk Manager - Beta-Weighted Delta

## 🎯 Purpose

Prevents over-concentration risk by tracking **beta-weighted delta** across all positions.

**Why Beta-Weighted Delta?**
- Different stocks have different volatility (beta)
- 100 delta in TSLA (beta=2.0) ≠ 100 delta in SPY (beta=1.0)
- Beta-weighting normalizes everything to SPY-equivalent

## 📊 Key Concepts

### Beta
**Definition:** Stock's correlation to market (SPY)
- Beta = 1.0: Moves with market (SPY)
- Beta = 1.5: Moves 50% more than market
- Beta = 0.5: Moves 50% less than market

### Beta-Weighted Delta
**Formula:** `BWD = Position Delta × Beta`

**Example:**
```
TSLA: 50 delta × 2.0 beta = 100 BWD
SPY:  50 delta × 1.0 beta = 50 BWD

Even though both are 50 delta, TSLA has 2x the market risk!
```

## ✅ Implementation

### Basic Usage

```python
from risk.portfolio_risk_manager import get_portfolio_risk_manager

# Initialize (limits in delta units)
pm = get_portfolio_risk_manager(
    max_beta_weighted_delta=100.0,  # Max SPY-equivalent exposure
    max_net_delta=50.0               # Max raw delta
)

# Add position
pm.add_position(
    symbol="AAPL",
    contracts=2,                    # 2 contracts
    delta_per_contract=0.30,        # 30 delta per contract
    strategy_type="PUT_SPREAD",
    beta=1.2                        # AAPL beta
)

# Get portfolio metrics
metrics = pm.get_portfolio_metrics()
print(f"Beta-Weighted Delta: {metrics['beta_weighted_delta']}")
print(f"Net Delta: {metrics['net_delta']}")

# Check if new trade is allowed
approval = pm.check_new_trade(
    symbol="NVDA",
    proposed_delta=40.0,  # Want to add 40 delta
    beta=1.8              # NVDA beta
)

if approval['approved']:
    print("✅ Trade approved")
    # Execute trade...
else:
    print(f"❌ Trade rejected: {approval['issues']}")
```

### Integration Example

```python
# In main trading loop
async def execute_trade(symbol, strategy, greeks):
    pm = get_portfolio_risk_manager()
    
    # Calculate proposed delta
    contracts = 2
    delta_per_contract = greeks['delta']
proposed_delta = contracts * delta_per_contract * 100
    
    # Check portfolio limits BEFORE executing
    approval = pm.check_new_trade(symbol, proposed_delta)
    
    if not approval['approved']:
        logger.warning(f"Portfolio limits prevent trade: {approval['issues']}")
        return {'status': 'REJECTED', 'reason': 'PORTFOLIO_LIMITS'}
    
    # Execute trade
    result = await order_executor.execute(...)
    
    # Add to portfolio tracking
    if result['status'] == 'FILLED':
        pm.add_position(
            symbol=symbol,
            contracts=contracts,
            delta_per_contract=delta_per_contract,
            strategy_type=strategy
        )
    
    return result
```

## 📈 Example Scenarios

### Scenario 1: Balanced Portfolio
```
Positions:
  AAPL: +30 delta × 1.2 beta = +36 BWD
  MSFT: +25 delta × 1.1 beta = +27.5 BWD
  SPY:  -50 delta × 1.0 beta = -50 BWD

Net BWD: +13.5 (balanced)
Status: ✅ Safe
```

### Scenario 2: Over-Concentrated
```
Positions:
  NVDA: +50 delta × 1.8 beta = +90 BWD
  TSLA: +40 delta × 2.0 beta = +80 BWD

Net BWD: +170 (EXCEEDS limit of 100)
Status: ❌ Reject new bullish trades
```

### Scenario 3: Proposed Trade
```
Current Portfolio:
  Net BWD: +75

Proposed Trade:
  AAPL Put Spread: +35 delta × 1.2 beta = +42 BWD

New Portfolio:
  Net BWD: +117 (EXCEEDS limit!)

Decision: ❌ REJECT
```

## 🎛️ Configuration

```python
# Conservative (lower risk)
pm = get_portfolio_risk_manager(
    max_beta_weighted_delta=50.0,   # Tight limit
    max_net_delta=25.0
)

# Aggressive (higher risk)
pm = get_portfolio_risk_manager(
    max_beta_weighted_delta=200.0,  # Loose limit
    max_net_delta=100.0
)

# Recommended for starting
pm = get_portfolio_risk_manager(
    max_beta_weighted_delta=100.0,  # Moderate
    max_net_delta=50.0
)
```

## 📊 Portfolio Report

```python
print(pm.get_risk_report())
```

**Output:**
```
============================================================
Portfolio Risk Report
============================================================

Position Count: 3

Delta Metrics:
  Net Delta:              +45.00
  Beta-Weighted Delta:    +52.50
  Bullish Exposure:       +80.00
  Bearish Exposure:       -27.50

Limits:
  Max Beta-Weighted:      100.00
  Max Net Delta:          50.00

Utilization:
  BW Delta:               52.5%
  Net Delta:              90.0%

============================================================
```

## 🔧 Advanced Features

### Custom Beta Values
```python
# Override cached beta
pm.beta_cache['CUSTOM'] = 1.5

# Or pass directly
pm.add_position(
    symbol="CUSTOM",
    contracts=1,
    delta_per_contract=0.25,
    strategy_type="IRON_CONDOR",
    beta=1.5  # Custom beta
)
```

### Directional Protection
- Bullish limit: 80% of max BWD
- Bearish limit: 80% of max BWD
- Prevents excessive one-sided exposure

## ✅ Best Practices

1. **Check before every trade**
   ```python
   approval = pm.check_new_trade(symbol, delta, beta)
   if not approval['approved']:
       return  # Don't execute
   ```

2. **Update on fills**
   ```python
   if trade_filled:
       pm.add_position(...)
   ```

3. **Remove on exits**
   ```python
   if position_closed:
       pm.remove_position(symbol)
   ```

4. **Review daily**
   ```python
   print(pm.get_risk_report())
   ```

## 🎯 Production Integration

```python
# In main.py or trading loop
from risk.portfolio_risk_manager import get_portfolio_risk_manager

pm = get_portfolio_risk_manager(
    max_beta_weighted_delta=100.0,
    max_net_delta=50.0
)

# Before Phase 3 execution
for recommendation in approved_trades:
    approval = pm.check_new_trade(
        symbol=recommendation['symbol'],
        proposed_delta=recommendation['position_delta']
    )
    
    if not approval['approved']:
        logger.warning(
            f"Skipping {recommendation['symbol']}: "
            f"Portfolio limits - {approval['issues']}"
        )
        continue
    
    # Execute trade...
```

---

**Status:** Production-ready ✅
**Risk Reduction:** Prevents over-concentration 🎯
**Integration:** Plug-and-play with existing system 🔌
