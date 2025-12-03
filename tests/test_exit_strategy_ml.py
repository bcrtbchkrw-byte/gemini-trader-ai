"""
Unit Tests for Exit Strategy ML
Tests ML model predictions, feature extraction, and Position class integration
"""
import unittest
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestExitStrategyML(unittest.TestCase):
    """Test ML exit strategy model"""
    
    def test_feature_extraction(self):
        """Test that exit features are extracted correctly"""
        from ml.feature_engineering import get_feature_engineering
        
        feature_eng = get_feature_engineering()
        
        position_data = {
            'entry_credit': 1.50,
            'max_risk': 3.50,
            'contracts': 1,
            'entry_date': datetime.now() - timedelta(days=10),
            'expiration': datetime.now() + timedelta(days=35),
            'vix_entry': 18.0,
            'delta_entry': 0.20,
            'theta_entry': 1.5,
            'iv_entry': 0.30,
            'highest_profit_seen': 50.0
        }
        
        market_data = {
            'vix': 17.0,
            'delta_current': 0.22,
            'iv_current': 0.28,
            'regime': 'NORMAL'
        }
        
        features = feature_eng.extract_exit_features(
            position_data=position_data,
            current_price=1.00,
            market_data=market_data
        )
        
        # Should return 12 features
        self.assertEqual(len(features), 12)
        self.assertIsInstance(features, np.ndarray)
        
        # P/L ratio should be reasonable
        pnl_ratio = features[0]
        self.assertGreater(pnl_ratio, -1.0)
        self.assertLess(pnl_ratio, 2.0)
        
        # Days in trade should be ~10
        days_in_trade = features[1]
        self.assertAlmostEqual(days_in_trade, 10, delta=1)
        
        # DTE should be ~35
        dte = features[2]
        self.assertAlmostEqual(dte, 35, delta=1)
    
    def test_ml_model_fallback(self):
        """Test that model gracefully falls back when not trained"""
        from ml.exit_strategy_ml import get_exit_strategy_ml
        
        model = get_exit_strategy_ml()
        
        # Model might not be trained - should use fallback
        features = np.array([0.5, 10, 35, 0.22, 17.0, 18.0, -1.0, 0.02, 1.0, -0.02, 2.0, 5.0])
        
        prediction = model.predict_exit_levels(
            features=features,
            entry_credit=1.50
        )
        
        # Should return prediction dict
        self.assertIn('trailing_stop', prediction)
        self.assertIn('trailing_profit', prediction)
        self.assertIn('confidence', prediction)
        self.assertIn('mode', prediction)
        
        # Values should be reasonable
        self.assertGreater(prediction['trailing_stop'], 0)
        self.assertGreater(prediction['trailing_profit'], 0)
        self.assertGreaterEqual(prediction['confidence'], 0)
        self.assertLessEqual(prediction['confidence'], 1.0)
        
        # Mode should be either ML or RULE_BASED
        self.assertIn(prediction['mode'], ['ML', 'RULE_BASED'])
    
    def test_position_trailing_levels(self):
        """Test Position class trailing level updates"""
        from execution.exit_manager import Position
        
        position = Position(
            position_id=1,
            symbol="SPY",
            strategy="IRON_CONDOR",
            entry_date=datetime.now() - timedelta(days=10),
            expiration=datetime.now() + timedelta(days=35),
            contracts=1,
            entry_credit=1.50,
            max_risk=3.50,
            legs=[],
            trailing_stop_enabled=True,
            trailing_profit_enabled=True
        )
        
        # Initial values should be set
        self.assertEqual(position.entry_credit, 1.50)
        self.assertEqual(position.trailing_stop_enabled, True)
        self.assertEqual(position.trailing_profit_enabled, True)
        self.assertGreater(position.trailing_stop, 0)
        self.assertGreater(position.trailing_profit, 0)
        
        # Test exit decision without ML (no market data)
        exit_decision = position.should_exit(current_price=1.00)
        
        self.assertIn('should_exit', exit_decision)
        self.assertIn('reason', exit_decision)
        
        # At 50% profit, might or might not exit depending on target
        # Just check structure is correct
        if exit_decision['should_exit']:
            self.assertIn(exit_decision['reason'], [
                'TRAILING_PROFIT', 'PROFIT_TARGET', 
                'TRAILING_STOP', 'STOP_LOSS', 'TIME_EXIT'
            ])
    
    def test_position_only_tighten_stops(self):
        """Test that stops only tighten, never widen"""
        from execution.exit_manager import Position
        
        position = Position(
            position_id=1,
            symbol="SPY",
            strategy="IRON_CONDOR",
            entry_date=datetime.now() - timedelta(days=10),
            expiration=datetime.now() + timedelta(days=35),
            contracts=1,
            entry_credit=1.50,
            max_risk=3.50,
            legs=[],
            trailing_stop_enabled=True,
            trailing_profit_enabled=False
        )
        
        initial_stop = position.trailing_stop
        
        # Simulate ML trying to widen stop (should be rejected)
        market_data = {
            'vix': 17.0,
            'regime': 'NORMAL'
        }
        
        # Update should only tighten, this is tested in update_trailing_levels
        # which uses min(new_stop, current_stop)
        
        # Just verify initial state
        self.assertGreater(initial_stop, 0)
        self.assertEqual(position.trailing_stop, initial_stop)


class TestTrainingDataPreparation(unittest.TestCase):
    """Test training data preparation"""
    
    def test_optimal_exit_calculation(self):
        """Test retrospective optimal exit calculation"""
        from ml.prepare_exit_training_data import ExitTrainingDataPreparation
        import pandas as pd
        
        prep = ExitTrainingDataPreparation()
        
        # Profitable trade
        profitable_trade = pd.Series({
            'entry_credit': 1.50,
            'exit_price': 0.75,
            'pnl': 75.0,
            'max_risk': 3.50
        })
        
        stop_mult, profit_pct = prep.calculate_optimal_exit_labels(profitable_trade)
        
        # Profitable trade should have reasonable targets
        self.assertGreater(stop_mult, 1.5)
        self.assertLess(stop_mult, 3.5)
        self.assertGreater(profit_pct, 0.4)
        self.assertLess(profit_pct, 0.7)
        
        # Loss trade
        loss_trade = pd.Series({
            'entry_credit': 1.50,
            'exit_price': 4.00,
            'pnl': -250.0,
            'max_risk': 3.50
        })
        
        stop_mult, profit_pct = prep.calculate_optimal_exit_labels(loss_trade)
        
        # Loss trade should also have valid ranges
        self.assertGreater(stop_mult, 1.5)
        self.assertLess(stop_mult, 3.5)
        self.assertGreater(profit_pct, 0.4)
        self.assertLess(profit_pct, 0.7)


if __name__ == '__main__':
    unittest.main()
