"""
Claude AI Client
Handles deep strategy analysis with Anthropic Claude with cost tracking.
"""
from typing import Optional, Dict, Any, List
from anthropic import Anthropic
from loguru import logger
from config import get_config
from ai.prompts import get_claude_greeks_analysis_prompt, parse_claude_response
from data.logger import get_ai_logger
from datetime import datetime, date
import os


class ClaudeClient:
    """
    Claude API client with token tracking and cost limits
    
    Token Pricing (Claude 3.5 Sonnet):
    - Input: $3.00 per 1M tokens
    - Output: $15.00 per 1M tokens
    """
    
    # Claude 3.5 Sonnet pricing
    INPUT_COST_PER_1M = 3.00  # $3 per 1M input tokens
    OUTPUT_COST_PER_1M = 15.00  # $15 per 1M output tokens
    
    def __init__(self, daily_limit_usd: float = 5.0):
        config = get_config()
        
        # Cost tracking
        self.daily_limit_usd = daily_limit_usd
        self.today = date.today()
        self.daily_input_tokens = 0
        self.daily_output_tokens = 0
        self.daily_cost = 0.0
        self.silent_mode = False
        
        self.client = Anthropic(api_key=config.ai.anthropic_api_key)
        
        # Use Claude Opus 4 for best analysis
        self.model = "claude-opus-4-20250514"
        
        # AI decision logger
        self.ai_logger = get_ai_logger()
        
        # Configuration
        self.account_size = config.trading.account_size
        self.max_risk = config.trading.max_risk_per_trade
        
        logger.info("Claude AI client initialized with model: " + self.model)
    
    
    def _reset_daily_if_needed(self):
        """Reset counters if new day"""
        today = date.today()
        if today != self.today:
            logger.info(
                f"📊 Daily Claude usage reset:\n"
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
        
        # Calculate cost (Claude is more expensive than Gemini!)
        input_cost = (input_tokens / 1_000_000) * self.INPUT_COST_PER_1M
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_COST_PER_1M
        call_cost = input_cost + output_cost
        
        self.daily_cost += call_cost
        
        logger.info(
            f"💰 Claude usage: {input_tokens:,} in + {output_tokens:,} out = ${call_cost:.4f}\n"
            f"   Daily total: ${self.daily_cost:.4f} / ${self.daily_limit_usd:.2f}"
        )
        
        # Check limit
        if self.daily_cost >= self.daily_limit_usd:
            self.silent_mode = True
            logger.error(
                f"🚨 CLAUDE DAILY LIMIT REACHED!\n"
                f"   Spent: ${self.daily_cost:.4f}\n"
                f"   Limit: ${self.daily_limit_usd:.2f}\n"
                f"   → SILENT MODE ACTIVATED"
            )
    
    def can_make_request(self) -> bool:
        """Check if we can make another API request"""
        self._reset_daily_if_needed()
        return not self.silent_mode
    
    async def analyze_strategy(
        self,
        stock_data: Dict[str, Any],
        options_data: Dict[str, Any],
        strategy_type: str
    ) -> Dict[str, Any]:
        """
        Deep analysis with Claude and cost tracking
        
        Returns early if daily limit exceeded
        
        Phase 2: Analyze specific strategy with confidence scoring
        
        Returns confidence score (1-10) instead of binary approval.
        Only trades with confidence >= 9 are executed.
        
        Args:
            stock_data: Stock market data
            options_data: Option Greeks and pricing
            strategy_type: e.g., "IRON_CONDOR", "VERTICAL_SPREAD"
            
        Returns:
            Analysis with confidence_score (1-10) and reasoning
        """
        try:
            prompt = f"""You are analyzing a {strategy_type} options strategy for {stock_data['symbol']}.

**CRITICAL: Provide a CONFIDENCE SCORE (1-10)**
- 1-3: Low confidence - clear red flags
- 4-6: Medium confidence - some concerns
- 7-8: Good confidence - minor concerns
- 9-10: High confidence - strong setup
**Trade ONLY if confidence >= 9/10**

Stock Data:
- Symbol: {stock_data['symbol']}
- Price: ${stock_data.get('price', 'N/A')}
- IV Rank: {stock_data.get('iv_rank', 'N/A')}
- Volume: {stock_data.get('volume', 'N/A'):,}
- Sector: {stock_data.get('sector', 'Unknown')}

Option Greeks:
- Delta: {options_data.get('delta', 'N/A')}
- Gamma: {options_data.get('gamma', 'N/A')}
- Theta: {options_data.get('theta', 'N/A')}
- Vega: {options_data.get('vega', 'N/A')}
- Vanna: {options_data.get('vanna', 'N/A')}
- Implied Vol: {options_data.get('impl_vol', 'N/A')}

Strategy: {strategy_type}

Analyze this setup and provide:

1. **CONFIDENCE SCORE**: X/10 (required - be honest!)

2. **Key Strengths** (what makes this attractive):
   - List 2-3 strongest points

3. **Key Risks** (what could go wrong):
   - List 2-3 main concerns

4. **Decision** (APPROVE or REJECT):
   - APPROVE only if confidence >= 9/10
   - REJECT if confidence < 9/10

5. **Reasoning** (2-3 sentences):
   - Why this confidence score?
   - What would improve it?

Be conservative. If unsure, confidence should be 7 or below.
Quality > Quantity. Better to skip marginal setups.

Format response as JSON:
{{
    "confidence_score": 9,
    "decision": "APPROVE",
    "strengths": ["strength1", "strength2"],
    "risks": ["risk1", "risk2"],
    "reasoning": "explanation",
    "greeks_validated": true
}}
"""
            
            # Call Claude API
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Track token usage from response
            if hasattr(message, 'usage'):
                input_tokens = message.usage.input_tokens
                output_tokens = message.usage.output_tokens
                self._track_usage(input_tokens, output_tokens)
            else:
                # Estimate if usage data unavailable
                estimated_input = len(prompt) // 4
                estimated_output = len(message.content[0].text) // 4
                self._track_usage(estimated_input, estimated_output)
                logger.warning("⚠️ Using estimated token counts (usage data unavailable)")
            
            response_text = message.content[0].text
            
            # Parse JSON response
            import json
            try:
                # Try to extract JSON from response
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    analysis = json.loads(json_str)
                else:
                    raise ValueError("No JSON found in response")
                
            except Exception as e:
                logger.warning(f"Failed to parse JSON: {e}, using fallback")
                # Fallback parsing
                analysis = {
                    'confidence_score': 5,  # Low confidence if parsing fails
                    'decision': 'REJECT',
                    'reasoning': response_text,
                    'greeks_validated': False
                }
            
            # Validate confidence score
            confidence = analysis.get('confidence_score', 0)
            if not isinstance(confidence, (int, float)) or confidence < 1 or confidence > 10:
                logger.warning(f"Invalid confidence score: {confidence}, defaulting to 5")
                confidence = 5
                analysis['confidence_score'] = 5
            
            # Override decision based on confidence threshold
            if confidence >= 9:
                analysis['decision'] = 'APPROVE'
                analysis['approved'] = True
            else:
                analysis['decision'] = 'REJECT'
                analysis['approved'] = False
                if 'reasoning' in analysis:
                    analysis['reasoning'] += f" (Confidence {confidence}/10 below threshold of 9)"
            
            logger.info(
                f"Claude analysis: {stock_data['symbol']} "
                f"Confidence={confidence}/10, Decision={analysis['decision']}"
            )
            
            if confidence < 9:
                logger.warning(
                    f"⚠️  Trade REJECTED: Confidence {confidence}/10 below threshold. "
                    f"Reason: {analysis.get('reasoning', 'N/A')}"
                )
            else:
                logger.info(
                    f"✅ Trade APPROVED: High confidence ({confidence}/10)"
                )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in Claude strategy analysis: {e}")
            return {
                'confidence_score': 1,
                'decision': 'REJECT',
                'reasoning': f"An unexpected error occurred: {str(e)}",
                'greeks_validated': False,
                'approved': False
            }
    
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
