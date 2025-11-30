# Gemini Trader AI 🤖📈

AI-powered options trading system pro IBKR s integrací Google Gemini a Claude Opus 4.5. Optimalizováno pro Raspberry Pi 5.

## 🎯 Přehled

Gemini Trader AI je komplexní systém pro automatizované obchodování opcí s důrazem na **ochranu kapitálu** a konzistentní příjmy. Systém využívá:

- **Google Gemini** - Fundamentální analýza a market sentiment
- **Claude Opus 4.5** - Pokročilá Greeks analýza a trade recommendations
- **IBKR API** - Real-time data, Greeks, VIX, order execution
- **Integrovaný Risk Management** - VIX regime monitoring, position sizing, Greeks validation

## ✨ Klíčové Funkce

### 🛡️ Risk Management
- **VIX Regime Classification** - Panic (>30), High Vol (20-30), Normal (15-20), Low Vol (<15)
- **Position Sizing** - Max 25% account allocation, max $120 risk per trade
- **Greeks Validation** - Delta, Theta, Vanna stress testing
- **Earnings Blackout** - 48-hour window před earnings

### 🤖 AI Integration
- **Gemini Fundamental Analysis** - JSON output, scoring 1-10, sentiment, macro context
- **Claude Greeks Analysis** - JSON output with "Gemini-Trader 5.1" systémový prompt
- **Greeks Data Sources**: 
  - IBKR API → Delta, Theta, Vega, Gamma (real-time přesná data)
  - AI výpočet → Pouze Vanna (IV sensitivity modeling)
- **Structured Decision Logging** - Audit trail všech AI rozhodnutí

### 📊 Trading Strategies
- **Credit Spreads** - Iron Condors, Vertical Credit Spreads (High VIX)
- **Debit Spreads** - Vertical Debit Spreads (Low VIX)
- **Calendar Spreads** - Time decay plays
- **Auto Exit Management** - 50% TP, 2.5x SL

## 🚀 Instalace

### Požadavky

- **Raspberry Pi 5** (16GB RAM doporučeno)
- **Python 3.11+**
- **IBKR Account** s API přístupem
- **API Keys**: Google Gemini, Anthropic Claude

### 1. Clone projektu

```bash
cd /home/jakub/.gemini/antigravity/scratch/gemini-trader-ai
```

### 2. Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalace dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Konfigurace

Zkopírujte `.env.example` → `.env` a vyplňte své credentials:

```bash
cp .env.example .env
nano .env
```

**Důležité nastavení:**

```bash
# IBKR
IBKR_HOST=127.0.0.1
IBKR_PORT=4002  # 4002=IB Gateway Paper, 4001=IB Gateway Live
IBKR_ACCOUNT=DU123456  # Váš account number

# IBKR Credentials for Docker IB Gateway
IBKR_USERNAME=your_ibkr_username
IBKR_PASSWORD=your_ibkr_password
TRADING_MODE=paper  # paper or live
VNC_PASSWORD=password  # For VNC access

# AI API Keys
GEMINI_API_KEY=your_gemini_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Trading (account balance is fetched from IBKR API)
MAX_RISK_PER_TRADE=120

# Safety
PAPER_TRADING=true  # Začněte s paper trading!
AUTO_EXECUTE=false  # Manual approval doporučeno zpočátku
```

### 5. IBKR Setup (Docker IB Gateway)

**Docker IB Gateway** (Doporučeno - automatizované, spolehlivé):

1. **Ujistěte se, že máte Docker nainstalovaný:**
```bash
sudo apt-get update
sudo apt-get install docker.io docker-compose
sudo usermod -aG docker $USER
# Logout a znovu login pro refresh skupin
```

2. **Nakonfigurujte credentials v `.env`:**
```bash
IBKR_USERNAME=your_ibkr_username
IBKR_PASSWORD=your_ibkr_password
TRADING_MODE=paper  # nebo 'live' pro live trading
```

