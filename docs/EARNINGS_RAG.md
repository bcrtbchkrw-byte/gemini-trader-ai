# Earnings RAG (Retrieval-Augmented Generation)

## 🎯 Concept

**Problem with old approach:**
```
AI: "Tell me the sentiment for AAPL earnings"
→ AI guesses based on training data
→ Outdated, inaccurate, generic
```

**RAG solution:**
```
1. RETRIEVE: Fetch real earnings numbers from IBKR
2. AUGMENT: Structure data as context
3. GENERATE: AI analyzes actual data
```

## 📊 How RAG Works

### Traditional (BAD)
```python
prompt = "What's the sentiment for AAPL earnings?"

AI response: "Generally positive..." # GUESSING!
```

### RAG (GOOD)
```python
# 1. RETRIEVE real data
earnings = await rag.fetch_earnings_data("AAPL")

# 2. AUGMENT with context
context = f"""
Revenue: $94.9B (actual) vs $94.5B (consensus) → BEAT by 0.4%
EPS: $1.52 (actual) vs $1.50 (consensus) → BEAT by 1.3%
Guidance: $90B revenue vs $92B consensus → MISS by 2.2%
YoY Growth: Revenue +2.1%, EPS -2.5% (slowing)
"""

# 3. GENERATE analysis with facts
prompt = f"{context}\nAnalyze these ACTUAL numbers..."

AI response: "Revenue beat but guidance missed. Bearish signal..."
# Based on FACTS, not guessing!
```

## ✅ Implementation

### Basic Usage

```python
from analysis.earnings_rag import get_earnings_rag

rag = get_earnings_rag()

# Fetch real earnings data
earnings_data = await rag.fetch_earnings_data("AAPL")

# Create RAG context
context = rag.create_rag_context(earnings_data)

# Use in AI prompt
prompt = f"""
{context}

Analyze these earnings...
"""
```

### Full RAG Pipeline

```python
# Automated RAG-enhanced analysis
analysis = await rag.get_rag_enhanced_analysis(
    symbol="AAPL",
    ai_client=claude_client
)

print(analysis)
# {
#   'earnings_quality_score': 7,
#   'guidance_analysis': 'miss',
#   'trading_implication': 'bearish',
#   'confidence': 9,
#   'reasoning': 'Beat on revenue but missed guidance...'
# }
```

## 📈 Data Retrieved

### Revenue Metrics
- **Actual Revenue**: What company reported
- **Consensus Estimate**: What analysts expected
- **Surprise %**: Beat or miss percentage
- **YoY Growth**: Year-over-year change

### EPS Metrics
- **Actual EPS**: Reported earnings per share
- **Consensus EPS**: Analyst estimates
- **Surprise %**: Beat or miss
- **YoY Growth**: Year-over-year change

### Guidance
- **Revenue Guidance**: Company's forward outlook
- **EPS Guidance**: Earnings projection
- **Analyst Target**: Street price target

### Example Data Structure
```json
{
  "symbol": "AAPL",
  "report_date": "2024-11-02",
  "fiscal_quarter": "Q4 2024",
  
  "revenue_actual": 94900000000,
  "revenue_consensus": 94500000000,
  "revenue_surprise_pct": 0.42,
  
  "eps_actual": 1.52,
  "eps_consensus": 1.50,
  "eps_surprise_pct": 1.33,
  
  "guidance_revenue": 90000000000,
  "revenue_yoy_growth": 2.1,
  "eps_yoy_growth": -2.5
}
```

## 🎯 AI Analysis with RAG

### Context Format
```
**EARNINGS DATA CONTEXT - AAPL**

Latest Earnings Report:
- Report Date: 2024-11-02
- Fiscal Quarter: Q4 2024

Revenue Metrics:
- Actual Revenue: $94.9B
- Consensus Estimate: $94.5B
- Surprise: +0.42%
- YoY Growth: +2.1%

EPS:
- Actual EPS: $1.52
- Consensus Estimate: $1.50
- Surprise: +1.3%
- YoY Growth: -2.5%

Forward Guidance:
- Revenue Guidance: $90B vs $92B consensus (MISS -2.2%)

**Analysis Instructions:**
Compare ACTUAL vs CONSENSUS.
A revenue beat + guidance miss = MIXED/BEARISH.
Slowing growth is concerning.
```

### AI Prompt Enhancement
```python
prompt = f"""
{rag_context}

Based on these ACTUAL numbers:

1. Earnings Quality Score (1-10)
2. Guidance Analysis (beat/meet/miss)
3. Trading Implication (bullish/bearish)
4. Confidence (1-10)

Be specific. Use the real numbers provided.
"""
```

## 📊 Benefits

### 1. Accuracy
```
Before (guessing):
  "AAPL earnings were good..."
  Vague, possibly wrong

After (RAG):
  "Revenue beat by 0.4% but guidance missed by 2.2%"
  Specific, factual
```

### 2. Confidence
```
Before:
  AI confidence: ~5/10 (guessing)

After:
  AI confidence: 9/10 (has facts)
```

### 3. Actionable
```
Before:
  "Sentiment is positive" → What does that mean for trading?

After:
  "Guidance miss suggests bearish IV contraction" → Clear signal
```

## ⚙️ Configuration

### Cache TTL
```python
rag = EarningsRAG()
rag.cache_ttl = 3600  # 1 hour cache
```

### Data Source
Currently uses IBKR `ReportsFinSummary`, can extend to:
- Yahoo Finance earnings
- Alpha Vantage earnings API
- SEC EDGAR filings

## 🚀 Production Integration

```python
# In Phase 2 AI analysis
async def analyze_with_earnings_context(symbol):
    rag = get_earnings_rag()
    
    # Get RAG-enhanced analysis
    earnings_analysis = await rag.get_rag_enhanced_analysis(
        symbol=symbol,
        ai_client=claude
    )
    
    if not earnings_analysis.get('has_earnings_data'):
        logger.warning(f"No earnings data for {symbol}, using generic")
        return await standard_analysis(symbol)
    
    # Use earnings context in trading decision
    quality_score = earnings_analysis['earnings_quality_score']
    
    if quality_score >= 8:
        logger.info(f"✅ Strong earnings quality: {quality_score}/10")
        # Proceed with trade
    else:
        logger.warning(f"⚠️ Weak earnings: {quality_score}/10")
        # Skip trade
```

## 🎯 Example Scenarios

### Scenario 1: Clean Beat
```
Revenue: Beat by 5%
EPS: Beat by 8%
Guidance: Beat by 3%

RAG Analysis:
  Quality Score: 10/10
  Implication: Bullish
  Confidence: 10/10
  → TRADE with high conviction
```

### Scenario 2: Mixed Results
```
Revenue: Beat by 2%
EPS: Miss by 1%
Guidance: Meet

RAG Analysis:
  Quality Score: 6/10
  Implication: Neutral
  Confidence: 7/10
  → SKIP - not clear enough
```

### Scenario 3: Guidance Miss
```
Revenue: Beat by 4%
EPS: Beat by 6%
Guidance: Miss by 5%

RAG Analysis:
  Quality Score: 4/10
  Implication: Bearish
  Confidence: 9/10
  → SKIP - guidance more important
```

---

**Status:** RAG implementation ready ✅  
**Data Source:** IBKR fundamental data  
**Improvement:** Facts instead of guessing 🎯
