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
    Generate prompt for Gemini fundamental analysis
    
    Args:
        symbol: Stock ticker
        current_price: Current stock price
        vix: Current VIX value
        additional_context: Any additional context to include
        
    Returns:
        Formatted prompt string
    """
    prompt = f"""Analyzuj aktuální tržní situaci pro ticker {symbol}.

Aktuální data:
- Ticker: {symbol}
- Cena: ${current_price:.2f}
- VIX: {vix:.2f}
- Datum: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Úkol:
1. **Fundamentální analýza**: Jaká je aktuální fundamentální situace společnosti? (Ziskovost, růst, zadlužení)
2. **Sentiment**: Jaký je aktuální market sentiment? (Zprávy, события, sector trends)
3. **Makro kontext**: Jaké makroekonomické faktory ovlivňují tento ticker?
4. **Rizika**: Jaká jsou hlavní rizika v nadcházejících 30-45 dnech?
5. **Doporučení**: Je vhodný čas na prodej opcí (credit spreads) nebo nákup opcí (debit spreads)?

"""
    
    if additional_context:
        prompt += f"\nDodatkový kontext:\n{additional_context}\n"
    
    prompt += """
Odpověď strukturuj jako:

**Fundamental Score**: [1-10] (1=velmi špatný, 10=výborný)
**Sentiment**: [BULLISH/NEUTRAL/BEARISH]
**Macro Environment**: [popis]
**Key Risks**: [seznam rizik]
**Recommendation**: [CREDIT_SPREADS/DEBIT_SPREADS/AVOID]
**Reasoning**: [odůvodnění]
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
    This uses your original "Gemini-Trader 5.1" system prompt
    
    Args:
        symbol: Stock ticker
        options_data: List of option contracts with Greeks
        vix: Current VIX value
        regime: Current VIX regime
        account_size: Account size in USD
        max_risk: Max risk per trade
        
    Returns:
        Formatted prompt with your trading rules
    """
    
    # Format options data
    options_text = "\n".join([
        f"- Strike {opt['strike']}{opt['right']}, Exp: {opt['expiration']}, "
        f"Delta: {opt['delta']:.3f}, Theta: {opt['theta']:.3f}, "
        f"Vega: {opt['vega']:.3f}, Vanna: {opt.get('vanna', 'N/A')}, "
        f"IV: {opt.get('impl_vol', 0)*100:.1f}%, "
        f"Bid: ${opt['bid']:.2f}, Ask: ${opt['ask']:.2f}"
        for opt in options_data[:10]  # Limit to top 10
    ])
    
    prompt = f"""Jsi "Gemini-Trader 5.1", elitní opční stratég a risk manager.

**Kontext**: Spravuješ "Micro Margin Account" (${account_size:.0f}) u IBKR. Máš k dispozici real-time data přes API.

**Cíl**: Generovat konzistentní příjmy (Income) při absolutní OCHRANĚ KAPITÁLU. Prioritou není maximální zisk, ale přežití účtu.

---

## 1. MAKRO PROTOKOL (VIX Logic)

**Aktuální stav trhu:**
- VIX: {vix:.2f}
- Regime: {regime}

**VIX pravidla:**
- VIX > 30 (PANIC): 🛑 HARD STOP. Zákaz nových Credit pozic.
- VIX 20-30 (HIGH VOL): ✅ Go Zone pro Credit Spreads.
- VIX 15-20 (NORMAL): ⚠️ Selektivní Credit Spreads.
- VIX < 15 (LOW VOL): 💤 Preferuj Debit Spreads nebo Calendar Spreads.

---

## 2. RISK MANAGEMENT (${account_size:.0f} Account Hard Limits)

- Kapitál v riziku: Max ${max_risk:.0f} na jeden obchod
- Max Allocation: Max 25% účtu na jeden trade
- Earnings: Zkontroluj datum earnings < 48h → ZÁKAZ nebo mimo Expected Move

---

## 3. ANALÝZA GREEKS (API DATA)

**Dostupné opce pro {symbol}:**
{options_text}

**Požadavky na Greeks:**

A. **DELTA** (Directional Risk)
   - Credit Spreads: Short Leg Delta ideálně 0.15 – 0.25
   - Debit Spreads: Long Leg Delta 0.60 – 0.75 (ITM)

B. **THETA** (Time Decay)
   - Pro Credit strategie: Theta kladná (> 0)
   - Check: Získáváme alespoň $1.00 denně?

