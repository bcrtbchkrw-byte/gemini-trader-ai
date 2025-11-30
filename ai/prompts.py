"""
AI Prompt Templates
Structured prompts for Gemini and Claude AI analysis.
"""
from typing import Dict, Any, Optional
from datetime import datetime


def get_gemini_fundamental_prompt(
    symbol: str,
    current_price: float,
    vix: float,
    additional_context: Optional[str] = None
) -> str:
    """
    Generate prompt for Gemini fundamental analysis with JSON output
    
    Args:
        symbol: Stock ticker
        current_price: Current stock price
        vix: Current VIX value
        additional_context: Any additional context to include
        
    Returns:
        Formatted prompt string requesting JSON response
    """
    prompt = f"""Analyzuj aktuální tržní situaci pro ticker {symbol}.

Aktuální data:
- Ticker: {symbol}
- Cena: ${current_price:.2f}
- VIX: {vix:.2f}
- Datum: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Úkol:
1. **Fundamentální analýza**: Jaká je aktuální fundamentální situace společnosti?
2. **Sentiment**: Jaký je aktuální market sentiment?
3. **Makro kontext**: Jaké makroekonomické faktory ovlivňují tento ticker?
4. **Rizika**: Jaká jsou hlavní rizika v nadcházejících 30-45 dnech?
5. **Doporučení**: Je vhodný čas na prodej opcí (credit spreads) nebo nákup opcí (debit spreads)?
"""
    
    if additional_context:
        prompt += f"\nDodatkový kontext:\n{additional_context}\n"
    
    prompt += """
DŮLEŽITÉ: Odpověz POUZE ve formátu JSON (pro úsporu tokenů). Struktura:

{
  "fundamental_score": <číslo 1-10>,
  "sentiment": "<BULLISH|NEUTRAL|BEARISH>",
  "macro_environment": "<stručný popis makro prostředí>",
  "key_risks": ["<riziko 1>", "<riziko 2>", "..."],
  "recommendation": "<CREDIT_SPREADS|DEBIT_SPREADS|AVOID>",
  "reasoning": "<stručné odůvodnění>"
}

Žádný další text mimo JSON.
"""
    
    return prompt


def get_gemini_batch_analysis_prompt(
    candidates: list,
    news_context: Dict[str, list],
    vix: float
) -> str:
    """
    Generate prompt for Gemini batch analysis (Phase 2)
    
    Args:
        candidates: List of stock candidates from Phase 1
        news_context: Dict mapping symbol to news articles
        vix: Current VIX value
        
    Returns:
        Formatted prompt for batch analysis
    """
    # Format candidates
    stocks_text = ""
    for i, candidate in enumerate(candidates, 1):
        symbol = candidate['symbol']
        news = news_context.get(symbol, [])
        news_headlines = "\n      ".join([f"- {article['title']}" for article in news[:5]])
        
        stocks_text += f"""
{i}. **{symbol}**
   - Cena: ${candidate['price']:.2f}
   - IV Rank: {candidate.get('iv_rank', 'N/A')}
   - Sektor: {candidate.get('sector', 'Unknown')}
   - Likvidita Score: {candidate.get('liquidity_score', 'N/A')}/10
   - News (7 dní):
      {news_headlines if news_headlines else '- Žádné news dostupné'}
"""
    
    prompt = f"""Jsi fundamentální analytik evaluující akcie pro options trading.

**Context**:
- VIX: {vix:.2f}
- Účel: Vybrat 2-3 nejlepší akcie pro options trading (malý účet ~$200)

**Kandidáti z Phase 1** (prošly filtrem cena, likvidita, IV rank):
{stocks_text}

**Tvůj úkol**:
Analyzuj fundamenty + news sentiment pro každou akcii a vyber TOP 2-3 kandidáty.

**Kritéria hodnocení**:
1. **Fundamentální zdraví** (earnings, cash flow, debt)
2. **News sentiment** (pozitivní/negativní catalysts v příštích 30-45 dnech)
3. **Makro prostředí** (sektor outlook, Fed policy impact)
4. **Options trading potential** (volatility, earnings date, catalysts)

**DŮLEŽITÉ**: Odpověz POUZE JSON:

{{
  "ranked_stocks": [
    {{
      "symbol": "...",
      "fundamental_score": 1-10,
      "news_sentiment": "POSITIVE|NEUTRAL|NEGATIVE",
      "recommendation": "TOP_PICK|CONSIDER|AVOID",
      "reasoning": "<stručné zdůvodnění max 50 slov>"
    }}
  ],
  "top_picks": ["SYMBOL1", "SYMBOL2", "SYMBOL3"]
}}

Žádný další text.
"""
    
    return prompt


