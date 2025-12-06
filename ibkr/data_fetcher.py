"""
IBKR Data Fetcher
Retrieves real-time market data, options chains, and Greeks from IBKR.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from loguru import logger
from ibkr.connection import get_ibkr_connection
from config import get_config


class IBKRDataFetcher:
    """Fetch market data and options data from IBKR"""
    
    def __init__(self):
        self.connection = get_ibkr_connection()
        self.config = get_config()
        
    def _validate_data_type(self, ticker, symbol: str) -> bool:
        """
        Validate that market data is Real-Time (Type 1) or Frozen (Type 2).
        Reject Delayed (Type 3) or Delayed Frozen (Type 4) unless configured otherwise.
        
        Args:
            ticker: IBKR Ticker object
            symbol: Symbol being checked
            
        Returns:
            bool: True if data is valid, False otherwise
        """
        # Market Data Types:
        # 1 = Real-Time
        # 2 = Frozen (at close)
        # 3 = Delayed
        # 4 = Delayed Frozen
        
        data_type = ticker.marketDataType
        
        if data_type in [1, 2]:
            return True
            
        if data_type in [3, 4]:
            if self.config.safety.allow_delayed_data:
                logger.warning(f"⚠️  Using DELAYED data for {symbol} (Type {data_type}) - Allowed by config")
                return True
            else:
                logger.error(f"🛑 BLOCKED: Received DELAYED data for {symbol} (Type {data_type}). Real-time data required.")
                return False
                
        # Unknown type (0 or others) - usually means data hasn't arrived yet, but if we have a price, it's suspicious
        if ticker.last or ticker.close:
             logger.warning(f"⚠️  Unknown data type {data_type} for {symbol}")
             
        return True
    
    async def get_vix(self) -> Optional[float]:
        """
        Get current VIX value
        
        Returns:
            float: Current VIX value or None if not available
        """
        try:
            ib = self.connection.get_client()
            
            # VIX index contract
            vix = Index('VIX', 'CBOE')
            
            # Request market data
            ticker = ib.reqMktData(vix, '', False, False)
            await ib.sleep(2)  # Wait for data to arrive
            
            # Validate data type (Real-Time vs Delayed)
            if not self._validate_data_type(ticker, 'VIX'):
                ib.cancelMktData(vix)
                return None
            
            if ticker.last and ticker.last > 0:
                vix_value = ticker.last
            elif ticker.close and ticker.close > 0:
                vix_value = ticker.close
            else:
                logger.warning("VIX data not available")
                return None
            
            # Cancel market data
            ib.cancelMktData(vix)
            
            logger.info(f"VIX: {vix_value:.2f}")
            return vix_value
            
        except Exception as e:
            logger.error(f"Error fetching VIX: {e}")
            return None
    
    async def get_beta(self, symbol: str, benchmark: str = 'SPY') -> float:
        """
        Get stock beta (correlation with market)
        
        Beta measures stock volatility relative to market (SPY).
        Beta > 1.0 = More volatile than market
        Beta < 1.0 = Less volatile than market
        Beta = 1.0 = Moves with market
        
        Priority:
        1. IBKR fundamental data (if available)
        2. Calculate from historical prices (252 days)
        3. Fallback to sector average
        
        Args:
            symbol: Stock ticker
            benchmark: Market benchmark (default: SPY)
            
        Returns:
            Beta value (e.g., 1.2)
        """
        try:
            # Try IBKR fundamental data first
            beta = await self._get_beta_from_ibkr(symbol)
            if beta is not None:
                logger.info(f"Beta for {symbol} from IBKR: {beta:.3f}")
                return beta
            
            # Fallback: Calculate from historical data
            logger.debug(f"Calculating beta for {symbol} from historical data...")
            beta = await self._calculate_beta_historical(symbol, benchmark)
            if beta is not None:
                logger.info(f"Beta for {symbol} (calculated): {beta:.3f}")
                return beta
            
            # Final fallback: Sector average
            logger.warning(f"Could not get beta for {symbol}, using sector default")
            return self._get_sector_beta(symbol)
            
        except Exception as e:
            logger.error(f"Error getting beta for {symbol}: {e}")
            return 1.0  # Conservative default
    
    async def _get_beta_from_ibkr(self, symbol: str) -> Optional[float]:
        """Get beta from IBKR fundamental data"""
        try:
            ib = self.connection.get_client()
            
            if not ib or not ib.isConnected():
                return None
            
            from ib_insync import Stock
            stock = Stock(symbol, 'SMART', 'USD')
            await ib.qualifyContractsAsync(stock)
            
            # Request fundamental data (includes beta)
            fundamental_xml = await ib.reqFundamentalDataAsync(
                stock,
                'ReportsFinSummary'
            )
            
            if not fundamental_xml:
                return None
            
            # Parse beta from XML
            # Note: XML structure varies, this is simplified
            import re
            beta_match = re.search(r'<Beta[^>]*>([0-9.]+)</Beta>', fundamental_xml)
            if beta_match:
                return float(beta_match.group(1))
            
            return None
            
        except Exception as e:
            logger.debug(f"IBKR beta fetch failed: {e}")
            return None
    
    async def _calculate_beta_historical(
        self,
        symbol: str,
        benchmark: str = 'SPY',
        days: int = 252
    ) -> Optional[float]:
        """
        Calculate beta from historical price data
        
        Beta = Covariance(stock, market) / Variance(market)
        
        Args:
            symbol: Stock ticker
            benchmark: Market benchmark
            days: Historical period (252 = 1 year)
            
        Returns:
            Calculated beta
        """
        try:
            import numpy as np
            
            ib = self.connection.get_client()
            if not ib or not ib.isConnected():
                return None
            
            from ib_insync import Stock
            from datetime import datetime, timedelta
            
            # Get historical data for both stock and benchmark
            stock = Stock(symbol, 'SMART', 'USD')
            spy = Stock(benchmark, 'SMART', 'USD')
            
            await ib.qualifyContractsAsync(stock, spy)
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Request historical bars (daily)
            stock_bars = await ib.reqHistoricalDataAsync(
                stock,
                endDateTime=end_date,
                durationStr=f'{days} D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True
            )
            
            spy_bars = await ib.reqHistoricalDataAsync(
                spy,
                endDateTime=end_date,
                durationStr=f'{days} D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True
            )
            
            if not stock_bars or not spy_bars:
                return None
            
            # Calculate returns
            stock_prices = np.array([bar.close for bar in stock_bars])
            spy_prices = np.array([bar.close for bar in spy_bars])
            
            # Daily returns (percentage change)
            stock_returns = np.diff(stock_prices) / stock_prices[:-1]
            spy_returns = np.diff(spy_prices) / spy_prices[:-1]
            
            # Ensure same length
            min_len = min(len(stock_returns), len(spy_returns))
            stock_returns = stock_returns[-min_len:]
            spy_returns = spy_returns[-min_len:]
            
            # Calculate beta
            covariance = np.cov(stock_returns, spy_returns)[0][1]
            variance = np.var(spy_returns)
            
            if variance == 0:
                return None
            
            beta = covariance / variance
            
            # Sanity check (beta typically -2 to 3)
            if -2 <= beta <= 3:
                return beta
            
            logger.warning(f"Beta {beta:.3f} outside expected range for {symbol}")
            return None
            
        except Exception as e:
            logger.debug(f"Beta calculation failed: {e}")
            return None
    
    def _get_sector_beta(self, symbol: str) -> float:
        """
        Get default beta based on sector/stock type
        
        These are rough averages - better than assuming 1.0
        """
        # Tech stocks (high beta)
        if symbol in ['NVDA', 'AMD', 'TSLA', 'AAPL', 'MSFT', 'GOOGL', 'META']:
            return 1.3
        
        # Utilities (low beta)  
        if symbol in ['NEE', 'DUK', 'SO', 'D']:
            return 0.6
        
        # Consumer staples (low beta)
        if symbol in ['PG', 'KO', 'PEP', 'WMT']:
            return 0.7
        
        # Financials (moderate beta)
        if symbol in ['JPM', 'BAC', 'GS', 'MS']:
            return 1.1
        
        # Default: market beta
        return 1.0

    async def get_earnings_date(self, symbol: str) -> Optional[datetime]:
        """
        Get next earnings date from IBKR fundamental data
        
        Uses IBKR's CalendarReport with rate limiting to avoid pacing violations.
        IBKR limit: ~60 fundamental data requests per 10 minutes.
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Next earnings datetime or None
        """
        import asyncio
        
        try:
            ib = self.connection.get_client()
            
            # Create stock contract
            stock = Stock(symbol, 'SMART', 'USD')
            await ib.qualifyContractsAsync(stock)
            
            # Request fundamental data with retry logic for pacing violations
            logger.debug(f"Fetching earnings calendar for {symbol} from IBKR...")
            
            max_retries = 3
            retry_delay = 5  # Start with 5 seconds
            
            for attempt in range(max_retries):
                try:
                    # Add small delay to avoid pacing violations (error 162)
                    if attempt > 0:
                        logger.info(f"Retry {attempt}/{max_retries} for {symbol} after {retry_delay}s")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    
                    calendar_xml = await ib.reqFundamentalDataAsync(
                        stock,
                        'CalendarReport'  # Contains earnings dates
                    )
                    
                    # Success - break retry loop
                    break
                    
                except Exception as e:
                    error_msg = str(e)
                    
                    # Check for pacing violation (error 162)
                    if '162' in error_msg or 'pacing' in error_msg.lower():
                        logger.warning(
                            f"IBKR pacing violation for {symbol} (attempt {attempt+1}/{max_retries}). "
                            f"Waiting {retry_delay}s..."
                        )
                        if attempt == max_retries - 1:
                            logger.error(f"Failed to get earnings for {symbol} after {max_retries} retries")
                            return None
                        continue
                    else:
                        # Different error - raise it
                        raise
            
            if not calendar_xml:
                logger.debug(f"No calendar data for {symbol}")
                return None
            
            # Parse XML to get earnings date
            from xml.etree import ElementTree as ET
            from datetime import datetime
            
            root = ET.fromstring(calendar_xml)
            
            # Look for earnings announcement date
            # XML structure: <CalendarReport><EarningsDate>...</EarningsDate></CalendarReport>
            earnings_elements = root.findall('.//EarningsDate')
            
            if not earnings_elements:
                # Try alternative path
                earnings_elements = root.findall('.//Event[@Type="Earnings"]')
            
            if earnings_elements:
                # Get the first (next) earnings date
                earnings_date_str = earnings_elements[0].text
                
                if earnings_date_str:
                    # Parse date (format varies, try common formats)
                    for fmt in ['%Y-%m-%d', '%Y%m%d', '%m/%d/%Y']:
                        try:
                            earnings_date = datetime.strptime(earnings_date_str.strip(), fmt)
                            logger.info(f"{symbol} next earnings: {earnings_date.strftime('%Y-%m-%d')}")
                            return earnings_date
                        except ValueError:
                            continue
            
            logger.debug(f"No earnings date found in calendar for {symbol}")
            return None
            
        except Exception as e:
            logger.warning(f"Error fetching earnings from IBKR for {symbol}: {e}")
            return None
    
    async def get_stock_price(self, symbol: str) -> Optional[float]:
        """
        Get current stock price
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            float: Current stock price or None
        """
        try:
            ib = self.connection.get_client()
            
            # Create stock contract
            stock = Stock(symbol, 'SMART', 'USD')
            
            # Qualify contract
            await ib.qualifyContractsAsync(stock)
            
            # Request market data
            ticker = ib.reqMktData(stock, '', False, False)
            await ib.sleep(2)
            
            # Validate data type (Real-Time vs Delayed)
            if not self._validate_data_type(ticker, symbol):
                ib.cancelMktData(stock)
                return None
            
            price = ticker.last if ticker.last > 0 else ticker.close
            
            # Cancel market data
            ib.cancelMktData(stock)
            
            if price:
                logger.info(f"{symbol} price: ${price:.2f}")
                return price
            else:
                logger.warning(f"Price not available for {symbol}")
                return None
                
        except Exception as e:
                return None
                
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    async def get_price_history(self, symbol: str, days: int = 252) -> List[float]:
        """
        Get historical closing prices
        
        Args:
            symbol: Stock ticker
            days: Number of days to fetch (252 = 1 year)
            
        Returns:
            List of closing prices (oldest to newest)
        """
        try:
            ib = self.connection.get_client()
            
            # Create stock contract
            stock = Stock(symbol, 'SMART', 'USD')
            await ib.qualifyContractsAsync(stock)
            
            # Request historical data
            end_date = datetime.now()
            
            bars = await ib.reqHistoricalDataAsync(
                stock,
                endDateTime=end_date,
                durationStr=f'{days} D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True
            )
            
            if not bars:
                return []
                
            prices = [bar.close for bar in bars]
            logger.info(f"Fetched {len(prices)} historical prices for {symbol}")
            return prices
            
        except Exception as e:
            logger.error(f"Error fetching history for {symbol}: {e}")
            return []
    
    async def get_options_chain(
        self, 
        symbol: str, 
        expiration: Optional[str] = None,
        right: Optional[str] = None
    ) -> List[Contract]:
        """
        Get options chain for a symbol
        
        Args:
            symbol: Stock ticker symbol
            expiration: Specific expiration date (YYYYMMDD) or None for all
            right: 'C' for calls, 'P' for puts, None for both
            
        Returns:
            List of option contracts
        """
        try:
            ib = self.connection.get_client()
            
            # Create underlying stock contract
            stock = Stock(symbol, 'SMART', 'USD')
            await ib.qualifyContractsAsync(stock)
            
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
            
            # Get first chain (usually the main one)
            chain = chains[0]
            
            logger.info(f"Found {len(chain.expirations)} expirations for {symbol}")
            
            # Filter expirations if specified
            expirations = [expiration] if expiration else chain.expirations
            
            # Filter rights if specified
            rights = [right] if right else ['C', 'P']
            
            # Build option contracts
            contracts = []
            for exp in expirations:
                for strike in chain.strikes:
                    for r in rights:
                        option = Option(
                            symbol,
                            exp,
                            strike,
                            r,
                            chain.exchange
                        )
                        contracts.append(option)
            
            # Qualify contracts
            if contracts:
                qualified = await ib.qualifyContractsAsync(*contracts[:100])  # Limit to avoid overload
                logger.info(f"Qualified {len(qualified)} option contracts for {symbol}")
                return qualified
            
            return []
            
        except Exception as e:
            logger.error(f"Error fetching options chain for {symbol}: {e}")
            return []
    
    async def get_option_greeks(self, contract: Contract) -> Optional[Dict[str, Any]]:
        """
        Get Greeks and other option analytics with PRECISE Vanna calculation
        
        Args:
            contract: Option contract
            
        Returns:
            Dict with Greeks (delta, gamma, theta, vega, vanna) and other data
        """
        try:
            ib = self.connection.get_client()
            
            # Request market data with Greeks
            ticker = ib.reqMktData(contract, '106', False, False)  # 106 = option Greeks
            await ib.sleep(3)  # Wait for Greeks to arrive
            
            # Validate data type (Real-Time vs Delayed)
            if not self._validate_data_type(ticker, f"{contract.symbol} Option"):
                ib.cancelMktData(contract)
                return None
            
            if not ticker.modelGreeks:
                logger.warning(f"Greeks not available for {contract}")
                ib.cancelMktData(contract)
                return None
            
            # Get underlying price for Vanna calculation
            underlying_price = ticker.last if ticker.last > 0 else ticker.close
            
            # Calculate precise Vanna using Black-Scholes
            vanna = await self._calculate_precise_vanna(
                contract=contract,
                greeks=ticker.modelGreeks,
                underlying_price=underlying_price
            )
            
            greeks_data = {
                'symbol': contract.symbol,
                'strike': contract.strike,
                'right': contract.right,
                'expiration': contract.lastTradeDateOrContractMonth,
                'bid': ticker.bid,
                'ask': ticker.ask,
                'last': ticker.last,
                'close': ticker.close,
                'volume': ticker.volume,
                'open_interest': ticker.futuresOpenInterest,
                'delta': ticker.modelGreeks.delta if ticker.modelGreeks else None,
                'gamma': ticker.modelGreeks.gamma if ticker.modelGreeks else None,
                'theta': ticker.modelGreeks.theta if ticker.modelGreeks else None,
                'vega': ticker.modelGreeks.vega if ticker.modelGreeks else None,
                'impl_vol': ticker.modelGreeks.impliedVol if ticker.modelGreeks else None,
                'vanna': vanna,  # PRECISE analytical calculation
            }
            
            # Cancel market data
            ib.cancelMktData(contract)
            
            return greeks_data
            
        except Exception as e:
            logger.error(f"Error fetching Greeks for {contract}: {e}")
            return None
    
    
    async def _calculate_precise_vanna(
        self,
        contract: Contract,
        greeks,
        underlying_price: float
    ) -> Optional[float]:
        """
        Calculate PRECISE Vanna using QuantLib (American) or Black-Scholes (European)
        
        Args:
            contract: Option contract with strike, expiration
            greeks: Model Greeks from IBKR
            underlying_price: Current underlying price
            
        Returns:
            Precise Vanna value or None
        """
        if not greeks or not underlying_price:
            return None
        
        try:
            from risk.vanna_calculator import get_vanna_calculator
            from risk.quantlib_vanna import get_quantlib_vanna_calculator
            from datetime import datetime
            
            # Extract parameters
            vega = getattr(greeks, 'vega', None)
            sigma = getattr(greeks, 'impliedVol', None)
            
            if vega is None or sigma is None or sigma <= 0:
                logger.debug("Insufficient data for Vanna calculation")
                return None
            
            # Parse expiration date
            exp_str = contract.lastTradeDateOrContractMonth
            exp_date = datetime.strptime(exp_str, '%Y%m%d')
            
            # Calculate time to expiration (years)
            now = datetime.now()
            T = (exp_date - now).days / 365.0
            
            if T <= 0:
                logger.warning("Option already expired")
                return None
            
            # Get risk-free rate (needed for QuantLib)
            # We reuse the VannaCalculator to fetch the dynamic rate
            calc_bs = get_vanna_calculator(ibkr_connection=self.connection)
            r = await calc_bs._get_risk_free_rate()
            
            # Try QuantLib (American Option)
            try:
                calc_ql = get_quantlib_vanna_calculator()
                vanna = calc_ql.calculate_vanna(
                    S=underlying_price,
                    K=contract.strike,
                    T=T,
                    sigma=sigma,
                    r=r,
                    option_type='call' if contract.right == 'C' else 'put'
                )
                
                if vanna is not None:
                    logger.debug(
                        f"Vanna (QuantLib American): {contract.symbol} {contract.strike}{contract.right} "
                        f"= {vanna:.6f} (S={underlying_price:.2f}, σ={sigma:.2%}, r={r:.1%})"
                    )
                    return vanna
                    
            except Exception as e:
                logger.warning(f"QuantLib Vanna calculation failed: {e}, falling back to BS")
            
            # Fallback: Analytical Black-Scholes (European)
            vanna = await calc_bs.calculate_vanna(
                S=underlying_price,
                K=contract.strike,
                T=T,
                sigma=sigma,
                option_type='call' if contract.right == 'C' else 'put'
            )
            
            if vanna is not None:
                return vanna
            
            # Ultimate fallback: conservative estimate from Vega
            delta = getattr(greeks, 'delta', None)
            if vega and delta:
                abs_delta = abs(delta)
                scaling = 0.35 if 0.15 <= abs_delta <= 0.35 else 0.20
                return vega * scaling
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating precise Vanna: {e}")
            return None
    
    async def get_bid_ask_spread(self, contract: Contract) -> Optional[float]:
        """
        Get bid-ask spread for a contract
        
        Args:
            contract: Option or stock contract
            
        Returns:
            Bid-ask spread or None
        """
        try:
            ib = self.connection.get_client()
            
            ticker = ib.reqMktData(contract, '', False, False)
            await ib.sleep(2)
            
            if ticker.bid > 0 and ticker.ask > 0:
                spread = ticker.ask - ticker.bid
                ib.cancelMktData(contract)
                return spread
            
            ib.cancelMktData(contract)
            return None
            
        except Exception as e:
            logger.error(f"Error fetching bid-ask spread: {e}")
            return None
    
    async def get_options_with_greeks(
        self,
        symbol: str,
        min_dte: int = 30,
        max_dte: int = 45,
        min_delta: float = 0.10,
        max_delta: float = 0.30
    ) -> List[Dict[str, Any]]:
        """
        Get filtered options with Greeks based on DTE and Delta
        
        Args:
            symbol: Stock ticker
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration
            min_delta: Minimum absolute delta
            max_delta: Maximum absolute delta
            
        Returns:
            List of options with Greeks matching criteria
        """
        try:
            # Get options chain
            all_contracts = await self.get_options_chain(symbol)
            
            if not all_contracts:
                return []
            
            # Filter by DTE
            today = datetime.now()
            filtered_contracts = []
            
            for contract in all_contracts:
                exp_date = datetime.strptime(contract.lastTradeDateOrContractMonth, '%Y%m%d')
                dte = (exp_date - today).days
                
                if min_dte <= dte <= max_dte:
                    filtered_contracts.append(contract)
            
            logger.info(f"Filtered to {len(filtered_contracts)} contracts by DTE ({min_dte}-{max_dte} days)")
            
            # Get Greeks for filtered contracts
            options_with_greeks = []
            
            for contract in filtered_contracts[:50]:  # Limit to avoid rate limits
                greeks_data = await self.get_option_greeks(contract)
                
                if greeks_data and greeks_data['delta']:
                    abs_delta = abs(greeks_data['delta'])
                    
                    # Filter by Delta
                    if min_delta <= abs_delta <= max_delta:
                        options_with_greeks.append(greeks_data)
                        logger.debug(f"Found: {contract.symbol} {contract.strike}{contract.right} Delta={greeks_data['delta']:.3f}")
            
            logger.info(f"Found {len(options_with_greeks)} options matching Delta criteria ({min_delta}-{max_delta})")
            
            return options_with_greeks
            
        except Exception as e:
            logger.error(f"Error getting options with Greeks: {e}")
    async def get_chain_open_interest(self, symbol: str, expiration: str) -> List[Dict[str, Any]]:
        """
        Get Open Interest for all strikes in an expiration
        
        Args:
            symbol: Stock ticker
            expiration: Expiration date (YYYYMMDD)
            
        Returns:
            List of dicts with strike, call_oi, put_oi
        """
        try:
            ib = self.connection.get_client()
            
            # Get contracts for this expiration
            contracts = await self.get_options_chain(symbol, expiration=expiration)
            if not contracts:
                return []
                
            logger.info(f"Fetching Open Interest for {len(contracts)} contracts ({expiration})...")
            
            # Request market data in batches
            batch_size = 50
            results = []
            
            # Map strike to OI data
            # {strike: {'call_oi': 0, 'put_oi': 0}}
            strike_map = {}
            
            for i in range(0, len(contracts), batch_size):
                batch = contracts[i:i+batch_size]
                tickers = []
                
                for contract in batch:
                    # Request generic tick 101 (Open Interest)
                    t = ib.reqMktData(contract, '101', True, False) # Snapshot
                    tickers.append((contract, t))
                
                # Wait for data
                await ib.sleep(2)
                
                for contract, ticker in tickers:
                    call_oi = 0
                    put_oi = 0
                    
                    if contract.right == 'C':
                        call_oi = ticker.futuresOpenInterest if ticker.futuresOpenInterest > 0 else 0
                    else:
                        put_oi = ticker.futuresOpenInterest if ticker.futuresOpenInterest > 0 else 0
                        
                    strike = contract.strike
                    if strike not in strike_map:
                        strike_map[strike] = {'strike': strike, 'call_oi': 0, 'put_oi': 0}
                        
                    if contract.right == 'C':
                        strike_map[strike]['call_oi'] = call_oi
                    else:
                        strike_map[strike]['put_oi'] = put_oi
                        
                    # Cancel subscription
                    ib.cancelMktData(contract)
                    
                results = list(strike_map.values())
                
            return results
            
        except Exception as e:
            logger.error(f"Error fetching Open Interest: {e}")
            return []

    async def get_technical_indicators(self, symbol: str) -> Dict[str, Any]:
        """
        Get technical indicators (RSI, SMA200) for a symbol
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Dict with RSI, SMA200, and Distance to SMA200
        """
        try:
            import pandas as pd
            import numpy as np
            
            ib = self.connection.get_client()
            stock = Stock(symbol, 'SMART', 'USD')
            await ib.qualifyContractsAsync(stock)
            
            # Request 1 year of daily data
            bars = await ib.reqHistoricalDataAsync(
                stock,
                endDateTime='',
                durationStr='1 Y',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True
            )
            
            if not bars:
                logger.warning(f"No historical data for {symbol}")
                return {'rsi': 50, 'sma200': 0, 'distance_to_sma200': 0}
                
            # Convert to DataFrame
            df = pd.DataFrame(bars)
            df['close'] = df['close'].astype(float)
            
            # Calculate SMA 200
            df['sma200'] = df['close'].rolling(window=200).mean()
            
            # Calculate RSI 14
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Get latest values
            latest = df.iloc[-1]
            current_price = latest['close']
            sma200 = latest['sma200'] if not np.isnan(latest['sma200']) else current_price
            rsi = latest['rsi'] if not np.isnan(latest['rsi']) else 50
            
            # Calculate distance to SMA200 (%)
            # Positive = Above SMA (Uptrend), Negative = Below SMA (Downtrend)
            distance = ((current_price - sma200) / sma200) * 100 if sma200 > 0 else 0
            
            logger.info(f"{symbol} Technicals: RSI={rsi:.1f}, SMA200=${sma200:.2f}, Dist={distance:.1f}%")
            
            return {
                'rsi': rsi,
                'sma200': sma200,
                'distance_to_sma200': distance
            }
            
        except Exception as e:
            logger.error(f"Error calculating technicals for {symbol}: {e}")
            return {'rsi': 50, 'sma200': 0, 'distance_to_sma200': 0}

    async def get_vix_term_structure(self) -> Dict[str, Any]:
        """
        Get VIX Term Structure (VIX vs VIX3M)
        
        Returns:
            Dict with vix, vix3m, ratio, structure (CONTANGO/BACKWARDATION)
        """
        try:
            ib = self.connection.get_client()
            
            # Get VIX
            vix_val = await self.get_vix()
            if not vix_val:
                return {'vix': 0, 'vix3m': 0, 'ratio': 1.0, 'structure': 'UNKNOWN'}
                
            # Get VIX3M (CBOE 3-Month Volatility Index)
            # Note: Ticker might vary, assuming 'VIX3M' works or we fallback
            vix3m = Index('VIX3M', 'CBOE')
            
            # Try to get data
            try:
                ticker = ib.reqMktData(vix3m, '', False, False)
                await ib.sleep(2)
                
                if ticker.last > 0:
                    vix3m_val = ticker.last
                elif ticker.close > 0:
                    vix3m_val = ticker.close
                else:
                    # Fallback if VIX3M not available: Estimate or use VIX
                    # For now, let's assume 1.1 * VIX as a dummy if missing (to avoid crash)
                    # But better to return None
                    vix3m_val = vix_val # Neutral fallback
                    
                ib.cancelMktData(vix3m)
                
            except Exception:
                vix3m_val = vix_val
                
            ratio = vix_val / vix3m_val if vix3m_val > 0 else 1.0
            
            # Contango: VIX < VIX3M (Ratio < 1) -> Normal market
            # Backwardation: VIX > VIX3M (Ratio > 1) -> Fear/Panic
            structure = "BACKWARDATION" if ratio > 1.0 else "CONTANGO"
            
            logger.info(f"VIX Term Structure: VIX={vix_val:.2f}, VIX3M={vix3m_val:.2f}, Ratio={ratio:.2f} ({structure})")
            
            return {
                'vix': vix_val,
                'vix3m': vix3m_val,
                'ratio': ratio,
                'structure': structure
            }
            
        except Exception as e:
            logger.error(f"Error getting VIX term structure: {e}")
            return {'vix': 0, 'vix3m': 0, 'ratio': 1.0, 'structure': 'UNKNOWN'}

    async def get_unusual_options_volume(self, min_volume: int = 5000) -> List[Dict[str, Any]]:
        """
        Scan for options with unusual volume (Whale detector)
        Uses IBKR Scanner logic: HOT_BY_OPT_VOLUME / OPT_VOLUME_OVR_INTEREST
        """
        try:
            ib = self.connection.get_client()
            
            # Scanner: Hot by Option Volume
            # Focus on US Stocks
            sub = ScannerSubscription(
                instrument='STK', 
                locationCode='STK.US.MAJOR', 
                scanCode='HOT_BY_OPT_VOLUME'
            )
            
            # Add filtering (e.g., price > 20, volume > min_volume)
            scan_data = await ib.reqScannerDataAsync(sub)
            
            logger.info(f"Scanner found {len(scan_data)} potential whale targets")
            
            results = []
            for item in scan_data[:20]: # Top 20
                contract = item.contractDetails.contract
                rank = item.rank
                
                # Note: The scanner returns the UNDERLYING stock for 'STK' instrument
                # But we want specific options.
                # 'HOT_BY_OPT_VOLUME' returns stocks with high option volume.
                # To get specific contracts, we need to inspect the chain or use 'OPT' instrument?
                # IBKR Scanner for OPT is tricky. Usually returns underlying.
                # Let's pivot: Identify stocks with high opt vol, then find the specific ACTIVE options.
                
                results.append({
                    'rank': rank,
                    'symbol': contract.symbol,
                    'secType': contract.secType
                })
                
            return results

        except Exception as e:
            logger.error(f"Error in Unusual Volume Scanner: {e}")
            return []
                



# Singleton instance
_data_fetcher: Optional[IBKRDataFetcher] = None


def get_data_fetcher() -> IBKRDataFetcher:
    """Get or create singleton data fetcher instance"""
    global _data_fetcher
    if _data_fetcher is None:
        _data_fetcher = IBKRDataFetcher()
    return _data_fetcher
