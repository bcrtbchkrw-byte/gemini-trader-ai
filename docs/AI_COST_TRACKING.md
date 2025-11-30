# AI Cost Tracking & Limits

## Overview
Both Gemini and Claude clients now track token usage and enforce daily cost limits to prevent runaway API expenses.

## Configuration
Set daily limits via environment variables or defaults:

```bash
# .env file
GEMINI_DAILY_LIMIT=5.0  # $5/day (default)
CLAUDE_DAILY_LIMIT=5.0  # $5/day (default)
```

## Pricing

### Gemini 1.5 Flash
- **Input:** $0.075 per 1M tokens
- **Output:** $0.30 per 1M tokens
- **Speed:** Very fast
- **Use case:** Batch screening (Phase 2)

### Claude 3.5 Sonnet
- **Input:** $3.00 per 1M tokens (~40x more than Gemini)
- **Output:** $15.00 per 1M tokens (~50x more than Gemini)
- **Speed:** Slower
- **Use case:** Deep strategy analysis (Phase 3)

## Cost Tracking

### Features
- ✅ Tracks input + output tokens per request
- ✅ Calculates cost in real-time
- ✅ Resets daily at midnight
- ✅ Logs cumulative daily spend
- ✅ Enters "Silent Mode" when limit reached

### Silent Mode
When daily limit is reached:
1. `silent_mode = True`
2. All new API calls return early with error
3. Robot continues with existing data
4. Resets at midnight

### Example Log Output
```
💰 Gemini usage: 1,234 in + 456 out = $0.0002
   Daily total: $0.45 / $5.00

💰 Claude usage: 2,100 in + 800 out = $0.0183
   Daily total: $2.35 / $5.00

🚨 CLAUDE DAILY LIMIT REACHED!
   Spent: $5.02
   Limit: $5.00
   → SILENT MODE ACTIVATED
```

## Implementation

### GeminiClient
```python
gemini = GeminiClient(daily_limit_usd=5.0)

# Check before request
if gemini.can_make_request():
    result = await gemini.batch_analyze_with_news(...)
else:
    # Skip - limit reached
    pass
```

### ClaudeClient
```python
claude = ClaudeClient(daily_limit_usd=5.0)

# Automatic check in analyze_strategy
result = await claude.analyze_strategy(...)

if result.get('silent_mode'):
    # Limit reached - result has approved=False
    pass
```

## Cost Estimation

### Typical Daily Usage
Assuming 20 screening runs per day:

**Phase 2 (Gemini):**
- 10 stocks × 20 runs = 200 analyses
- ~500 tokens input + 200 output per stock
- Total: ~100k in + 40k out
- Cost: **~$0.02/day** ✅ Very cheap!

**Phase 3 (Claude):**
- 3 stocks × 20 runs = 60 deep analyses
- ~2k tokens input + 1k output per stock
- Total: ~120k in + 60k out  
- Cost: **~$1.26/day** ⚠️ More expensive

**Combined:** ~$1.28/day (well under $5 limit)

### Peak Usage
If robot runs every hour (24x):
- Gemini: ~$0.05/day
- Claude: ~$3.00/day
- **Total: ~$3.05/day** (still under $5)

## Monitoring

### Check Current Usage
```python
# Gemini
logger.info(f"Gemini today: ${gemini.daily_cost:.4f} / ${gemini.daily_limit_usd:.2f}")

# Claude
logger.info(f"Claude today: ${claude.daily_cost:.4f} / ${claude.daily_limit_usd:.2f}")
```

### Daily Reset
Both clients auto-reset at midnight:
- Counters → 0
- Cost → $0
- Silent mode → OFF

## Best Practices

1. **Set Conservative Limits:** Start with $5/day, adjust based on usage
2. **Monitor Logs:** Watch for cost spikes
3. **Batch Requests:** Use Gemini's batch analysis (cheaper)
4. **Selective Claude:** Only use Phase 3 for high-confidence candidates
5. **Cache Results:** Don't re-analyze same stock multiple times

## Safety Net
Even with limits, always:
- Review API bills monthly
- Set billing alerts in Google Cloud / Anthropic
- Use separate API keys for dev vs prod
