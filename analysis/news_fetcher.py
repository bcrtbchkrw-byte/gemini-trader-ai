"""
News Fetcher - Phase 2 Support
Fetches recent news for stock analysis.
"""
from typing import List, Dict, Any, Optional
from loguru import logger
from datetime import datetime, timedelta
import os


class NewsFetcher:
    """Fetches news for stocks using NewsAPI"""
    
    def __init__(self):
        # NewsAPI key from environment
        self.api_key = os.getenv('NEWS_API_KEY', '')
        self.lookback_days = int(os.getenv('NEWS_LOOKBACK_DAYS', '7'))
        
        if not self.api_key:
            logger.warning("NEWS_API_KEY not set - news fetching will return empty results")
        
        logger.info("News fetcher initialized")
    
    async def fetch_news(
        self,
        symbol: str,
        days: int = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent news for a single symbol
        
        Args:
            symbol: Stock ticker
            days: Days to look back (default from config)
            
        Returns:
            List of news articles
        """
        if days is None:
            days = self.lookback_days
        
        try:
            # If no API key, return placeholder
            if not self.api_key:
                return self._get_placeholder_news(symbol)
            
            # Use NewsAPI
            from newsapi import NewsApiClient
            
            newsapi = NewsApiClient(api_key=self.api_key)
            
            # Get company name for better search
            company_name = self._get_company_name(symbol)
            
            # Calculate date range
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            
            # Fetch news
            articles = newsapi.get_everything(
                q=f"{symbol} OR {company_name}",
                from_param=from_date.strftime('%Y-%m-%d'),
                to=to_date.strftime('%Y-%m-%d'),
                language='en',
                sort_by='relevancy',
                page_size=10
            )
            
            # Format results
            formatted = []
            for article in articles.get('articles', []):
                formatted.append({
                    'title': article.get('title', ''),
                    'description': article.get('description', ''),
                    'source': article.get('source', {}).get('name', ''),
                    'published': article.get('publishedAt', ''),
                    'url': article.get('url', '')
                })
            
            logger.info(f"Fetched {len(formatted)} news articles for {symbol}")
            return formatted
            
        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return self._get_placeholder_news(symbol)
    
    async def fetch_batch(
        self,
        symbols: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch news for multiple symbols
        
        Args:
            symbols: List of stock tickers
            
        Returns:
            Dict mapping symbol to news list
        """
        logger.info(f"Fetching news for {len(symbols)} symbols...")
        
        results = {}
        for symbol in symbols:
            results[symbol] = await self.fetch_news(symbol)
        
        total_articles = sum(len(articles) for articles in results.values())
        logger.info(f"✅ Fetched {total_articles} total articles for {len(symbols)} symbols")
        
        return results
    
    def _get_company_name(self, symbol: str) -> str:
        """Get company name from symbol"""
        # Simple mapping for common symbols
        names = {
            'AAPL': 'Apple',
            'MSFT': 'Microsoft',
            'GOOGL': 'Google',
            'AMZN': 'Amazon',
            'META': 'Meta Facebook',
            'TSLA': 'Tesla',
            'NVDA': 'Nvidia',
            'JPM': 'JPMorgan',
            'SPY': 'S&P500 SPY',
        }
        return names.get(symbol, symbol)
    
    def _get_placeholder_news(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Get placeholder news when API unavailable
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Placeholder news list
        """
        return [
            {
                'title': f'{symbol} - No news API configured',
                'description': 'Set NEWS_API_KEY in .env to enable news fetching',
                'source': 'Placeholder',
                'published': datetime.now().isoformat(),
                'url': ''
            }
        ]


# Singleton instance
_news_fetcher: Optional[NewsFetcher] = None


def get_news_fetcher() -> NewsFetcher:
    """Get or create singleton news fetcher instance"""
    global _news_fetcher
    if _news_fetcher is None:
        _news_fetcher = NewsFetcher()
    return _news_fetcher
