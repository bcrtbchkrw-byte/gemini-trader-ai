"""
Stock Screener - Phase 1 Pipeline
Uses IBKR native scanner for high IV stock discovery (no yfinance dependency).
"""
from typing import List, Dict, Any, Optional
from loguru import logger
from ibkr.connection import get_ibkr_connection
from ib_insync import ScannerSubscription


class StockScreener:
    """Phase 1: Screen for high IV opportunities using IBKR scanner"""
    
    def __init__(self):
        self.connection = get_ibkr_connection()
        self.min_iv_rank = 50  # Minimum IV percentile
        self.max_candidates = 10  # Phase 1 output limit
    
    async def scan_high_iv_stocks(
        self,
        max_results: int = 50,
        min_price: float = 20.0,
        max_price: float = 500.0
    ) -> List[Dict[str, Any]]:
        """
        Scan for high IV stocks using IBKR native scanner
        
        Uses reqScannerSubscription - professional-grade scanner.
        NO yfinance dependency!
        
        Args:
            max_results: Maximum stocks to return from scanner
            min_price: Minimum stock price filter
            max_price: Maximum stock price filter
            
        Returns:
            List of stock candidates with IV data
        """
        try:
            ib = self.connection.get_client()
            
            if not ib or not ib.isConnected():
                logger.error("Not connected to IBKR for scanning")
                return []
            
            logger.info("🔍 Scanning for high IV stocks using IBKR scanner...")
            
            # Create scanner subscription for high IV stocks
            scanner = ScannerSubscription(
                instrument='STK',                    # Stocks only
                locationCode='STK.US',               # US stocks
                scanCode='HIGH_OPT_IMP_VOLAT',       # High option implied volatility
                abovePrice=min_price,
                belowPrice=max_price,
                numberOfRows=max_results
            )
            
            # Request scan from IBKR
            scan_data = await ib.reqScannerDataAsync(scanner)
            
            if not scan_data:
                logger.warning("Scanner returned no results")
                return []
            
            logger.info(f"IBKR scanner found {len(scan_data)} stocks")
            
            # Process scanner results
            candidates = []
            for item in scan_data[:max_results]:
                try:
                    contract = item.contractDetails.contract
                    
                    # Get real-time market data
                    ticker = ib.reqMktData(contract, '', False, False)
                    await ib.sleep(1)  # Wait for data to arrive
                    
                    # Parse scanner data
                    iv_rank = item.rank if hasattr(item, 'rank') else 50
                    
                    candidate = {
                        'symbol': contract.symbol,
                        'price': ticker.last if ticker.last > 0 else ticker.close,
                        'iv_rank': iv_rank,
                        'volume': ticker.volume if ticker.volume > 0 else 0,
                        'sector': contract.industry if hasattr(contract, 'industry') else 'Unknown',
                        'distance': item.distance if hasattr(item, 'distance') else None,
                        'score': 0  # Will calculate below
                    }
                    
                    # Calculate screening score
                    candidate['score'] = self._calculate_score(candidate)
                    
                    candidates.append(candidate)
                    
                    # Cancel market data to avoid subscriptions
                    ib.cancelMktData(contract)
                    
                except Exception as e:
                    logger.debug(f"Error processing scanner item: {e}")
                    continue
            
            # Sort by score descending
            candidates.sort(key=lambda x: x['score'], reverse=True)
            
            # Return top candidates
            top_candidates = candidates[:self.max_candidates]
            
            logger.info(
                f"✅ Phase 1 complete: {len(top_candidates)} candidates\n"
                f"Top 3: {', '.join([c['symbol'] for c in top_candidates[:3]])}"
            )
            
            return top_candidates
            
        except Exception as e:
            logger.error(f"Scanner error: {e}")
            return []
    
    def _calculate_score(self, candidate: Dict[str, Any]) -> float:
        """
        Calculate screening score for candidate
        
        Scoring factors:
        - IV rank: Higher = better for premium selling (0-50 points)
        - Price range: Prefer mid-range stocks (0-25 points)
        - Volume: Higher = better liquidity (0-25 points)
        
        Args:
            candidate: Stock data from scanner
            
        Returns:
            Total score (0-100)
        """
        score = 0.0
        
        # IV rank score (0-50 points)
        # Higher IV rank = better for options strategies
        iv_rank = candidate.get('iv_rank', 50)
        score += min(iv_rank / 2, 50)
        
        # Price score (0-25 points)
        # Prefer $50-$200 range (sweet spot for options)
        price = candidate.get('price', 0)
        if 50 <= price <= 200:
            score += 25
        elif 20 <= price <= 500:
            score += 15
        
        # Volume score (0-25 points)
        # Higher volume = better liquidity
        volume = candidate.get('volume', 0)
        if volume > 1_000_000:
            score += 25
        elif volume > 500_000:
            score += 15
        elif volume > 100_000:
            score += 10
        
        return score
    
    async def screen(
        self,
        max_candidates: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Main screening entry point - runs IBKR scanner
        
        Args:
            max_candidates: Maximum candidates to return (Phase 1 output)
            
        Returns:
            Top candidate stocks with scores
        """
        self.max_candidates = max_candidates
        
        results = await self.scan_high_iv_stocks(
            max_results=50,  # Scan 50 from market
            min_price=20.0,   # Filter $20+
            max_price=500.0   # Filter $500-
        )
        
        return results


# Singleton instance
_stock_screener: Optional['StockScreener'] = None


def get_stock_screener() -> StockScreener:
    """Get or create singleton stock screener"""
    global _stock_screener
    if _stock_screener is None:
        _stock_screener = StockScreener()
    return _stock_screener