def get_claude_greeks_analysis_prompt(
    symbol: str,
    options_data: list,
    vix: float,
    regime: str,
    account_size: float,
    max_risk: float
) -> str:
    """
    Generate prompt for Claude Greeks analysis and trade recommendation
    This uses your original "Gemini-Trader 5.1" system prompt with JSON output
    
    Args:
        symbol: Stock ticker
        options_data: List of option contracts with Greeks from IBKR API
        vix: Current VIX value
        regime: Current VIX regime
        account_size: Account size in USD
        max_risk: Max risk per trade
        
    Returns:
        Formatted prompt with your trading rules requesting JSON response
    """
    
    # Format options data - Greeks come from IBKR API
    options_text = "\n".join([
        f"- Strike {opt['strike']}{opt['right']}, Exp: {opt['expiration']}, "
        f"Delta: {opt['delta']:.3f}, Theta: {opt['theta']:.3f}, "
        f"Vega: {opt['vega']:.3f}, Gamma: {opt.get('gamma', 0):.4f}, "
        f"IV: {opt.get('impl_vol', 0)*100:.1f}%, "
        f"Bid: ${opt['bid']:.2f}, Ask: ${opt['ask']:.2f}"
        for opt in options_data[:10]  # Limit to top 10
    ])
    
    prompt = f"""Jsi "Gemini-Trader 5.1", elitní opční stratég a risk manager.

**Kontext**: Spravuješ "Micro Margin Account" (${account_size:.0f}) u IBKR. Máš k dispozici real-time data přes API.

**Cíl**: Generovat konzistentní příjmy (Income) při absolutní OCHRANĚ KAPITÁLU.

---

## 1. MAKRO PROTOKOL (VIX Logic)

**Aktuální stav trhu:**
- VIX: {vix:.2f}
- Regime: {regime}

**VIX pravidla:**
- VIX > 30 (PANIC): 🛑 HARD STOP. Zákaz nových Credit pozic.
- VIX 20-30 (HIGH VOL): ✅ Go Zone pro Credit Spreads.
- VIX 15-20 (NORMAL): ⚠️ Selektivní Credit Spreads.
- VIX < 15 (LOW VOL): 💤 Preferuj Debit/Calendar Spreads.

---

## 2. DOSTUPNÉ STRATEGIE

**PREMIUM SELLING (High IV):**
1. **IRON_CONDOR** - OTM call spread + OTM put spread
   - Best: VIX > 20, range-bound market
   - Max Profit: Total credit
   - Risk: Defined (width - credit)

2. **IRON_BUTTERFLY** - ATM straddle + protective wings
   - Best: VIX > 25, expect pin at strike
   - Max Profit: Higher than Iron Condor
   - Risk: Narrower profit zone

3. **VERTICAL_CREDIT_SPREAD** - Sell closer, buy further OTM
   - Best: Directional conviction + high IV
   - Max Profit: Credit received
   - Risk: Defined spread width

**TIME DECAY PLAYS:**
4. **CALENDAR_SPREAD** - Sell near-term, buy far-term
   - Best: Low-medium IV, expect IV rise
   - Profit: Time decay differential
   - Risk: Near-term moves against you

5. **THETA_DECAY_OPTIMIZED** - Maximum theta extraction
   - Best: 20-35 DTE for OTM options
   - Focus: Accelerating decay curve
   - Strategy: Sell at optimal decay point

**DIRECTIONAL (Low IV):**
6. **VERTICAL_DEBIT_SPREAD** - Buy ITM, sell OTM
   - Best: VIX < 15, directional conviction
   - Leverage: Defined risk directional play
   - Max Profit: Spread width - debit

**QUANTITATIVE:**
7. **MEAN_REVERSION** - Jim Simons style
   - Best: Z-score > 2 (price extreme)
   - Signal: Price reverting to mean
   - Entry: Sell spreads in reversion direction

---

## 3. RISK MANAGEMENT

- Kapitál v riziku: Max ${max_risk:.0f} na jeden obchod
- Max Allocation: Max 25% účtu na jeden trade
- Earnings: < 48h → ZÁKAZ

---

## 3. ANALÝZA GREEKS

**DŮLEŽITÉ**: Greeks (Delta, Theta, Vega, Gamma) jsou z IBKR API - jsou již přesné! 
**TVŮJ ÚKOL**: Vypočítat VANNA risk (jediný Greek, který musíš analyzovat).

**Dostupné opce pro {symbol} (Greeks z IBKR):**
{options_text}

**Požadavky:**

A. **DELTA** (z IBKR)
   - Credit Spreads: Short Leg Delta 0.15 – 0.25
   - Debit Spreads: Long Leg Delta 0.60 – 0.75

B. **THETA** (z IBKR)
   - Pro Credit: Theta > $1.00 denně

C. **VANNA** (VYPOČTI!)
   - Koncept: dΔ/dσ - citlivost Delty na změnu volatility
   - Test: "Pokud IV stoupne o 5 bodů, zůstane Delta pod 0.40?"
   - Pokud VANNA příliš vysoká → ZAMÍTNI

D. **LIKVIDITA**
   - Bid/Ask Spread: < $0.05
   - Volume/OI: > 10%

---

## 4. VÝSTUPNÍ STRATEGIE

- **Take Profit**: @ 50% Max Profit
- **Stop Loss**: @ 2.5x Credit Received

---

## FORMÁT ODPOVĚDI (JSON PRO ÚSPORU TOKENŮ)

Odpověz POUZE JSON bez dalšího textu:

{{
  "verdict": "<SCHVÁLENO|ZAMÍTNUTO|UPRAVIT>",
  "vix_check": "<stručný komentář>",
  "greeks_health": {{
    "delta": {{"value": {vix}, "status": "<SAFE|RISKY>"}},
    "vanna": {{
      "calculated_delta_expansion": 0.0,
      "iv_stress_test": "+5%",
      "projected_delta": 0.0,
      "status": "<SAFE|RISKY>"
    }},
    "theta": {{"value": 0.0, "status": "<SAFE|RISKY>"}},
    "liquidity": "<GOOD|POOR>"
  }},
  "execution_instructions": {{
    "strategy": "<IRON_CONDOR|IRON_BUTTERFLY|VERTICAL_PUT_SPREAD|VERTICAL_CALL_SPREAD|CALENDAR_SPREAD|THETA_DECAY|MEAN_REVERSION|null>",
    "short_strike": 0.0,
    "long_strike": 0.0,
    "expiration": "<YYYY-MM-DD nebo null>",
    "limit_price": 0.0,
    "max_risk": 0.0,
    "strategy_specific": {{
      "iron_condor_wings": {{"call_wing": 0.0, "put_wing": 0.0}},
      "calendar_spread_legs": {{"near_dte": 30, "far_dte": 60}}
    }}
  }},
  "exit_rules": {{
    "take_profit": 0.0,
    "stop_loss": 0.0
  }},
  "reasoning": "<stručné zdůvodnění>"
}}

Analyzuj data a vrať čistý JSON.
"""
    
    return prompt


