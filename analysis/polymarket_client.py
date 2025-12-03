"""
Polymarket Client
Fetches prediction market data to provide "wisdom of the crowd" signals.
"""
import aiohttp
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger
from datetime import datetime, timedelta

class PolymarketClient:
    """
    Client for interacting with Polymarket API.
    Uses Gamma API for market discovery and CLOB API for prices.
    """
    
    GAMMA_API_URL = "https://gamma-api.polymarket.com"
    CLOB_API_URL = "https://clob.polymarket.com"
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()
            
    async def _fetch(self, url: str, params: Dict[str, Any] = None) -> Any:
        """Fetch data from API with error handling"""
        try:
            session = await self._get_session()
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(f"Polymarket API error {response.status}: {url}")
                    return None
                return await response.json()
        except Exception as e:
            logger.error(f"Error fetching from Polymarket: {e}")
            return None

    async def get_macro_context(self) -> Dict[str, Any]:
        """
        Get macro-economic context from prediction markets.
        Focuses on: Fed Rates, Recession, Inflation.
        """
        cache_key = "macro_context"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]
            
        logger.info("Fetching macro context from Polymarket...")
        
        # Search for key macro markets
        # Note: In a real implementation, we might want to hardcode specific market IDs 
        # for stability, but searching allows for dynamic updates.
        queries = [
            "Fed Interest Rate",
            "Recession 2024", 
            "Inflation 2024"
        ]
        
        results = {}
        
        for query in queries:
            markets = await self.search_markets(query)
            if markets:
                # Take the top market by volume/liquidity
                top_market = markets[0]
                results[query] = {
                    "question": top_market.get("question"),
                    "probability": self._extract_probability(top_market),
                    "volume": top_market.get("volume"),
                    "url": f"https://polymarket.com/event/{top_market.get('slug')}"
                }
                
        self._update_cache(cache_key, results, ttl_minutes=60)
        return results

    async def get_crypto_sentiment(self) -> Dict[str, Any]:
        """
        Get crypto sentiment (BTC/ETH price predictions).
        Useful for correlating with crypto stocks (COIN, MSTR).
        """
        cache_key = "crypto_sentiment"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]
            
        logger.info("Fetching crypto sentiment from Polymarket...")
        
        queries = ["Bitcoin Price", "Ethereum Price"]
        results = {}
        
        for query in queries:
            markets = await self.search_markets(query)
            if markets:
                # Filter for current month/year relevant markets
                relevant_markets = [m for m in markets[:3]] # Take top 3
                
                market_data = []
                for m in relevant_markets:
                    market_data.append({
                        "question": m.get("question"),
                        "probability": self._extract_probability(m),
                        "outcome": m.get("outcomes"), # e.g. ["Yes", "No"] or price ranges
                    })
                
                results[query] = market_data
                
        self._update_cache(cache_key, results, ttl_minutes=30)
        return results

    async def get_event_probs(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for specific event probabilities (e.g. 'Tesla Earnings').
        """
        # Don't cache generic searches aggressively
        logger.info(f"Searching Polymarket for: {query}")
        
        markets = await self.search_markets(query)
        if not markets:
            return []
            
        results = []
        for m in markets[:5]: # Top 5
            results.append({
                "question": m.get("question"),
                "probability": self._extract_probability(m),
                "volume": m.get("volume"),
                "end_date": m.get("endDate")
            })
            
        return results

    async def search_markets(self, query: str) -> List[Dict[str, Any]]:
        """
        Search markets using Gamma API /public-search endpoint.
        This endpoint supports 'q' for text search and returns events.
        """
        url = f"{self.GAMMA_API_URL}/public-search"
        params = {
            "q": query
        }
        
        logger.debug(f"Searching: {url} {params}")
        data = await self._fetch(url, params)
        
        if not data:
            logger.warning(f"No data returned for query: {query}")
            return []
            
        if isinstance(data, dict):
            logger.debug(f"Response keys: {list(data.keys())}")
            # Try to find the list of items
            items = []
            for key, value in data.items():
                if isinstance(value, list):
                    items = value
                    break
            if not items:
                logger.warning("No list found in dictionary response")
                return []
        elif isinstance(data, list):
            items = data
        else:
            logger.warning(f"Unexpected response type: {type(data)}")
            return []
            
        logger.debug(f"Found {len(items)} items in response")
        
        markets = []
        for item in items:
            # Check if it's an event with markets
            if "markets" in item and isinstance(item["markets"], list):
                if not item["markets"]:
                    logger.debug(f"Skipping event {item.get('slug')}: Empty markets list")
                    continue
                    
                for m in item["markets"]:
                    # Enrich with event info
                    m["slug"] = item.get("slug")
                    m["event_title"] = item.get("title")
                    
                    # Ensure it has necessary fields
                    if m.get("question") and m.get("outcomes"):
                        markets.append(m)
                    else:
                        logger.debug(f"Skipping market in {item.get('slug')}: Missing question or outcomes")
            
            # Sometimes it might return a market directly (rare but possible)
            elif "question" in item and "outcomes" in item:
                markets.append(item)
            else:
                logger.debug(f"Skipping item: No markets or question/outcomes found. Keys: {list(item.keys())}")
                
        logger.debug(f"Parsed {len(markets)} valid markets")
        return markets

    def _extract_probability(self, market: Dict[str, Any]) -> float:
        """
        Extract probability from market data.
        Polymarket usually provides 'outcomePrices' or we calculate from CLOB.
        Gamma API often includes 'outcomePrices'.
        """
        try:
            # Try to get pre-calculated probability (last trade price)
            # outcomePrices is often a JSON string or list in Gamma API
            import json
            
            prices = market.get("outcomePrices")
            if not prices:
                return 0.5 # Default/Unknown
                
            if isinstance(prices, str):
                prices = json.loads(prices)
                
            # For Yes/No markets, we usually want the "Yes" price (index 0 or 1 depending on structure)
            # Typically ["Yes", "No"] or ["Long", "Short"]
            # We assume index 0 is the primary outcome we care about (e.g. "Yes")
            # BUT Polymarket convention varies. Usually '0' is 'No', '1' is 'Yes' for binary.
            # Let's check outcomes list
            outcomes = market.get("outcomes")
            if outcomes and isinstance(outcomes, str):
                outcomes = json.loads(outcomes)
                
            if outcomes and "Yes" in outcomes:
                yes_index = outcomes.index("Yes")
                if len(prices) > yes_index:
                    return float(prices[yes_index])
            
            # Fallback: return the first price
            return float(prices[0]) if prices else 0.5
            
        except Exception as e:
            logger.debug(f"Error extracting probability: {e}")
            return 0.5

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache is valid"""
        if key not in self._cache:
            return False
        if datetime.now() > self._cache_expiry.get(key, datetime.min):
            return False
        return True
        
    def _update_cache(self, key: str, data: Any, ttl_minutes: int):
        """Update cache"""
        self._cache[key] = data
        self._cache_expiry[key] = datetime.now() + timedelta(minutes=ttl_minutes)


# Singleton instance
_polymarket_client: Optional[PolymarketClient] = None

def get_polymarket_client() -> PolymarketClient:
    """Get or create singleton Polymarket client"""
    global _polymarket_client
    if _polymarket_client is None:
        _polymarket_client = PolymarketClient()
    return _polymarket_client
