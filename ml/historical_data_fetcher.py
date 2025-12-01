"""
Historical Data Fetcher for ML Training
Downloads and stores historical OHLCV data for SPY, VIX, and options chains.
"""
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
from loguru import logger
from ib_insync import Stock, Index, Option
from ibkr.connection import get_ibkr_connection
import asyncio
import time


class HistoricalDataFetcher:
    """Fetch and store historical market data for ML training"""
    
    def __init__(self, data_dir: str = "data/historical"):
        self.connection = get_ibkr_connection()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    async def fetch_equity_history(
        self,
        symbol: str,
        years: int = 10,
        bar_size: str = '1 day'
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data for a stock/index
        
        Args:
            symbol: Ticker symbol (e.g., 'SPY', 'VIX')
            years: Number of years of history
            bar_size: Bar size ('1 day', '1 hour', etc.)
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            ib = self.connection.get_client()
            
            # Create contract
            if symbol == 'VIX':
                contract = Index(symbol, 'CBOE')
            else:
                contract = Stock(symbol, 'SMART', 'USD')
            
            await ib.qualifyContractsAsync(contract)
            
            # IBKR limits: max 1 year per request for daily data
            # We'll fetch in chunks
            all_bars = []
            end_date = datetime.now()
            
            for year in range(years):
                chunk_end = end_date - timedelta(days=365 * year)
                chunk_start = chunk_end - timedelta(days=365)
                
                logger.info(f"Fetching {symbol} data from {chunk_start.date()} to {chunk_end.date()}...")
                
                try:
                    bars = await ib.reqHistoricalDataAsync(
                        contract,
                        endDateTime=chunk_end,
                        durationStr='1 Y',
                        barSizeSetting=bar_size,
                        whatToShow='TRADES',
                        useRTH=True,
                        formatDate=1
                    )
                    
                    if bars:
                        all_bars.extend(bars)
                        logger.info(f"  ✓ Fetched {len(bars)} bars")
                    else:
                        logger.warning(f"  ✗ No data for this period")
                    
                    # Rate limiting - IBKR has strict limits
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error fetching chunk {year}: {e}")
                    continue
            
            if not all_bars:
                logger.error(f"No historical data retrieved for {symbol}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame([
                {
                    'date': bar.date,
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume
                }
                for bar in all_bars
            ])
            
            # Sort by date
            df = df.sort_values('date').reset_index(drop=True)
            
            # Remove duplicates
            df = df.drop_duplicates(subset=['date'], keep='last')
            
            logger.info(f"✅ Retrieved {len(df)} bars for {symbol} ({df['date'].min()} to {df['date'].max()})")
            
            # Save to CSV
            csv_path = self.data_dir / f"{symbol}_daily_{years}y.csv"
            df.to_csv(csv_path, index=False)
            logger.info(f"Saved to {csv_path}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching equity history for {symbol}: {e}")
            return pd.DataFrame()
    
    async def fetch_incremental_data(
        self,
        symbol: str,
        days: int = 35,
        bar_size: str = '1 day'
    ) -> pd.DataFrame:
        """
        Fetch recent data and append to existing historical data
        
        This method:
        1. Loads existing historical data from CSV
        2. Fetches last N days of new data
        3. Merges and removes duplicates
        4. Saves updated data back to CSV
        
        Used for monthly retraining to accumulate data over time.
        
        Args:
            symbol: Ticker symbol
            days: Number of recent days to fetch (default 35 for monthly update)
            bar_size: Bar size
            
        Returns:
            Complete DataFrame with old + new data
        """
        try:
            ib = self.connection.get_client()
            
            # Create contract
            if symbol == 'VIX':
                contract = Index(symbol, 'CBOE')
            else:
                contract = Stock(symbol, 'SMART', 'USD')
            
            await ib.qualifyContractsAsync(contract)
            
            # Fetch recent data
            logger.info(f"Fetching last {days} days of {symbol} data...")
            
            bars = await ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',  # Now
                durationStr=f'{days} D',
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )
            
            if not bars:
                logger.warning(f"No new data retrieved for {symbol}")
                return pd.DataFrame()
            
            # Convert new data to DataFrame
            new_df = pd.DataFrame([
                {
                    'date': bar.date,
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume
                }
                for bar in bars
            ])
            
            logger.info(f"✅ Fetched {len(new_df)} new bars for {symbol}")
            
            # Load existing data if available
            csv_pattern = self.data_dir / f"{symbol}_daily_*.csv"
            existing_files = list(self.data_dir.glob(f"{symbol}_daily_*.csv"))
            
            if existing_files:
                # Load the most recent file
                latest_file = max(existing_files, key=lambda p: p.stat().st_mtime)
                logger.info(f"Loading existing data from {latest_file.name}")
                
                existing_df = pd.read_csv(latest_file)
                existing_df['date'] = pd.to_datetime(existing_df['date'])
                
                # Combine old and new
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                
                # Remove duplicates, keep newest
                combined_df = combined_df.sort_values('date').reset_index(drop=True)
                combined_df = combined_df.drop_duplicates(subset=['date'], keep='last')
                
                logger.info(f"Combined data: {len(existing_df)} old + {len(new_df)} new = {len(combined_df)} total")
                
            else:
                logger.warning(f"No existing data found for {symbol}, using only new data")
                combined_df = new_df
            
            # Calculate years for filename (roughly)
            days_total = (combined_df['date'].max() - combined_df['date'].min()).days
            years_approx = max(1, days_total // 365)
            
            # Save updated data
            csv_path = self.data_dir / f"{symbol}_daily_{years_approx}y.csv"
            combined_df.to_csv(csv_path, index=False)
            logger.info(f"✅ Saved updated data to {csv_path}")
            logger.info(f"   Date range: {combined_df['date'].min()} to {combined_df['date'].max()}")
            logger.info(f"   Total rows: {len(combined_df)}")
            
            return combined_df
            
        except Exception as e:
            logger.error(f"Error fetching incremental data for {symbol}: {e}")
            return pd.DataFrame()
    
    async def fetch_option_history(
        self,
        symbol: str,
        expiration: str,
        strike: float,
        right: str,
        years: int = 2
    ) -> pd.DataFrame:
        """
        Fetch historical data for a specific option contract
        
        Args:
            symbol: Underlying symbol
            expiration: Expiration date (YYYYMMDD)
            strike: Strike price
            right: 'C' or 'P'
            years: Years of history
            
        Returns:
            DataFrame with option price history
        """
        try:
            ib = self.connection.get_client()
            
            # Create option contract
            option = Option(symbol, expiration, strike, right, 'SMART')
            await ib.qualifyContractsAsync(option)
            
            logger.info(f"Fetching option history: {symbol} {strike}{right} exp {expiration}")
            
            # Fetch historical data
            bars = await ib.reqHistoricalDataAsync(
                option,
                endDateTime='',
                durationStr=f'{years} Y',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )
            
            if not bars:
                logger.warning(f"No historical data for option {symbol} {strike}{right}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame([
                {
                    'date': bar.date,
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume,
                    'strike': strike,
                    'right': right,
                    'expiration': expiration
                }
                for bar in bars
            ])
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching option history: {e}")
            return pd.DataFrame()
    
    async def fetch_option_chain_snapshot(
        self,
        symbol: str,
        min_dte: int = 30,
        max_dte: int = 60
    ) -> List[Dict]:
        """
        Fetch current option chain for a symbol
        
        Args:
            symbol: Underlying symbol
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration
            
        Returns:
            List of option data dictionaries
        """
        try:
            ib = self.connection.get_client()
            
            # Create underlying stock contract
            stock = Stock(symbol, 'SMART', 'USD')
            await ib.qualifyContractsAsync(stock)
            
            # Get underlying price
            ticker = ib.reqMktData(stock, '', False, False)
            await asyncio.sleep(2)
            underlying_price = ticker.last if ticker.last > 0 else ticker.close
            ib.cancelMktData(stock)
            
            # Request option chains
            chains = await ib.reqSecDefOptParamsAsync(
                stock.symbol,
                '',
                stock.secType,
                stock.conId
            )
            
            if not chains:
                logger.warning(f"No options chains found for {symbol}")
                return []
            
            chain = chains[0]
            today = datetime.now()
            
            # Filter expirations by DTE
            valid_expirations = []
            for exp_str in chain.expirations:
                exp_date = datetime.strptime(exp_str, '%Y%m%d')
                dte = (exp_date - today).days
                if min_dte <= dte <= max_dte:
                    valid_expirations.append(exp_str)
            
            if not valid_expirations:
                logger.warning(f"No expirations in DTE range {min_dte}-{max_dte}")
                return []
            
            logger.info(f"Found {len(valid_expirations)} expirations for {symbol}")
            
            # Build option contracts (limit to ATM strikes)
            options_data = []
            
            for exp in valid_expirations[:2]:  # Limit to 2 expirations to avoid rate limits
                # Filter strikes near ATM (±20%)
                atm_strikes = [
                    s for s in chain.strikes
                    if 0.80 * underlying_price <= s <= 1.20 * underlying_price
                ]
                
                logger.info(f"Processing {len(atm_strikes)} strikes for expiration {exp}")
                
                for strike in atm_strikes[:20]:  # Limit strikes
                    for right in ['C', 'P']:
                        option = Option(symbol, exp, strike, right, chain.exchange)
                        
                        try:
                            await ib.qualifyContractsAsync(option)
                            
                            # Request market data with Greeks
                            ticker = ib.reqMktData(option, '106', False, False)
                            await asyncio.sleep(1)  # Rate limiting
                            
                            if ticker.modelGreeks and ticker.bid > 0:
                                options_data.append({
                                    'symbol': symbol,
                                    'underlying_price': underlying_price,
                                    'strike': strike,
                                    'right': right,
                                    'expiration': exp,
                                    'dte': (datetime.strptime(exp, '%Y%m%d') - today).days,
                                    'bid': ticker.bid,
                                    'ask': ticker.ask,
                                    'last': ticker.last,
                                    'volume': ticker.volume,
                                    'delta': ticker.modelGreeks.delta,
                                    'gamma': ticker.modelGreeks.gamma,
                                    'theta': ticker.modelGreeks.theta,
                                    'vega': ticker.modelGreeks.vega,
                                    'iv': ticker.modelGreeks.impliedVol,
                                    'timestamp': datetime.now()
                                })
                            
                            ib.cancelMktData(option)
                            
                        except Exception as e:
                            logger.debug(f"Error getting data for {strike}{right}: {e}")
                            continue
            
            logger.info(f"✅ Collected {len(options_data)} option contracts")
            
            return options_data
            
        except Exception as e:
            logger.error(f"Error fetching option chain: {e}")
            return []
    
    def save_option_chain_snapshot(
        self,
        options_data: List[Dict],
        symbol: str
    ):
        """Save option chain snapshot to CSV"""
        if not options_data:
            return
        
        df = pd.DataFrame(options_data)
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_path = self.data_dir / f"options_{symbol}_{timestamp}.csv"
        
        df.to_csv(csv_path, index=False)
        logger.info(f"Saved option chain snapshot to {csv_path}")


# Singleton
_historical_fetcher: Optional[HistoricalDataFetcher] = None


def get_historical_fetcher() -> HistoricalDataFetcher:
    """Get or create singleton historical data fetcher"""
    global _historical_fetcher
    if _historical_fetcher is None:
        _historical_fetcher = HistoricalDataFetcher()
    return _historical_fetcher
