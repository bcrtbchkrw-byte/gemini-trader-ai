"""
Prepare Training Data for Exit Strategy ML Model
Extracts historical trade data and labels for optimal exit points.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from loguru import logger
from typing import Dict, List, Tuple
from datetime import datetime
import asyncio


class ExitTrainingDataPreparation:
    """
    Prepare labeled training data for exit strategy ML model
    
    Process:
    1. Load closed trades from database
    2. For each trade, extract features at multiple points
    3. Label with optimal exit points (retrospectively)
    4. Generate training dataset
    """
    
    def __init__(self, data_dir: str = "data/historical"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    async def load_historical_trades(self) -> pd.DataFrame:
        """Load closed trades from database"""
        from data.database import get_database
        
        logger.info("Loading historical trades from database...")
        
        db = await get_database()
        
        cursor = await db.execute("""
            SELECT 
                id,
                symbol,
                strategy,
                entry_date,
                expiration,
                contracts,
                entry_credit,
                max_risk,
                exit_date,
                exit_price,
                exit_reason,
                pnl
            FROM positions
            WHERE status = 'CLOSED'
            AND pnl IS NOT NULL
            ORDER BY exit_date DESC
        """)
        
        rows = await cursor.fetchall()
        
        if not rows:
            logger.warning("No closed trades found in database")
            return pd.DataFrame()
        
        df = pd.DataFrame(rows, columns=[
            'id', 'symbol', 'strategy', 'entry_date', 'expiration',
            'contracts', 'entry_credit', 'max_risk', 'exit_date',
            'exit_price', 'exit_reason', 'pnl'
        ])
        
        # Convert dates
        df['entry_date'] = pd.to_datetime(df['entry_date'])
        df['expiration'] = pd.to_datetime(df['expiration'])
        df['exit_date'] = pd.to_datetime(df['exit_date'])
        
        logger.info(f"Loaded {len(df)} historical trades")
        return df
    
    def calculate_optimal_exit_labels(
        self,
        trade: pd.Series
    ) -> Tuple[float, float]:
        """
        Calculate optimal exit parameters retrospectively
        
        Args:
            trade: Single trade row
            
        Returns:
            (optimal_stop_multiplier, optimal_profit_pct)
        """
        entry_credit = trade['entry_credit']
        exit_price = trade['exit_price']
        pnl = trade['pnl']
        max_risk = trade['max_risk']
        
        # Calculate what actually happened
        actual_loss_per_contract = exit_price - entry_credit
        
        # Optimal stop loss (retrospective)
        # If trade was profitable, could have used tighter stop
        # If trade lost, optimal stop would have been just before it hit
        if pnl > 0:
            # Profitable trade - could use tighter stop
            optimal_stop_multiplier = 2.0  # Tighter
        else:
            # Loss - optimal stop would have been 1.2x the actual loss
            if entry_credit > 0:
                optimal_stop_multiplier = abs(actual_loss_per_contract / entry_credit) * 1.2
                optimal_stop_multiplier = np.clip(optimal_stop_multiplier, 1.5, 3.5)
            else:
                optimal_stop_multiplier = 2.5  # Default
        
        # Optimal profit target
        # If we captured 50%+ of max profit, that was good
        # If we exited early, should have held longer
        max_profit = entry_credit  # For credit spreads
        actual_profit_pct = (entry_credit - exit_price) / entry_credit if entry_credit > 0 else 0
        
        if actual_profit_pct >= 0.5:
            # Hit good target
            optimal_profit_pct = 0.5
        elif actual_profit_pct > 0:
            # Exited too early - could have waited
            optimal_profit_pct = min(0.65, actual_profit_pct + 0.15)
        else:
            # Loss - should have exited earlier
            optimal_profit_pct = 0.4
        
        optimal_profit_pct = np.clip(optimal_profit_pct, 0.4, 0.7)
        
        return optimal_stop_multiplier, optimal_profit_pct
    
    def create_feature_matrix(
        self,
        trades_df: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Create feature matrix and labels from trades
        
        Args:
            trades_df: DataFrame of historical trades
            
        Returns:
            (X, y_stop, y_profit) - features and labels
        """
        from ml.feature_engineering import get_feature_engineering
        
        feature_eng = get_feature_engineering()
        
        X_list = []
        y_stop_list = []
        y_profit_list = []
        
        logger.info("Extracting features from trades...")
        
        for idx, trade in trades_df.iterrows():
            try:
                # Calculate days in trade and DTE at mid-point
                entry_date = trade['entry_date']
                exit_date = trade['exit_date']
                expiration = trade['expiration']
                
                # Simulate mid-point of trade for features
                mid_point = entry_date + (exit_date - entry_date) / 2
                days_in_trade = (mid_point - entry_date).days
                dte = (expiration - mid_point).days
                
                # Build position data dict
                position_data = {
                    'entry_credit': trade['entry_credit'],
                    'max_risk': trade['max_risk'],
                    'contracts': trade['contracts'],
                    'entry_date': entry_date,
                    'expiration': expiration,
                    'vix_entry': 18.0,  # Default (TODO: store this in future)
                    'delta_entry': 0.2,  # Default
                    'theta_entry': 1.5,  # Default
                    'iv_entry': 0.3,  # Default
                    'highest_profit_seen': trade['pnl'] * 0.8 if trade['pnl'] > 0 else 0
                }
                
                # Market data at mid-point
                market_data = {
                    'vix': 17.0,  # Default (TODO: fetch historical VIX)
                    'delta_current': 0.22,
                    'iv_current': 0.28,
                    'regime': 'NORMAL'
                }
                
                # Current price at mid-point (estimate)
                current_price = trade['entry_credit'] * 0.7  # Assume 30% of profit captured
                
                # Extract features
                features = feature_eng.extract_exit_features(
                    position_data=position_data,
                    current_price=current_price,
                    market_data=market_data
                )
                
                # Calculate optimal labels
                optimal_stop, optimal_profit = self.calculate_optimal_exit_labels(trade)
                
                X_list.append(features)
                y_stop_list.append(optimal_stop)
                y_profit_list.append(optimal_profit)
                
            except Exception as e:
                logger.warning(f"Error processing trade {trade['id']}: {e}")
                continue
        
        if not X_list:
            logger.error("No valid training samples generated")
            return np.array([]), np.array([]), np.array([])
        
        X = np.vstack(X_list)
        y_stop = np.array(y_stop_list)
        y_profit = np.array(y_profit_list)
        
        logger.info(f"Generated {len(X)} training samples")
        logger.info(f"Stop loss range: {y_stop.min():.2f} - {y_stop.max():.2f}")
        logger.info(f"Profit target range: {y_profit.min():.1%} - {y_profit.max():.1%}")
        
        return X, y_stop, y_profit
    
    async def prepare_and_save(
        self,
        output_file: str = "exit_training_data.npz"
    ) -> bool:
        """
        Complete pipeline: load trades, extract features, save
        
        Returns:
            True if successful
        """
        logger.info("Starting exit strategy training data preparation...")
        
        # Load historical trades
        trades_df = await self.load_historical_trades()
        
        if trades_df.empty:
            logger.error("No trades available for training")
            return False
        
        if len(trades_df) < 20:
            logger.warning(f"Only {len(trades_df)} trades - recommend at least 50 for good model")
        
        # Create feature matrix
        X, y_stop, y_profit = self.create_feature_matrix(trades_df)
        
        if len(X) == 0:
            logger.error("Failed to generate training data")
            return False
        
        # Save to disk
        output_path = self.data_dir / output_file
        np.savez(
            output_path,
            X=X,
            y_stop=y_stop,
            y_profit=y_profit
        )
        
        logger.info(f"✅ Training data saved to {output_path}")
        logger.info(f"   Samples: {len(X)}")
        logger.info(f"   Features: {X.shape[1]}")
        
        return True


async def main():
    """Test function"""
    prep = ExitTrainingDataPreparation()
    success = await prep.prepare_and_save()
    
    if success:
        logger.info("✅ Exit training data preparation complete!")
    else:
        logger.error("❌ Failed to prepare training data")


if __name__ == "__main__":
    asyncio.run(main())
