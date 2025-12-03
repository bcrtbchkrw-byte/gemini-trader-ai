"""
Monthly Retraining for Exit Strategy ML Model
Automatically retrain on all accumulated closed trades for continuous improvement
"""
import asyncio
import numpy as np
from pathlib import Path
from loguru import logger
from datetime import datetime


async def update_exit_training_data():
    """
    Update training data with new closed trades
    
    This appends new data to existing training set
    for incremental learning
    """
    logger.info("\n" + "="*60)
    logger.info("STEP 1: Updating Exit Training Data")
    logger.info("="*60)
    
    try:
        from ml.prepare_exit_training_data import ExitTrainingDataPreparation
        
        prep = ExitTrainingDataPreparation()
        
        # Load ALL closed trades (including new ones since last training)
        trades_df = await prep.load_historical_trades()
        
        if trades_df.empty:
            logger.warning("No closed trades found")
            return False
        
        logger.info(f"Found {len(trades_df)} total closed trades")
        
        # Generate features from all trades
        X, y_stop, y_profit = prep.create_feature_matrix(trades_df)
        
        if len(X) == 0:
            logger.error("Failed to generate training data")
            return False
        
        # Save training data
        output_path = Path("data/historical/exit_training_data.npz")
        np.savez(
            output_path,
            X=X,
            y_stop=y_stop,
            y_profit=y_profit,
            last_updated=datetime.now().isoformat()
        )
        
        logger.info(f"\n✅ Exit training data updated!")
        logger.info(f"   Total samples: {len(X)}")
        logger.info(f"   Features: {X.shape[1]}")
        logger.info(f"   Saved to: {output_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating exit training data: {e}")
        import traceback
        traceback.print_exc()
        return False


async def retrain_exit_model():
    """
    Retrain exit strategy model on accumulated data
    """
    logger.info("\n" + "="*60)
    logger.info("STEP 2: Retraining Exit Strategy Model")
    logger.info("="*60)
    
    try:
        # Load training data
        data_path = Path("data/historical/exit_training_data.npz")
        
        if not data_path.exists():
            logger.error(f"Training data not found: {data_path}")
            return False
        
        data = np.load(data_path, allow_pickle=True)
        X = data['X']
        y_stop = data['y_stop']
        y_profit = data['y_profit']
        
        logger.info(f"Loaded {len(X)} samples for retraining")
        
        # Train model
        from ml.exit_strategy_ml import get_exit_strategy_ml
        
        model = get_exit_strategy_ml()
        
        logger.info("Retraining exit strategy model...")
        metrics = model.train(X, y_stop, y_profit, test_size=0.2)
        
        if 'error' in metrics:
            logger.error(f"Retraining failed: {metrics['error']}")
            return False
        
        logger.info("\n✅ Exit strategy model retrained!")
        logger.info(f"   Stop Loss Model:")
        logger.info(f"     - R² Score: {metrics['stop_r2']:.3f}")
        logger.info(f"     - MSE: {metrics['stop_mse']:.4f}")
        logger.info(f"   Profit Target Model:")
        logger.info(f"     - R² Score: {metrics['profit_r2']:.3f}")
        logger.info(f"     - MSE: {metrics['profit_mse']:.4f}")
        logger.info(f"   Train samples: {metrics['train_samples']}")
        logger.info(f"   Test samples: {metrics['test_samples']}")
        
        # Log feature importance
        logger.info("\nTop 5 Important Features:")
        feature_importance = metrics.get('feature_importance', {})
        for feature, importance in sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]:
            logger.info(f"   {feature}: {importance:.3f}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error retraining exit model: {e}")
        import traceback
        traceback.print_exc()
        return False


async def monthly_retrain_exit_model():
    """
    Complete monthly retraining pipeline for exit strategy
    
    Steps:
    1. Update training data with new closed trades
    2. Retrain model on all accumulated data
    """
    logger.info("\n" + "="*70)
    logger.info("MONTHLY EXIT MODEL RETRAINING")
    logger.info("="*70)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*70)
    
    # Step 1: Update training data
    step1_success = await update_exit_training_data()
    
    if not step1_success:
        logger.error("\n❌ Failed to update training data")
        return False
    
    # Step 2: Retrain model
    step2_success = await retrain_exit_model()
    
    if not step2_success:
        logger.error("\n❌ Failed to retrain model")
        return False
    
    logger.info("\n" + "="*70)
    logger.info("✅ MONTHLY RETRAINING COMPLETE")
    logger.info("="*70)
    logger.info(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("\nNext retraining: ~30 days from now")
    logger.info("Model will continue improving as more trades close")
    logger.info("="*70)
    
    return True


async def main():
    """Main entry point"""
    success = await monthly_retrain_exit_model()
    
    if not success:
        logger.error("\n⚠️  Retraining encountered errors")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