3. **Spusťte IB Gateway v Dockeru:**
```bash
docker-compose up -d
```

4. **Ověřte, že běží:**
```bash
docker-compose ps
docker-compose logs -f ib-gateway
```

5. **Přístup přes VNC (volitelné):**
- Připojte se k `localhost:5900` s VNC clientem
- Heslo: hodnota z `VNC_PASSWORD` v `.env`
- Můžete vidět GUI IB Gateway a zkontrolovat připojení



## 💻 Použití

### Spuštění systému

```bash
source venv/bin/activate
python main.py
```

### První spuštění

Systém v paper trading módu automaticky:
1. Připojí se k IBKR
2. Načte VIX a určí market regime
3. Provede demo analýzu na SPY
4. Ukáže Gemini fundamental analysis
5. Ukáže Claude Greeks recommendation

### Výstup

```
========================================================== 
Gemini Trader AI - Initialization
==========================================================
Connecting to IBKR...
Successfully connected to IBKR. Account: DU123456
Fetching initial VIX value...
VIX: 18.5 | Regime: NORMAL

==========================================================
CURRENT MARKET STATUS
==========================================================
⚠️ NORMAL VOLATILITY (VIX 18.5) - Selective Credit Spreads
Preferred strategies: iron_condor, vertical_credit_spread
==========================================================
Account Size: $500.00
Max Risk Per Trade: $120.00
Max Allocation: 25%
Paper Trading: True
Auto Execute: False
==========================================================
```

## 📁 Struktura Projektu

```
gemini-trader-ai/
├── main.py                 # Entry point
├── config.py              # Configuration management
├── requirements.txt       # Dependencies
├── docker-compose.yml     # Docker IB Gateway setup
│
├── ibkr/                  # IBKR Integration
│   ├── connection.py      # Connection manager
│   └── data_fetcher.py    # Market data & Greeks
│
├── analysis/              # Market Analysis
│   ├── vix_monitor.py     # VIX regime detector
│   ├── liquidity_checker.py  # Bid-ask validation
│   └── earnings_calendar.py  # Earnings proximity
│
├── ai/                    # AI Integration
│   ├── gemini_client.py   # Gemini fundamental analysis
│   ├── claude_client.py   # Claude Greeks analysis
│   └── prompts.py         # Prompt templates
│
├── risk/                  # Risk Management
│   ├── greeks_validator.py  # Greeks validation
│   └── position_sizer.py    # Position sizing
│
├── strategies/            # Trading Strategies
│   ├── credit_spreads.py  # Credit spread builders
│   ├── debit_spreads.py   # Debit spread builders
│   └── calendar_spreads.py # Calendar spread builders
│
├── orders/                # Order Management
│   ├── exit_manager.py    # Auto TP/SL
│   └── bracket_orders.py  # OCO orders
│
├── data/                  # Data & Logging
│   ├── database.py        # SQLite manager
│   └── logger.py          # Logging setup
│
├── systemd/               # Raspberry Pi deployment
│   └── gemini-trader.service  # Systemd service
│
├── tests/                 # Unit tests
└── logs/                  # Log files (auto-created)
```

## 🔒 Bezpečnost

### Kill Switch

Systém má několik safety mechanismů:

1. **VIX Panic Mode** - VIX >30 → HARD STOP na nové pozice
2. **Earnings Blackout** - 48h window před earnings
3. **Position Size Limits** - Max 25% account, max $120 risk
4. **Greeks Validation** - Automatický reject riskantních pozic
5. **Paper Trading** - Default mód pro testování

### Doporučený Workflow

1. **Week 1-2**: Paper trading, monitoring, tweaking
2. **Week 3-4**: Manual approval každého trade
3. **Week 5+**: Semi-auto s oversight
4. **Never**: Plně autonomní bez supervision na micro account

## 📊 Monitoring

### Logy

Systém vytváří několik log files:

