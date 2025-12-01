"""
Quick test script to verify ML training pipeline setup
"""
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def check_dependencies():
    """Check if ML dependencies are installed"""
    logger.info("Checking ML dependencies...")
    
    try:
        import xgboost
        logger.info("  ✓ xgboost")
    except ImportError:
        logger.error("  ✗ xgboost - Install with: pip install -r requirements_ml.txt")
        return False
    
    try:
        import sklearn
        logger.info("  ✓ scikit-learn")
    except ImportError:
        logger.error("  ✗ scikit-learn - Install with: pip install -r requirements_ml.txt")
        return False
    
    try:
        import pandas
        logger.info("  ✓ pandas")
    except ImportError:
        logger.error("  ✗ pandas")
        return False
    
    try:
        import numpy
        logger.info("  ✓ numpy")
    except ImportError:
        logger.error("  ✗ numpy")
        return False
    
    return True


def check_file_structure():
    """Check if all necessary files exist"""
    logger.info("\nChecking file structure...")
    
    required_files = [
        "ml/historical_data_fetcher.py",
        "ml/prepare_regime_training_data.py",
        "ml/prepare_pot_training_data.py",
        "ml/scripts/prepare_ml_training_pipeline.py",
        "ml/regime_classifier.py",
        "ml/probability_of_touch.py"
    ]
    
    all_exist = True
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            logger.info(f"  ✓ {file_path}")
        else:
            logger.error(f"  ✗ {file_path} - MISSING")
            all_exist = False
    
    return all_exist


def check_directories():
    """Check if data directories exist"""
    logger.info("\nChecking directories...")
    
    data_dir = Path("data/historical")
    models_dir = Path("ml/models")
    
    if not data_dir.exists():
        logger.warning(f"  ! {data_dir} does not exist - creating...")
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"  ✓ Created {data_dir}")
    else:
        logger.info(f"  ✓ {data_dir} exists")
    
    if not models_dir.exists():
        logger.warning(f"  ! {models_dir} does not exist - creating...")
        models_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"  ✓ Created {models_dir}")
    else:
        logger.info(f"  ✓ {models_dir} exists")
    
    return True


def check_ibkr_connection():
    """Check if IBKR connection can be established"""
    logger.info("\nChecking IBKR connection...")
    
    try:
        from ibkr.connection import get_ibkr_connection
        
        connection = get_ibkr_connection()
        ib = connection.get_client()
        
        if ib and ib.isConnected():
            logger.info("  ✓ IBKR connection established")
            return True
        else:
            logger.warning("  ! IBKR not connected - Make sure TWS/Gateway is running")
            logger.info("    You can still prepare synthetic training data without connection")
            return False
    except Exception as e:
        logger.error(f"  ✗ IBKR connection error: {e}")
        return False


def main():
    """Run all checks"""
    logger.info("="*60)
    logger.info("ML TRAINING PIPELINE - SETUP VERIFICATION")
    logger.info("="*60 + "\n")
    
    # Check dependencies
    deps_ok = check_dependencies()
    
    # Check files
    files_ok = check_file_structure()
    
    # Check directories
    dirs_ok = check_directories()
    
    # Check IBKR (optional)
    ibkr_ok = check_ibkr_connection()
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("SUMMARY")
    logger.info("="*60)
    
    if deps_ok and files_ok and dirs_ok:
        logger.info("✅ Setup is complete!")
        
        if ibkr_ok:
            logger.info("\n🚀 Ready to run full pipeline:")
            logger.info("   python -m ml.scripts.prepare_ml_training_pipeline")
        else:
            logger.info("\n⚠️  IBKR not connected. You can:")
            logger.info("   1. Start TWS/Gateway and run full pipeline")
            logger.info("   2. OR prepare synthetic PoT data without IBKR:")
            logger.info("      python -m ml.prepare_pot_training_data")
    else:
        logger.error("\n❌ Setup incomplete. Please fix the issues above.")
        
        if not deps_ok:
            logger.info("\n📦 Install dependencies:")
            logger.info("   pip install -r requirements_ml.txt")


if __name__ == '__main__':
    main()
