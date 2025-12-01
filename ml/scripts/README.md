# ML Training Pipeline

This directory contains scripts for preparing historical data and training ML models.

## Overview

The trading bot uses two ML models with **incremental learning**:

1. **RegimeClassifier**: Classifies market conditions into 5 regimes
   - BULL_TRENDING (0)
   - BEAR_TRENDING (1)
   - HIGH_VOL_NEUTRAL (2)
   - LOW_VOL_NEUTRAL (3)
   - EXTREME_STRESS (4)

2. **ProbabilityOfTouch**: Predicts probability of strike being touched before expiration

### Incremental Learning

- **Initial Setup**: Download 10 years of historical data, train models
- **Monthly Updates**: Fetch last month's data, append to existing, retrain
- **Data Accumulation**: Old data is NEVER deleted - dataset grows over time
- **Continuous Improvement**: Models learn from expanding historical dataset

📖 **See [INCREMENTAL_LEARNING.md](INCREMENTAL_LEARNING.md) for detailed documentation**

## Quick Start

### Initial Setup (One-Time)

Run the complete pipeline to download data, prepare training datasets, and train both models:

```bash
python -m ml.scripts.prepare_ml_training_pipeline
```

This will:
1. Download 10 years of SPY, VIX, TSLA, NVDA, AMD daily OHLCV data
2. Prepare labeled training data for RegimeClassifier (SPY + VIX)
3. Prepare labeled training data for ProbabilityOfTouch (multi-symbol)
4. Train both models
5. Save models to `ml/models/`

**Time required**: 30-50 minutes (depends on IBKR connection speed)

## Step-by-Step (Advanced)

### Step 1: Download Historical Data

```python
from ml.historical_data_fetcher import get_historical_fetcher
import asyncio

async def download():
    fetcher = get_historical_fetcher()
    
    # Download multiple symbols (10 years each)
    for symbol in ['SPY', 'VIX', 'TSLA', 'NVDA', 'AMD']:
        df = await fetcher.fetch_equity_history(symbol, years=10)

asyncio.run(download())
```

Data saved to: `data/historical/{SYMBOL}_daily_10y.csv`

### Step 2: Prepare RegimeClassifier Training Data

```bash
python -m ml.prepare_regime_training_data
```

This script:
- Loads SPY and VIX historical data
- Calculates technical indicators (RSI, moving averages, volatility)
- Assigns regime labels based on rules:
  - `VIX > 30` → EXTREME_STRESS
  - `VIX 15-30 + negative momentum` → BEAR_TRENDING
  - `VIX > 20 + choppy` → HIGH_VOL_NEUTRAL
  - `VIX < 15 + positive momentum` → BULL_TRENDING
  - `VIX < 15 + range-bound` → LOW_VOL_NEUTRAL
- Creates feature matrix (X) and labels (y)
- Saves to: `data/historical/regime_training_data.npz`

### Step 3: Prepare ProbabilityOfTouch Training Data

```bash
python -m ml.prepare_pot_training_data
```

This script:
- Loads historical data for **multiple symbols**: SPY, TSLA, NVDA, AMD
- Generates synthetic historical options (4,000 samples per symbol = 16,000 total)
- For each option, looks forward to expiration
- Labels: `touched=1` if price hit strike, `touched=0` otherwise
- Creates feature matrix with:
  - Distance to strike (%)
  - Direction
  - Days to expiration
  - Implied volatility
  - Historical volatility
  - Momentum
- Saves to: `data/historical/pot_training_data.npz`

**Why multiple symbols?**
- **SPY**: Low volatility, stable moves (β ~ 1.0)
- **TSLA**: High volatility, wild swings (β > 2.0)
- **NVDA**: Tech momentum, gap moves
- **AMD**: Semiconductor volatility

This trains the model to handle diverse price action patterns!

### Step 4: Train Models

