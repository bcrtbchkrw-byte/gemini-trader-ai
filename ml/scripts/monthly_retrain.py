"""
Monthly Incremental Retraining Script

This script:
1. Fetches last month's data for all symbols
2. Appends to existing historical data (accumulation)
3. Regenerates training datasets with ALL accumulated data
4. Retrains both ML models

Run this at the end of each month (e.g., via cron):
    0 0 1 * * cd /path/to/gemini-trader-ai && python -m ml.scripts.monthly_retrain

Data accumulates over time - older data is NEVER deleted.
"""
import asyncio
from loguru import logger
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ml.historical_data_fetcher import get_historical_fetcher
from ml.prepare_regime_training_data import RegimeTrainingDataPreparation
from ml.prepare_pot_training_data import PoTTrainingDataPreparation
from ml.regime_classifier import get_regime_classifier
from ml.probability_of_touch import get_pot_model
import numpy as np


async def fetch_incremental_monthly_data():
    """
    Step 1: Fetch last month's data and append to existing data
    
    Fetches ~35 days to ensure we capture the full month
    """
    logger.info("="*60)
    logger.info("STEP 1: Fetching Incremental Monthly Data")
    logger.info("="*60)
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    
    fetcher = get_historical_fetcher()
    
    # Symbols to update
    symbols = ['SPY', 'VIX', 'TSLA', 'NVDA', 'AMD']
    
    failed = []
    
    for symbol in symbols:
        logger.info(f"\n📥 Fetching incremental data for {symbol}...")
        
        df = await fetcher.fetch_incremental_data(symbol, days=35)
        
        if df.empty:
            logger.error(f"❌ Failed to fetch incremental data for {symbol}")
            failed.append(symbol)
        else:
            logger.info(f"✅ {symbol}: {len(df)} total rows (accumulated)")
    
    # Check critical symbols
    if 'SPY' in failed or 'VIX' in failed:
        logger.error("❌ Critical symbols (SPY/VIX) failed to update")
        return False
    
    if len(failed) > 0:
        logger.warning(f"⚠️  Some symbols failed: {', '.join(failed)}")
        logger.info("Continuing with available data...")
    
    logger.info("\n✅ Incremental data fetch complete!")
    logger.info(f"   Successfully updated: {len(symbols) - len(failed)}/{len(symbols)} symbols")
    
    return True


def regenerate_regime_training_data():
    """
    Step 2: Regenerate RegimeClassifier training data
    
    Uses ALL accumulated historical data (old + new)
    """
    logger.info("\n" + "="*60)
    logger.info("STEP 2: Regenerating Regime Training Data")
    logger.info("="*60)
    
    prep = RegimeTrainingDataPreparation()
    success = prep.prepare_and_save()
    
    if success:
        logger.info("\n✅ Regime training data regenerated with accumulated data!")
    else:
        logger.error("\n❌ Failed to regenerate regime training data")
    
    return success


def regenerate_pot_training_data():
    """
    Step 3: Regenerate PoT training data
    
    Uses ALL accumulated historical data for all symbols
    """
    logger.info("\n" + "="*60)
    logger.info("STEP 3: Regenerating PoT Training Data")
    logger.info("="*60)
    
    prep = PoTTrainingDataPreparation()
    
    # Generate 4000 samples per symbol from accumulated data
    success = prep.prepare_and_save(samples_per_symbol=4000)
    
    if success:
        logger.info("\n✅ PoT training data regenerated with accumulated data!")
    else:
        logger.error("\n❌ Failed to regenerate PoT training data")
    
    return success


