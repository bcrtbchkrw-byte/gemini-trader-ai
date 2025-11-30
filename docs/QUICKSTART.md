# Gemini Trader AI - Quick Start Guide

## 🎯 Spouštění

### 1. Jednorázové spuštění (manuální)
```bash
python main.py
```
- Spustí 3-phase pipeline
- Jednorázová analýza
- Bez automatizace

### 2. Auto-scheduler (doporučeno)
```bash
# V .env nastav:
AUTO_PREMARKET_SCAN=true

# Pak spusť:
python main.py
```
- **8:45 AM**: Premarket scan (najde movers)
- **9:00 AM**: AI analýza top picks
- Výsledky cached celý den

### 3. Continuous Scheduler (daemon)
```bash
./run_scheduler.sh

# Nebo přímo:
python main.py --scheduler
```
- Běží celý den
- 8:45 AM - premarket scan
- 9:00 AM - AI analýza
- Pak monitoruje cache

---

## ⚙️ Konfigurace (.env)

```bash
# Scheduler
AUTO_PREMARKET_SCAN=true
PREMARKET_SCAN_TIME=08:45
ANALYSIS_TIME=09:00
PREMARKET_MAX_CANDIDATES=15
```

---

## 📊 Workflow Comparison

### Bez Scheduleru (velké náklady)
```
10:00 → AI call
10:10 → AI call  
10:20 → AI call
...
16:00 → AI call

= 48 AI calls/den = ~$1.50
```

### Se Schedulerem (úspora 97%)
```
8:45 → Premarket scan (FREE)
9:00 → 1x AI call na top picks
Rest of day → používá cache

= 1 AI call/den = ~$0.05
```

---

## 🎯 Příklady použití

### Ranní workflow
```bash
# 1. Ráno spusť scheduler
./run_scheduler.sh

# 2. V 8:45 - automatický premarket scan
# 3. V 9:00 - AI analýza
# 4. Výsledky v data/premarket_candidates.json
```

### API přístup k výsledkům
```python
from automation.premarket_scanner import get_premarket_scanner

scanner = get_premarket_scanner()

# Get cached candidates (celý den)
candidates = scanner.get_cached_candidates()

# Get top picks
top_5 = scanner.get_top_picks(5)
```

---

## 🔍 Co hledá Premarket Scanner

**Metriky:**
- Gap > 2% (50 bodů) nebo > 4% (30 bodů)
- Volume ratio > 2x (30 bodů)
- High volatility (20 bodů)

**Výstup:**
```json
{
  "symbol": "AAPL",
  "score": 80,
  "gap_pct": 3.5,
  "volume_ratio": 2.8,
  "reasons": ["GAP_3.5%", "HIGH_VOLUME", "VOLATILE"]
}
```

---

## 💰 Úspora nákladů

| Metoda | AI Calls | Náklady/den |
|--------|----------|-------------|
| Bez scheduleru | 48 | ~$1.50 |
| Se schedulerem | 1 | ~$0.05 |
| **Úspora** | **97%** | **$1.45** |

---

## 🚀 Production Deployment

### Na Raspberry Pi
```bash
# 1. Clone repo
git clone ...
cd gemini-trader-ai

# 2. Setup
./setup.sh

# 3. Configure
cp .env.example .env
nano .env

# 4. Run as service
sudo systemctl enable gemini-trader
sudo systemctl start gemini-trader
```

### Docker
```bash
docker-compose up -d
```

---

**Tip:** Pro maximální úsporu používej scheduler + cache celý den!
