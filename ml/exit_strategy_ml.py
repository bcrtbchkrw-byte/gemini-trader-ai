"""
Exit Strategy ML Model
Predicts optimal trailing stop loss and take profit levels using XGBoost.
"""
from typing import Dict, Any, Tuple, Optional
import numpy as np
from loguru import logger
from pathlib import Path
import joblib


class ExitStrategyML:
    """
    ML-based exit strategy optimizer
    
    Predicts optimal trailing stop and profit targets based on:
    - Current position P/L
    - Time factors (days in trade, DTE)
    - Market regime
    - Volatility changes
    - Greeks evolution
    """
    
    def __init__(self, model_path: str = "ml/models/exit_strategy_ml.joblib"):
        self.model_path = Path(model_path)
        self.model = None
        self.scaler = None
        self.feature_importance = {}
        self.mode = 'UNKNOWN'
        self.fallback_warning_shown = False
        
        # Feature names for interpretability
        self.feature_names = [
            'pnl_ratio',              # Current P/L / Max Risk
            'days_in_trade',          # Days since entry
            'dte',                    # Days to expiration
            'time_ratio',             # days_in_trade / total_duration
            'vix_current',            # Current VIX
            'vix_entry',              # VIX at entry
            'vix_change',             # VIX_current - VIX_entry
            'delta_drift',            # Delta change since entry
            'theta_realization',      # Actual theta / Expected theta
            'volatility_trend',       # IV trend (rising/falling)
            'regime_stress',          # Market regime score (0-4)
            'profit_velocity'         # Rate of P/L change
        ]
        
        # Try to load existing model
        if self.model_path.exists():
            self.load_model()
            if self.model is not None:
                self.mode = 'ML'
                logger.info("✅ ExitStrategyML: Running in ML mode")
        
        if self.model is None:
            self.mode = 'RULE_BASED'
            logger.warning("")
            logger.warning("="*70)
            logger.warning("⚠️  WARNING: ExitStrategyML - NO TRAINED MODEL FOUND")
            logger.warning(f"   Model path: {model_path}")
            logger.warning("   🔴 RUNNING IN RULE-BASED FALLBACK MODE")
            logger.warning("   Using static exit targets (50% profit, 2.5x stop)")
            logger.warning("   TO FIX: Run python -m ml.scripts.train_exit_model")
            logger.warning("="*70)
            logger.warning("")
    
    def train(
        self,
        X: np.ndarray,
        y_stop: np.ndarray,
        y_profit: np.ndarray,
        test_size: float = 0.2
    ) -> Dict[str, Any]:
        """
        Train the exit strategy model
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y_stop: Optimal stop loss multipliers (n_samples,)
            y_profit: Optimal profit targets as % (n_samples,)
            test_size: Fraction for test set
            
        Returns:
            Training metrics
        """
        try:
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import StandardScaler
            from xgboost import XGBRegressor
            from sklearn.metrics import mean_squared_error, r2_score
            
            logger.info(f"Training exit strategy model on {len(X)} samples...")
            
            # Split data
            X_train, X_test, y_stop_train, y_stop_test, y_profit_train, y_profit_test = train_test_split(
                X, y_stop, y_profit, test_size=test_size, random_state=42
            )
            
            # Scale features
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train two separate models (multi-output regression)
            logger.info("Training stop loss model...")
            model_stop = XGBRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
                objective='reg:squarederror'
            )
            model_stop.fit(X_train_scaled, y_stop_train, verbose=False)
            
            logger.info("Training profit target model...")
            model_profit = XGBRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
                objective='reg:squarederror'
            )
            model_profit.fit(X_train_scaled, y_profit_train, verbose=False)
            
            # Store both models
            self.model = {
                'stop': model_stop,
                'profit': model_profit
            }
            
            # Evaluate
            y_stop_pred = model_stop.predict(X_test_scaled)
            y_profit_pred = model_profit.predict(X_test_scaled)
            
            stop_mse = mean_squared_error(y_stop_test, y_stop_pred)
            stop_r2 = r2_score(y_stop_test, y_stop_pred)
            
            profit_mse = mean_squared_error(y_profit_test, y_profit_pred)
            profit_r2 = r2_score(y_profit_test, y_profit_pred)
            
            # Feature importance (average from both models)
            importance_stop = model_stop.feature_importances_
            importance_profit = model_profit.feature_importances_
            avg_importance = (importance_stop + importance_profit) / 2
            
            self.feature_importance = dict(zip(
                self.feature_names[:len(avg_importance)],
                avg_importance
            ))
            
            logger.info(f"✅ Stop Loss Model: R² = {stop_r2:.3f}, MSE = {stop_mse:.4f}")
            logger.info(f"✅ Profit Target Model: R² = {profit_r2:.3f}, MSE = {profit_mse:.4f}")
            
            # Save model
            self.save_model()
            
            return {
                'stop_r2': stop_r2,
                'stop_mse': stop_mse,
                'profit_r2': profit_r2,
                'profit_mse': profit_mse,
                'train_samples': len(X_train),
                'test_samples': len(X_test),
                'feature_importance': self.feature_importance
            }
            
        except ImportError as e:
            logger.error(f"Missing ML dependencies: {e}")
            logger.info("Install with: pip install -r requirements_ml.txt")
            return {'error': str(e)}
            
        except Exception as e:
            logger.error(f"Error training exit strategy model: {e}")
            return {'error': str(e)}
    
    def predict_exit_levels(
        self,
        features: np.ndarray,
        entry_credit: float,
        current_stop: float = None,
        current_profit: float = None
    ) -> Dict[str, Any]:
        """
        Predict optimal trailing stop and profit levels
        
        Args:
            features: Feature vector matching self.feature_names
            entry_credit: Entry credit per contract
            current_stop: Current stop level (for comparison)
            current_profit: Current profit level (for comparison)
            
        Returns:
            Dict with predictions and confidence
        """
        if self.model is None or self.scaler is None:
            # Fallback to static rules
            if not self.fallback_warning_shown:
                logger.warning("🔴 Using RULE-BASED exit levels (no ML model)")
                self.fallback_warning_shown = True
            return self._rule_based_fallback(entry_credit)
        
        try:
            # Ensure 2D for sklearn
            if features.ndim == 1:
                features = features.reshape(1, -1)
            
            # Scale features
            features_scaled = self.scaler.transform(features)
            
            # Predict
            stop_multiplier = self.model['stop'].predict(features_scaled)[0]
            profit_target_pct = self.model['profit'].predict(features_scaled)[0]
            
            # Clamp to reasonable ranges
            stop_multiplier = np.clip(stop_multiplier, 1.5, 3.5)
            profit_target_pct = np.clip(profit_target_pct, 0.4, 0.7)
            
            # Convert to actual levels
            trailing_stop = entry_credit * stop_multiplier
            trailing_profit = entry_credit * profit_target_pct
            
            # Calculate confidence (based on feature importance and values)
            confidence = self._calculate_confidence(features, stop_multiplier, profit_target_pct)
            
            logger.debug(
                f"✨ ML Exit Levels: Stop={stop_multiplier:.2f}x (${trailing_stop:.2f}), "
                f"Profit={profit_target_pct:.1%} (${trailing_profit:.2f}), "
                f"Confidence={confidence:.1%}"
            )
            
            return {
                'trailing_stop': trailing_stop,
                'trailing_profit': trailing_profit,
                'stop_multiplier': stop_multiplier,
                'profit_target_pct': profit_target_pct,
                'confidence': confidence,
                'mode': 'ML',
                'recommendation': self._get_recommendation(
                    trailing_stop, trailing_profit, 
                    current_stop, current_profit
                )
            }
            
        except Exception as e:
            logger.error(f"Error predicting exit levels: {e}")
            logger.warning("Falling back to rule-based exit levels")
            return self._rule_based_fallback(entry_credit)
    
    def _rule_based_fallback(self, entry_credit: float) -> Dict[str, Any]:
        """
        Fallback to static exit rules
        
        Default: 50% profit target, 2.5x stop loss
        """
        return {
            'trailing_stop': entry_credit * 2.5,
            'trailing_profit': entry_credit * 0.5,
            'stop_multiplier': 2.5,
            'profit_target_pct': 0.5,
            'confidence': 0.7,  # Medium confidence for static rules
            'mode': 'RULE_BASED',
            'recommendation': 'Using static exit levels'
        }
    
    def _calculate_confidence(
        self,
        features: np.ndarray,
        stop_multiplier: float,
        profit_target_pct: float
    ) -> float:
        """
        Calculate confidence score for predictions
        
        Based on:
        - Feature values (extreme values = lower confidence)
        - Prediction ranges (closer to bounds = lower confidence)
        """
        confidence = 1.0
        
        # Reduce confidence if predictions near bounds
        if stop_multiplier < 1.7 or stop_multiplier > 3.3:
            confidence *= 0.8
        
        if profit_target_pct < 0.42 or profit_target_pct > 0.68:
            confidence *= 0.8
        
        # Reduce confidence for extreme feature values
        features_flat = features.flatten()
        
        # Check P/L ratio (feature 0)
        if len(features_flat) > 0:
            pnl_ratio = features_flat[0]
            if abs(pnl_ratio) > 0.8:  # Very high P/L
                confidence *= 0.85
        
        # Check VIX change (feature 6)
        if len(features_flat) > 6:
            vix_change = features_flat[6]
            if abs(vix_change) > 10:  # Large VIX spike
                confidence *= 0.85
        
        return float(np.clip(confidence, 0.4, 1.0))
    
    def _get_recommendation(
        self,
        new_stop: float,
        new_profit: float,
        current_stop: float = None,
        current_profit: float = None
    ) -> str:
        """Generate human-readable recommendation"""
        if current_stop is None or current_profit is None:
            return "Initialize trailing levels"
        
        stop_change = ((new_stop - current_stop) / current_stop * 100) if current_stop > 0 else 0
        profit_change = ((new_profit - current_profit) / current_profit * 100) if current_profit > 0 else 0
        
        recommendations = []
        
        if abs(stop_change) > 10:
            direction = "Tighten" if stop_change < 0 else "Widen"
            recommendations.append(f"{direction} stop by {abs(stop_change):.1f}%")
        
        if abs(profit_change) > 10:
            direction = "Lower" if profit_change < 0 else "Raise"
            recommendations.append(f"{direction} profit target by {abs(profit_change):.1f}%")
        
        if not recommendations:
            return "Maintain current levels"
        
        return ", ".join(recommendations)
    
    def save_model(self):
        """Save trained model to disk"""
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'feature_importance': self.feature_importance,
                'feature_names': self.feature_names
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
            self.feature_names = model_data.get('feature_names', self.feature_names)
            
            logger.info(f"✅ Exit strategy model loaded from {self.model_path}")
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.model = None
            self.scaler = None


# Singleton
_exit_strategy_ml: Optional[ExitStrategyML] = None


def get_exit_strategy_ml(model_path: str = "ml/models/exit_strategy_ml.joblib") -> ExitStrategyML:
    """Get or create singleton exit strategy ML model"""
    global _exit_strategy_ml
    if _exit_strategy_ml is None:
        _exit_strategy_ml = ExitStrategyML(model_path)
    return _exit_strategy_ml
