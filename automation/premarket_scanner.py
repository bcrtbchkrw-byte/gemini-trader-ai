"""
Premarket Scanner - Find opportunities before market open
Runs once in premarket, identifies interesting stocks, saves for later analysis.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, time
from loguru import logger
import pandas as pd


class PremarketScanner:
    """Scan for premarket opportunities to avoid constant AI calls"""
    
    def __init__(self):
        self.cache_file = "data/premarket_candidates.json"
        self.last_scan_time = None
        self.cached_candidates = []
    
    async def scan_premarket(self, max_candidates: int = 15) -> List[Dict[str, Any]]:
        """
        Run full premarket scan - call ONCE per day before market open
        
        Finds stocks with:
        - Large premarket gaps (>2%)
        - High premarket volume
        - News catalysts
        - Earnings today
        
        Args:
            max_candidates: Max stocks to return
            
        Returns:
            List of candidate stocks with scores
        """
        try:
            import yfinance as yf
            
            logger.info("🔍 Starting premarket scan...")
            
            # Stock universe (can expand)
            universe = self._get_premarket_universe()
            
            candidates = []
            
            for symbol in universe:
                try:
                    ticker = yf.Ticker(symbol)
                    
                    # Get premarket data
                    hist = ticker.history(period="2d", interval="1m", prepost=True)
                    
                    if hist.empty:
                        continue
                    
                    # Calculate premarket metrics
                    metrics = self._calculate_premarket_metrics(symbol, hist, ticker)
                    
                    if metrics and metrics['score'] > 0:
                        candidates.append(metrics)
                        
                except Exception as e:
                    logger.debug(f"Error scanning {symbol}: {e}")
                    continue
            
            # Sort by score
            candidates.sort(key=lambda x: x['score'], reverse=True)
            top_candidates = candidates[:max_candidates]
            
            # Cache results
            self.cached_candidates = top_candidates
            self.last_scan_time = datetime.now()
            self._save_to_cache(top_candidates)
            
            logger.info(
                f"✅ Premarket scan complete: {len(top_candidates)} candidates found\n"
                f"Top 5: {', '.join([c['symbol'] for c in top_candidates[:5]])}"
            )
            
            return top_candidates
            
        except Exception as e:
            logger.error(f"Premarket scan error: {e}")
            return []
    
    def _get_premarket_universe(self) -> List[str]:
        """
        Get universe of stocks to scan
        Focus on liquid, volatile stocks
        """
        return [
            # High volume tech
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD",
            # Volatile growth
            "PLTR", "SNOW", "CRWD", "NET", "DDOG", "ZM", "SHOP",
            # Movers
            "MARA", "RIOT", "COIN", "SQ", "HOOD", "SOFI",
            # ETFs for market context
            "SPY", "QQQ", "IWM",
            # Energy
            "XOM", "CVX", "SLB", "OXY",
            # Finance
            "JPM", "BAC", "GS", "MS",
        ]
    
    def _calculate_premarket_metrics(
        self,
        symbol: str,
        hist: pd.DataFrame,
        ticker
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate premarket metrics and score
        
        Args:
            symbol: Stock symbol
            hist: Historical data with premarket
            ticker: yfinance Ticker object
            
        Returns:
            Dict with metrics and score
        """
        try:
            # Get yesterday's close vs current premarket
            yesterday_close = hist['Close'].iloc[-100] if len(hist) > 100 else hist['Close'].iloc[0]
            current_price = hist['Close'].iloc[-1]
            
            # Gap %
            gap_pct = ((current_price - yesterday_close) / yesterday_close) * 100
            
            # Premarket volume (rough estimate)
            recent_volume = hist['Volume'].iloc[-30:].sum() if len(hist) > 30 else hist['Volume'].sum()
            
            # Get regular market stats
            info = ticker.info
            avg_volume = info.get('averageVolume', 1)
            
            # Volume ratio
            volume_ratio = recent_volume / (avg_volume / 390 * 30) if avg_volume > 0 else 0
            
            # Score calculation
            score = 0
            reasons = []
            
            # Gap scoring
            if abs(gap_pct) > 4:
                score += 50
                reasons.append(f"LARGE_GAP_{gap_pct:.1f}%")
            elif abs(gap_pct) > 2:
                score += 30
                reasons.append(f"GAP_{gap_pct:.1f}%")
            
            # Volume scoring
            if volume_ratio > 2:
                score += 30
                reasons.append("HIGH_VOLUME")
            elif volume_ratio > 1:
                score += 15
                reasons.append("ELEVATED_VOLUME")
            
            # Price range (volatility indicator)
            price_range = (hist['High'].iloc[-30:].max() - hist['Low'].iloc[-30:].min()) / current_price
            if price_range > 0.03:  # >3% range
                score += 20
                reasons.append("VOLATILE")
            
            if score == 0:
                return None
            
            return {
                'symbol': symbol,
                'score': score,
                'gap_pct': round(gap_pct, 2),
                'current_price': round(current_price, 2),
                'yesterday_close': round(yesterday_close, 2),
                'volume_ratio': round(volume_ratio, 2),
                'reasons': reasons,
                'scanned_at': datetime.now().isoformat(),
                'sector': info.get('sector', 'Unknown')
            }
            
        except Exception as e:
            logger.debug(f"Error calculating metrics for {symbol}: {e}")
            return None
    
    def get_cached_candidates(self) -> List[Dict[str, Any]]:
        """
        Get cached candidates from today's premarket scan
        Call this throughout the day instead of rescanning
        
        Returns:
            List of candidates or empty if cache expired
        """
        # Check if cache is from today
        if self.last_scan_time:
            now = datetime.now()
            if self.last_scan_time.date() == now.date():
                logger.info(f"Using cached candidates from {self.last_scan_time.strftime('%H:%M')}")
                return self.cached_candidates
        
        # Try to load from file
        try:
            import json
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                
            scan_time = datetime.fromisoformat(data['scan_time'])
            if scan_time.date() == datetime.now().date():
                self.cached_candidates = data['candidates']
                self.last_scan_time = scan_time
                logger.info(f"Loaded {len(self.cached_candidates)} candidates from cache")
                return self.cached_candidates
                
        except Exception as e:
            logger.debug(f"Could not load cache: {e}")
        
        logger.warning("No valid cache found - run scan_premarket() first")
        return []
    
    def _save_to_cache(self, candidates: List[Dict[str, Any]]):
        """Save candidates to cache file"""
        try:
            import json
            import os
            
            os.makedirs('data', exist_ok=True)
            
            cache_data = {
                'scan_time': datetime.now().isoformat(),
                'candidates': candidates
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            logger.info(f"Cached {len(candidates)} candidates to {self.cache_file}")
            
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
    
    def should_run_scan(self) -> bool:
        """
        Check if it's time to run premarket scan
        Recommended: 8:30-9:25 AM ET (before market open)
        
        Returns:
            True if should scan now
        """
        now = datetime.now()
        
        # Check if already scanned today
        if self.last_scan_time and self.last_scan_time.date() == now.date():
            return False
        
        # Check time window (8:30-9:25 AM ET)
        # Adjust for your timezone
        current_time = now.time()
        scan_start = time(8, 30)
        scan_end = time(9, 25)
        
        if scan_start <= current_time <= scan_end:
            return True
        
        return False
    
    def get_top_picks(self, count: int = 5) -> List[str]:
        """
        Get top N symbols from cached candidates
        
        Args:
            count: Number of symbols to return
            
        Returns:
            List of top symbols
        """
        candidates = self.get_cached_candidates()
        return [c['symbol'] for c in candidates[:count]]


# Singleton instance
_premarket_scanner: Optional[PremarketScanner] = None


def get_premarket_scanner() -> PremarketScanner:
    """Get or create singleton premarket scanner"""
    global _premarket_scanner
    if _premarket_scanner is None:
        _premarket_scanner = PremarketScanner()
    return _premarket_scanner
