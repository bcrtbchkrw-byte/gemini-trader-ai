"""
Trade Success Predictor (Gatekeeper)
ML model to predict trade success probability BEFORE Claude analysis.
"""
import os
import joblib
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from loguru import logger
from datetime import datetime

class TradeSuccessPredictor:
    """
    XGBoost Classifier to predict trade success.
    Acts as a Gatekeeper between Screening and AI Analysis.
    """
    
    def __init__(self, model_path: str = "data/models/success_predictor.pkl"):
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.features = [
            # Macro
            'vix',
            'market_regime_val', # Encoded regime
            'vix_term_structure_ratio',
            
            # Asset
            'rsi',
            'distance_to_sma200',
            'iv_rank',
            'beta',
            
            # Strategy
            'delta',
            'dte',
            'pot_probability',
            
            # Time
            'day_of_week'
        ]
        self._load_model()
        
    def _load_model(self):
        """Load trained model if exists"""
        try:
            if os.path.exists(self.model_path):
                data = joblib.load(self.model_path)
                self.model = data['model']
                self.scaler = data.get('scaler') # XGBoost doesn't strictly need scaling, but good practice
                logger.info(f"✅ Loaded Trade Success Predictor from {self.model_path}")
            else:
                logger.warning("⚠️ No trained Trade Success Predictor found. Gatekeeper is OPEN (Pass all).")
        except Exception as e:
            logger.error(f"Error loading success predictor: {e}")
            
    def train(self, trades: pd.DataFrame):
        """
        Train the model on historical trades (Real + Shadow)
        
        Args:
            trades: DataFrame with features and 'is_successful' target
        """
        try:
            import xgboost as xgb
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import accuracy_score, roc_auc_score
        except ImportError:
            logger.error("XGBoost not installed. Please run: pip install xgboost")
            return

        if trades.empty:
            logger.warning("No data to train Success Predictor.")
            return
            
        logger.info(f"Training Trade Success Predictor on {len(trades)} records...")
        
        # Prepare target
        y = trades['is_successful'].astype(int)
        
        # Prepare features
        X = trades[self.features].copy()
        X = X.fillna(0) # Simple imputation
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Train XGBoost
        self.model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            objective='binary:logistic',
            eval_metric='logloss',
            use_label_encoder=False,
            random_state=42
        )
        
        self.model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        try:
            auc = roc_auc_score(y_test, self.model.predict_proba(X_test)[:, 1])
        except:
            auc = 0.5
            
        logger.info(f"✅ Model trained. Accuracy: {acc:.2%}, AUC: {auc:.3f}")
        
        # Save
        self._save_model()
        
    def predict(self, features: Dict[str, Any]) -> float:
        """
        Predict probability of success.
        
        Returns:
            Probability (0.0 to 1.0). High score = High chance of profit.
        """
        if self.model is None:
            return 0.5 # Neutral if no model
            
        try:
            # Create DataFrame (single row)
            df = pd.DataFrame([features])
            
            # Ensure all feature columns exist
            for col in self.features:
                if col not in df.columns:
                    df[col] = 0
            
            # Predict probability of class 1 (Success)
            prob = self.model.predict_proba(df[self.features])[0][1]
            
            return prob
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return 0.5
            
    def _save_model(self):
        """Save model to disk"""
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump({
                'model': self.model,
                'scaler': self.scaler,
                'timestamp': datetime.now(),
                'features': self.features
            }, self.model_path)
            logger.info(f"Saved model to {self.model_path}")
        except Exception as e:
            logger.error(f"Error saving model: {e}")

# Singleton
_predictor = None

def get_success_predictor():
    global _predictor
    if _predictor is None:
        _predictor = TradeSuccessPredictor()
    return _predictor
