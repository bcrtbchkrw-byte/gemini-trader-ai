"""
Training Script for Exit Strategy ML Model
Trains the model on historical trade data.
"""
import numpy as np
from pathlib import Path
from loguru import logger
import asyncio


async def train_exit_model():
    """
    Train the exit strategy ML model
    
    Steps:
    1. Load training data
    2. Train model
    3. Validate performance
    4. Save model
    """
    logger.info("\n" + "="*60)
    logger.info("TRAINING EXIT STRATEGY ML MODEL")
    logger.info("="*60)
    
    try:
        # Load training data
        data_path = Path("data/historical/exit_training_data.npz")
        
        if not data_path.exists():
            logger.error(f"Training data not found: {data_path}")
            logger.info("Run: python -m ml.prepare_exit_training_data")
            return False
        
        logger.info(f"Loading training data from {data_path}...")
        data = np.load(data_path)
        X = data['X']
        y_stop = data['y_stop']
        y_profit = data['y_profit']
        
        logger.info(f"Loaded {len(X)} samples with {X.shape[1]} features")
        logger.info(f"Stop loss range: {y_stop.min():.2f}x - {y_stop.max():.2f}x")
        logger.info(f"Profit target range: {y_profit.min():.1%} - {y_profit.max():.1%}")
        
        # Train model
        from ml.exit_strategy_ml import get_exit_strategy_ml
        
        model = get_exit_strategy_ml()
        
        logger.info("\nTraining exit strategy model...")
        metrics = model.train(X, y_stop, y_profit, test_size=0.2)
        
        if 'error' in metrics:
            logger.error(f"Training failed: {metrics['error']}")
            return False
        
        logger.info("\n✅ Exit strategy model trained!")
        logger.info(f"   Stop Loss Model:")
        logger.info(f"     - R² Score: {metrics['stop_r2']:.3f}")
        logger.info(f"     - MSE: {metrics['stop_mse']:.4f}")
        logger.info(f"   Profit Target Model:")
        logger.info(f"     - R² Score: {metrics['profit_r2']:.3f}")
        logger.info(f"     - MSE: {metrics['profit_mse']:.4f}")
        logger.info(f"   Train samples: {metrics['train_samples']}")
        logger.info(f"   Test samples: {metrics['test_samples']}")
        
        # Show feature importance
        logger.info("\nTop 5 Most Important Features:")
        feature_importance = metrics.get('feature_importance', {})
        sorted_features = sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for feature, importance in sorted_features[:5]:
            logger.info(f"   {feature}: {importance:.3f}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error training exit strategy model: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main entry point"""
    success = await train_exit_model()
    
    if success:
        logger.info("\n" + "="*60)
        logger.info("✅ EXIT STRATEGY MODEL TRAINING COMPLETE")
        logger.info("="*60)
        logger.info("\nModel saved to: ml/models/exit_strategy_ml.joblib")
        logger.info("\nNext steps:")
        logger.info("  1. Test the model: python -m ml.scripts.test_exit_model")
        logger.info("  2. Update exit_manager.py to use ML predictions")
    else:
        logger.error("\n" + "="*60)
        logger.error("❌ TRAINING FAILED")
        logger.error("="*60)


if __name__ == "__main__":
    asyncio.run(main())
