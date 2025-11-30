# Loss Analysis System

## 📉 Overview

The Loss Analysis System is an AI-powered module that automatically analyzes losing trades to identify root causes and generate actionable prevention strategies.

## 🔄 Workflow

1.  **Detection**: Identifies closed trades with negative P&L.
2.  **Context Reconstruction**: Gathers market data at entry/exit (VIX, Regime, News).
3.  **AI Analysis**: Uses Gemini 1.5 Pro to answer:
    *   Was this bad luck or bad process?
    *   Did the market regime change?
    *   What is the single most important lesson?
4.  **Reporting**: Generates a Markdown report and sends it via Telegram (Weekly).

## 🛠️ Components

### `LossAnalyzer` (`analysis/loss_analyzer.py`)
Core class that orchestrates the analysis.

```python
from analysis.loss_analyzer import get_loss_analyzer

analyzer = get_loss_analyzer()
report = await analyzer.analyze_recent_losses(days=30)
print(report)
```

### Database Integration
*   `get_losing_trades(limit, days)`: Efficiently fetches relevant loss data.

### Scheduler
*   Runs automatically every **Friday** after market close.
*   Sends report to Telegram.

## 📊 Report Format

```markdown
# 📉 Loss Analysis Report
**Total Analyzed Loss:** $-450.00
**Trades Analyzed:** 2

## 🔍 Root Cause Breakdown

### BAD_PROCESS (1 trades)
- **NVDA** ($-200.00): Entered long call during high IV rank (IV Crush)
  - *Lesson:* Always check IV Rank before buying premium

### MARKET_SHIFT (1 trades)
- **SPY** ($-250.00): Unexpected hawkish Fed speech caused reversal
  - *Lesson:* Avoid 0DTE during FOMC days

## 🛡️ Strategic Improvements
- Add IV Rank > 50 filter for long options
- Implement "No Trade" window during Fed events
```

## 🚀 Usage

### Manual Run
```python
# scripts/analyze_losses.py
import asyncio
from analysis.loss_analyzer import get_loss_analyzer

async def main():
    analyzer = get_loss_analyzer()
    print(await analyzer.analyze_recent_losses())

asyncio.run(main())
```

### Configuration
Ensure `GEMINI_API_KEY` is set in `.env`.
