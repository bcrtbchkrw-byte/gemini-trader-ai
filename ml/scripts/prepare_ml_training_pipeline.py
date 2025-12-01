"""
Main Script to Download Historical Data and Prepare ML Training Datasets

This script:
1. Downloads 5-10 years of daily OHLCV data for SPY, VIX, TSLA, NVDA, AMD
2. Prepares labeled training data for RegimeClassifier
3. Prepares labeled training data for ProbabilityOfTouch model (multi-symbol)
4. Trains both ML models

Usage:
    python -m ml.scripts.prepare_ml_training_pipeline
"""
import asyncio
from loguru import logger
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ml.historical_data_fetcher import get_historical_fetcher
from ml.prepare_regime_training_data import RegimeTrainingDataPreparation
from ml.prepare_pot_training_data import PoTTrainingDataPreparation
from ml.regime_classifier import get_regime_classifier
from ml.probability_of_touch import get_pot_model
import numpy as np


async def download_historical_data(years: int = 10):
    """
    Step 1: Download historical OHLCV data for multiple symbols
    
    SPY & VIX: For regime classification
    TSLA, NVDA, AMD: For PoT training with diverse volatility
    """
    logger.info("="*60)
    logger.info("STEP 1: Downloading Historical Data")
    logger.info("="*60)
    
    fetcher = get_historical_fetcher()
    
    # Symbols to download
    symbols = ['SPY', 'VIX', 'TSLA', 'NVDA', 'AMD']
    
    failed = []
    
    for symbol in symbols:
        logger.info(f"\n📥 Downloading {years} years of {symbol} data...")
        
        df = await fetcher.fetch_equity_history(symbol, years=years)
        
        if df.empty:
            logger.error(f"❌ Failed to download {symbol} data")
            failed.append(symbol)
        else:
            logger.info(f"✅ {symbol}: {len(df)} days downloaded")
    
    # Check critical symbols
    if 'SPY' in failed or 'VIX' in failed:
        logger.error("❌ Critical symbols (SPY/VIX) failed to download")
        return False
    
    if len(failed) > 0:
        logger.warning(f"⚠️  Some symbols failed: {', '.join(failed)}")
        logger.info("Continuing with available data...")
    
    logger.info("\n✅ Historical data download complete!")
    logger.info(f"   Successfully downloaded: {len(symbols) - len(failed)}/{len(symbols)} symbols")
    
    return True


def prepare_regime_training_data():
    """
    Step 2: Prepare labeled training data for RegimeClassifier
    """
    logger.info("\n" + "="*60)
    logger.info("STEP 2: Preparing Regime Classifier Training Data")
    logger.info("="*60)
    
    prep = RegimeTrainingDataPreparation()
    success = prep.prepare_and_save()
    
    if success:
        logger.info("\n✅ Regime training data prepared!")
    else:
        logger.error("\n❌ Failed to prepare regime training data")
    
    return success


def prepare_pot_training_data(samples_per_symbol: int = 4000):
    """
    Step 3: Prepare labeled training data for Probability of Touch model
    
    Uses multiple symbols (SPY, TSLA, NVDA, AMD) for diverse volatility
    """
    logger.info("\n" + "="*60)
    logger.info("STEP 3: Preparing Probability of Touch Training Data")
    logger.info("="*60)
    
    prep = PoTTrainingDataPreparation()
    # Will use SPY, TSLA, NVDA, AMD by default
    success = prep.prepare_and_save(samples_per_symbol=samples_per_symbol)
    
    if success:
        logger.info("\n✅ PoT training data prepared!")
    else:
        logger.error("\n❌ Failed to prepare PoT training data")
    
    return success


def train_regime_classifier():
    """
    Step 4: Train the RegimeClassifier model
    """
    logger.info("\n" + "="*60)
    logger.info("STEP 4: Training Regime Classifier")
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
        
        logger.info(f"Loaded training data: {len(X)} samples, {X.shape[1]} features")
        
        # Train model
        classifier = get_regime_classifier()
        metrics = classifier.train(X, y, test_size=0.2)
        
        if 'error' in metrics:
            logger.error(f"Training failed: {metrics['error']}")
            return False
        
        logger.info("\n✅ Regime classifier trained!")
        logger.info(f"   Accuracy: {metrics['accuracy']:.1%}")
        logger.info(f"   Train samples: {metrics['train_samples']}")
        logger.info(f"   Test samples: {metrics['test_samples']}")
        
        # Show feature importance
        logger.info("\nFeature Importance:")
        feature_names = data['feature_names']
        for idx, importance in sorted(
            metrics['feature_importance'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]:  # Top 5
            logger.info(f"   {feature_names[idx]}: {importance:.3f}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error training regime classifier: {e}")
        return False


def train_pot_model():
    """
    Step 5: Train the Probability of Touch model
    """
    logger.info("\n" + "="*60)
    logger.info("STEP 5: Training Probability of Touch Model")
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
        
        logger.info(f"Loaded training data: {len(X)} samples, {X.shape[1]} features")
        logger.info(f"Touch rate: {y.mean():.1%}")
        
        # Show symbol distribution if available
        if 'symbols' in data:
            symbols = data['symbols']
            logger.info(f"Trained on symbols: {', '.join(symbols)}")
        
        # Train model
        pot_model = get_pot_model()
        metrics = pot_model.train(X, y, test_size=0.2)
        
        if 'error' in metrics:
            logger.error(f"Training failed: {metrics['error']}")
            return False
        
        logger.info("\n✅ PoT model trained!")
        logger.info(f"   MSE: {metrics['mse']:.4f}")
        logger.info(f"   R²: {metrics['r2']:.4f}")
        logger.info(f"   Train samples: {metrics['train_samples']}")
        logger.info(f"   Test samples: {metrics['test_samples']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error training PoT model: {e}")
        return False


async def main():
    """Run complete ML training pipeline"""
    logger.info("\n" + "🚀 " + "="*56)
    logger.info("🚀 ML TRAINING PIPELINE - COMPLETE SETUP")
    logger.info("🚀 " + "="*56 + "\n")
    
    # Step 1: Download historical data
    success = await download_historical_data(years=10)
    if not success:
        logger.error("\n❌ Pipeline failed at Step 1: Historical data download")
        return
    
    # Step 2: Prepare regime training data
    success = prepare_regime_training_data()
    if not success:
        logger.error("\n❌ Pipeline failed at Step 2: Regime data preparation")
        return
    
    # Step 3: Prepare PoT training data (4000 samples per symbol = 16000 total)
    success = prepare_pot_training_data(samples_per_symbol=4000)
    if not success:
        logger.error("\n❌ Pipeline failed at Step 3: PoT data preparation")
        return
    
    # Step 4: Train regime classifier
    success = train_regime_classifier()
    if not success:
        logger.error("\n❌ Pipeline failed at Step 4: Regime classifier training")
        return
    
    # Step 5: Train PoT model
    success = train_pot_model()
    if not success:
        logger.error("\n❌ Pipeline failed at Step 5: PoT model training")
        return
    
    # Success!
    logger.info("\n" + "🎉 " + "="*56)
    logger.info("🎉 ML TRAINING PIPELINE COMPLETE!")
    logger.info("🎉 " + "="*56)
    logger.info("\nBoth ML models are now trained and ready to use:")
    logger.info("  ✅ RegimeClassifier → ml/models/regime_classifier.joblib")
    logger.info("  ✅ ProbabilityOfTouch → ml/models/probability_of_touch.joblib")
    logger.info("\nYou can now run your trading bot with ML-powered analysis!")


if __name__ == '__main__':
    asyncio.run(main())
