"""
Loss Analyzer - AI-Powered Post-Mortem Analysis
Analyzes losing trades to identify root causes and generate prevention strategies.
"""
from typing import List, Dict, Any, Optional
from loguru import logger
from datetime import datetime, timedelta
import asyncio

from data.database import get_database
from ai.gemini_client import get_gemini_client
from ibkr.data_fetcher import get_data_fetcher


class LossAnalyzer:
    """
    Analyzes losing trades to improve future performance.
    
    Process:
    1. Fetch losing trades from DB
    2. Reconstruct market context (VIX, regime, news)
    3. Use AI to analyze WHY the trade failed
    4. Generate actionable prevention rules
    """
    
    def __init__(self):
        self.db = None
        self.gemini = get_gemini_client()
        self.data_fetcher = get_data_fetcher()
        
    async def initialize(self):
        """Initialize database connection"""
        self.db = await get_database()
        
    async def analyze_recent_losses(self, days: int = 30, limit: int = 5) -> str:
        """
        Analyze recent losing trades and generate a report
        
        Args:
            days: Lookback period
            limit: Max trades to analyze
            
        Returns:
            Markdown report
        """
        if not self.db:
            await self.initialize()
            
        # 1. Get losing trades
        losses = await self.db.get_losing_trades(limit=limit, days=days)
        
        if not losses:
            logger.info("No losing trades found in recent history! 🎉")
            return "No recent losses to analyze. Great job! 🎉"
        
        logger.info(f"Analyzing {len(losses)} losing trades...")
        
        # 2. Analyze each loss
        analyses = []
        for trade in losses:
            analysis = await self._analyze_single_loss(trade)
            if analysis:
                analyses.append(analysis)
        
        # 3. Generate synthesis report
        report = await self._generate_prevention_report(analyses)
        
        return report
    
    async def _analyze_single_loss(self, trade: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze a single losing trade using AI"""
        try:
            symbol = trade['symbol']
            pnl = trade['realized_pnl']
            logger.debug(f"Analyzing loss: {symbol} (${pnl:.2f})")
            
            # Reconstruct context
            context = {
                "trade": trade,
                "market_context": {
                    "vix_entry": trade.get('vix_at_entry'),
                    "regime_entry": trade.get('regime_at_entry'),
                    "entry_date": trade.get('timestamp'),
                    "exit_date": trade.get('close_timestamp'),
                }
            }
            
            # Ask AI for root cause
            prompt = f"""
            Analyze this losing trade and identify the ROOT CAUSE of failure.
            
            Trade Details:
            - Symbol: {symbol}
            - Strategy: {trade['strategy']}
            - Direction: {trade['direction']}
            - Entry: {trade['timestamp']} (VIX: {trade.get('vix_at_entry')}, Regime: {trade.get('regime_at_entry')})
            - Exit: {trade['close_timestamp']}
            - P/L: ${pnl:.2f}
            - Notes: {trade.get('notes', 'None')}
            
            Task:
            1. Was this a Bad Luck (market moved unexpectedly) or Bad Process (ignored rules)?
            2. Did the market regime change during the trade?
            3. Was the position size appropriate?
            4. What is the single most important lesson from this loss?
            
            Output JSON:
            {{
                "root_cause": "...",
                "category": "BAD_LUCK" or "BAD_PROCESS" or "MARKET_SHIFT",
                "lesson": "...",
                "prevention": "..."
            }}
            """
            
            response = await self.gemini.generate_response(prompt)
            
            # Parse JSON (simplified)
            import json
            import re
            
            # Extract JSON block
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                analysis = json.loads(match.group(0))
                analysis['symbol'] = symbol
                analysis['pnl'] = pnl
                return analysis
            else:
                logger.warning(f"Could not parse AI analysis for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error analyzing trade {trade.get('symbol')}: {e}")
            return None
            
    async def _generate_prevention_report(self, analyses: List[Dict[str, Any]]) -> str:
        """Synthesize analyses into a prevention report"""
        if not analyses:
            return "Analysis failed."
            
        # Group by category
        categories = {}
        total_loss = 0
        
        for a in analyses:
            cat = a.get('category', 'UNKNOWN')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(a)
            total_loss += a.get('pnl', 0)
            
        # Generate Markdown
        report = f"""
# 📉 Loss Analysis Report
**Total Analyzed Loss:** ${total_loss:.2f}
**Trades Analyzed:** {len(analyses)}

## 🔍 Root Cause Breakdown

"""
        for cat, items in categories.items():
            report += f"### {cat} ({len(items)} trades)\n"
            for item in items:
                report += f"- **{item['symbol']}** (${item['pnl']:.2f}): {item['root_cause']}\n"
                report += f"  - *Lesson:* {item['lesson']}\n"
            report += "\n"
            
        # Ask AI for strategic improvements
        summary_prompt = f"""
        Based on these losing trades, suggest 3 SYSTEMIC improvements to the trading bot.
        
        Losses:
        {analyses}
        
        Focus on:
        - Risk management rules
        - Entry filters (VIX, liquidity)
        - Exit discipline
        
        Format as Markdown bullet points.
        """
        
        improvements = await self.gemini.generate_response(summary_prompt)
        
        report += "## 🛡️ Strategic Improvements\n\n"
        report += improvements
        
        return report


# Singleton
_loss_analyzer: Optional[LossAnalyzer] = None


def get_loss_analyzer() -> LossAnalyzer:
    """Get or create singleton loss analyzer"""
    global _loss_analyzer
    if _loss_analyzer is None:
        _loss_analyzer = LossAnalyzer()
    return _loss_analyzer
