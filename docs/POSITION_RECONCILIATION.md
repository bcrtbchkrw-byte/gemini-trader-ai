# Position Reconciliation

## 🎯 Problem

**Scenario:**
```
1. Bot running, has open positions in DB
2. Raspberry Pi crashes / restart
3. While offline:
   - You manually close position in TWS
   - OR IBKR closes it (margin call)
4. Bot starts again
5. DB still shows position as OPEN
6. Bot thinks it has allocated capital
7. PositionSizer makes wrong calculations
8. ExitManager tries to close non-existent position
```

**Result:** System state is BROKEN ⚠️

## ✅ Solution: Position Reconciliation

### On Every Startup

```python
# In main.py initialize()
reconciler = get_position_reconciler(db, ibkr)
report = await reconciler.reconcile_positions()
```

### What It Does

**1. Get DB Positions**
```sql
SELECT * FROM positions WHERE status = 'OPEN'
```

**2. Get IBKR Portfolio**
```python
portfolio = ib.portfolio()  # Real positions
```

**3. Compare**
```
DB says OPEN but NOT in IBKR?
→ Mark as CLOSED_EXTERNALLY

In IBKR but NOT in DB?
→ Warn (manual entry?)
```

**4. Update DB**
```sql
UPDATE positions
SET status = 'CLOSED_EXTERNALLY',
    exit_date = NOW(),
    exit_reason = 'External close'
WHERE id = ?
```

## 📊 Reconciliation Report

### Example Output

```
============================================================
🔄 POSITION RECONCILIATION - Syncing DB with IBKR
============================================================
📊 Database: 3 open positions
📈 IBKR Portfolio: 2 positions

============================================================
📊 RECONCILIATION REPORT
============================================================
✅ Matched: 2 positions
⚠️  Closed Externally: 1 position
   - AAPL: 2 contracts (entry: 2024-11-25)

All positions synced!
============================================================
```

## 🎯 Use Cases

### Case 1: Manual TWS Close
```
DB: AAPL position OPEN (2 contracts)
IBKR: No AAPL position

Action: Mark AAPL as CLOSED_EXTERNALLY
Result: ✅ DB now accurate
```

### Case 2: Margin Call
```
DB: NVDA position OPEN (5 contracts)
IBKR: No NVDA position (liquidated)

Action: Mark NVDA as CLOSED_EXTERNALLY
Reason: "External close detected"
Result: ✅ Prevents ghost positions
```

### Case 3: All Matched
```
DB: AAPL, MSFT OPEN
IBKR: AAPL, MSFT positions

Action: None (perfect sync)
Result: ✅ System healthy
```

### Case 4: Manual IBKR Entry
```
DB: AAPL OPEN
IBKR: AAPL + GOOGL positions

Action: Warn about GOOGL
Result: ⚠️ User entered GOOGL manually
```

## 🔧 Implementation

### Database Schema

```sql
-- New status value
status IN (
  'OPEN',
  'CLOSED',
  'CLOSED_EXTERNALLY',  -- New!
  'EXPIRED'
)

-- New column
exit_reason TEXT  -- e.g., "External close detected"
```

### Integration Points

**1. Startup (main.py)**
```python
async def initialize(self):
    # ... connect to IBKR ...
    
    # RECONCILE before anything else
    reconciler = get_position_reconciler(db, ibkr)
    await reconciler.reconcile_positions()
    
    # Now safe to proceed
```

**2. PositionSizer**
```python
# Now sees accurate capital allocation
allocated = sum(pos.capital for pos in db.positions if pos.status == 'OPEN')
# Excludes CLOSED_EXTERNALLY positions ✅
```

**3. ExitManager**
```python
# Only tries to close positions that exist
open_positions = [p for p in db.positions if p.status == 'OPEN']
# Skips CLOSED_EXTERNALLY ✅
```

## ⚙️ Configuration

### Reconciliation Frequency

**On Startup (default):**
```python
# In main.py initialize()
await reconciler.reconcile_positions()
```

**Periodic (optional):**
```python
# Every 1 hour during trading
async def periodic_reconciliation():
    while True:
        await asyncio.sleep(3600)  # 1 hour
        await reconciler.reconcile_positions()
```

## 🎯 Benefits

### 1. Data Integrity
```
Before: DB may have stale data
After: DB always matches reality ✅
```

### 2. Accurate Capital
```
Before: PositionSizer thinks capital allocated
After: Knows exact free capital ✅
```

### 3. No Ghost Exits
```
Before: ExitManager tries closing non-existent position
After: Only closes real positions ✅
```

### 4. Audit Trail
```
status = 'CLOSED_EXTERNALLY'
exit_reason = 'External close detected during reconciliation'
→ Know what happened ✅
```

## 🚨 Edge Cases

### Multiple Legs (Spreads)
```python
# Reconciliation checks ALL legs
# If ANY leg missing → mark entire position CLOSED_EXTERNALLY
```

### Partial Closes
```python
# DB: 5 contracts
# IBKR: 3 contracts
# Action: Update DB to 3 contracts (partial close)
```

### Same Symbol, Different Strategies
```python
# DB: Iron Condor on SPY
# IBKR: Different SPY position
# Action: Warn - may require manual review
```

---

**Status:** Production-critical feature ✅  
**When:** Runs on EVERY startup automatically  
**Impact:** Prevents catastrophic state inconsistency 🎯
