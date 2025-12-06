"""
DTE Optimizer
Predicts optimal Days To Expiration (DTE) based on VIX Term Structure and market conditions.
"""
from typing import Dict, Any, Tuple, Optional
import numpy as np
import joblib
import os
from datetime import datetime
from loguru import logger
from sklearn.ensemble import RandomForestRegressor

class DTEOptimizer:
    """
    ML Model to select optimal DTE.
    
    Logic:
    - VIX Term Structure (VIX / VIX3M) is the primary driver.
    - Contango (Ratio < 1.0) -> Longer DTE (45-60) to collect more premium safely.
    - Backwardation (Ratio > 1.0) -> Shorter DTE (21-30) to capture volatility crush.
    """
    
    def __init__(self):
        self.model_path = 'models/dte_optimizer_rf.joblib'
        self.model = None
        self._load_model()
        
    def _load_model(self):
        """Load trained model or initialize new one"""
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                logger.info("Loaded DTE Optimizer model")
            except Exception as e:
                logger.error(f"Error loading DTE model: {e}")
                self.model = None
        else:
            logger.info("No trained DTE model found. Using rule-based fallback (Cold Start).")
            self.model = None

    def predict_optimal_dte(self, market_data: Dict[str, Any]) -> Tuple[int, int]:
        """
        Predict optimal DTE range.
        
        Args:
            market_data: Dict containing:
                - vix_term_structure (dict with 'ratio')
                - iv_rank (float)
                - (optional) earnings_proximity
                
        Returns:
            Tuple (min_dte, max_dte)
        """
        try:
            # Extract features
            vix_ratio = market_data.get('vix_term_structure', {}).get('ratio', 1.0)
            structure = market_data.get('vix_term_structure', {}).get('structure', 'UNKNOWN')
            iv_rank = market_data.get('iv_rank', 50)
            
            # 1. Rule-Based Fallback (Cold Start / Safety)
            # This logic is robust and recommended by the user
            if not self.model:
                return self._rule_based_dte(vix_ratio, iv_rank)
            
            # 2. ML Prediction (if model exists)
            # Feature vector: [vix_ratio, iv_rank]
            features = np.array([[vix_ratio, iv_rank]])
            predicted_dte = self.model.predict(features)[0]
            
            # Create a 15-day window around prediction
            center_dte = int(predicted_dte)
            min_dte = max(21, center_dte - 7)
            max_dte = min(60, center_dte + 7)
            
            logger.info(f"🤖 ML DTE Prediction: {center_dte} days (Window: {min_dte}-{max_dte})")
            return min_dte, max_dte
            
        except Exception as e:
            logger.error(f"Error predicting DTE: {e}")
            return 30, 45  # Safe default

    def _rule_based_dte(self, vix_ratio: float, iv_rank: float) -> Tuple[int, int]:
        """
        Rule-based logic derived from VIX Term Structure
        """
        # BACKWARDATION (Panic) -> Short DTE
        if vix_ratio > 1.05 or iv_rank > 80:
            logger.info(f"Term Structure: BACKWARDATION (Ratio {vix_ratio:.2f}). Panic detected. Targeting short expiration (Vega Crush).")
            return 21, 30
            
        # CONTANGO (Calm) -> Long DTE
        elif vix_ratio < 0.95:
            logger.info(f"Term Structure: CONTANGO (Ratio {vix_ratio:.2f}). Market calm. Targeting long expiration (Theta/Premium).")
            return 45, 60
            
        # NEUTRAL / TRANSITION
        else:
            logger.info(f"Term Structure: NEUTRAL (Ratio {vix_ratio:.2f}). Using standard expiration.")
            return 30, 45

    def train(self, X: np.ndarray, y: np.ndarray):
        """
        Train the model on historical data.
        X: features [vix_ratio, iv_rank, ...]
        y: optimal_dte (derived from Sharpe Ratio analysis)
        """
        try:
            self.model = RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42)
            self.model.fit(X, y)
            
            # Save model
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump(self.model, self.model_path)
            logger.info("Trained and saved DTE Optimizer model")
            
        except Exception as e:
            logger.error(f"Error training DTE model: {e}")

# Singleton
_dte_optimizer = None

def get_dte_optimizer() -> DTEOptimizer:
    global _dte_optimizer
    if _dte_optimizer is None:
        _dte_optimizer = DTEOptimizer()
    return _dte_optimizer
