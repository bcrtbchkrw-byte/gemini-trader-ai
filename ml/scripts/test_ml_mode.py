"""
Test ML Mode Detection

Demonstrates the warning messages when ML models are not trained.
Run this BEFORE training models to see fallback warnings.
"""
import numpy as np
from loguru import logger


def test_regime_classifier():
    """Test RegimeClassifier mode detection"""
    logger.info("\n" + "="*70)
    logger.info("Testing RegimeClassifier...")
    logger.info("="*70)
    
    from ml.regime_classifier import get_regime_classifier
    
    # This will show WARNING if model not trained
    classifier = get_regime_classifier()
    
    # Check mode
    logger.info(f"Current mode: {classifier.mode}")
    
    # Make a prediction (will use fallback if no model)
    features = np.array([18.5, 450.0, 0.3, 0.25, 50.0, 0.005, 0.01])
    regime, confidence = classifier.predict_regime(features)
    
    logger.info(f"Predicted regime: {regime} ({confidence:.1%} confidence)")
    
    if classifier.mode == 'RULE_BASED':
        logger.warning("⚠️  This was a RULE-BASED prediction, not ML!")


def test_pot_model():
    """Test ProbabilityOfTouch mode detection"""
    logger.info("\n" + "="*70)
    logger.info("Testing ProbabilityOfTouch...")
    logger.info("="*70)
    
    from ml.probability_of_touch import get_pot_model
    
    # This will show WARNING if model not trained
    pot_model = get_pot_model()
    
    # Check mode
    logger.info(f"Current mode: {pot_model.mode}")
    
    # Make a prediction (will use fallback if no model)
    pot = pot_model.predict_pot(
        current_price=450.0,
        strike=460.0,
        dte=30,
        iv=0.25
    )
    
    logger.info(f"Probability of Touch: {pot:.1%}")
    
    if pot_model.mode == 'ANALYTICAL':
        logger.warning("⚠️  This was an ANALYTICAL approximation, not ML!")


def main():
    """Run all tests"""
    logger.info("\n" + "🔬 " + "="*60)
    logger.info("🔬 ML MODE DETECTION TEST")
    logger.info("🔬 " + "="*60 + "\n")
    
    test_regime_classifier()
    test_pot_model()
    
    logger.info("\n" + "="*70)
    logger.info("✅ Tests complete")
    logger.info("="*70)
    logger.info("\nExpected behavior:")
    logger.info("  - If models NOT trained: Big red WARNING boxes on startup")
    logger.info("  - Predictions will use fallback (rule-based or analytical)")
    logger.info("  - Clear indication in logs: 🔴 or 🟡 emojis")
    logger.info("\nTo fix:")
    logger.info("  python -m ml.scripts.prepare_ml_training_pipeline")


if __name__ == '__main__':
    main()