def parse_gemini_response(response_text: str) -> Dict[str, Any]:
    """
    Parse Gemini analysis JSON response
    
    Args:
        response_text: Raw JSON response from Gemini
        
    Returns:
        Structured dict with parsed data
    """
    import json
    
    try:
        # Try to parse as JSON
        parsed = json.loads(response_text)
        parsed['raw_response'] = response_text
        return parsed
    except json.JSONDecodeError:
        # Fallback to text parsing if JSON fails
        return {
            'raw_response': response_text,
            'fundamental_score': None,
            'sentiment': 'NEUTRAL',
            'recommendation': 'AVOID',
            'reasoning': response_text,
            'error': 'Failed to parse JSON response'
        }


def parse_claude_response(response_text: str) -> Dict[str, Any]:
    """
    Parse Claude trade analysis JSON response
    
    Args:
        response_text: Raw JSON response from Claude
        
    Returns:
        Structured dict with trade recommendation
    """
    import json
    
    try:
        # Try to parse as JSON
        parsed = json.loads(response_text)
        parsed['raw_response'] = response_text
        
        # Extract key fields for backward compatibility
        execution = parsed.get('execution_instructions', {})
        parsed['strategy'] = execution.get('strategy')
        parsed['short_strike'] = execution.get('short_strike')
        parsed['long_strike'] = execution.get('long_strike')
        parsed['expiration'] = execution.get('expiration')
        parsed['max_risk'] = execution.get('max_risk')
        parsed['limit_price'] = execution.get('limit_price')
        
        exit_rules = parsed.get('exit_rules', {})
        parsed['take_profit'] = exit_rules.get('take_profit')
        parsed['stop_loss'] = exit_rules.get('stop_loss')
        
        return parsed
    except json.JSONDecodeError:
        # Fallback to text parsing if JSON fails
        return {
            'raw_response': response_text,
            'verdict': 'ZAMÍTNUTO',
            'strategy': None,
            'reasoning': response_text,
            'error': 'Failed to parse JSON response'
        }
