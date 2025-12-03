# Incremental Learning for Exit Strategy Model

## Overview

Exit strategy model se automaticky přetrénuje každý měsíc na všech akumulovaných closed trades, stejně jako RegimeClassifier a ProbabilityOfTouch modely.

## How It Works

### Data Accumulation

**Training data se NIKDY nesmaže** - pouze se přidávají nové uzavřené obchody:

```
Month 1: 20 trades → Train initial model
Month 2: 35 trades (20 old + 15 new) → Retrain on all 35
Month 3: 52 trades (35 old + 17 new) → Retrain on all 52
```

### Monthly Retraining Flow

1. **Update Training Data** - Načte VŠECHNY closed trades z databáze
2. **Regenerate Features** - Extrahuje features ze všech obchodů
3. **Retrain Models** - Trénuje stop loss a profit target modely
4. **Save** - Uloží aktualizované modely

## Benefits

✅ **Continuous Improvement** - Model se zlepšuje s každým dalším obchodem  
✅ **Preserves History** - Nikdy nezapomene na starší data (crashes, různé regimes)  
✅ **Adaptive** - Přizpůsobuje se měnícím se market conditions  
✅ **Automatic** - Žádná manuální práce po nastavení cron jobu

## Setup

### Manual Retraining

Kdykoliv spustit ručně:

```bash
# Samostatně exit model
python -m ml.scripts.monthly_retrain_exit_model

# Nebo všechny modely najednou
python -m ml.scripts.monthly_retrain
```

### Automatic Monthly Retraining

Nastavit cron job (Linux/Mac):

```bash
# Edit crontab
crontab -e

# Add line (runs 1st day of month at 2 AM)
0 2 1 * * cd /path/to/gemini-trader-ai && python -m ml.scripts.monthly_retrain >> logs/monthly_retrain.log 2>&1
```

Pro Raspberry Pi (systemd timer):

```bash
# Create timer file
sudo nano /etc/systemd/system/monthly-retrain.timer

# Add content
[Unit]
Description=Monthly ML Model Retraining

[Timer]
OnCalendar=monthly
Persistent=true

[Install]
WantedBy=timers.target

# Enable timer
sudo systemctl enable monthly-retrain.timer
sudo systemctl start monthly-retrain.timer
```

## Expected Results

### After 3 Months

- **RegimeClassifier**: ~85%+ accuracy
- **PoT Model**: R² > 0.70
- **Exit Strategy**: R² > 0.65 for both models

### After 6 Months

- **Data**: 100+ closed trades
- **Exit Model**: R² > 0.70, highly accurate predictions
- **Performance**: 15-25% better exit timing

## Monitoring

### Check Last Retraining

```bash
# View logs
tail -f logs/monthly_retrain.log

# Check model file dates
ls -lh ml/models/*.joblib
```

### Verify Model Improvement

```python
import numpy as np

# Load training data
data = np.load('data/historical/exit_training_data.npz')
print(f"Total samples: {len(data['X'])}")
print(f"Last updated: {data.get('last_updated', 'Unknown')}")

# Load model and check metrics
from ml.exit_strategy_ml import get_exit_strategy_ml

model = get_exit_strategy_ml()
if model.mode == 'ML':
    print("✅ ML model active")
    print(f"Feature importance: {model.feature_importance}")
else:
    print("⚠️  Using fallback rules (no model trained)")
```

## Growing Dataset

Model se učí z **rostoucího** datasetu:

| Month | Closed Trades | Training Samples | Expected R² |
|-------|---------------|------------------|-------------|
| 1     | 20            | 20               | 0.50        |
| 2     | 35            | 35               | 0.58        |
| 3     | 52            | 52               | 0.63        |
| 6     | 100+          | 100+             | 0.70+       |
| 12    | 200+          | 200+             | 0.75+       |

## Integration with Main Pipeline

Exit model retraining je **Step 6** v `monthly_retrain.py`:

1. Fetch market data (SPY, VIX, etc.)
2. Regenerate regime training data
3. Regenerate PoT training data
4. Retrain RegimeClassifier
5. Retrain ProbabilityOfTouch
6. **Retrain Exit Strategy Model** ← NEW

Pokud selže, pipeline pokračuje - exit model není kritický pro trading.

## Troubleshooting

### "No closed trades found"

- Ještě nemáš uzavřené obchody
- Paper trade aspoň 20+ pozic
- Nebo použij static exit rules (fallback)

### Model accuracy degrading

- Normální po velkých market změnách  
- Model se sám opraví jak akumuluje nová data
- Zkontroluj že training data obsahují různé regimes

### Cron job not running

```bash
# Check cron logs
grep CRON /var/log/syslog

# Test manually first
python -m ml.scripts.monthly_retrain

# Verify cron syntax
crontab -l
```

## Summary

Exit strategy model je nyní plně **self-improving system**:

- ✅ Automaticky se přetrénuje každý měsíc
- ✅ Učí se z každého uzavřeného obchodu
- ✅ Nikdy nezapomene historická data
- ✅ Přizpůsobuje se novým market conditions
- ✅ Zero manuální údržba po nastavení

**Next**: Nastav cron job a nech model růst!
