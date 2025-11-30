"""
Earnings RAG (Retrieval-Augmented Generation)
Fetches real earnings data and provides context for AI analysis.
"""
from typing import Dict, Any, Optional, List
from loguru import logger
from datetime import datetime
import asyncio


class EarningsRAG:
    """Fetch and structure earnings data for AI context"""
    
    def __init__(self):
        self.cache = {}  # Cache earnings data
        self.cache_ttl = 86400  # 24 hours
    
    async def fetch_earnings_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch earnings data from IBKR fundamental data
        
        Returns structured earnings metrics for AI context:
        - Revenue (actual vs consensus)
        - EPS (actual vs consensus)
        - Guidance (company vs consensus)
        - Year-over-year growth
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Earnings data dict or None
        """
        # Check cache
        if symbol in self.cache:
            cached_time, data = self.cache[symbol]
            age = (datetime.now() - cached_time).seconds
            if age < self.cache_ttl:
                logger.debug(f"Using cached earnings data for {symbol}")
                return data
        
        try:
            from ibkr.data_fetcher import get_data_fetcher
            
            fetcher = get_data_fetcher()
            ib = fetcher.connection.get_client()
            
            # Get stock contract
            from ib_insync import Stock
            stock = Stock(symbol, 'SMART', 'USD')
            await ib.qualifyContractsAsync(stock)
            
            logger.info(f"Fetching earnings fundamentals for {symbol}...")
            
            # Request financial summary from IBKR
            financial_xml = await ib.reqFundamentalDataAsync(
                stock,
                'ReportsFinSummary'  # Financial summary with earnings
            )
            
            if not financial_xml:
                logger.warning(f"No financial data for {symbol}")
                return None
            
            # Parse XML earnings data
            earnings_data = self._parse_earnings_xml(financial_xml, symbol)
            
            if earnings_data:
                # Cache result
                self.cache[symbol] = (datetime.now(), earnings_data)
                logger.info(f"✅ Fetched earnings data for {symbol}")
                return earnings_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching earnings data for {symbol}: {e}")
            return None
    
    def _parse_earnings_xml(self, xml_data: str, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Parse IBKR financial XML for earnings metrics
        
        Args:
            xml_data: XML from IBKR
            symbol: Stock symbol
            
        Returns:
            Structured earnings dict
        """
        try:
            from xml.etree import ElementTree as ET
            
            root = ET.fromstring(xml_data)
            
            # Extract key metrics
            # Note: XML structure varies, this is a simplified example
            
            earnings = {
                'symbol': symbol,
                'report_date': None,
                'fiscal_quarter': None,
                
                # Revenue
                'revenue_actual': None,
                'revenue_consensus': None,
                'revenue_surprise_pct': None,
                
                # EPS
                'eps_actual': None,
                'eps_consensus': None,
                'eps_surprise_pct': None,
                
                # Guidance
                'guidance_revenue': None,
                'guidance_eps': None,
                'analyst_target_price': None,
                
                # Growth
                'revenue_yoy_growth': None,
                'eps_yoy_growth': None,
            }
            
            # Parse earnings elements
            # (Actual XML parsing would be more complex)
            for elem in root.iter():
                if 'Revenue' in elem.tag:
                    try:
                        earnings['revenue_actual'] = float(elem.text)
                    except (ValueError, AttributeError):
                        pass
                
                elif 'EPS' in elem.tag or 'EarningsPerShare' in elem.tag:
                    try:
                        earnings['eps_actual'] = float(elem.text)
                    except (ValueError, AttributeError):
                        pass
            
            return earnings
            
        except Exception as e:
            logger.error(f"Error parsing earnings XML: {e}")
            return None
    
    def create_rag_context(self, earnings_data: Dict[str, Any]) -> str:
        """
        Create structured context for AI from earnings data
        
        This is the "Retrieval" part of RAG - we retrieve real data
        and format it for AI to use.
        
        Args:
            earnings_data: Parsed earnings metrics
            
        Returns:
            Formatted context string for AI prompt
        """
        if not earnings_data:
            return "No earnings data available."
        
        symbol = earnings_data['symbol']
        
        context = f"""
**EARNINGS DATA CONTEXT - {symbol}**

Latest Earnings Report:
- Report Date: {earnings_data.get('report_date', 'N/A')}
- Fiscal Quarter: {earnings_data.get('fiscal_quarter', 'N/A')}

Revenue Metrics:
- Actual Revenue: ${earnings_data.get('revenue_actual', 'N/A')}
- Consensus Estimate: ${earnings_data.get('revenue_consensus', 'N/A')}
- Surprise: {earnings_data.get('revenue_surprise_pct', 'N/A')}%
- YoY Growth: {earnings_data.get('revenue_yoy_growth', 'N/A')}%

Earnings Per Share (EPS):
- Actual EPS: ${earnings_data.get('eps_actual', 'N/A')}
- Consensus Estimate: ${earnings_data.get('eps_consensus', 'N/A')}
- Surprise: {earnings_data.get('eps_surprise_pct', 'N/A')}%
- YoY Growth: {earnings_data.get('eps_yoy_growth', 'N/A')}%

Forward Guidance:
- Revenue Guidance: ${earnings_data.get('guidance_revenue', 'N/A')}
- EPS Guidance: ${earnings_data.get('guidance_eps', 'N/A')}
- Analyst Price Target: ${earnings_data.get('analyst_target_price', 'N/A')}

**Analysis Instructions:**
Compare ACTUAL vs CONSENSUS on both revenue and EPS.
A "beat" on revenue but "miss" on guidance is BEARISH.
Look at YoY growth trends - slowing growth is concerning.
"""
        return context.strip()
    
    async def get_rag_enhanced_analysis(
        self,
        symbol: str,
        ai_client  # Claude or Gemini client
    ) -> Dict[str, Any]:
        """
        Get AI analysis enhanced with RAG earnings context + transcript tone
        
        This is the FULL RAG pipeline:
        1. RETRIEVE: Fetch real earnings data
        2. AUGMENT: Format as context + fetch transcript
        3. GENERATE: AI analyzes with real data + management tone
        
        Args:
            symbol: Stock ticker
            ai_client: AI client (Claude/Gemini)
            
        Returns:
            AI analysis with earnings context and tone analysis
        """
        try:
            # Step 1: RETRIEVE earnings data
            earnings_data = await self.fetch_earnings_data(symbol)
            
            if not earnings_data:
                logger.warning(f"No earnings data for {symbol}, using generic analysis")
                return {
                    'has_earnings_data': False,
                    'analysis': 'No recent earnings data available'
                }
            
            # Step 2: AUGMENT - create numerical context
            rag_context = self.create_rag_context(earnings_data)
            
            # Step 2b: AUGMENT - fetch and analyze transcript (NEW!)
            from analysis.earnings_transcript import get_transcript_analyzer
            
            transcript_analyzer = get_transcript_analyzer()
            transcript = await transcript_analyzer.fetch_transcript(symbol)
            
            tone_analysis = None
            if transcript:
                logger.info(f"📞 Analyzing earnings call tone for {symbol}...")
                tone_analysis = await transcript_analyzer.analyze_management_tone(
                    symbol=symbol,
                    transcript=transcript,
                    earnings_data=earnings_data,
                    gemini_client=ai_client  # Use Gemini for tone analysis
                )
            
            # Step 3: GENERATE - AI analysis with BOTH numbers and tone
            prompt = f"""
You are analyzing {symbol} with COMPLETE EARNINGS CONTEXT.

{rag_context}
"""
            
            if tone_analysis:
                prompt += f"""

**MANAGEMENT TONE ANALYSIS (from Earnings Call):**
- Confidence Score: {tone_analysis.get('confidence_score', 'N/A')}/10
- Guidance Tone: {tone_analysis.get('guidance_tone', 'N/A')}
- Management Sentiment: {tone_analysis.get('management_sentiment', 'N/A')}
- Red Flags: {', '.join(tone_analysis.get('red_flags', []))}
- Green Flags: {', '.join(tone_analysis.get('green_flags', []))}
- Key Insight: {tone_analysis.get('reasoning', 'N/A')}

**CRITICAL:** Management tone often predicts stock movement better than numbers!
- Good numbers + cautious tone = BEARISH
- Miss numbers + confident tone = could be BULLISH
"""
            
            prompt += """

Based on BOTH the numerical data AND management tone:

1. **Overall Earnings Quality** (1-10)
2. **Trading Implication** (Bullish/Neutral/Bearish)
3. **Confidence in Signal** (1-10)
4. **Reasoning** (2-3 sentences)

Format as JSON:
{
    "overall_earnings_quality": 8,
    "trading_implication": "bullish",
    "confidence_in_signal": 9,
    "reasoning": "explanation combining numbers AND tone"
}
"""
            
            # Call AI with enriched context
            if hasattr(ai_client, 'analyze_with_context'):
                analysis = await ai_client.analyze_with_context(prompt)
            else:
                # Fallback
                logger.info("Using RAG context with standard AI call")
                analysis = {
                    'has_earnings_data': True,
                    'rag_context': rag_context,
                    'earnings_data': earnings_data,
                    'tone_analysis': tone_analysis
                }
            
            # Add tone analysis to result
            if tone_analysis:
                analysis['management_tone'] = tone_analysis
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in RAG analysis: {e}")
            return {
                'has_earnings_data': False,
                'error': str(e)
            }


# Singleton
_earnings_rag: Optional[EarningsRAG] = None


def get_earnings_rag() -> EarningsRAG:
    """Get or create singleton earnings RAG"""
    global _earnings_rag
    if _earnings_rag is None:
        _earnings_rag = EarningsRAG()
    return _earnings_rag
