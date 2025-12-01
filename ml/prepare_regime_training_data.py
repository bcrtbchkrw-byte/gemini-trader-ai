"""
Prepare Training Data for RegimeClassifier
Labels historical data with market regime classes based on VIX and price action.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from loguru import logger
from typing import Dict
from ml.feature_engineering import extract_market_features


class RegimeTrainingDataPreparation:
    """
    Prepare labeled training data for regime classifier
    
    Regime Labels:
    0 - BULL_TRENDING: VIX < 15, positive momentum
    1 - BEAR_TRENDING: VIX 15-30, negative momentum
    2 - HIGH_VOL_NEUTRAL: VIX > 20, choppy (no clear trend)
    3 - LOW_VOL_NEUTRAL: VIX < 15, range-bound
    4 - EXTREME_STRESS: VIX > 30
    """
    
    REGIME_LABELS = {
        'BULL_TRENDING': 0,
        'BEAR_TRENDING': 1,
        'HIGH_VOL_NEUTRAL': 2,
        'LOW_VOL_NEUTRAL': 3,
        'EXTREME_STRESS': 4
    }
    
    def __init__(self, data_dir: str = "data/historical"):
        self.data_dir = Path(data_dir)
    
    def load_historical_data(self) -> Dict[str, pd.DataFrame]:
        """Load SPY and VIX historical data"""
        spy_file = self.data_dir / "SPY_daily_10y.csv"
        vix_file = self.data_dir / "VIX_daily_10y.csv"
        
        if not spy_file.exists() or not vix_file.exists():
            logger.error(f"Historical data files not found in {self.data_dir}")
            logger.info("Run: python -m ml.scripts.fetch_historical_data first")
            return {}
        
        spy_df = pd.read_csv(spy_file)
        vix_df = pd.read_csv(vix_file)
        
        # Convert dates
        spy_df['date'] = pd.to_datetime(spy_df['date'])
        vix_df['date'] = pd.to_datetime(vix_df['date'])
        
        logger.info(f"Loaded SPY: {len(spy_df)} days")
        logger.info(f"Loaded VIX: {len(vix_df)} days")
        
        return {'SPY': spy_df, 'VIX': vix_df}
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators for labeling"""
        df = df.copy()
        
        # Price returns
        df['returns_1d'] = df['close'].pct_change(1)
        df['returns_5d'] = df['close'].pct_change(5)
        df['returns_20d'] = df['close'].pct_change(20)
        
        # Moving averages
        df['sma_20'] = df['close'].rolling(20).mean()
        df['sma_50'] = df['close'].rolling(50).mean()
        df['sma_200'] = df['close'].rolling(200).mean()
        
        # Volatility
        df['volatility_20d'] = df['returns_1d'].rolling(20).std() * np.sqrt(252)
        
        # RSI
        df['rsi_14'] = self._calculate_rsi(df['close'], 14)
        
        # ATR (Average True Range)
        df['atr_14'] = self._calculate_atr(df, 14)
        
        return df
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        return atr
    
    def assign_regime_labels(
        self,
        spy_df: pd.DataFrame,
        vix_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Assign regime labels to each day based on market conditions
        
        Logic:
        1. VIX > 30 → EXTREME_STRESS (4)
        2. VIX 20-30 + negative momentum → BEAR_TRENDING (1)
        3. VIX > 20 + choppy → HIGH_VOL_NEUTRAL (2)
        4. VIX < 15 + positive momentum → BULL_TRENDING (0)
        5. VIX < 15 + no trend → LOW_VOL_NEUTRAL (3)
        """
        # Merge SPY and VIX data
        merged = pd.merge(spy_df, vix_df[['date', 'close']], on='date', suffixes=('_spy', '_vix'))
        
        # Calculate indicators
        merged = self.calculate_technical_indicators(merged)
        
        # Initialize regime column
        merged['regime'] = -1
        
        # Rule 1: EXTREME_STRESS (VIX > 30)
        merged.loc[merged['close_vix'] > 30, 'regime'] = self.REGIME_LABELS['EXTREME_STRESS']
        
        # Rule 2: BEAR_TRENDING (VIX 15-30, negative momentum)
        bear_mask = (
            (merged['close_vix'] >= 15) &
            (merged['close_vix'] <= 30) &
            (merged['returns_20d'] < -0.05) &  # Down >5% over 20 days
            (merged['regime'] == -1)
        )
        merged.loc[bear_mask, 'regime'] = self.REGIME_LABELS['BEAR_TRENDING']
        
        # Rule 3: HIGH_VOL_NEUTRAL (VIX > 20, choppy - no strong trend)
        high_vol_neutral_mask = (
            (merged['close_vix'] > 20) &
            (merged['returns_20d'].abs() < 0.05) &  # Low 20-day returns
            (merged['regime'] == -1)
        )
        merged.loc[high_vol_neutral_mask, 'regime'] = self.REGIME_LABELS['HIGH_VOL_NEUTRAL']
        
        # Rule 4: BULL_TRENDING (VIX < 15, positive momentum)
        bull_mask = (
            (merged['close_vix'] < 15) &
            (merged['returns_20d'] > 0.03) &  # Up >3% over 20 days
            (merged['close_spy'] > merged['sma_50']) &  # Price above 50-day MA
            (merged['regime'] == -1)
        )
        merged.loc[bull_mask, 'regime'] = self.REGIME_LABELS['BULL_TRENDING']
        
        # Rule 5: LOW_VOL_NEUTRAL (VIX < 15, range-bound)
        low_vol_neutral_mask = (
            (merged['close_vix'] < 15) &
            (merged['regime'] == -1)
        )
        merged.loc[low_vol_neutral_mask, 'regime'] = self.REGIME_LABELS['LOW_VOL_NEUTRAL']
        
        # Count labels
        regime_counts = merged['regime'].value_counts().sort_index()
        logger.info("Regime distribution:")
        for regime_name, regime_id in self.REGIME_LABELS.items():
            count = regime_counts.get(regime_id, 0)
            logger.info(f"  {regime_name}: {count} days ({count/len(merged)*100:.1f}%)")
        
        return merged
    
    def create_feature_matrix(self, labeled_df: pd.DataFrame) -> tuple:
        """
        Create feature matrix (X) and labels (y) for training
        
        Features:
        - VIX level
        - VIX change (1d, 5d)
        - SPY returns (1d, 5d, 20d)
        - SPY volatility
        - RSI
        - Price vs moving averages
        """
        # Drop rows with NaN (from rolling calculations)
        df = labeled_df.dropna().copy()
        
        # Calculate additional features
        df['vix_change_1d'] = df['close_vix'].pct_change(1)
        df['vix_change_5d'] = df['close_vix'].pct_change(5)
        df['price_vs_sma20'] = (df['close_spy'] - df['sma_20']) / df['sma_20']
        df['price_vs_sma50'] = (df['close_spy'] - df['sma_50']) / df['sma_50']
        
        # Feature columns
        feature_cols = [
            'close_vix',           # 0: VIX level
            'vix_change_1d',       # 1: VIX 1-day change
            'vix_change_5d',       # 2: VIX 5-day change
            'volatility_20d',      # 3: Historical volatility
            'returns_1d',          # 4: SPY 1-day return
            'returns_5d',          # 5: SPY 5-day return
            'returns_20d',         # 6: SPY 20-day return
            'rsi_14',              # 7: RSI
            'price_vs_sma20',      # 8: Price vs 20-day MA
            'price_vs_sma50',      # 9: Price vs 50-day MA
        ]
        
        # Drop final NaNs
        df = df.dropna(subset=feature_cols + ['regime'])
        
        X = df[feature_cols].values
        y = df['regime'].values
        
        logger.info(f"Created feature matrix: X shape = {X.shape}, y shape = {y.shape}")
        logger.info(f"Features: {feature_cols}")
        
        # Save feature names for reference
        feature_names_file = self.data_dir / "regime_feature_names.txt"
        with open(feature_names_file, 'w') as f:
            for i, name in enumerate(feature_cols):
                f.write(f"{i}: {name}\n")
        
        logger.info(f"Feature names saved to {feature_names_file}")
        
        return X, y, feature_cols
    
    def prepare_and_save(self, output_file: str = "regime_training_data.npz"):
        """Complete pipeline: load, label, create features, save"""
        logger.info("Starting regime training data preparation...")
        
        # Load data
        data = self.load_historical_data()
        if not data:
            return False
        
        # Assign labels
        labeled_df = self.assign_regime_labels(data['SPY'], data['VIX'])
        
        # Create feature matrix
        X, y, feature_names = self.create_feature_matrix(labeled_df)
        
        # Save to disk
        output_path = self.data_dir / output_file
        np.savez(
            output_path,
            X=X,
            y=y,
            feature_names=feature_names
        )
        
        logger.info(f"✅ Training data saved to {output_path}")
        logger.info(f"   Samples: {len(X)}")
        logger.info(f"   Features: {X.shape[1]}")
        logger.info(f"   Classes: {len(np.unique(y))}")
        
        return True


if __name__ == '__main__':
    prep = RegimeTrainingDataPreparation()
    prep.prepare_and_save()
