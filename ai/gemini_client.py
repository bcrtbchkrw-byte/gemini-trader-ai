"""
Gemini AI Client
Handles fundamental analysis using Google Gemini AI.
"""
from typing import Optional, Dict, Any
import google.generativeai as genai
from loguru import logger
from config import get_config
from ai.prompts import get_gemini_fundamental_prompt, parse_gemini_response
from data.logger import get_ai_logger


class GeminiClient:
    """Client for Google Gemini AI fundamental analysis"""
    
    def __init__(self):
        config = get_config()
        genai.configure(api_key=config.ai.gemini_api_key)
        
        # Use Gemini 1.5 Pro for better analysis
        self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
        
        # AI decision logger
        self.ai_logger = get_ai_logger()
        
        logger.info("Gemini AI client initialized")
    
    async def analyze_fundamental(
        self,
        symbol: str,
        current_price: float,
        vix: float,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform fundamental analysis on a symbol
        
        Args:
            symbol: Stock ticker
            current_price: Current stock price
            vix: Current VIX value
            additional_context: Optional additional context
            
        Returns:
            Dict with analysis results
        """
        try:
            # Generate prompt
            prompt = get_gemini_fundamental_prompt(
                symbol=symbol,
                current_price=current_price,
                vix=vix,
                additional_context=additional_context
            )
            
            logger.info(f"Requesting Gemini fundamental analysis for {symbol}...")
            
            # Generate response
            response = await self._generate_async(prompt)
            
            if not response:
                logger.error("Failed to get response from Gemini")
                return {
                    'success': False,
                    'error': 'No response from Gemini'
                }
            
            # Parse response
            parsed = parse_gemini_response(response)
            
            # Log AI decision
            self.ai_logger.info(
                f"Gemini Fundamental Analysis - {symbol}\n"
                f"Score: {parsed.get('fundamental_score', 'N/A')}/10\n"
                f"Sentiment: {parsed.get('sentiment', 'N/A')}\n"
                f"Recommendation: {parsed.get('recommendation', 'N/A')}\n"
                f"---\n{response}\n"
            )
            
            logger.info(
                f"✅ Gemini analysis complete for {symbol}: "
                f"Score={parsed.get('fundamental_score', 'N/A')}, "
                f"Sentiment={parsed.get('sentiment', 'N/A')}"
            )
            
            return {
                'success': True,
                'symbol': symbol,
                'analysis': parsed,
                'raw_response': response
            }
            
        except Exception as e:
            logger.error(f"Error in Gemini fundamental analysis: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def batch_analyze_with_news(
        self,
        candidates: list,
        news_context: Dict[str, list],
        vix: float
    ) -> Dict[str, Any]:
        """
        Phase 2: Batch analyze multiple stocks with news context
        
        Args:
            candidates: List of stock candidates from Phase 1
            news_context: Dict mapping symbol to news articles
            vix: Current VIX value
            
        Returns:
            Dict with ranked stocks and top picks
        """
        try:
            from ai.prompts import get_gemini_batch_analysis_prompt
            
            logger.info(f"Phase 2: Batch analyzing {len(candidates)} candidates with Gemini...")
            
            # Generate batch prompt
            prompt = get_gemini_batch_analysis_prompt(
                candidates=candidates,
                news_context=news_context,
                vix=vix
            )
            
            # Generate response
            response = await self._generate_async(prompt)
            
            if not response:
                logger.error("Failed to get batch response from Gemini")
                return {
                    'success': False,
                    'error': 'No response from Gemini'
                }
            
            # Parse response
            parsed = parse_gemini_response(response)
            
            # Extract top picks
            ranked_stocks = parsed.get('ranked_stocks', [])
            top_picks = parsed.get('top_picks', [])
            
            # Log decision
            self.ai_logger.info(
                f"Gemini Batch Analysis\\n"
                f"Candidates: {len(candidates)}\\n"
                f"Top Picks: {', '.join(top_picks)}\\n"
                f"---\\n{response}\\n"
            )
            
            logger.info(
                f"✅ Phase 2 complete: {len(top_picks)} stocks selected from {len(candidates)} candidates"
            )
            
            return {
                'success': True,
                'ranked_stocks': ranked_stocks,
                'top_picks': top_picks,
                'raw_response': response
            }
            
        except Exception as e:
            logger.error(f"Error in Gemini batch analysis: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _generate_async(self, prompt: str) -> Optional[str]:
        """
        Generate response asynchronously with JSON mode
        
        Args:
            prompt: Input prompt
            
        Returns:
            Generated JSON text or None
        """
        try:
            # Use JSON response mode for structured output
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json"
                )
            )
            
            if response and response.text:
                return response.text
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            return None


# Singleton instance
_gemini_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Get or create singleton Gemini client instance"""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client
