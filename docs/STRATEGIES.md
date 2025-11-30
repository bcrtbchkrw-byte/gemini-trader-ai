# Advanced Trading Strategies Guide

## Overview

This document describes all available options trading strategies in the Gemini Trader AI system.

---

## Premium Selling Strategies (High IV)

### 1. Iron Condor

**Structure:** OTM call credit spread + OTM put credit spread

**Best Conditions:**
- VIX: 20-30 (High volatility)
- Market: Range-bound, neutral outlook
- Time: 30-45 DTE

**Greeks:**
- Positive Theta (time decay working for you)
- Negative Vega (benefits from IV crush)
- Near-zero Delta (neutral position)

**Example:**
```
Stock @ $100
Sell 110 Call / Buy 115 Call  (+$0.50 credit)
Sell 90 Put / Buy 85 Put      (+$0.50 credit)
Total Credit: $1.00 ($100 per contract)
Max Risk: $4.00 ($400 per contract)
```

**Exit Rules:**
- Take Profit: 50% of max profit
- Stop Loss: 2.5x credit received

---

### 2. Iron Butterfly

**Structure:** ATM short straddle + protective wings

**Best Conditions:**
- VIX: 25+ (Very high volatility)
- Market: Expect price to pin near current level
- Time: 30-45 DTE

**Characteristics:**
- Higher credit than Iron Condor
- Narrower profit zone
- Maximum theta decay at ATM

**Example:**
```
Stock @ $100
Sell 100 Call / Buy 105 Call
Sell 100 Put / Buy 95 Put
Credit: $3.00 ($300 per contract)
Max Risk: $2.00 ($200 per contract)
```

---

### 3. Vertical Credit Spreads

**Structure:** Sell closer OTM, buy further OTM

**Best Conditions:**
- VIX: 18+ (Medium-high IV)
- Market: Directional bias + high premium
- Time: 30-45 DTE

**Types:**
- **Put Credit Spread:** Bullish bias (sell below market)
- **Call Credit Spread:** Bearish bias (sell above market)

**Example (Put Credit Spread):**
```
Stock @ $100 (bullish bias)
Sell 95 Put / Buy 90 Put
Credit: $0.75 per spread
Max Risk: $4.25 per spread
```

---

## Time Decay Strategies

### 4. Calendar Spread

**Structure:** Sell near-term, buy far-term (same strike)

**Best Conditions:**
- VIX: 15-25 (Low-medium IV, expect rise)
- Market: Minimal movement expected
- Time: Sell 30 DTE, Buy 60 DTE

**Profit Mechanism:**
- Near-term theta decays faster
- Profit if stock stays near strike
- Benefits from IV increase in back month

**Example:**
```
Stock @ $100
Sell 100 Call (30 DTE) @ $3.00
Buy 100 Call (60 DTE) @ $5.00
Net Debit: $2.00
Max Profit: ~$3.00 (at near-term expiration)
```

---

### 5. Theta Decay Optimized

**Strategy:** Enter at optimal point on decay curve

**Key Insights:**
- **ATM Options:** Maximum decay 14-21 DTE
- **10-15 Delta OTM:** Maximum decay 21-35 DTE
- **Far OTM (5 Delta):** Maximum decay 30-45 DTE

**Application:**
- Sell Iron Condors at 30-35 DTE (optimal for OTM)
- Roll before theta decay flattens
- Target high IV rank stocks

---

## Directional Strategies (Low IV)

### 6. Vertical Debit Spreads

**Structure:** Buy ITM, sell OTM

**Best Conditions:**
- VIX: <15 (Low IV = cheap options)
- Market: Strong directional conviction
- Time: 45-60 DTE

**Types:**
- **Call Debit Spread:** Bullish
- **Put Debit Spread:** Bearish

**Example (Call Debit Spread):**
```
Stock @ $100 (bullish)
Buy 95 Call @ $7.00
Sell 105 Call @ $2.00
Net Debit: $5.00
Max Profit: $5.00 (if stock > $105)
```

---

## Quantitative Strategies

### 7. Mean Reversion (Jim Simons Style)

**Concept:** Price extremes tend to revert to mean

**Signal Generation:**
```
Z-Score = (Current Price - Mean) / Std Dev

If Z > +2.0: SELL signal (price too high)
If Z < -2.0: BUY signal (price too low)
```

**Implementation:**
- Calculate 20-day moving average
- Measure standard deviations
- Z-score > 2: Sell call spreads
- Z-score < -2: Sell put spreads

**Example:**
```
Stock historically trades $95-$105 (Mean: $100, StdDev: $2.50)
Current Price: $107.50
Z-Score = (107.50 - 100) / 2.50 = +3.0

Signal: STRONG SELL (expect reversion down)
Strategy: Sell 110/115 Call Credit Spread
```

---

## Strategy Selection Matrix

| VIX Range | IV Rank | Market Outlook | Best Strategy |
|-----------|---------|----------------|---------------|
| >30 | >75 | Any | **NONE - Wait** |
| 20-30 | 50-75 | Neutral | **Iron Condor** |
| 20-30 | 60-80 | Pin at strike | **Iron Butterfly** |
| 15-25 | 40-60 | Mild directional | **Credit Spreads** |
| 15-25 | 30-50 | Stable | **Calendar Spread** |
| <15 | <30 | Strong directional | **Debit Spreads** |
| Any | Any | Price extreme (Z>2) | **Mean Reversion** |

---

## Risk Management Rules

**Position Sizing:**
- Max 25% of account per position
- Max $120 risk per trade (for $200 account)
- Never more than 3 simultaneous positions

**Greeks Limits:**
- Delta: 0.15-0.25 for credit spreads
- Theta: Minimum $1.00 daily decay
- Vanna: Max 0.15 delta expansion per 5 IV points

**Exit Rules:**
- Take Profit: 50% of max profit
- Stop Loss: 2.5x credit received (credit spreads)
- Time-based: Close at 7 DTE if not hit targets

---

## Summary

✅ **High IV (VIX 20+):** Iron Condor, Iron Butterfly, Credit Spreads
✅ **Medium IV (VIX 15-20):** Calendar Spreads, Selective Credit Spreads  
✅ **Low IV (VIX <15):** Debit Spreads, Wait for better conditions
✅ **Any Conditions:** Mean Reversion on extreme Z-scores

🎯 **Focus:** Capital preservation first, consistent income second
