# 3-Phase Screening Pipeline

## 📊 Overview

The 3-phase pipeline efficiently filters stocks from thousands of candidates down to 2-3 executable trades.

## 🔄 Pipeline Flow

```
Universe (3000+ stocks)
    ↓
Phase 1: Pre-check (Free, Local)
    ↓ (~10 candidates)
Phase 1.5: Earnings Blackout Filter ⚡ NEW
    ↓ (~7-10 candidates)
Phase 2: Gemini Analysis ($$$, Expensive)
    ↓ (~2-3 winners)
Phase 3: Claude Strategy ($$, Greeks)
    ↓ (1-2 approved trades)
Execute
```

## 📝 Phase Details

### Phase 1: Pre-Check (Free, Local)
**Purpose:** Filter on basic criteria without API costs.

**Filters:**
- Price: $20 - $300
- Volume: > 1M daily
- IV Rank: > 50 (for selling premium)
- Liquidity: Enough option volume

**Duration:** ~5 seconds  
**Output:** ~10 candidates

---

### Phase 1.5: Earnings Blackout Filter ⚡ **NEW**
**Purpose:** Remove stocks in earnings blackout window **BEFORE** expensive Gemini calls.

**Why this phase?**
- **Saves Money:** Avoids Gemini API costs on stocks we won't trade anyway
- **Efficiency:** Filters ~30% of candidates (stocks with earnings within 48h)
- **Safety:** Prevents trading into earnings volatility

**How it works:**
```python
from analysis.earnings_checker import get_earnings_checker

checker = get_earnings_checker()
safe_symbols = await checker.filter_safe_symbols(candidate_symbols)
# Returns only stocks NOT in 48h earnings window
```

**Duration:** ~2-3 seconds  
**Typical Filter Rate:** 20-40% removed  
**Output:** ~7-10 "clean" candidates

**Example:**
```
Phase 1:     10 candidates [NVDA, AAPL, MSFT, META, AMZN, TSLA, GOOGL, AMD, PLTR, SNOW]
Phase 1.5:   3 filtered    [NVDA, META, TSLA] ← Earnings this week
             ↓
             7 clean        [AAPL, MSFT, AMZN, GOOGL, AMD, PLTR, SNOW]
Phase 2:     Gemini analyzes ONLY the 7 clean stocks → saves 30% API cost
```

---

### Phase 2: Gemini Analysis ($$$, Expensive)
**Purpose:** Deep fundamental analysis with news sentiment.

**Gemini analyzes:**
- Fundamental strength (earnings, revenue, margins)
- News sentiment (recent articles)
- Sector rotation
- Risk factors

**Duration:** ~10-20 seconds  
**Cost:** ~$0.05 per batch (10 stocks)  
**Output:** 2-3 winners

---

### Phase 3: Claude Strategy ($$, Greeks)
**Purpose:** Precise strategy selection with real Greeks from IBKR.

**Claude evaluates:**
- Live option Greeks (Delta, Vega, Theta, Vanna)
- Strike selection
- Risk/Reward ratio
- Position sizing
- Final approval (SCHVÁLENO / ZAMÍTNUTO)

**Duration:** ~30 seconds (IBKR connection + Greeks)  
**Cost:** ~$0.02 per stock  
**Output:** 1-2 approved trades

---

## 💰 Cost Savings with Phase 1.5

**Before (Phase 1 → Phase 2 directly):**
```
10 candidates → Gemini analyzes all 10
API Cost: $0.05 per batch
```

**After (Phase 1 → Phase 1.5 → Phase 2):**
```
10 candidates → 7 clean → Gemini analyzes 7
API Cost: $0.035 per batch
Savings: 30% reduction
```

**Monthly Savings (20 trading days):**
- Before: $0.05 × 20 = $1.00 / month
- After: $0.035 × 20 = $0.70 / month
- **Savings: $0.30 / month (30%)**

Not huge in absolute terms, but adds up over time and prevents wasted analysis.

---

## 🎯 Example Pipeline Run

```
Phase 1: Pre-check
  Scanned: 3000 stocks
  Passed: 10 candidates
  
Phase 1.5: Earnings Filter ← NEW
  Input: 10 candidates
  Filtered: 3 (earnings blackout)
    - NVDA: Earnings in 24h
    - META: Earnings in 36h
    - TSLA: Earnings tomorrow
  Passed: 7 clean stocks
  
Phase 2: Gemini Analysis
  Analyzed: 7 stocks (saved 3 API calls!)
  Winners: 2 stocks [AAPL, MSFT]
  
Phase 3: Claude Strategy
  Analyzed: 2 stocks
  Approved: 1 trade [AAPL Iron Condor]
```

---

## 🛠️ Configuration

### Earnings Blackout Window
Default: **48 hours** before/after earnings

```python
# In .env or config
EARNINGS_BLACKOUT_HOURS=48  # Adjust if needed
```

### Why 48 hours?
- **24h before:** IV often spikes
- **24h after:** Price volatility, gap risk
- **48h total:** Conservative, safe window

---

## 📈 Performance Impact

| Metric | Before Phase 1.5 | After Phase 1.5 |
|--------|------------------|-----------------|
| Gemini API calls | 10 stocks | ~7 stocks |
| API cost per run | $0.05 | $0.035 |
| Trades into earnings | Occasional | Zero ✅ |
| Pipeline duration | 40s | 43s (+3s) |

**Verdict:** Tiny time cost (+3s) for 30% savings + zero earnings risk. Great tradeoff! 🎯

---

**Status:** Production-ready ✅  
**Since:** Phase 1.5 integrated  
**Impact:** 30% API savings + safer trading
