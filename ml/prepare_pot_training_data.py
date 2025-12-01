"""
Prepare Training Data for Probability of Touch (PoT) Model
Creates labeled dataset from historical option data:
- For each historical option, check if price touched strike before expiration
- Label: y=1 if touched, y=0 if not touched

Uses multiple symbols (SPY, TSLA, NVDA, AMD) to train on different volatility profiles:
- SPY: Low volatility, stable ETF
- TSLA: High volatility, large moves
- NVDA: Tech stock, momentum-driven
- AMD: Semiconductor, volatile intraday
"""
import pandas as pd
import numpy as np
from pathlib import Path
from loguru import logger
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import asyncio
from ml.historical_data_fetcher import get_historical_fetcher


class PoTTrainingDataPreparation:
    """
    Prepare labeled training data for Probability of Touch model
    
    Process:
    1. Load historical underlying price data for multiple symbols
    2. For each historical date, identify available options
    3. For each option, look forward to expiration
    4. Check if underlying price touched the strike
    5. Label: touched=1, not touched=0
    
    Supports multiple symbols for diverse volatility profiles.
    """
    
    # Symbols with different volatility characteristics
    TRAINING_SYMBOLS = ['SPY', 'TSLA', 'NVDA', 'AMD']
    
    def __init__(self, data_dir: str = "data/historical"):
        self.data_dir = Path(data_dir)
        self.fetcher = get_historical_fetcher()
    
    def load_underlying_data(self, symbol: str = 'SPY') -> pd.DataFrame:
        """Load historical underlying price data"""
        file_path = self.data_dir / f"{symbol}_daily_10y.csv"
        
        if not file_path.exists():
            logger.error(f"Underlying data not found: {file_path}")
            return pd.DataFrame()
        
        df = pd.read_csv(file_path)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        logger.info(f"Loaded {len(df)} days of {symbol} data")
        
        return df
    
    def generate_synthetic_options(
        self,
        underlying_df: pd.DataFrame,
        symbol: str,
        num_samples: int = 10000
    ) -> pd.DataFrame:
        """
        Generate synthetic historical option scenarios
        
        Since we can't fetch all historical option chains, we'll:
        1. Sample random historical dates
        2. Create synthetic options at various strikes
        3. Label them by checking if strike was touched
        
        Args:
            underlying_df: Historical price data
            symbol: Stock/ETF symbol
            num_samples: Number of synthetic options to generate
            
        Returns:
            DataFrame with synthetic options and labels
        """
        logger.info(f"Generating {num_samples} synthetic option scenarios for {symbol}...")
        
        options_data = []
        
        # Sample random start dates (leave room for DTE)
        max_date = underlying_df['date'].max() - timedelta(days=60)
        min_date = underlying_df['date'].min() + timedelta(days=200)
        
        available_dates = underlying_df[
            (underlying_df['date'] >= min_date) &
            (underlying_df['date'] <= max_date)
        ]
        
        for i in range(num_samples):
            # Random start date
            start_idx = np.random.randint(0, len(available_dates))
            start_row = available_dates.iloc[start_idx]
            start_date = start_row['date']
            start_price = start_row['close']
            
            # Random DTE (15-60 days)
            dte = np.random.randint(15, 61)
            exp_date = start_date + timedelta(days=dte)
            
            # Random strike (±30% from current price)
            strike_offset = np.random.uniform(-0.30, 0.30)
            strike = start_price * (1 + strike_offset)
            strike = round(strike / 5) * 5  # Round to $5 increments
            
            # Random option type
            right = np.random.choice(['C', 'P'])
            
            # Calculate IV using historical volatility as proxy
            lookback_data = underlying_df[
                (underlying_df['date'] > start_date - timedelta(days=30)) &
                (underlying_df['date'] <= start_date)
            ]
            
            if len(lookback_data) > 5:
                returns = lookback_data['close'].pct_change().dropna()
                hv = returns.std() * np.sqrt(252)
                iv = hv * np.random.uniform(0.9, 1.3)  # IV slightly different from HV
            else:
                iv = 0.20  # Default
            
            # Check if strike was touched before expiration
            future_data = underlying_df[
                (underlying_df['date'] > start_date) &
                (underlying_df['date'] <= exp_date)
            ]
            
            if len(future_data) == 0:
                continue  # Skip if no future data
            
            # For calls: check if high >= strike
            # For puts: check if low <= strike
            if right == 'C':
                touched = int(future_data['high'].max() >= strike)
            else:  # Put
                touched = int(future_data['low'].min() <= strike)
            
            # Calculate features
            distance_pct = abs(strike - start_price) / start_price
            direction = 1.0 if strike > start_price else -1.0
            
            # Calculate momentum (RSI-like)
            if len(lookback_data) >= 14:
                returns = lookback_data['close'].pct_change().dropna()
                momentum = returns[-14:].mean() / returns[-14:].std() if returns[-14:].std() > 0 else 0
                momentum = np.clip(momentum, -1, 1)
            else:
                momentum = 0.0
            
            options_data.append({
                'symbol': symbol,
                'start_date': start_date,
                'exp_date': exp_date,
                'dte': dte,
                'start_price': start_price,
                'strike': strike,
                'right': right,
                'distance_pct': distance_pct,
                'direction': direction,
                'iv': iv,
                'hv': hv if 'hv' in locals() else iv,
                'momentum': momentum,
                'touched': touched
            })
            
            if (i + 1) % 1000 == 0:
                logger.info(f"  Generated {i+1}/{num_samples} samples...")
        
        df = pd.DataFrame(options_data)
        
        # Log statistics
        touch_rate = df['touched'].mean()
        logger.info(f"✅ Generated {len(df)} synthetic options for {symbol}")
        logger.info(f"   Touch rate: {touch_rate:.1%}")
        logger.info(f"   Calls: {(df['right'] == 'C').sum()}")
        logger.info(f"   Puts: {(df['right'] == 'P').sum()}")
        
        return df
    
    async def fetch_real_option_chains(
        self,
        symbol: str = 'SPY',
        num_snapshots: int = 20,
        days_between: int = 7
    ) -> pd.DataFrame:
        """
        Fetch real option chain snapshots over time
        
        This is complementary to synthetic data - provides real IV, Greeks, etc.
        
        Args:
            symbol: Underlying symbol
            num_snapshots: Number of snapshots to collect
            days_between: Days to wait between snapshots
            
        Returns:
            DataFrame with option chain snapshots
        """
        logger.info(f"Fetching {num_snapshots} real option chain snapshots...")
        logger.warning("This will take a while and requires active market hours")
        
        all_options = []
        
        for i in range(num_snapshots):
            logger.info(f"\nSnapshot {i+1}/{num_snapshots}")
            
            try:
                # Fetch current option chain
                options_data = await self.fetcher.fetch_option_chain_snapshot(
                    symbol,
                    min_dte=30,
                    max_dte=60
                )
                
                if options_data:
                    all_options.extend(options_data)
                    self.fetcher.save_option_chain_snapshot(options_data, symbol)
                
                # Wait before next snapshot
                if i < num_snapshots - 1:
                    wait_time = days_between * 24 * 3600
                    logger.info(f"Waiting {days_between} days until next snapshot...")
                    await asyncio.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Error fetching snapshot {i+1}: {e}")
                continue
        
        if not all_options:
            logger.warning("No real option data collected")
            return pd.DataFrame()
        
        df = pd.DataFrame(all_options)
        logger.info(f"✅ Collected {len(df)} real option contracts")
        
        return df
    
    def create_pot_training_features(
        self,
        options_df: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create feature matrix (X) and labels (y) for PoT model
        
        Features (matching probability_of_touch.py):
        - distance_pct: Distance to strike (%)
        - direction: 1 if strike > price, -1 otherwise
        - dte_norm: Normalized DTE (0-1)
        - iv: Implied volatility
        - hv: Historical volatility
        - momentum: Price momentum indicator
        - vol_time_interaction: sqrt(dte_norm) * iv
        """
        df = options_df.copy()
        
        # Normalize DTE
        df['dte_norm'] = df['dte'] / 365.0
        
        # Volatility-time interaction
        df['vol_time_interaction'] = np.sqrt(df['dte_norm']) * df['iv']
        
        # Feature columns
        feature_cols = [
            'distance_pct',
            'direction',
            'dte_norm',
            'iv',
            'hv',
            'momentum',
            'vol_time_interaction'
        ]
        
        # Drop rows with NaN
        df = df.dropna(subset=feature_cols + ['touched'])
        
        X = df[feature_cols].values.astype(np.float32)
        y = df['touched'].values.astype(np.float32)
        
        logger.info(f"Created PoT feature matrix: X shape = {X.shape}, y shape = {y.shape}")
        logger.info(f"Features: {feature_cols}")
        logger.info(f"Touch rate: {y.mean():.1%}")
        
        return X, y
    
    def prepare_and_save(
        self,
        symbols: List[str] = None,
        samples_per_symbol: int = 4000,
        output_file: str = "pot_training_data.npz"
    ):
        """
        Complete pipeline: generate synthetic options from multiple symbols
        
        Args:
            symbols: List of symbols to use (default: SPY, TSLA, NVDA, AMD)
            samples_per_symbol: Samples to generate per symbol
            output_file: Output filename
        """
        if symbols is None:
            symbols = self.TRAINING_SYMBOLS
        
        logger.info(f"Starting PoT training data preparation for {len(symbols)} symbols...")
        logger.info(f"Symbols: {', '.join(symbols)}")
        
        all_options = []
        
        # Generate data for each symbol
        for symbol in symbols:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing {symbol}")
            logger.info(f"{'='*60}")
            
            # Load underlying data
            underlying_df = self.load_underlying_data(symbol)
            if underlying_df.empty:
                logger.warning(f"Skip {symbol} - no data available")
                continue
            
            # Generate synthetic options
            options_df = self.generate_synthetic_options(
                underlying_df, 
                symbol,
                samples_per_symbol
            )
            
            if not options_df.empty:
                all_options.append(options_df)
        
        if not all_options:
            logger.error("Failed to generate any synthetic options")
            return False
        
        # Combine all symbols
        combined_df = pd.concat(all_options, ignore_index=True)
        logger.info(f"\n{'='*60}")
        logger.info(f"COMBINED DATASET")
        logger.info(f"{'='*60}")
        logger.info(f"Total samples: {len(combined_df)}")
        for symbol in symbols:
            count = (combined_df['symbol'] == symbol).sum()
            touch_rate = combined_df[combined_df['symbol'] == symbol]['touched'].mean()
            logger.info(f"  {symbol}: {count} samples, touch rate: {touch_rate:.1%}")
        
        # Create feature matrix
        X, y = self.create_pot_training_features(combined_df)
        
        # Save to disk
        output_path = self.data_dir / output_file
        np.savez(
            output_path,
            X=X,
            y=y,
            symbols=symbols  # Save symbol list for reference
        )
        
        logger.info(f"\n✅ PoT training data saved to {output_path}")
        logger.info(f"   Total samples: {len(X)}")
        logger.info(f"   Features: {X.shape[1]}")
        logger.info(f"   Overall touch rate: {y.mean():.1%}")
        logger.info(f"   Symbols: {', '.join(symbols)}")
        
        return True


if __name__ == '__main__':
    prep = PoTTrainingDataPreparation()
    # Generate 4000 samples per symbol = 16000 total
    prep.prepare_and_save(samples_per_symbol=4000)
