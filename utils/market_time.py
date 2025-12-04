"""
Market Time Utility
Ensures the bot operates on US/Eastern time, regardless of server location.
Fetches atomic time to prevent drift and handle DST correctly.
"""
import asyncio
import aiohttp
import pytz
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger

class MarketTime:
    """
    Manages market time synchronization.
    """
    
    _offset_seconds = 0
    _last_sync = datetime.min
    _tz_eastern = pytz.timezone('US/Eastern')
    
    @classmethod
    async def sync_time(cls):
        """
        Sync with online atomic clock (WorldTimeAPI)
        """
        try:
            url = "http://worldtimeapi.org/api/timezone/America/New_York"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Parse datetime string (ISO 8601)
                        # Example: "2023-10-27T09:30:00.123456-04:00"
                        online_time_str = data['datetime']
                        
                        # We need to handle the offset manually or let datetime.fromisoformat do it
                        online_time = datetime.fromisoformat(online_time_str)
                        
                        # Current system time (UTC)
                        system_time = datetime.now(pytz.utc)
                        
                        # Calculate offset (Online - System)
                        # Note: online_time has timezone info, system_time has timezone info
                        diff = online_time - system_time
                        cls._offset_seconds = diff.total_seconds()
                        cls._last_sync = datetime.now()
                        
                        logger.info(f"✅ Time Synced! Market Time: {online_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                        logger.info(f"   System Offset: {cls._offset_seconds:.2f} seconds")
                    else:
                        logger.warning(f"Time sync failed: HTTP {response.status}")
                        
        except Exception as e:
            logger.warning(f"Time sync error: {e}. Using system time.")

    @classmethod
    def get_now(cls) -> datetime:
        """
        Get current time in US/Eastern (with offset applied)
        """
        # 1. Get system UTC time
        now_utc = datetime.now(pytz.utc)
        
        # 2. Apply offset (if any)
        if cls._offset_seconds != 0:
            now_utc += timedelta(seconds=cls._offset_seconds)
            
        # 3. Convert to US/Eastern
        return now_utc.astimezone(cls._tz_eastern)

    @classmethod
    def get_market_hours(cls):
        """
        Get today's market open/close times in US/Eastern
        """
        now = cls.get_now()
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        return market_open, market_close

    @classmethod
    def is_market_open(cls) -> bool:
        """
        Check if market is currently open
        """
        now = cls.get_now()
        
        # Check weekend
        if now.weekday() >= 5: # 5=Sat, 6=Sun
            return False
            
        # Check hours (9:30 - 16:00)
        market_open, market_close = cls.get_market_hours()
        
        return market_open <= now <= market_close

async def initialize_market_time():
    """Helper to initialize time on startup"""
    logger.info("⏳ Synchronizing Market Time...")
    await MarketTime.sync_time()

if __name__ == "__main__":
    # Test script
    from data.logger import setup_logger
    setup_logger()
    
    async def test():
        await initialize_market_time()
        now = MarketTime.get_now()
        print(f"Current Market Time: {now}")
        print(f"Is Market Open? {MarketTime.is_market_open()}")
        
    asyncio.run(test())
