"""
Gemini AI Client
Handles interactions with Google Gemini API for fast batch analysis with cost tracking.
"""
from typing import Dict, Any, List, Optional
import google.generativeai as genai
from loguru import logger
from datetime import datetime, date
import os
from config import get_config
from ai.prompts import get_gemini_fundamental_prompt, parse_gemini_response
from data.logger import get_ai_logger


class GeminiClient:
    """
    Gemini API client with token tracking and cost limits
    
    Token Pricing (Gemini 1.5 Flash):
    - Input: $0.075 per 1M tokens
    - Output: $0.30 per 1M tokens
    """
    
    # Gemini 1.5 Flash pricing
    INPUT_COST_PER_1M = 0.075  # $0.075 per 1M input tokens
    OUTPUT_COST_PER_1M = 0.30  # $0.30 per 1M output tokens
    
    def __init__(self, daily_limit_usd: float = 5.0):
        """
        Initialize Gemini client with cost tracking
        
        Args:
            daily_limit_usd: Maximum daily spend in USD (default $5)
        """
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            # Fallback to config if not in environment
            config = get_config()
            self.api_key = config.ai.gemini_api_key
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY not found in environment or config")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Cost tracking
        self.daily_limit_usd = daily_limit_usd
        self.today = date.today()
        self.daily_input_tokens = 0
        self.daily_output_tokens = 0
        self.daily_cost = 0.0
        self.silent_mode = False
        
        logger.info(f"✅ Gemini client initialized (Daily limit: ${daily_limit_usd:.2f})")
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
            return {
                'success': False,
                'error': str(e)
            }
            
    async def generate_response(self, prompt: str) -> str:
        """
        Generate a generic response from Gemini
        
        Args:
            prompt: Input prompt
            
        Returns:
            Generated text response
        """
        response = await self._generate_async(prompt)
        return response if response else ""
    
    
    def _reset_daily_if_needed(self):
        """Reset counters if new day"""
        today = date.today()
        if today != self.today:
            logger.info(
                f"📊 Daily Gemini usage reset:\n"
                f"   Yesterday: {self.daily_input_tokens:,} in + {self.daily_output_tokens:,} out\n"
                f"   Cost: ${self.daily_cost:.4f}"
            )
            self.today = today
            self.daily_input_tokens = 0
            self.daily_output_tokens = 0
            self.daily_cost = 0.0
            self.silent_mode = False
    
    def _track_usage(self, input_tokens: int, output_tokens: int):
        """Track token usage and cost"""
        self._reset_daily_if_needed()
        
        self.daily_input_tokens += input_tokens
        self.daily_output_tokens += output_tokens
        
        # Calculate cost
        input_cost = (input_tokens / 1_000_000) * self.INPUT_COST_PER_1M
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_COST_PER_1M
        call_cost = input_cost + output_cost
        
        self.daily_cost += call_cost
        
        logger.info(
            f"💰 Gemini usage: {input_tokens:,} in + {output_tokens:,} out = ${call_cost:.4f}\n"
            f"   Daily total: ${self.daily_cost:.4f} / ${self.daily_limit_usd:.2f}"
        )
        
        # Check limit
        if self.daily_cost >= self.daily_limit_usd:
            self.silent_mode = True
            logger.error(
                f"🚨 GEMINI DAILY LIMIT REACHED!\n"
                f"   Spent: ${self.daily_cost:.4f}\n"
                f"   Limit: ${self.daily_limit_usd:.2f}\n"
                f"   → SILENT MODE ACTIVATED"
            )
    
    def can_make_request(self) -> bool:
        """Check if we can make another API request"""
        self._reset_daily_if_needed()
        return not self.silent_mode
    
    async def batch_analyze_with_news(
        self,
        candidates: List[Dict[str, Any]],
        news_context: Dict[str, List[Dict]],
        vix: float
    ) -> Dict[str, Any]:
        """
        Batch analyze stocks with news context and cost tracking
        
        Returns early if daily limit exceeded
        """
        # Check if we can make request
        if not self.can_make_request():
            logger.warning("⚠️ Gemini in SILENT MODE (daily limit reached) - skipping analysis")
            return {
                'success': False,
                'error': 'Daily cost limit exceeded',
                'silent_mode': True,
                'top_picks': []
            }
        
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
