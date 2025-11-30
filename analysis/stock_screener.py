"""
Stock Screener - Phase 1 Pre-check
Filters stock universe based on price, liquidity, and IV rank.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta


@dataclass
class ScreeningCriteria:
    """Criteria for stock screening"""
    min_price: float = 20.0
    max_price: float = 300.0
    min_daily_volume: int = 1_000_000
    min_option_volume: int = 1000
    max_bid_ask_spread: float = 0.10
    iv_rank_threshold: float = 30.0
    vix_regime: str = "NORMAL"


class StockScreener:
    """Phase 1: Pre-check stock screener"""
    
    def __init__(self):
        self.sp500_symbols = self._get_sp500_symbols()
        logger.info(f"Stock screener initialized with {len(self.sp500_symbols)} symbols")
    
    def _get_sp500_symbols(self) -> List[str]:
        """
        Get S&P 500 symbols
        
        Returns:
            List of stock symbols
        """
        # Top liquid stocks for testing - in production, fetch from API
        return [
            # Tech
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "INTC", "NFLX",
            # Finance
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
                logger.debug(f"Error evaluating {symbol}: {e}")
                continue
        
        # Sort by score descending
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Take top N
        top_candidates = candidates[:max_results]
        
        logger.info(f"✅ Phase 1 complete: {len(top_candidates)}/{len(self.sp500_symbols)} stocks passed filters")
        
        return top_candidates
    
    async def _evaluate_stock(
        self,
        symbol: str,
        criteria: ScreeningCriteria
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate a single stock against criteria
        
        Args:
            symbol: Stock ticker
            criteria: Screening criteria
            
        Returns:
            Stock data if passes filters, None otherwise
        """
        try:
            # Fetch stock data
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Price check
            price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
            if not (criteria.min_price <= price <= criteria.max_price):
                return None
            
            # Volume check
            avg_volume = info.get('averageVolume', 0)
            if avg_volume < criteria.min_daily_volume:
                return None
            
            # Get implied volatility (approximation from beta + market IV)
            # In production, would fetch from IBKR or options data
            beta = info.get('beta', 1.0)
            iv_rank = self._estimate_iv_rank(symbol, beta)
            
            # Calculate liquidity score
            liquidity_score = self._calculate_liquidity_score(
                avg_volume, 
                info.get('marketCap', 0),
                price
            )
            
            # Try to add technical analysis score
            technical_score = self._calculate_technical_score(symbol, info)
            
            # Calculate overall score (including technical if available)
            score = self._calculate_score(
                price=price,
                volume=avg_volume,
                iv_rank=iv_rank,
                liquidity_score=liquidity_score,
                technical_score=technical_score,
                criteria=criteria
            )
            # Request scan
            scan_data = await ib.reqScannerDataAsync(scanner)
            
            if not scan_data:
                logger.warning("Scanner returned no results")
                return []
            
            logger.info(f"IBKR scanner found {len(scan_data)} stocks")
            
            # Process results
            candidates = []
            for item in scan_data[:max_results]:
                try:
                    contract = item.contractDetails.contract
                    
                    # Get additional market data
                    ticker = ib.reqMktData(contract, '', False, False)
                    await ib.sleep(1)  # Wait for data
                    
                    # Get IV rank (from scanner rank or calculate)
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
                    
                    # Cancel market data
                    ib.cancelMktData(contract)
                    
                except Exception as e:
                    logger.debug(f"Error processing scanner item: {e}")
                    continue
            
            # Sort by score
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
        
        Factors:
        - IV rank (higher = better for selling premium)
        - Price range (prefer mid-range)
        - Volume (higher = better liquidity)
        
        Args:
            candidate: Stock data
            
        Returns:
            Score (0-100)
        """
        score = 0.0
        
        # IV rank score (0-50 points)
        iv_rank = candidate.get('iv_rank', 50)
        score += min(iv_rank / 2, 50)
        
        # Price score (0-25 points) - prefer $50-$200 range
        price = candidate.get('price', 0)
        if 50 <= price <= 200:
            score += 25
        elif 20 <= price <= 500:
            score += 15
        
        # Volume score (0-25 points)
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
        Main screening method - wrapper for scan_high_iv_stocks
        
        Args:
            max_candidates: Max candidates to return
            
        Returns:
            Top candidate stocks
        """
        self.max_candidates = max_candidates
        
        results = await self.scan_high_iv_stocks(
            max_results=50,  # Scan 50, return top 10
            min_price=20.0,
            max_price=500.0
        )
        
        return resultsymbol,
                'price': round(price, 2),
                'avg_volume': avg_volume,
                'iv_rank': round(iv_rank, 1),
                'liquidity_score': round(liquidity_score, 2),
                'market_cap': info.get('marketCap', 0),
                'sector': info.get('sector', 'Unknown'),
                'score': round(score, 2),
                'passes_filters': True
            }
            
            # Add technical data if available
            if technical_score is not None:
                result['technical_score'] = round(technical_score, 2)
            
            return result
            
        except Exception as e:
            logger.debug(f"Could not evaluate {symbol}: {e}")
            return None
    
    def _estimate_iv_rank(self, symbol: str, beta: float) -> float:
        """
        Estimate IV rank (simplified)
        In production: fetch real IV rank from IBKR or options data
        
        Args:
            symbol: Stock ticker
            beta: Stock beta
            
        Returns:
            Estimated IV rank (0-100)
        """
        # Placeholder: higher beta = higher IV rank tendency
        # Real implementation would use historical IV data
        base_iv = 50
        beta_adjustment = (beta - 1.0) * 20
        
        # Add some randomness for testing
        import random
        random_factor = random.uniform(-10, 10)
        
        iv_rank = max(0, min(100, base_iv + beta_adjustment + random_factor))
        return iv_rank
    
    def _calculate_liquidity_score(
        self,
        volume: int,
        market_cap: float,
        price: float
    ) -> float:
        """
        Calculate liquidity score (0-10)
        
        Args:
            volume: Average daily volume
            market_cap: Market capitalization
            price: Stock price
            
        Returns:
            Liquidity score
        """
        # Volume score (0-5)
        if volume > 10_000_000:
            volume_score = 5.0
        elif volume > 5_000_000:
            volume_score = 4.0
        elif volume > 2_000_000:
            volume_score = 3.0
        elif volume > 1_000_000:
            volume_score = 2.0
        else:
            volume_score = 1.0
        
        # Market cap score (0-3)
        if market_cap > 100_000_000_000:  # > $100B
            cap_score = 3.0
        elif market_cap > 10_000_000_000:  # > $10B
            cap_score = 2.0
        elif market_cap > 1_000_000_000:  # > $1B
            cap_score = 1.0
        else:
            cap_score = 0.5
        
        # Price score (0-2) - prefer mid-range prices
        if 50 <= price <= 200:
            price_score = 2.0
        elif 20 <= price <= 300:
            price_score = 1.5
        else:
            price_score = 1.0
        
        return volume_score + cap_score + price_score
    
    def _calculate_technical_score(self, symbol: str, info: dict) -> Optional[float]:
        """
        Calculate technical analysis score using pandas_ta
        
        Args:
            symbol: Stock ticker
            info: Stock info from yfinance
            
        Returns:
            Technical score (0-10) or None if unavailable
        """
        try:
            import pandas_ta as ta
            import yfinance as yf
            
            # Fetch historical data (past 50 days for indicators)
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="3mo")
            
            if len(hist) < 20:
                return None
            
            score = 5.0  # Neutral baseline
            
            # RSI (30-70 is good, extremes are risky for mean reversion)
            rsi = ta.rsi(hist['Close'], length=14)
            if not rsi.empty and not pd.isna(rsi.iloc[-1]):
                current_rsi = float(rsi.iloc[-1])
                if 35 < current_rsi < 65:
                    score += 2.0  # Neutral RSI is good
                elif current_rsi < 30 or current_rsi > 70:
                    score += 1.0  # Extreme = mean reversion opportunity
            
            # MACD momentum
            macd = ta.macd(hist['Close'])
            if macd is not None and not macd.empty:
                macd_hist = macd['MACDh_12_26_9'].iloc[-1]
                if not pd.isna(macd_hist) and macd_hist > 0:
                    score += 1.5  # Positive momentum
            
            # Volume trend (increasing volume is good)
            vol_sma = ta.sma(hist['Volume'], length=20)
            if not vol_sma.empty and not pd.isna(vol_sma.iloc[-1]):
                recent_vol = hist['Volume'].iloc[-5:].mean()
                avg_vol = float(vol_sma.iloc[-1])
                if recent_vol > avg_vol * 1.2:
                    score += 1.5  # Volume surge
            
            return min(10.0, max(0.0, score))
            
        except Exception as e:
            logger.debug(f"Technical scoring failed for {symbol}: {e}")
            return None
    
    def _calculate_score(
        self,
        price: float,
        volume: int,
        iv_rank: float,
        liquidity_score: float,
        technical_score: Optional[float],
        criteria: ScreeningCriteria
    ) -> float:
        """
        Calculate overall stock score
        
        Args:
            price: Stock price
            volume: Average volume
            iv_rank: IV rank
            liquidity_score: Liquidity score
            technical_score: Technical analysis score (optional)
            criteria: Screening criteria
            
        Returns:
            Overall score (0-100)
        """
        score = 0.0
        
        # Liquidity weight: 35%
        score += (liquidity_score / 10.0) * 35
        
        # IV rank weight: 30% (higher IV = better for credit spreads)
        if criteria.vix_regime in ["HIGH_VOL", "NORMAL"]:
            # Credit spreads - prefer higher IV
            iv_score = min(100, iv_rank) / 100.0
            score += iv_score * 30
        else:
            # Debit spreads - prefer lower IV
            iv_score = (100 - min(100, iv_rank)) / 100.0
            score += iv_score * 30
        
        # Volume weight: 20%
        volume_normalized = min(1.0, volume / 50_000_000)
        score += volume_normalized * 20
        
        # Technical score weight: 15% (if available)
        if technical_score is not None:
            score += (technical_score / 10.0) * 15
        else:
            # Redistribute to other factors
            score = score * (100 / 85)
        
        return score


# Singleton instance
_screener: Optional[StockScreener] = None


def get_stock_screener() -> StockScreener:
    """Get or create singleton stock screener instance"""
    global _screener
    if _screener is None:
        _screener = StockScreener()
    return _screener
