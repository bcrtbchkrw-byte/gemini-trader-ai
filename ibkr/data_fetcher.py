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
        Get Greeks and other option analytics
        
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
                # Vanna not directly available, need to calculate
                'vanna': self._estimate_vanna(ticker.modelGreeks) if ticker.modelGreeks else None,
            }
            
            # Cancel market data
            ib.cancelMktData(contract)
            
            return greeks_data
            
        except Exception as e:
            logger.error(f"Error fetching Greeks for {contract}: {e}")
            return None
    
    def _estimate_vanna(self, greeks) -> Optional[float]:
        """
        Estimate Vanna (dDelta/dVol)
        This is a rough estimate as IBKR doesn't provide Vanna directly
        
        Args:
            greeks: Model Greeks object
            
        Returns:
            Estimated Vanna value
        """
        if not greeks or not greeks.vega or not greeks.delta:
            return None
        
        # Vanna ≈ Vega * (1 - Delta) / IV
        # This is a simplified estimation
        if greeks.impliedVol and greeks.impliedVol > 0:
            vanna_estimate = greeks.vega * (1 - abs(greeks.delta)) / greeks.impliedVol
            return vanna_estimate
        
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
