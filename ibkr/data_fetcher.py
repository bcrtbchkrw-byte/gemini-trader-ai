"""
IBKR Data Fetcher
Retrieves real-time market data, options chains, and Greeks from IBKR.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from ib_insync import Stock, Option, Index, Contract
from loguru import logger
from ibkr.connection import get_ibkr_connection


class IBKRDataFetcher:
    """Fetch market data and options data from IBKR"""
    
    def __init__(self):
        self.connection = get_ibkr_connection()
    
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
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None
    
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
            
            if not ticker.modelGreeks:
                logger.warning(f"Greeks not available for {contract}")
                ib.cancelMktData(contract)
                return None
            
            # Get underlying price for Vanna calculation
            underlying_price = ticker.last if ticker.last > 0 else ticker.close
            
            # Calculate precise Vanna using Black-Scholes
            vanna = self._calculate_precise_vanna(
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
    
    
    def _calculate_precise_vanna(
        self,
        contract: Contract,
        greeks,
        underlying_price: float
    ) -> Optional[float]:
        """
        Calculate PRECISE Vanna using Black-Scholes analytical formula
        
        Uses full contract details (S, K, T, σ) for accurate calculation.
        
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
            
            # Get Vanna calculator
            calc = get_vanna_calculator()
            
            # Method 1: Full analytical Black-Scholes (BEST)
            vanna = calc.calculate_vanna(
                S=underlying_price,
                K=contract.strike,
                T=T,
                sigma=sigma,
                option_type='call' if contract.right == 'C' else 'put'
            )
            
            if vanna is not None:
                logger.debug(
                    f"Vanna (analytical): {contract.symbol} {contract.strike}{contract.right} "
                    f"= {vanna:.6f} (S={underlying_price:.2f}, σ={sigma:.2%}, T={T:.3f}y)"
                )
                return vanna
            
            # Method 2: Fallback - from Vega
            vanna = calc.calculate_vanna_from_vega(
                vega=vega,
                S=underlying_price,
                K=contract.strike,
                T=T,
                sigma=sigma
            )
            
            if vanna is not None:
                logger.debug(f"Vanna (from Vega): {vanna:.6f}")
                return vanna
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating precise Vanna: {e}")
            
            # Ultimate fallback: conservative estimate
            vega = getattr(greeks, 'vega', None)
            delta = getattr(greeks, 'delta', None)
            
            if vega and delta:
                abs_delta = abs(delta)
                scaling = 0.35 if 0.15 <= abs_delta <= 0.35 else 0.20
                return vega * scaling
            
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
            return []


# Singleton instance
_data_fetcher: Optional[IBKRDataFetcher] = None


def get_data_fetcher() -> IBKRDataFetcher:
    """Get or create singleton data fetcher instance"""
    global _data_fetcher
    if _data_fetcher is None:
        _data_fetcher = IBKRDataFetcher()
    return _data_fetcher
