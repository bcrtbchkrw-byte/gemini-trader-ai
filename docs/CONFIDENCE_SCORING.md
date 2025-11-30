# Confidence-Based Trade Approval

## 🎯 Problem

**Before:** Binary decision (APPROVED / REJECTED)
```python
verdict = "SCHVÁLENO"  # No differentiation between:
# - Perfect setup (should be 10/10)
# - Barely acceptable (should be 6/10)
```

**Risk:** Trading marginal setups that Claude wasn't truly confident about.

---

## ✅ Solution: Confidence Scoring (1-10)

### New Approach
```python
result = await claude.analyze_strategy(
    stock_data=stock_data,
    options_data=greeks_data,
    strategy_type="CREDIT_SPREAD"
)

# Returns:
{
    'confidence_score': 9,  # 1-10 scale
    'decision': 'APPROVE',
    'strengths': [...],
    'risks': [...],
    'reasoning': "..."
}
```

### Confidence Scale

| Score | Meaning | Action |
|-------|---------|--------|
| 1-3 | Low confidence - clear red flags | ❌ Reject |
| 4-6 | Medium - some concerns | ❌ Reject |
| 7-8 | Good - minor concerns | ⚠️ Reject (below threshold) |
| **9-10** | **High confidence - strong setup** | **✅ Approve** |

**Threshold:** Only trades with **confidence >= 9/10** are executed.

---

## 📊 Example Outputs

### Example 1: Strong Setup (Approved)
```
Symbol: AAPL
Confidence: 9/10
Decision: APPROVE

Strengths:
- High IV rank (72%) ideal for selling premium
- Tight bid-ask spread (excellent liquidity)
- Earnings 60 days away

Risks:
- Tech sector volatility
- Fed announcement next week (minor)

✅ APPROVED - High conviction trade
```

### Example 2: Marginal Setup (Rejected)
```
Symbol: TSLA
Confidence: 7/10
Decision: REJECT

Strengths:
- Good IV rank (65%)
- Acceptable volume

Risks:
- Wide bid-ask spread on OTM strikes
- Sector rotation uncertainty
- Recent news catalyst unpredictable

❌ REJECTED - Confidence 7/10 below threshold of 9
Reason: Liquidity concerns and uncertain catalysts
```

### Example 3: Weak Setup (Rejected)
```
Symbol: XYZ
Confidence: 4/10
Decision: REJECT

Strengths:
- None significant

Risks:
- Earnings in 7 days (blackout window)
- Low volume (< 500K daily)
- Wide bid-ask spreads

❌ REJECTED - Confidence 4/10 below threshold of 9
Reason: Multiple red flags - avoid
```

---

## 🔧 Implementation

### In `main.py` (Phase 3)
```python
# OLD: Binary decision
claude_result = await claude.analyze_greeks_and_recommend(...)
verdict = recommendation.get('verdict')  # SCHVÁLENO or ZAMÍTNUTO

# NEW: Confidence-based
claude_result = await claude.analyze_strategy(
    stock_data={'symbol': symbol, 'price': price, ...},
    options_data={'delta': delta, 'vega': vega, ...},
    strategy_type="CREDIT_SPREAD"
)

confidence = claude_result.get('confidence_score', 0)
approved = claude_result.get('approved', False)

if approved:  # Only if confidence >= 9
    logger.info(f"✅ APPROVED - Confidence {confidence}/10")
else:
    logger.info(f"❌ REJECTED - Confidence {confidence}/10")
```

### Logging Output
```
Phase 3: Claude Strategy + IBKR Greeks
--------------------------------------------------------------
Analyzing AAPL...
   🔥 Confidence: 9/10 - APPROVE
   ✅ APPROVED - High conviction trade

Analyzing TSLA...
   ⚠️ Confidence: 7/10 - REJECT
   ❌ REJECTED - Liquidity concerns

Analyzing NVDA...
   ❌ Confidence: 5/10 - REJECT
   ❌ REJECTED - Earnings risk
```

---

## 📈 Impact

### Before (Binary Approval)
```
10 strategies analyzed
5 approved ("SCHVÁLENO")
  - 2 were actually 9-10/10 (strong)
  - 3 were actually 6-7/10 (marginal)
  
→ Marginal trades executed
→ Lower win rate
```

### After (Confidence Threshold)
```
10 strategies analyzed
2 approved (confidence >= 9/10)
  - All are truly strong setups
8 rejected (confidence < 9)
  - Including 3 that were previously approved
  
→ Only high-conviction trades
→ Higher win rate
```

**Quality > Quantity** ✅

---

## ⚙️ Configuration

### Adjusting Threshold

**In `ai/claude_client.py`:**
```python
# Current: 9/10 threshold (conservative)
if confidence >= 9:
    analysis['decision'] = 'APPROVE'

# To be more aggressive (not recommended):
if confidence >= 7:  # Lower threshold
    analysis['decision'] = 'APPROVE'

# To be even more conservative:
if confidence >= 10:  # Perfect setups only
    analysis['decision'] = 'APPROVE'
```

**Recommendation:** Keep at **9/10**. Better to miss opportunities than take marginal trades.

---

## 🎓 Claude's Conservative Bias

Claude is instructed to be conservative:
```
"Be conservative. If unsure, confidence should be 7 or below.
Quality > Quantity. Better to skip marginal setups."
```

This means:
- **9/10:** Strong conviction, clear edge
- **7-8/10:** Good but with concerns → Skip
- **<7/10:** Weak or red flags → Definitely skip

---

## ✅ Benefits

1. **Higher Win Rate:** Only trade strong setups
2. **Risk Reduction:** Avoid marginal edge
3. **Transparency:** Know *why* trades are approved
4. **Iterative Learning:** Review rejected 7-8/10 trades to refine criteria

---

**Status:** Production-ready ✅  
**Default Threshold:** 9/10  
**Impact:** Filters ~60% more trades vs binary approval 🎯
