"""
Earnings Call Transcript Analyzer
Fetches earnings call transcripts and analyzes management tone using Gemini.
"""
from typing import Dict, Any, Optional
from loguru import logger
import os


class EarningsTranscriptAnalyzer:
    """Analyze earnings call transcripts for management tone"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 86400  # 24 hours
    
    async def fetch_transcript(self, symbol: str) -> Optional[str]:
        """
        Fetch earnings call transcript
        
        Sources (in priority order):
        1. Alpha Vantage (if available)
        2. Yahoo Finance (limited)
        3. News API articles about earnings
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Transcript text or None
        """
        # Check cache
        if symbol in self.cache:
            cached_time, transcript = self.cache[symbol]
            from datetime import datetime
            age = (datetime.now() - cached_time).seconds
            if age < self.cache_ttl:
                return transcript
        
        try:
            # Try multiple sources
            transcript = await self._fetch_from_news_api(symbol)
            
            if transcript:
                from datetime import datetime
                self.cache[symbol] = (datetime.now(), transcript)
                logger.info(f"✅ Fetched transcript for {symbol} ({len(transcript)} chars)")
                return transcript
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching transcript for {symbol}: {e}")
            return None
    
    async def _fetch_from_news_api(self, symbol: str) -> Optional[str]:
        """
        Fetch earnings-related articles from News API
        
        This is a workaround when proper transcripts aren't available.
        We fetch recent news about earnings calls and use that.
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Combined article text or None
        """
        try:
            from analysis.news_fetcher import get_news_fetcher
            
            news_fetcher = get_news_fetcher()
            
            # Search for earnings call news
            query = f'{symbol} earnings call'
            news = await news_fetcher.fetch_news(query, max_articles=5)
            
            if not news:
                return None
            
            # Combine article content
            transcript_parts = []
            for article in news[:3]:  # Top 3 articles
                if article.get('content'):
                    transcript_parts.append(article['content'])
                elif article.get('description'):
                    transcript_parts.append(article['description'])
            
            if transcript_parts:
                combined = "\n\n---\n\n".join(transcript_parts)
                return combined
            
            return None
            
        except Exception as e:
            logger.debug(f"News API fetch error: {e}")
            return None
    
    async def analyze_management_tone(
        self,
        symbol: str,
        transcript: str,
        earnings_data: Dict[str, Any],
        gemini_client
    ) -> Dict[str, Any]:
        """
        Analyze management tone using Gemini 1.5 Pro
        
        Gemini's huge context window allows full transcript analysis.
        
        Args:
            symbol: Stock ticker
            transcript: Full earnings call transcript
            earnings_data: Numerical earnings data
            gemini_client: Gemini AI client
            
        Returns:
            Analysis with tone score and insights
        """
        try:
            prompt = f"""You are analyzing the earnings call for {symbol}.

**NUMERICAL RESULTS:**
- Revenue: ${earnings_data.get('revenue_actual', 'N/A')} (Consensus: ${earnings_data.get('revenue_consensus', 'N/A')})
- EPS: ${earnings_data.get('eps_actual', 'N/A')} (Consensus: ${earnings_data.get('eps_consensus', 'N/A')})
- Revenue Surprise: {earnings_data.get('revenue_surprise_pct', 'N/A')}%
- EPS Surprise: {earnings_data.get('eps_surprise_pct', 'N/A')}%

**EARNINGS CALL TRANSCRIPT/COMMENTARY:**
{transcript[:8000]}  # Gemini 1.5 Pro can handle much more, but limiting for safety

**YOUR TASK:**
Analyze the TONE and SENTIMENT of management, not just the numbers.

Focus on:
1. **Confidence Level** (1-10): How confident does management sound?
   - Hesitant language ("we hope", "maybe", "uncertain")
   - Confident language ("we will", "committed", "strong")

2. **Guidance Tone**: 
   - Optimistic about future?
   - Cautious/conservative?
   - Defensive about challenges?

3. **Red Flags**:
   - Avoiding questions?
   - Blaming external factors excessively?
   - Vague about specifics?

4. **Green Flags**:
   - Specific numbers and targets?
   - Clear strategy articulation?
   - Addressing concerns directly?

5. **Overall Sentiment** (Bullish/Neutral/Bearish):
   - Consider BOTH numbers AND tone
   - Numbers might beat but tone cautious = BEARISH
   - Numbers miss but tone confident = could be NEUTRAL

Respond in JSON:
{{
    "confidence_score": 7,
    "guidance_tone": "cautious/neutral/optimistic",
    "management_sentiment": "bullish/neutral/bearish",
    "red_flags": ["flag1", "flag2"],
    "green_flags": ["flag1", "flag2"],
    "key_quotes": ["quote1", "quote2"],
    "trading_implication": "bullish/neutral/bearish",
    "reasoning": "2-3 sentence summary"
}}

**CRITICAL:** Trust the TONE more than the numbers. 
If numbers beat but CEO sounds worried → BEARISH
If numbers miss but CEO sounds confident with strong guidance → NEUTRAL/BULLISH
"""
            
            # Call Gemini for analysis
            response = await gemini_client.generate_async(prompt)
            
            # Parse JSON response
            import json
            try:
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    analysis = json.loads(json_str)
                else:
                    raise ValueError("No JSON in response")
                
            except Exception as e:
                logger.warning(f"Failed to parse JSON: {e}")
                analysis = {
                    'confidence_score': 5,
                    'management_sentiment': 'neutral',
                    'reasoning': response[:500]
                }
            
            logger.info(
                f"📞 {symbol} Call Analysis: "
                f"Confidence={analysis.get('confidence_score', 'N/A')}/10, "
                f"Tone={analysis.get('guidance_tone', 'N/A')}, "
                f"Sentiment={analysis.get('management_sentiment', 'N/A')}"
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing transcript: {e}")
            return {
                'error': str(e),
                'confidence_score': 5,
                'management_sentiment': 'unknown'
            }


# Singleton
_transcript_analyzer: Optional['EarningsTranscriptAnalyzer'] = None


def get_transcript_analyzer() -> EarningsTranscriptAnalyzer:
    """Get or create singleton transcript analyzer"""
    global _transcript_analyzer
    if _transcript_analyzer is None:
        _transcript_analyzer = EarningsTranscriptAnalyzer()
    return _transcript_analyzer
