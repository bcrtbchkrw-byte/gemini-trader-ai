"""
Rejection Model
ML model to predict if a rejected trade is a "Missed Opportunity" (False Negative).
"""
import os
import joblib
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from loguru import logger
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from datetime import datetime

class RejectionModel:
    """
    Machine Learning model to evaluate rejected trades.
    Predicts probability that a rejection is a MISTAKE (Missed Opportunity).
    """
    
    def __init__(self, model_path: str = "data/models/rejection_model.pkl"):
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.features = [
            'confidence_score',
            'vix',
            'delta',
            'gamma',
            'theta',
            'vega',
            'iv_rank'
        ]
        self._load_model()
        
    def _load_model(self):
        """Load trained model if exists"""
        try:
            if os.path.exists(self.model_path):
                data = joblib.load(self.model_path)
                self.model = data['model']
                self.scaler = data['scaler']
                logger.info(f"✅ Loaded Rejection Model from {self.model_path}")
            else:
                logger.warning("⚠️ No trained Rejection Model found. Using dummy mode.")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            
    def train(self, trades: pd.DataFrame):
        """
        Train the model on historical shadow trades
        
        Args:
            trades: DataFrame containing shadow trades with 'outcome' column
        """
        if trades.empty:
            logger.warning("No data to train on.")
            return
            
        logger.info(f"Training Rejection Model on {len(trades)} records...")
        
        # Prepare target: 1 if Missed Opportunity (Bad Reject), 0 if Good Reject
        y = (trades['outcome'] == 'MISSED_OPPORTUNITY').astype(int)
        
        # Prepare features
        X = trades[self.features].copy()
        
        # Handle missing values
        X = X.fillna(0)
        
        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Train model
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=5,
            random_state=42,
            class_weight='balanced' # Handle imbalanced classes (few missed opps vs many good rejects)
        )
        self.model.fit(X_scaled, y)
        
        # Evaluate (simple in-sample accuracy for logging)
        score = self.model.score(X_scaled, y)
        logger.info(f"✅ Model trained. Accuracy: {score:.2%}")
        
        # Save
        self._save_model()
        
    def predict(self, trade_data: Dict[str, Any]) -> float:
        """
        Predict probability that rejecting this trade is a MISTAKE.
        
        Returns:
            Probability (0.0 to 1.0). High score = High chance we should have taken it.
        """
        if self.model is None:
            return 0.0 # Default to "Don't know"
            
        try:
            # Extract features
            features_dict = {
                'confidence_score': trade_data.get('confidence_score', 0),
                'vix': trade_data.get('vix', 20), # Default VIX
                'delta': trade_data.get('greeks', {}).get('delta', 0),
                'gamma': trade_data.get('greeks', {}).get('gamma', 0),
                'theta': trade_data.get('greeks', {}).get('theta', 0),
                'vega': trade_data.get('greeks', {}).get('vega', 0),
                'iv_rank': trade_data.get('iv_rank', 50)
            }
            
            # Create DataFrame (single row)
            df = pd.DataFrame([features_dict])
            
            # Ensure all feature columns exist (fill missing with 0)
            for col in self.features:
                if col not in df.columns:
                    df[col] = 0
            
            # Scale
            X_scaled = self.scaler.transform(df[self.features])
            
            # Predict probability of class 1 (Missed Opportunity)
            prob = self.model.predict_proba(X_scaled)[0][1]
            
            return prob
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return 0.0
            
    def _save_model(self):
        """Save model to disk"""
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump({
                'model': self.model,
                'scaler': self.scaler,
                'timestamp': datetime.now()
            }, self.model_path)
            logger.info(f"Saved model to {self.model_path}")
        except Exception as e:
            logger.error(f"Error saving model: {e}")

# Singleton
_rejection_model = None

def get_rejection_model():
    global _rejection_model
    if _rejection_model is None:
        _rejection_model = RejectionModel()
    return _rejection_model
