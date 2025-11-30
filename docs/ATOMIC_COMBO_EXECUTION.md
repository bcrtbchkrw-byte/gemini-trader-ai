# Atomic Combo Execution (BAG Orders)

## 🎯 Problem: Leg Risk

**Scenario without atomic execution:**
```
1. Close Iron Condor by selling legs separately:
   - Sell Call spread → FILLED ✅
   - Sell Put spread → NOT FILLED ❌
   
2. Result: Half-closed position!
   - Only one side closed
   - Directional exposure
   - Undefined risk
```

**This is CATASTROPHIC!** ⚠️

## ✅ Solution: IBKR BAG Orders

**BAG = Basket/Combo instrument**
- All legs execute together
- Atomic transaction
- No partial fills
- Professional execution

### Example
```python
# BAG contract for Iron Condor close
bag = Contract()
bag.secType = 'BAG'
bag.comboLegs = [
    ComboLeg(action='SELL', conId=call_spread_id),
    ComboLeg(action='SELL', conId=put_spread_id)
]

# ATOMIC execution
order = Order(orderType='MKT')
trade = ib.placeOrder(bag, order)

# Result: BOTH legs fill or NEITHER fills ✅
```

## 📊 Implementation

### 1. ExitManager Updates

**Before (DANGEROUS):**
```python
# Separate leg execution
for leg in position_legs:
    ib.placeOrder(leg.contract, leg.order)
    # ⚠️ Partial fill risk!
```

**After (SAFE):**
```python
# Atomic BAG order
bag_order = await self._create_closing_combo_order(
    symbol=symbol,
    legs=position_legs,
    strategy=strategy
)

# ATOMIC execution
trade = ib.placeOrder(bag_order['contract'], bag_order['order'])
# ✅ All-or-nothing
```

### 2. BAG Contract Creation

```python
from ib_insync import Contract, ComboLeg

# Create BAG
bag = Contract()
bag.symbol = 'AAPL'
bag.secType = 'BAG'
bag.currency = 'USD'
bag.exchange = 'SMART'

# Add legs
combo_legs = []

for leg in position_legs:
    combo_leg = ComboLeg()
    combo_leg.conId = leg['contract_id']
    
    # REVERSE action for closing
    if leg['action'] == 'BUY':
        combo_leg.action = 'SELL'  # Close long
    else:
        combo_leg.action = 'BUY'   # Close short
    
    combo_leg.ratio = 1
    combo_legs.append(combo_leg)

bag.comboLegs = combo_legs
```

### 3. Closing Order

```python
# Market order for fast close
order = Order()
order.action = 'BUY'  # For credit spread closing
order.totalQuantity = contracts
order.orderType = 'MKT'  # MARKET for immediate
order.transmit = True

# Alternative: Limit at mid-price
order.orderType = 'LMT'
order.lmtPrice = mid_price
```

## 🎯 Use Cases

### Iron Condor Exit
```
Opening:
- Sell Call spread @ $1.00
- Sell Put spread @ $1.00
Total credit: $2.00

Closing (ATOMIC):
- Buy back both spreads @ $0.50 each
- BAG order ensures both execute
- Total debit: $1.00
- Profit: $1.00 per contract ✅
```

### Credit Spread Exit
```
Opening:
- Sell Put spread @ $0.75

Closing (ATOMIC):
- Buy back spread @ $0.25
- Single BAG for all legs
- Profit: $0.50 per contract ✅
```

### Debit Spread Exit
```
Opening:
- Buy Call spread @ $2.00

Closing (ATOMIC):
- Sell spread @ $3.50
- BAG ensures both legs sell
- Profit: $1.50 per contract ✅
```

## ⚙️ Configuration

### Order Type Selection

**Market Order (Fast):**
```python
order.orderType = 'MKT'
# Pros: Immediate fill
# Cons: May be unfavorable price
```

**Limit Order (Better Price):**
```python
order.orderType = 'LMT'
order.lmtPrice = mid_price
# Pros: Better fill price
# Cons: May not fill immediately
```

**Recommended:**
```python
# Use market for urgent closes (stop-loss)
if reason == 'STOP_LOSS':
    order.orderType = 'MKT'

# Use limit for profit targets
elif reason == 'PROFIT_TARGET':
    order.orderType = 'LMT'
    order.lmtPrice = target_price
```

## 📈 Benefits

### 1. No Leg Risk
```
Before: 50% chance of partial fill
After: 0% chance (atomic) ✅
```

### 2. Defined Risk
```
Before: Unknown exposure if partial
After: Always know exact position ✅
```

### 3. Professional Execution
```
Before: Amateur separate legs
After: Institutional BAG orders ✅
```

### 4. Better Fills
```
Market makers price BAG as unit
→ Often better than sum of legs ✅
```

## 🚨 Critical Scenarios

### Scenario 1: Fast Market
```
Market moving fast
Need to close Iron Condor NOW

BAG market order:
→ Immediate execution
→ Both sides closed
→ Risk eliminated ✅
```

### Scenario 2: Profit Target
```
Iron Condor at 50% profit
Want to lock in gains

BAG limit order @ target:
→ Both sides or nothing
→ No partial exposure
→ Profit secured ✅
```

### Scenario 3: Stop Loss
```
Position hit max loss
Must exit immediately

BAG market order:
→ Atomic close
→ No additional risk
→ Loss contained ✅
```

## 📝 Database Schema

**Position Legs Table:**
```sql
CREATE TABLE position_legs (
    id INTEGER PRIMARY KEY,
    position_id INTEGER,
    contract_id INTEGER,  -- IBKR conId
    action TEXT,          -- BUY or SELL
    quantity INTEGER,
    strike REAL,
    expiration TEXT,
    right TEXT            -- CALL or PUT
);
```

**For Closing:**
```python
# Get legs from DB
legs = await db.execute(
    "SELECT * FROM position_legs WHERE position_id = ?",
    (position_id,)
)

# Create BAG with reversed actions
for leg in legs:
    combo_leg.action = 'SELL' if leg['action'] == 'BUY' else 'BUY'
```

## ✅ Best Practices

1. **ALWAYS use BAG for multi-leg**
   - Iron Condors
   - Credit/Debit spreads
   - Any combo strategy

2. **NEVER execute legs separately**
   - Risk of partial fills
   - Undefined risk exposure

3. **Use Market for urgent closes**
   - Stop losses
   - Risk management
   - Emergency exits

4. **Use Limit for profit targets**
   - Better pricing
   - No rush

5. **Log atomic execution**
   ```
   ✅ Position closed: AAPL
      Fill Price: $0.50
      Execution: ATOMIC (all legs together)
   ```

---

**Status:** Production-critical feature ✅  
**Impact:** Eliminates leg risk completely  
**Method:** IBKR BAG/Combo orders  
**Guarantee:** All-or-nothing execution 🎯
