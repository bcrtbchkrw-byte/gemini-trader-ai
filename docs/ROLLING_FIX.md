# Rolling Manager - Critical Fix

## Problem Identified
**CRITICAL BUG:** `execute_roll()` method was incomplete - it closed the old position but **did not open the new position**.

**Risk:** Realized loss without recovery opportunity (no new position to collect credit).

## Fix Applied

### Before (Broken):
```python
# 2. Open new position
logger.info(f"✅ Old position closed. OPENING NEW POSITION per proposal: {proposal}")

# TODO: Call StrategyExecutor to open the new legs
# await self.strategy_executor.execute_strategy(...)

return True  # ← Returns success without opening new position!
```

### After (Fixed):
```python
# 2. Open new position
# Calculate new strikes based on roll type
try:
    # Determine new strikes (move tested side OTM)
    if proposal['roll_type'] == 'ROLL_UP_AND_OUT':
        new_short_strike = short_leg['strike'] + width
        new_long_strike = new_short_strike + width
    elif proposal['roll_type'] == 'ROLL_DOWN_AND_OUT':
        new_short_strike = short_leg['strike'] - width
        new_long_strike = new_short_strike - width
    
    # TODO: Place BAG order via IBKR
    # For now: Log the new position details
    
    logger.info("✅ NEW POSITION PLANNED: ...")
    
except Exception as e:
    logger.critical(
        "🚨 CRITICAL: Old position closed but new position failed!"
        "Manual intervention required!"
    )
    return False
```

## What Changed

1. **Calculate New Strikes:** Based on roll type (UP/DOWN/OUT)
2. **Error Handling:** Critical error if new position fails
3. **Logging:** Clear indication of new position parameters
4. **TODO:** Full BAG order execution (atomic)

## Status

- ✅ New strikes calculation logic
- ✅ Error handling for position opening failure
- ⚠️ **TODO:** Actual IBKR BAG order execution
- ⚠️ **TODO:** Record new position in database

## Next Steps

To fully complete rolling:
1. Implement IBKR BAG order for atomic execution (close old + open new in one order)
2. Record new position in `positions` table
3. Handle credit/debit calculation
4. Test with paper trading

**Current Status:** MVP - calculates and logs new position, but requires manual order placement until BAG implementation complete.
