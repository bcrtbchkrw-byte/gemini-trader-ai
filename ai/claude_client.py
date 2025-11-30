"""
Claude AI Client
Handles advanced Greeks analysis and trade recommendations using Claude Opus.
"""
from typing import Optional, Dict, Any, List
from anthropic import Anthropic
from loguru import logger
from config import get_config
from ai.prompts import get_claude_greeks_analysis_prompt, parse_claude_response
from data.logger import get_ai_logger


class ClaudeClient:
    """Client for Claude Opus AI Greeks analysis and trade recommendations"""
    
    def __init__(self):
        config = get_config()
        self.client = Anthropic(api_key=config.ai.anthropic_api_key)
        
        # Use Claude Opus 4 for best analysis
        self.model = "claude-opus-4-20250514"
        
        # AI decision logger
        self.ai_logger = get_ai_logger()
        
        # Configuration
        self.account_size = config.trading.account_size
        self.max_risk = config.trading.max_risk_per_trade
        
        logger.info("Claude AI client initialized with model: " + self.model)
    
    async def analyze_greeks_and_recommend(
        self,
        symbol: str,
        options_data: List[Dict[str, Any]],
        vix: float,
        regime: str
    ) -> Dict[str, Any]:
        """
        Perform advanced Greeks analysis and generate trade recommendation
        
        Args:
            symbol: Stock ticker
            options_data: List of options with Greeks data
            vix: Current VIX value
            regime: Current VIX regime
            
        Returns:
            Dict with trade recommendation
        """
        try:
            if not options_data:
                logger.warning(f"No options data provided for {symbol}")
                return {
                    'success': False,
                    'error': 'No options data available'
                }
            
            # Generate prompt using your Gemini-Trader 5.1 system
            prompt = get_claude_greeks_analysis_prompt(
                symbol=symbol,
                options_data=options_data,
                vix=vix,
                regime=regime,
                account_size=self.account_size,
                max_risk=self.max_risk
            )
            
            logger.info(f"Requesting Claude Greeks analysis for {symbol}...")
            
            # Generate response
            response = await self._generate_async(prompt)
            
            if not response:
                logger.error("Failed to get response from Claude")
                return {
                    'success': False,
                    'error': 'No response from Claude'
                }
            
            # Parse response
            parsed = parse_claude_response(response)
            
            # Log AI decision
            self.ai_logger.info(
                f"Claude Greeks Analysis - {symbol}\n"
                f"Verdict: {parsed.get('verdict', 'N/A')}\n"
                f"Strategy: {parsed.get('strategy', 'N/A')}\n"
                f"---\n{response}\n"
            )
            
            verdict_emoji = "✅" if parsed['verdict'] == 'SCHVÁLENO' else "❌"
            logger.info(
                f"{verdict_emoji} Claude analysis complete for {symbol}: "
                f"Verdict={parsed['verdict']}, Strategy={parsed.get('strategy', 'N/A')}"
            )
            
            return {
                'success': True,
                'symbol': symbol,
                'recommendation': parsed,
                'raw_response': response
            }
            
        except Exception as e:
            logger.error(f"Error in Claude Greeks analysis: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _generate_async(self, prompt: str) -> Optional[str]:
        """
        Generate response asynchronously in JSON format
        
        Args:
            prompt: Input prompt requesting JSON output
            
        Returns:
            Generated JSON text or None
        """
        try:
            # Create message with explicit JSON request
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.3,  # Lower temperature for consistent structured output
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            if message and message.content:
                # Extract text from response
                response_text = message.content[0].text
                return response_text
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating Claude response: {e}")
            return None
    
    async def stress_test_greeks(
        self,
        options_data: Dict[str, Any],
        iv_change: float = 5.0
    ) -> Dict[str, Any]:
        """
        Perform Vanna stress test - simulate IV change impact on Delta
        
        Uses PRECISE Vanna from analytical Black-Scholes calculation.
        
        NOTE: Vanna is calculated analytically in data_fetcher.py
        All other Greeks (delta, theta, vega, gamma) come from IBKR API.
        
        Args:
            options_data: Option Greeks data (with precise Vanna)
            iv_change: IV change in percentage points
            
        Returns:
            Stress test results with precise Vanna calculation
        """
        try:
            current_delta = options_data.get('delta', 0)
            vanna = options_data.get('vanna', 0)
            current_iv = options_data.get('impl_vol', 0) * 100  # Convert to percentage
            
            if not vanna:
                logger.warning("Vanna not available for stress test")
                return {
                    'delta_change': None,
                    'new_delta': None,
                    'safe': False,
                    'warning': 'Vanna data not available'
                }
            
            # Calculate delta change using PRECISE Vanna
            # ΔDelta = Vanna × Δσ
            # Note: Vanna is ∂Delta/∂σ, so multiply by IV change in decimal
            delta_change = vanna * (iv_change / 100)  # Convert % to decimal
            new_delta = current_delta + delta_change
            
            # Safety check - Delta should stay under 0.40 for credit spreads
            is_safe = abs(new_delta) < 0.40
            
            result = {
                'current_delta': current_delta,
                'current_iv': current_iv,
                'iv_change': iv_change,
                'vanna': vanna,
                'vanna_source': 'analytical_bs',  # Indicate this is precise
                'delta_change': delta_change,
                'projected_delta': new_delta,
                'safe': is_safe,
                'warning': None if is_safe else f"Projected Delta {new_delta:.3f} exceeds safety threshold"
            }
            
            logger.info(
                f"Vanna stress test (PRECISE): IV {iv_change:+.0f}% → "
                f"Delta {current_delta:.3f} → {new_delta:.3f} "
                f"({'SAFE' if is_safe else 'RISKY'})"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in Vanna stress test: {e}")
            return {
                'delta_change': None,
                'new_delta': None,
                'safe': False,
                'error': str(e)
            }


# Singleton instance
_claude_client: Optional[ClaudeClient] = None


def get_claude_client() -> ClaudeClient:
    """Get or create singleton Claude client instance"""
    global _claude_client
    if _claude_client is None:
        _claude_client = ClaudeClient()
    return _claude_client
