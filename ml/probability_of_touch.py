"""
Probability of Touch (PoT) Model
Predicts the probability that an underlying price will touch a strike price before expiration.
"""
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from loguru import logger
from pathlib import Path
import joblib


class ProbabilityOfTouchModel:
    """
    ML model to predict probability of touching a strike
    
    Features:
    - Distance to strike (%)
    - Days to expiration
    - Implied volatility
    - Historical volatility
    - Price momentum (RSI, MACD)
    - Trend strength
    
    Output: Probability [0, 1] of touching strike before expiration
    """
    
    def __init__(self, model_path: str = "ml/models/probability_of_touch.joblib"):
        self.model_path = Path(model_path)
        self.model = None
        self.scaler = None
        
        # Try to load existing model
        if self.model_path.exists():
            self.load_model()
        else:
            logger.warning(f"No trained PoT model found at {model_path}")
            logger.info("Will use analytical approximation until model is trained")
    
    def extract_pot_features(
        self,
        current_price: float,
        strike: float,
        dte: int,
        iv: float,
        hv: Optional[float] = None,
        momentum: Optional[float] = None
    ) -> np.ndarray:
        """
        Extract features for PoT prediction
        
        Args:
            current_price: Current underlying price
            strike: Option strike price
            dte: Days to expiration
            iv: Implied volatility (decimal, e.g., 0.30)
            hv: Historical volatility (optional)
            momentum: Price momentum indicator (optional, -1 to 1)
            
        Returns:
            Feature vector
        """
        # Distance to strike (%)
        distance_pct = abs(strike - current_price) / current_price
        
        # Direction (1 if strike > price, -1 if strike < price)
        direction = 1.0 if strike > current_price else -1.0
        
        # Normalized DTE (assume max 365 days)
        dte_norm = dte / 365.0
        
        # Volatility features
        iv_norm = iv
        hv_norm = hv if hv is not None else iv  # Use IV as fallback
        
        # Momentum (default neutral if not provided)
        momentum_norm = momentum if momentum is not None else 0.0
        
        features = np.array([
            distance_pct,
            direction,
            dte_norm,
            iv_norm,
            hv_norm,
            momentum_norm,
            np.sqrt(dte_norm) * iv_norm,  # Volatility-time interaction
        ], dtype=np.float32)
        
        return features
    
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        test_size: float = 0.2
    ) -> Dict[str, Any]:
        """
        Train the PoT model
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Binary labels (n_samples,) - 1 if touched, 0 if not
            test_size: Fraction for test set
            
        Returns:
            Training metrics
        """
        try:
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import StandardScaler
            from xgboost import XGBRegressor
            from sklearn.metrics import mean_squared_error, r2_score
            
            logger.info(f"Training PoT model on {len(X)} samples...")
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=42
            )
            
            # Scale features
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train XGBoost Regressor
            self.model = XGBRegressor(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                objective='reg:squarederror',
                random_state=42
            )
            
            self.model.fit(
                X_train_scaled,
                y_train,
                eval_set=[(X_test_scaled, y_test)],
                verbose=False
            )
            
            # Evaluate
            y_pred = self.model.predict(X_test_scaled)
            y_pred_clipped = np.clip(y_pred, 0, 1)  # Ensure [0, 1]
            
            mse = mean_squared_error(y_test, y_pred_clipped)
            r2 = r2_score(y_test, y_pred_clipped)
            
            logger.info(f"✅ PoT model trained - MSE: {mse:.4f}, R²: {r2:.4f}")
            
            # Save model
            self.save_model()
            
            return {
                'mse': mse,
                'r2': r2,
                'train_samples': len(X_train),
                'test_samples': len(X_test)
            }
            
        except ImportError as e:
            logger.error(f"Missing ML dependencies: {e}")
            return {'error': str(e)}
            
        except Exception as e:
            logger.error(f"Error training PoT model: {e}")
            return {'error': str(e)}
    
    def predict_pot(
        self,
        current_price: float,
        strike: float,
        dte: int,
        iv: float,
        hv: Optional[float] = None,
        momentum: Optional[float] = None
    ) -> float:
        """
        Predict probability of touching strike
        
        Args:
            current_price: Current underlying price
            strike: Option strike price
            dte: Days to expiration
            iv: Implied volatility
            hv: Historical volatility (optional)
            momentum: Price momentum (optional)
            
        Returns:
            Probability [0, 1]
        """
        features = self.extract_pot_features(
            current_price, strike, dte, iv, hv, momentum
        )
        
        if self.model is None or self.scaler is None:
            # Fallback to analytical approximation
            return self._analytical_pot(current_price, strike, dte, iv)
        
        try:
            # Ensure 2D for sklearn
            if features.ndim == 1:
                features = features.reshape(1, -1)
            
            # Scale and predict
            features_scaled = self.scaler.transform(features)
            pot = self.model.predict(features_scaled)[0]
            
            # Clip to [0, 1]
            pot = float(np.clip(pot, 0.0, 1.0))
            
            logger.debug(f"PoT for strike {strike}: {pot:.1%}")
            
            return pot
            
        except Exception as e:
            logger.error(f"Error predicting PoT: {e}")
            return self._analytical_pot(current_price, strike, dte, iv)
    
    def _analytical_pot(
        self,
        current_price: float,
        strike: float,
        dte: int,
        iv: float
    ) -> float:
        """
        Analytical approximation of PoT using Black-Scholes
        
        PoT ≈ 2 * N(d2) where d2 is from Black-Scholes
        
        Simplified: PoT ≈ CDF of normal distribution
        """
        from scipy.stats import norm
        
        # Distance to strike in standard deviations
        distance = abs(strike - current_price) / current_price
        time_factor = np.sqrt(dte / 365.0)
        vol_adjusted_distance = distance / (iv * time_factor) if iv > 0 and dte > 0 else 0
        
        # Simplified PoT
        pot = 2 * (1 - norm.cdf(vol_adjusted_distance))
        
        return float(np.clip(pot, 0.0, 1.0))
    
    def get_safe_strikes(
        self,
        current_price: float,
        strike_list: List[float],
        dte: int,
        iv: float,
        max_pot: float = 0.30
    ) -> List[Tuple[float, float]]:
        """
        Filter strikes by maximum PoT threshold
        
        Args:
            current_price: Current underlying price
            strike_list: List of available strikes
            dte: Days to expiration
            iv: Implied volatility
            max_pot: Maximum acceptable PoT (default 30%)
            
        Returns:
            List of (strike, pot) tuples for safe strikes
        """
        safe_strikes = []
        
        for strike in strike_list:
            pot = self.predict_pot(current_price, strike, dte, iv)
            
            if pot <= max_pot:
                safe_strikes.append((strike, pot))
        
        # Sort by PoT (lowest first = safest)
        safe_strikes.sort(key=lambda x: x[1])
        
        logger.info(f"Found {len(safe_strikes)}/{len(strike_list)} safe strikes (PoT ≤ {max_pot:.0%})")
        
        return safe_strikes
    
    def save_model(self):
        """Save trained model to disk"""
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            
            model_data = {
                'model': self.model,
                'scaler': self.scaler
            }
            
            joblib.dump(model_data, self.model_path)
            logger.info(f"PoT model saved to {self.model_path}")
            
        except Exception as e:
            logger.error(f"Error saving PoT model: {e}")
    
    def load_model(self):
        """Load trained model from disk"""
        try:
            model_data = joblib.load(self.model_path)
            
            self.model = model_data['model']
            self.scaler = model_data['scaler']
            
            logger.info(f"✅ PoT model loaded from {self.model_path}")
            
        except Exception as e:
            logger.error(f"Error loading PoT model: {e}")
            self.model = None
            self.scaler = None


# Singleton
_pot_model: Optional[ProbabilityOfTouchModel] = None


def get_pot_model(model_path: str = "ml/models/probability_of_touch.joblib") -> ProbabilityOfTouchModel:
    """Get or create singleton PoT model"""
    global _pot_model
    if _pot_model is None:
        _pot_model = ProbabilityOfTouchModel(model_path)
    return _pot_model