```python
from ml.regime_classifier import get_regime_classifier
from ml.probability_of_touch import get_pot_model
import numpy as np

# Train RegimeClassifier
data = np.load('data/historical/regime_training_data.npz')
classifier = get_regime_classifier()
metrics = classifier.train(data['X'], data['y'])
print(f"Accuracy: {metrics['accuracy']:.1%}")

# Train ProbabilityOfTouch
data = np.load('data/historical/pot_training_data.npz')
pot_model = get_pot_model()
metrics = pot_model.train(data['X'], data['y'])
print(f"R²: {metrics['r2']:.3f}")
```

## Data Labeling Logic

### RegimeClassifier Labeling

Rules applied to each historical day:

```python
if VIX > 30:
    regime = EXTREME_STRESS (4)
elif VIX >= 15 and VIX <= 30 and returns_20d < -5%:
    regime = BEAR_TRENDING (1)
elif VIX > 20 and abs(returns_20d) < 5%:
    regime = HIGH_VOL_NEUTRAL (2)
elif VIX < 15 and returns_20d > 3% and price > SMA50:
    regime = BULL_TRENDING (0)
else:
    regime = LOW_VOL_NEUTRAL (3)
```

### ProbabilityOfTouch Labeling

For each historical option:

```python
# Look forward from option start date to expiration
if option_type == 'CALL':
    # Check if high price touched strike
    touched = 1 if max(future_highs) >= strike else 0
else:  # PUT
    # Check if low price touched strike
    touched = 1 if min(future_lows) <= strike else 0
```

## Output Files

After running the pipeline:

```
data/historical/
├── SPY_daily_10y.csv                    # 10 years of SPY OHLCV
├── VIX_daily_10y.csv                    # 10 years of VIX data
├── regime_training_data.npz             # Regime classifier training data
├── pot_training_data.npz                # PoT model training data
└── regime_feature_names.txt             # Feature names reference

ml/models/
├── regime_classifier.joblib             # Trained regime classifier
└── probability_of_touch.joblib          # Trained PoT model
```

## Requirements

Make sure ML dependencies are installed:

```bash
pip install -r requirements_ml.txt
```

Required packages:
- `xgboost` - ML models
- `scikit-learn` - Feature scaling, train/test split
- `pandas` - Data manipulation
- `numpy` - Numerical operations
- `joblib` - Model serialization

## Troubleshooting

### "No historical data found"
- Make sure IBKR TWS/Gateway is running
- Check connection in `config.py`
- Run Step 1 first to download data

### "Pacing violation" errors
- IBKR has rate limits on historical data requests
- The script includes automatic retry with exponential backoff
- If errors persist, increase sleep delays in `historical_data_fetcher.py`

### "Insufficient data for training"
- Ensure you have at least 2 years of data
- Check CSV files are not empty
- Verify data quality (no large gaps)

### Model accuracy is low
- Increase training data size (more years, more samples)
- Adjust labeling rules in preparation scripts
- Fine-tune XGBoost hyperparameters in model files

## Advanced: Real Option Data

To supplement synthetic PoT data with real option chains:

```python
from ml.prepare_pot_training_data import PoTTrainingDataPreparation
import asyncio

async def fetch_real_data():
    prep = PoTTrainingDataPreparation()
    
    # Fetch 20 snapshots, 7 days apart
    real_df = await prep.fetch_real_option_chains(
        symbol='SPY',
        num_snapshots=20,
        days_between=7
    )

asyncio.run(fetch_real_data())
```

**Note**: This requires ~20 weeks of data collection during market hours.

## Next Steps

After initial training:

1. **Setup Monthly Retraining** (Recommended):
   ```bash
   ./ml/scripts/setup_monthly_retrain.sh
   ```
   This sets up automatic monthly retraining to keep models fresh.

2. **Verify models work**:
   ```bash
   python
   >>> from ml.regime_classifier import get_regime_classifier
   >>> classifier = get_regime_classifier()
   >>> # Model should load without errors
   ```

3. **Run your trading bot** - it will automatically use the trained models

4. **Monitor model performance** in production

5. **Data accumulates automatically** - models retrain monthly with growing dataset

📖 **See [INCREMENTAL_LEARNING.md](INCREMENTAL_LEARNING.md) for monthly retraining details**
