"""
Loss Analyzer - AI-Powered Post-Mortem Analysis
Analyzes losing trades to identify root causes and generate prevention strategies.

Uses Claude Opus 4.5 for deep analysis due to superior reasoning capabilities.
"""
from typing import List, Dict, Any, Optional
from loguru import logger
from datetime import datetime, timedelta
import asyncio

from data.database import get_database
from ai.claude_client import get_claude_client
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
        self.claude = get_claude_client(use_opus=True)  # Use Opus 4.5 for deep analysis
        self.data_fetcher = get_data_fetcher()
        
    async def initialize(self):
        """Initialize database connection"""
        self.db = await get_database()
        
    async def analyze_recent_losses(
        self, 
        days: int = 7, 
        max_analyses: int = 20
    ) -> str:
        """
        Analyze recent losing trades and generate a report
        
        Args:
            days: Lookback period (default 7 for weekly analysis)
            max_analyses: Maximum trades to send to Claude for deep analysis
                          (prevents excessive API costs if there are many losses)
            
        Returns:
            Markdown report
        """
        if not self.db:
            await self.initialize()
            
        # 1. Get ALL losing trades in period (no limit)
        losses = await self.db.get_losing_trades(limit=None, days=days)
        
        if not losses:
            logger.info("No losing trades found in recent history! 🎉")
            return "No recent losses to analyze. Great job! 🎉"
        
        logger.info(f"Found {len(losses)} losing trades in last {days} days")
        
        # Calculate total loss
        total_loss = sum(trade['realized_pnl'] for trade in losses)
        logger.info(f"Total loss: ${total_loss:.2f}")
        
        # 2. Analyze each loss (with safety limit for API costs)
        analyses = []
        
        # Analyze worst losses first (already sorted by realized_pnl ASC)
        trades_to_analyze = losses[:max_analyses] if len(losses) > max_analyses else losses
        
        if len(losses) > max_analyses:
            logger.warning(
                f"⚠️  Found {len(losses)} losses, analyzing worst {max_analyses} "
                f"to control Claude API costs"
            )
        
        for i, trade in enumerate(trades_to_analyze, 1):
            logger.info(f"Analyzing loss {i}/{len(trades_to_analyze)}: {trade['symbol']} (${trade['realized_pnl']:.2f})")
            analysis = await self._analyze_single_loss(trade)
            if analysis:
                analyses.append(analysis)
        
        # 3. Generate synthesis report (includes all losses, even non-analyzed ones)
        report = await self._generate_prevention_report(
            analyses, 
            total_losses=len(losses),
            total_loss_amount=total_loss
        )
        
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
            
            response = await self.claude.generate_response(prompt)
            
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
            
    async def _generate_prevention_report(
        self, 
        analyses: List[Dict[str, Any]],
        total_losses: int,
        total_loss_amount: float
    ) -> str:
        """
        Synthesize analyses into a prevention report
        
        Args:
            analyses: List of AI analyses for individual trades
            total_losses: Total number of losing trades found
            total_loss_amount: Total $ amount of all losses
        """
        if not analyses:
            return "Analysis failed."
            
        # Group by category
        categories = {}
        analyzed_loss = 0
        
        for a in analyses:
            cat = a.get('category', 'UNKNOWN')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(a)
            analyzed_loss += a.get('pnl', 0)
            
        # Generate Markdown
        report = f"""
# 📉 Loss Analysis Report
**Total Losses Found:** {total_losses} trades
**Total Loss Amount:** ${total_loss_amount:.2f}

**Analyzed in Detail:** {len(analyses)} worst trades (${analyzed_loss:.2f})
"""
        
        # Add note if not all trades were analyzed
        if len(analyses) < total_losses:
            report += f"*(Analyzed worst {len(analyses)} to control API costs)*\n"
        
        report += "\n## 🔍 Root Cause Breakdown\n\n"
        
        for cat, items in categories.items():
            report += f"### {cat} ({len(items)} trades)\n"
            for item in items:
                report += f"- **{item['symbol']}** (${item['pnl']:.2f}): {item['root_cause']}\n"
                report += f"  - *Lesson:* {item['lesson']}\n"
            report += "\n"
            
        # Ask AI for strategic improvements
        summary_prompt = f"""
        Based on these losing trades, suggest 3 SYSTEMIC improvements to the trading bot.
        
        Total losses in period: {total_losses} trades, ${total_loss_amount:.2f}
        Analyzed trades: {analyses}
        
        Focus on:
        - Risk management rules
        - Entry filters (VIX, liquidity)
        - Exit discipline
        
        Format as Markdown bullet points.
        """
        
        improvements = await self.claude.generate_response(summary_prompt)
        
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
