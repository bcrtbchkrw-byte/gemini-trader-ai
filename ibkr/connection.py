"""
IBKR Connection Manager
Handles connection to TWS or IB Gateway with auto-reconnect logic.
"""
import asyncio
from typing import Optional, Dict
from ib_insync import IB, util
from loguru import logger
from config import get_config


class IBKRConnection:
    """Manages IBKR API connection with health monitoring"""
    
    def __init__(self):
        self.config = get_config().ibkr
        self.ib: Optional[IB] = None
        self._connected = False
    
    async def connect(self) -> bool:
        """
        Connect to IBKR with error handling and retry logic
        
        Returns:
            bool: True if connection successful
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                if self.ib is None:
                    self.ib = IB()
                
                if not self.ib.isConnected():
                    logger.info(f"Connecting to IBKR (Attempt {attempt + 1}/{max_retries})...")
                    await self.ib.connectAsync(
                        self.config.host,
                        self.config.port,
                        clientId=self.config.client_id
                    )
                    self._connected = True
                    logger.info("✅ Connected to IBKR")
                    
                    # Request Real-Time Data (Type 1)
                    # This tells IBKR we prefer live data. If not available, it might send delayed (Type 3).
                    # We will check the data type on each request to enforce safety.
                    self.ib.reqMarketDataType(1)
                    
                    # Verify account
                    await self._verify_account()
                    return True
                
                return True
                
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("❌ Failed to connect to IBKR after all retries")
                    self._connected = False
                    return False
    
    async def _verify_account(self):
        """Verify account exists and get account summary"""
        try:
            # Request account summary
            account_values = self.ib.accountValues(self.config.account)
            
            if not account_values:
                logger.warning(f"No account values found for account {self.config.account}")
                return
            
            # Log important account metrics
            for av in account_values:
                if av.tag in ['NetLiquidation', 'AvailableFunds', 'BuyingPower']:
                    logger.info(f"Account {av.tag}: {av.value} {av.currency}")
            
        except Exception as e:
            logger.error(f"Error verifying account: {e}")
    
    async def get_account_balance(self) -> Optional[float]:
        """Get current account balance (NetLiquidation)"""
        if not self.is_connected():
            logger.error("Not connected to IBKR")
            return None
        
        try:
            account_values = self.ib.accountValues()
            
            for value in account_values:
                if value.tag == 'NetLiquidation' and value.currency == 'USD':
                    balance = float(value.value)
                    logger.info(f"Account balance (NetLiq): ${balance:,.2f}")
                    return balance
            
            logger.warning("NetLiquidation value not found")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching account balance: {e}")
            return None
    
    async def get_available_funds(self) -> Optional[float]:
        """
        Get available funds for trading (AvailableFunds)
        
        This is the actual cash/margin available for new positions,
        excluding funds tied up in existing positions.
        
        Returns:
            Available funds in USD
        """
        if not self.is_connected():
            logger.error("Not connected to IBKR")
            return None
        
        try:
            account_values = self.ib.accountValues()
            
            for value in account_values:
                if value.tag == 'AvailableFunds' and value.currency == 'USD':
                    available = float(value.value)
                    logger.info(f"💰 Available Funds: ${available:,.2f}")
                    return available
            
            logger.warning("AvailableFunds value not found")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching available funds: {e}")
            return None
    
    async def get_buying_power(self) -> Optional[float]:
        """
        Get buying power (BuyingPower)
        
        This includes margin leverage and is typically higher than AvailableFunds.
        For conservative position sizing, use AvailableFunds instead.
        
        Returns:
            Buying power in USD
        """
        if not self.is_connected():
            logger.error("Not connected to IBKR")
            return None
        
        try:
            account_values = self.ib.accountValues()
            
            for value in account_values:
                if value.tag == 'BuyingPower' and value.currency == 'USD':
                    buying_power = float(value.value)
                    logger.info(f"💪 Buying Power: ${buying_power:,.2f}")
                    return buying_power
            
            logger.warning("BuyingPower value not found")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching buying power: {e}")
            return None
    
    async def get_account_summary(self) -> Dict[str, float]:
        """
        Get comprehensive account summary
        
        Returns:
            Dict with NetLiquidation, AvailableFunds, BuyingPower, etc.
        """
        if not self.is_connected():
            logger.error("Not connected to IBKR")
            return {}
        
        try:
            account_values = self.ib.accountValues()
            
            summary = {}
            for value in account_values:
                if value.currency == 'USD':
                    if value.tag in ['NetLiquidation', 'AvailableFunds', 'BuyingPower', 
                                    'TotalCashValue', 'GrossPositionValue']:
                        summary[value.tag] = float(value.value)
            
            logger.info(
                f"📊 Account Summary:\n"
                f"   NetLiquidation: ${summary.get('NetLiquidation', 0):,.2f}\n"
                f"   AvailableFunds: ${summary.get('AvailableFunds', 0):,.2f}\n"
                f"   BuyingPower: ${summary.get('BuyingPower', 0):,.2f}\n"
                f"   Cash: ${summary.get('TotalCashValue', 0):,.2f}\n"
                f"   Positions: ${summary.get('GrossPositionValue', 0):,.2f}"
            )
            
            return summary
            
        except Exception as e:
            logger.error(f"Error fetching account summary: {e}")
            return {}

    
    def _on_disconnected(self):
        """Callback when connection is lost"""
        logger.warning("IBKR connection lost!")
        self._connected = False
    
    async def disconnect(self):
        """Gracefully disconnect from IBKR"""
        if self.ib and self._connected:
            logger.info("Disconnecting from IBKR...")
            self.ib.disconnect()
            self._connected = False
            logger.info("Disconnected from IBKR")
    
    async def reconnect(self) -> bool:
        """Attempt to reconnect to IBKR"""
        logger.info("Attempting to reconnect to IBKR...")
        await self.disconnect()
        return await self.connect()
    
    def is_connected(self) -> bool:
        """Check if currently connected to IBKR"""
        return self._connected and self.ib is not None and self.ib.isConnected()
    
    async def ensure_connected(self) -> bool:
        """
        Ensure connection is active, reconnect if necessary
        
        Returns:
            bool: True if connected, False otherwise
        """
        if self.is_connected():
            return True
        
        logger.warning("Connection not active, attempting reconnect...")
        return await self.reconnect()
    
    def get_client(self) -> IB:
        """
        Get IB client instance
        
        Returns:
            IB: Interactive Brokers client
            
        Raises:
            RuntimeError: If not connected
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to IBKR. Call connect() first.")
        return self.ib


# Singleton instance
_connection: Optional[IBKRConnection] = None


def get_ibkr_connection() -> IBKRConnection:
    """Get or create singleton IBKR connection instance"""
    global _connection
    if _connection is None:
        _connection = IBKRConnection()
    return _connection