C. **VANNA** (Volatility Stability) – CRITICAL CHECK
   - Koncept: Vanna měří citlivost Delty na změnu volatility (dΔ/dσ)
   - Riziko: Pokud VIX vystřelí (IV spike), Vanna může "nafouknout" Delta
   - Test: "Pokud IV stoupne o 5 bodů, zůstane Delta pod 0.40?"
   - Pokud je Vanna příliš vysoká → obchod ZAMÍTNI

D. **LIKVIDITA**
   - Bid/Ask Spread: < $0.05 nebo < 2% ceny opce
   - Volume/OI: Denní Volume alespoň 10% Open Interestu

---

## 4. VÝSTUPNÍ STRATEGIE

- **Take Profit**: BTC @ 50% Max Profit
- **Stop Loss**: BTC @ 2x - 2.5x Credit Received

---

## FORMÁT ODPOVĚDI

📊 **ANALÝZA OBCHODU: {symbol}**

**Verdikt**: [SCHVÁLENO / ZAMÍTNUTO / UPRAVIT]

**1. Logika & VIX Check:**
"VIX je {vix:.2f}, trh je v režimu {regime}. Strategie [Název] je [Vhodná/Nevhodná]."

**2. Greeks Health Check:**
- Delta: [Hodnota] (Bezpečné/Rizikové)
- Vanna Risk: [Hodnota/Komentář] – "Při nárůstu IV hrozí/nehrozí Delta expansion."
- Theta: [Hodnota] – "Čas hraje pro nás/proti nám."
- Likvidita: [Hodnocení]

**3. Exekuční Instrukce (pokud SCHVÁLENO):**
- Strategy: [Vertical Put/Call Spread / Iron Condor]
- Legs: Sell [Strike] / Buy [Strike]
- Expirace: [Datum]
- Limit Price: $[Mid-Point]
- Max Risk: $[Dolarová hodnota]

**4. Exit Pravidla:**
"Zadej GTC příkaz: Profit Taker @ $[Cena], Stop Loss @ $[Cena]."

---

Nyní analyzuj dostupná data a poskytni doporučení.
"""
    
    return prompt


def parse_gemini_response(response_text: str) -> Dict[str, Any]:
    """
    Parse Gemini analysis response
    
    Args:
        response_text: Raw response from Gemini
        
    Returns:
        Structured dict with parsed data
    """
    # Simple parsing - in production, use more robust parsing
    parsed = {
        'raw_response': response_text,
        'fundamental_score': None,
        'sentiment': 'NEUTRAL',
        'recommendation': 'AVOID',
        'reasoning': response_text
    }
    
    # Extract fundamental score
    if 'Fundamental Score' in response_text:
        try:
            score_line = [line for line in response_text.split('\n') if 'Fundamental Score' in line][0]
            score = int(score_line.split('[')[1].split(']')[0].split('-')[0])
            parsed['fundamental_score'] = score
        except:
            pass
    
    # Extract sentiment
    if 'BULLISH' in response_text.upper():
        parsed['sentiment'] = 'BULLISH'
    elif 'BEARISH' in response_text.upper():
        parsed['sentiment'] = 'BEARISH'
    
    # Extract recommendation
    if 'CREDIT_SPREADS' in response_text.upper():
        parsed['recommendation'] = 'CREDIT_SPREADS'
    elif 'DEBIT_SPREADS' in response_text.upper():
        parsed['recommendation'] = 'DEBIT_SPREADS'
    
    return parsed


def parse_claude_response(response_text: str) -> Dict[str, Any]:
    """
    Parse Claude trade analysis response
    
    Args:
        response_text: Raw response from Claude
        
    Returns:
        Structured dict with trade recommendation
    """
    parsed = {
        'raw_response': response_text,
        'verdict': 'ZAMÍTNUTO',
        'strategy': None,
        'short_strike': None,
        'long_strike': None,
        'expiration': None,
        'max_risk': None,
        'limit_price': None,
        'take_profit': None,
        'stop_loss': None,
        'reasoning': response_text
    }
    
    # Extract verdict
    if 'SCHVÁLENO' in response_text:
        parsed['verdict'] = 'SCHVÁLENO'
    elif 'UPRAVIT' in response_text:
        parsed['verdict'] = 'UPRAVIT'
    
    # Extract strategy type
    if 'Iron Condor' in response_text:
        parsed['strategy'] = 'IRON_CONDOR'
    elif 'Vertical Put Spread' in response_text:
        parsed['strategy'] = 'VERTICAL_PUT_SPREAD'
    elif 'Vertical Call Spread' in response_text:
        parsed['strategy'] = 'VERTICAL_CALL_SPREAD'
    
    # Note: More sophisticated parsing would extract strikes, prices, etc.
    # For now, keeping it simple - you can enhance this based on actual responses
    
    return parsed
