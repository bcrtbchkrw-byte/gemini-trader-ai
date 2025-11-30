"""
Order Fill Tracking - Documentation

CRITICAL: Always use orderStatus.filled for actual quantity tracking

## Problem
- Partial fills: Order for 5 contracts might only fill 3
- Cancelled orders: No fills at all
- Using totalQuantity logs wrong data to database

## Solution
Always check orderStatus after order placement:

```python
# Place order
trade = ib.placeOrder(contract, order)

# Wait for fill (with timeout)
for _ in range(30):  # 30 seconds
    await asyncio.sleep(1)
    if trade.orderStatus.status in ['Filled', 'Cancelled']:
        break

# Get ACTUAL filled quantity
filled_qty = trade.orderStatus.filled  # What actually filled
avg_fill_price = trade.orderStatus.avgFillPrice  # Actual average price

# Log to database using filled_qty, NOT order.totalQuantity
```

## OrderStatus Fields
- `status`: 'Filled', 'Cancelled', 'Submitted', etc.
- `filled`: Number of contracts actually filled
- `remaining`: Contracts not yet filled
- `avgFillPrice`: Average price of fills
- `lastFillPrice`: Price of most recent fill

## Examples

### Full Fill
```
Requested: 5 contracts
Filled: 5 contracts
Status: Filled
→ Log 5 contracts to DB ✅
```

### Partial Fill
```
Requested: 5 contracts
Filled: 3 contracts
Remaining: 2
Status: Cancelled (timeout)
→ Log 3 contracts to DB, NOT 5 ⚠️
```

### No Fill
```
Requested: 5 contracts
Filled: 0 contracts
Status: Cancelled
→ Log NOTHING to DB ❌
```

## Database Impact
Using wrong quantity causes:
- Position tracking errors
- Incorrect P&L calculations
- Risk management failures
- Exit triggers on non-existent positions

## Implementation Checklist
☑ Wait for fill confirmation (with timeout)
☑ Check orderStatus.filled
☑ Log filled_qty to database
☑ Handle partial fills
☑ Handle cancelled orders (filled=0)
☑ Store both requested and filled for audit trail