```
logs/
├── gemini_trader_2025-11-29.log  # General log
├── trades_2025-11-29.log         # Trade execution audit
├── errors_2025-11-29.log         # Errors only
└── ai_decisions_2025-11-29.log   # AI recommendations
```

### Database

SQLite database `data/trading.db` obsahuje:
- `trades` - Všechny trades s P&L
- `positions` - Aktivní pozice
- `pnl_history` - Daily P&L tracking
- `ai_decisions` - AI decision audit trail

Query example:

```bash
sqlite3 data/trading.db "SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10;"
```

## 🍓 Raspberry Pi Deployment

### Systemd Service

Pro automatické spuštění na boot:

```bash
# Edit service file with correct paths
nano systemd/gemini-trader.service

# Copy to systemd
sudo cp systemd/gemini-trader.service /etc/systemd/system/

# Enable and start
sudo systemctl enable gemini-trader
sudo systemctl start gemini-trader

# Check status
sudo systemctl status gemini-trader

# View logs
sudo journalctl -u gemini-trader -f
```

### Resource Management

Na Raspberry Pi 5:
- **RAM usage**: ~300-500MB
- **CPU usage**: <25% průměrně
- **Disk**: ~100MB + logs (rotace po 100MB)

## 🧪 Testing

### Unit Tests

```bash
pytest tests/
```

### Integration Test

```bash
# Test IBKR connection
python -c "
import asyncio
from ibkr.connection import get_ibkr_connection

async def test():
    conn = get_ibkr_connection()
    success = await conn.connect()
    print(f'Connection: {\"OK\" if success else \"FAILED\"}')
    await conn.disconnect()

asyncio.run(test())
"
```

## 🐛 Troubleshooting

### IBKR Connection Failed

```bash
# Check TWS/Gateway is running
ps aux | grep -i tws

# Check API settings enabled
# TWS → Configure → API → Enable Socket Clients

# Check firewall
sudo ufw allow 7497/tcp  # Paper TWS
```

### API Keys Invalid

```bash
# Verify .env file
cat .env | grep API_KEY

# Test Gemini
python -c "import google.generativeai as genai; genai.configure(api_key='YOUR_KEY'); print('OK')"

# Test Claude
python -c "from anthropic import Anthropic; c=Anthropic(api_key='YOUR_KEY'); print('OK')"
```

### Memory Issues on RPI

```bash
# Check memory
free -h

# Reduce log rotation
nano .env
# Change: LOG_RETENTION=5  # Keep fewer log files
```

## 📚 Další Vývoj

### Phase 2 (Planned)
- [ ] Order execution module
- [ ] Auto exit manager
- [ ] Strategy builders (Iron Condor, etc.)
- [ ] Performance analytics dashboard

### Phase 3 (Future)
- [ ] Web UI pro monitoring
- [ ] Telegram/Discord alerts
- [ ] Multi-symbol portfolios
- [ ] Advanced ML models
- [ ] Options flow analysis

## ⚠️ Disclaimer

**DŮLEŽITÉ**: Tento software je poskytován "AS IS" bez jakékoli záruky. Obchodování opcí je velmi rizikové a můžete ztratit veškerý investovaný kapitál.

- Vždy začněte s paper trading
- Nikdy neriskujte peníze, které si nemůžete dovolit ztratit
- AI doporučení nejsou finanční poradenství
- Autor neodpovídá za jakékoli ztráty
- Důkladně testujte před live trading

## 📜 License

MIT License - Použijte na vlastní riziko

## 🤝 Podpora

Pro otázky nebo problémy:
- Zkontrolujte `logs/` pro error messages
- Review `ai_decisions` log pro AI reasoning
- Check IBKR connection status
- Verify API keys v `.env`

---

**Vytvořeno s ❤️ pomocí Antigravity a Claude Opus 4**

*"In trading, risk management is not about avoiding risk, it's about understanding it." - Your Gemini-Trader 5.1 System*
