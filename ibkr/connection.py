"""
IBKR Connection Manager
Handles connection to TWS or IB Gateway with auto-reconnect logic.
"""
from typing import Optional
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
        
        # Ensure IB instance is initialized
        if self.ib is None:
            self.ib = IB()
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to IBKR: {e}")
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
        """
        Get account net liquidation value
        
        Returns:
            float or None: Account balance in USD
        """
        try:
            account_values = self.ib.accountValues(self.config.account)
            
            for av in account_values:
                if av.tag == 'NetLiquidation' and av.currency == 'USD':
                    balance = float(av.value)
                    logger.info(f"Account balance: ${balance:.2f}")
                    return balance
            
            logger.warning("Could not find NetLiquidation value")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching account balance: {e}")
            return None

    
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
