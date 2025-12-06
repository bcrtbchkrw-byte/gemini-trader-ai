"""
Whale Detector
Analyzes option flow to identify unusual institutional activity.
Focuses on Volume/OI anomalies and aggressive premiums.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
import pandas as pd
from ibkr.data_fetcher import get_data_fetcher

class WhaleDetector:
    def __init__(self):
        self.data_fetcher = get_data_fetcher()
        
    async def scan_for_whales(self, min_volume: int = 2000) -> List[Dict[str, Any]]:
        """
        Main method to find "Whale" trades.
        1. Gets stocks with high option volume (Scanner).
        2. Drills down to find specific contracts with Vol/OI > 1.2.
        """
        logger.info("🐋 Starting Whale Scan...")
        
        # 1. Get Hot Stocks
        hot_stocks = await self.data_fetcher.get_unusual_options_volume()
        if not hot_stocks:
            logger.warning("No hot stocks found by scanner")
            return []
            
        whale_alerts = []
        
        # 2. Analyze top 5 hottest stocks to save API calls
        for item in hot_stocks[:5]:
            symbol = item['symbol']
            logger.info(f"🔎 Analysing flow for {symbol}...")
            
            try:
                # Fetch active options (e.g. next monthly expiration)
                # This is a simplification. Ideal: Monitor live feed. 
                # Here we check the most active chain.
                
                # Retrieve chains and look for high vol
                # We'll stick to near-term monthly for best liquidity
                options = await self.data_fetcher.get_options_with_greeks(
                    symbol=symbol,
                    min_dte=7,
                    max_dte=45,
                    min_delta=0.1,
                    max_delta=0.9
                )
                
                for opt in options:
                    vol = opt.get('volume', 0)
                    oi = opt.get('openInterest', 0)
                    if vol < min_volume:
                        continue
                        
                    # CRITICAL METRIC: Vol/OI Ratio
                    # If Vol > OI, it implies opening new positions (Aggressive)
                    ratio = vol / oi if oi > 0 else 10.0 # High if OI is 0
                    
                    if ratio > 1.2:
                        sentiment = 'BULLISH' if opt['right'] == 'C' else 'BEARISH'
                        alert = {
                            'symbol': symbol,
                            'contract': f"{symbol} {opt['expiration']} {opt['strike']}{opt['right']}",
                            'type': 'WHALE_ALERT',
                            'sentiment': sentiment,
                            'volume': vol,
                            'open_interest': oi,
                            'ratio': ratio,
                            'price': opt.get('stock_price', 0),
                            'strike': opt['strike'],
                            'delta': opt.get('delta', 0),
                            'timestamp': datetime.now().isoformat()
                        }
                        whale_alerts.append(alert)
                        logger.info(
                            f"🚨 WHALE DETECTED: {alert['contract']} "
                            f"Vol={vol} OI={oi} Ratio={ratio:.1f} ({sentiment})"
                        )
                        
            except Exception as e:
                logger.error(f"Error analyzing whale flow for {symbol}: {e}")
                continue
                
        return whale_alerts

    async def get_whale_score(self, symbol: str) -> float:
        """
        Get a 'Whale Score' for a specific symbol to use in ML features.
        Score > 0: Bullish Flow
        Score < 0: Bearish Flow
        Score 0: Neutral / No Activity
        """
        # TODO: Implement cached check for specific symbol
        # For now, return 0 to avoid latency in loop
        return 0.0

# Singleton
_whale_detector = None

def get_whale_detector() -> WhaleDetector:
    global _whale_detector
    if _whale_detector is None:
        _whale_detector = WhaleDetector()
    return _whale_detector