def retrain_regime_classifier():
    """
    Step 4: Retrain RegimeClassifier on accumulated data
    """
    logger.info("\n" + "="*60)
    logger.info("STEP 4: Retraining Regime Classifier")
    logger.info("="*60)
    
    try:
        # Load training data
        data_path = Path("data/historical/regime_training_data.npz")
        
        if not data_path.exists():
            logger.error(f"Training data not found: {data_path}")
            return False
        
        data = np.load(data_path)
        X = data['X']
        y = data['y']
        
        logger.info(f"Training on {len(X)} samples (accumulated data)")
        
        # Retrain model
        classifier = get_regime_classifier()
        metrics = classifier.train(X, y, test_size=0.2)
        
        if 'error' in metrics:
            logger.error(f"Retraining failed: {metrics['error']}")
            return False
        
        logger.info("\n✅ Regime classifier retrained!")
        logger.info(f"   Accuracy: {metrics['accuracy']:.1%}")
        logger.info(f"   Train samples: {metrics['train_samples']}")
        logger.info(f"   Test samples: {metrics['test_samples']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error retraining regime classifier: {e}")
        return False


def retrain_pot_model():
    """
    Step 5: Retrain ProbabilityOfTouch model on accumulated data
    """
    logger.info("\n" + "="*60)
    logger.info("STEP 5: Retraining Probability of Touch Model")
    logger.info("="*60)
    
    try:
        # Load training data
        data_path = Path("data/historical/pot_training_data.npz")
        
        if not data_path.exists():
            logger.error(f"Training data not found: {data_path}")
            return False
        
        data = np.load(data_path)
        X = data['X']
        y = data['y']
        
        logger.info(f"Training on {len(X)} samples (accumulated data)")
        logger.info(f"Touch rate: {y.mean():.1%}")
        
        # Show symbol distribution if available
        if 'symbols' in data:
            symbols = data['symbols']
            logger.info(f"Symbols: {', '.join(symbols)}")
        
        # Retrain model
        pot_model = get_pot_model()
        metrics = pot_model.train(X, y, test_size=0.2)
        
        if 'error' in metrics:
            logger.error(f"Retraining failed: {metrics['error']}")
            return False
        
        logger.info("\n✅ PoT model retrained!")
        logger.info(f"   MSE: {metrics['mse']:.4f}")
        logger.info(f"   R²: {metrics['r2']:.4f}")
        logger.info(f"   Train samples: {metrics['train_samples']}")
        logger.info(f"   Test samples: {metrics['test_samples']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error retraining PoT model: {e}")
        return False


async def main():
    """Run monthly incremental retraining"""
    logger.info("\n" + "📅 " + "="*56)
    logger.info("📅 MONTHLY INCREMENTAL RETRAINING")
    logger.info("📅 " + "="*56)
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Step 1: Fetch last month's data
    success = await fetch_incremental_monthly_data()
    if not success:
        logger.error("\n❌ Retraining failed at Step 1: Incremental data fetch")
        return
    
    # Step 2: Regenerate regime training data
    success = regenerate_regime_training_data()
    if not success:
        logger.error("\n❌ Retraining failed at Step 2: Regime data regeneration")
        return
    
    # Step 3: Regenerate PoT training data
    success = regenerate_pot_training_data()
    if not success:
        logger.error("\n❌ Retraining failed at Step 3: PoT data regeneration")
        return
    
    # Step 4: Retrain regime classifier
    success = retrain_regime_classifier()
    if not success:
        logger.error("\n❌ Retraining failed at Step 4: Regime classifier retraining")
        return
    
    # Step 5: Retrain PoT model
    success = retrain_pot_model()
    if not success:
        logger.error("\n❌ Retraining failed at Step 5: PoT model retraining")
        return
    
    # Success!
    logger.info("\n" + "🎉 " + "="*56)
    logger.info("🎉 MONTHLY RETRAINING COMPLETE!")
    logger.info("🎉 " + "="*56)
    logger.info("\nModels retrained with accumulated data:")
    logger.info("  ✅ RegimeClassifier → ml/models/regime_classifier.joblib")
    logger.info("  ✅ ProbabilityOfTouch → ml/models/probability_of_touch.joblib")
    logger.info("\nOld data preserved, new data added.")
    logger.info("Models now trained on complete historical dataset!")


if __name__ == '__main__':
    asyncio.run(main())
