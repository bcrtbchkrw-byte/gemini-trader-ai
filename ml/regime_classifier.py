"""
Market Regime Classifier using XGBoost
Classifies market conditions faster and more accurately than rule-based systems.
"""
from typing import Dict, Any, Tuple, Optional, List
import numpy as np
from loguru import logger
from pathlib import Path
import joblib


class RegimeClassifier:
    """
    ML-based market regime classifier
    
    Regimes:
    - BULL_TRENDING: Low VIX, strong momentum, bullish sentiment
    - BEAR_TRENDING: High VIX, negative momentum, bearish sentiment
    - HIGH_VOL_NEUTRAL: High VIX, choppy price action
    - LOW_VOL_NEUTRAL: Low VIX, range-bound
    - EXTREME_STRESS: VIX > 30, crisis mode
    """
    
    REGIMES = [
        'BULL_TRENDING',
        'BEAR_TRENDING',
        'HIGH_VOL_NEUTRAL',
        'LOW_VOL_NEUTRAL',
        'EXTREME_STRESS'
    ]
    
    def __init__(self, model_path: str = "ml/models/regime_classifier.joblib"):
        self.model_path = Path(model_path)
        self.model = None
        self.scaler = None
        self.feature_importance = {}
        self.mode = 'UNKNOWN'  # Track current mode: ML or RULE_BASED
        self.fallback_warning_shown = False
        
        # Try to load existing model
        if self.model_path.exists():
            self.load_model()
            if self.model is not None:
                self.mode = 'ML'
                logger.info("✅ RegimeClassifier: Running in ML mode")
        
        if self.model is None:
            self.mode = 'RULE_BASED'
            logger.error("")
            logger.error("="*70)
            logger.error("⚠️  WARNING: RegimeClassifier - NO TRAINED MODEL FOUND")
            logger.error(f"   Model path: {model_path}")
            logger.error("   🔴 RUNNING IN RULE-BASED FALLBACK MODE")
            logger.error("   This uses simple if/else rules instead of ML")
            logger.error("   TO FIX: Run python -m ml.scripts.prepare_ml_training_pipeline")
            logger.error("="*70)
            logger.error("")
    
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        test_size: float = 0.2
    ) -> Dict[str, Any]:
        """
        Train the regime classifier
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Labels (n_samples,) - integers 0-4 for regime classes
            test_size: Fraction for test set
            
        Returns:
            Training metrics
        """
        try:
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import StandardScaler
            from xgboost import XGBClassifier
            from sklearn.metrics import accuracy_score, classification_report
            
            logger.info(f"Training regime classifier on {len(X)} samples...")
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=42, stratify=y
            )
            
            # Scale features
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train XGBoost
            self.model = XGBClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                objective='multi:softmax',
                num_class=len(self.REGIMES),
                random_state=42,
                eval_metric='mlogloss'
            )
            
            self.model.fit(
                X_train_scaled,
                y_train,
                eval_set=[(X_test_scaled, y_test)],
                verbose=False
            )
            
            # Evaluate
            y_pred = self.model.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)
            
            # Feature importance
            self.feature_importance = dict(zip(
                range(X.shape[1]),
                self.model.feature_importances_
            ))
            
            logger.info(f"✅ Model trained with {accuracy:.1%} accuracy")
            
            # Save model
            self.save_model()
            
            return {
                'accuracy': accuracy,
                'train_samples': len(X_train),
                'test_samples': len(X_test),
                'feature_importance': self.feature_importance
            }
            
        except ImportError as e:
            logger.error(f"Missing ML dependencies: {e}")
            logger.info("Install with: pip install -r requirements_ml.txt")
            return {'error': str(e)}
            
        except Exception as e:
            logger.error(f"Error training regime classifier: {e}")
            return {'error': str(e)}
    
    def predict_regime(
        self,
        features: np.ndarray
    ) -> Tuple[str, float]:
        """
        Predict market regime from features
        
        Args:
            features: Feature vector (1D array)
            
        Returns:
            (regime_name, confidence) tuple
        """
        if self.model is None or self.scaler is None:
            # Fallback to rule-based
            if not self.fallback_warning_shown:
                logger.warning("🔴 Using RULE-BASED fallback (no ML model)")
                self.fallback_warning_shown = True
            return self._rule_based_fallback(features)
        
        try:
            # Ensure 2D for sklearn
            if features.ndim == 1:
                features = features.reshape(1, -1)
            
            # Scale features
            features_scaled = self.scaler.transform(features)
            
            # Predict
            pred_class = self.model.predict(features_scaled)[0]
            pred_proba = self.model.predict_proba(features_scaled)[0]
            
            regime = self.REGIMES[pred_class]
            confidence = pred_proba[pred_class]
            
            logger.debug(f"✨ ML Regime: {regime} ({confidence:.1%} confidence)")
            
            return regime, float(confidence)
            
        except Exception as e:
            logger.error(f"Error predicting regime: {e}")
            logger.warning("Falling back to rule-based regime detection")
            return self._rule_based_fallback(features)
    
    def _rule_based_fallback(
        self,
        features: np.ndarray
    ) -> Tuple[str, float]:
        """
        Fallback to simple rule-based regime detection
        Uses VIX and returns features
        
        ⚠️ WARNING: This is NOT ML - just simple if/else rules!
        """
        # Assume feature[0] = VIX, feature[5] = returns_1d
        vix = features[0] if len(features) > 0 else 15.0
        returns_1d = features[5] if len(features) > 5 else 0.0
        
        logger.debug(f"⚙️  Rule-based: VIX={vix:.1f}, returns={returns_1d:.3f}")
        
        if vix > 30:
            return 'EXTREME_STRESS', 0.8
        elif vix > 20 and returns_1d < -0.01:
            return 'BEAR_TRENDING', 0.7
        elif vix > 20:
            return 'HIGH_VOL_NEUTRAL', 0.7
        elif returns_1d > 0.01:
            return 'BULL_TRENDING', 0.7
        else:
            return 'LOW_VOL_NEUTRAL', 0.7
    
    def get_feature_importance(
        self,
        feature_names: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """
        Get feature importance scores
        
        Args:
            feature_names: Optional list of feature names
            
        Returns:
            Dict mapping feature name to importance
        """
        if not self.feature_importance:
            return {}
        
        if feature_names:
            return {
                feature_names[idx]: importance
                for idx, importance in self.feature_importance.items()
                if idx < len(feature_names)
            }
        else:
            return self.feature_importance
    
    def save_model(self):
        """Save trained model to disk"""
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'feature_importance': self.feature_importance,
                'regimes': self.REGIMES
            }
            
            joblib.dump(model_data, self.model_path)
            logger.info(f"Model saved to {self.model_path}")
            
        except Exception as e:
            logger.error(f"Error saving model: {e}")
    
    def load_model(self):
        """Load trained model from disk"""
        try:
            model_data = joblib.load(self.model_path)
            
            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_importance = model_data.get('feature_importance', {})
            
            logger.info(f"✅ Model loaded from {self.model_path}")
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.model = None
            self.scaler = None


# Singleton
_regime_classifier: Optional[RegimeClassifier] = None


def get_regime_classifier(model_path: str = "ml/models/regime_classifier.joblib") -> RegimeClassifier:
    """Get or create singleton regime classifier"""
    global _regime_classifier
    if _regime_classifier is None:
        _regime_classifier = RegimeClassifier(model_path)
    return _regime_classifier
