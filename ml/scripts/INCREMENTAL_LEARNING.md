# Incremental Learning & Monthly Retraining

## Overview

The ML models use **incremental learning** - they accumulate data over time and retrain monthly:

1. **Initial Training**: Download 10 years of historical data
2. **Monthly Updates**: Fetch last month's data, append to existing, retrain
3. **Data Accumulation**: Old data is NEVER deleted - dataset grows over time
4. **Continuous Improvement**: Models learn from both historical and recent market conditions

## Architecture

```
Initial Setup (One-time):
  ├─ Download 10 years of SPY, VIX, TSLA, NVDA, AMD
  ├─ Generate training datasets
  └─ Train initial models

Monthly Retraining (Automatic):
  ├─ Fetch last 35 days of data (covers full month)
  ├─ Append to existing CSV files (merge, deduplicate)
  ├─ Regenerate training datasets from ALL accumulated data
  ├─ Retrain models on complete dataset
  └─ Save updated models
```

## Initial Setup

Run once when first setting up:

```bash
# Download 10 years of historical data and train models
python -m ml.scripts.prepare_ml_training_pipeline
```

This creates:
- `data/historical/SPY_daily_10y.csv` (~2,500 rows)
- `data/historical/VIX_daily_10y.csv` (~2,500 rows)
- `data/historical/TSLA_daily_10y.csv`
- `data/historical/NVDA_daily_10y.csv`
- `data/historical/AMD_daily_10y.csv`
- Trained models in `ml/models/`

## Monthly Retraining

### Manual Run

Test the monthly retraining manually:

```bash
python -m ml.scripts.monthly_retrain
```

This will:
1. Fetch last ~35 days of data for each symbol
2. **Append** to existing CSV files (e.g., `SPY_daily_10y.csv` → `SPY_daily_11y.csv` after ~1 year)
3. Regenerate training datasets using ALL accumulated data
4. Retrain both models
5. Save updated models

**Time required**: ~10-15 minutes

### Automatic Monthly Retraining

Setup automatic monthly retraining via cron:

```bash
./ml/scripts/setup_monthly_retrain.sh
```

This configures a cron job that runs:
- **When**: 1st day of every month at 2:00 AM
- **What**: `python -m ml.scripts.monthly_retrain`
- **Logs**: Saved to `logs/monthly_retrain.log`

#### Manual Cron Setup

Alternatively, add manually:

```bash
crontab -e
```

Add this line:

```cron
0 2 1 * * cd /path/to/gemini-trader-ai && /path/to/venv/bin/python -m ml.scripts.monthly_retrain >> /path/to/logs/monthly_retrain.log 2>&1
```

## Data Accumulation Strategy

### How Data Grows

**Month 0** (Initial):
- SPY: 10 years = ~2,500 rows

**Month 1**:
- Fetch last 35 days (~25 new rows)
- SPY: 10y + 1m = ~2,525 rows

**Month 12**:
- SPY: 10y + 12m = ~2,750 rows
- File becomes `SPY_daily_11y.csv`

**Year 5**:
- SPY: 15 years = ~3,750 rows
- Models trained on 15 years of diverse market conditions!

### Deduplication

The `fetch_incremental_data()` method:
- Fetches last 35 days (overlaps with existing data)
- Merges with existing DataFrame
- Removes duplicates by date (keeps latest)
- This ensures no missing days even if retraining is skipped

## Training Data Regeneration

Each month:

### RegimeClassifier
- Loads ALL accumulated SPY + VIX data
- Recalculates technical indicators
- Assigns regime labels to ALL days (including new ones)
- Generates new training dataset
- Result: Model sees how current month fits into historical regimes

### ProbabilityOfTouch
- Loads ALL accumulated data for SPY, TSLA, NVDA, AMD
- Generates 4,000 synthetic options per symbol from complete dataset
- Labels with touch detection
- Result: 16,000 training samples from expanding time period

## Benefits of Incremental Learning

1. **Adapts to Market Evolution**
   - Recent crash patterns added to historical data
   - Model learns new volatility regimes
   - Captures recent correlations

2. **Preserves Historical Knowledge**
   - 2008 crash data remains
   - COVID crash data remains  
   - Learns that "extreme stress" can recur

3. **Growing Dataset**
   - More data = better generalization
   - Edge cases from different periods
   - Robust to various market conditions

4. **Efficient**
   - Only fetch ~35 days per month (~fast)
   - Retrain on full dataset (~10-15 min)
   - No need to re-download years of data

## Monitoring

### Check Retraining Logs

```bash
tail -f logs/monthly_retrain.log
```

### Verify Data Growth

```bash
# Check data size growth
ls -lh data/historical/*.csv

# Check date ranges
python -c "
import pandas as pd
spy = pd.read_csv('data/historical/SPY_daily_10y.csv')
spy['date'] = pd.to_datetime(spy['date'])
print(f'SPY data: {spy[\"date\"].min()} to {spy[\"date\"].max()}')
print(f'Total rows: {len(spy)}')
"
```

### Check Model Performance

After retraining, verify accuracy:

```python
from ml.regime_classifier import get_regime_classifier
from ml.probability_of_touch import get_pot_model
import numpy as np

# Check RegimeClassifier
data = np.load('data/historical/regime_training_data.npz')
print(f"Regime training samples: {len(data['X'])}")

# Check PoT
data = np.load('data/historical/pot_training_data.npz')
print(f"PoT training samples: {len(data['X'])}")
print(f"Touch rate: {data['y'].mean():.1%}")
```

## Troubleshooting

### "No existing data found"
- Initial setup not run
- Run full pipeline first: `python -m ml.scripts.prepare_ml_training_pipeline`

### Cron job not running
- Check cron logs: `grep CRON /var/log/syslog`
- Verify crontab: `crontab -l`
- Test manually first: `python -m ml.scripts.monthly_retrain`
- Ensure TWS/Gateway is running at 2 AM

### Data not growing
- Check if fetch succeeded in logs
- Verify IBKR connection
- Make sure CSV files are writable

### Model accuracy degrading
- Normal after major market shifts
- Will improve as new data accumulates
- Consider adjusting labeling rules if persistent

## Best Practices

1. **Initial Training**: Always start with ≥5 years of data
2. **Monthly Cadence**: Run on 1st of month when previous month is complete
3. **Backup Models**: Keep previous month's models as fallback
4. **Monitor Logs**: Check retraining succeeded each month
5. **Data Validation**: Verify no large gaps in data

## Advanced: Manual Data Cleanup

If you need to remove bad data:

```python
import pandas as pd

# Load data
df = pd.read_csv('data/historical/SPY_daily_10y.csv')
df['date'] = pd.to_datetime(df['date'])

# Remove specific date range (example: bad data from 2024-11-15 to 2024-11-20)
df = df[(df['date'] < '2024-11-15') | (df['date'] > '2024-11-20')]

# Save cleaned data
df.to_csv('data/historical/SPY_daily_10y.csv', index=False)

# Regenerate training data
# Run: python -m ml.prepare_regime_training_data
#      python -m ml.prepare_pot_training_data
```

## Summary

- ✅ **Data Persists**: Old data is never deleted
- ✅ **Monthly Updates**: Automatic via cron
- ✅ **Continuous Learning**: Models improve with more data
- ✅ **Efficient**: Only fetch ~35 days per month
- ✅ **Robust**: Learns from expanding historical dataset
