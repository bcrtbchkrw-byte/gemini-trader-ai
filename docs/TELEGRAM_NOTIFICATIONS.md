# Telegram Notifications Setup

## 🎯 Purpose

Get real-time alerts on your phone for:
- 🟢 **Trade opened**
- 🔴 **Trade closed** (with P/L)
- 🚨 **VIX panic mode**
- ⚠️ **VIX backwardation**
- ❌ **Pipeline errors**
- 🔄 **Bot restarts**
- 📊 **Daily summaries**

## 🚀 Setup (5 minutes)

### Step 1: Create Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Choose a name: `Gemini Trader Alerts`
4. Choose username: `your_gemini_trader_bot`
5. Copy the **bot token**:
   ```
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

### Step 2: Get Chat ID

1. Start chat with your new bot (click link from BotFather)
2. Send any message: `Hello`
3. Visit this URL in browser (replace YOUR_TOKEN):
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
4. Look for `"chat":{"id":123456789}`
5. Copy the **chat ID** number

### Step 3: Configure Bot

Add to `.env`:
```bash
# Telegram Notifications
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

### Step 4: Test

```python
from notifications.telegram_notifier import get_telegram_notifier

notifier = get_telegram_notifier()
await notifier.notify_startup()
```

You should receive: "✅ BOT STARTED"

## 📱 Message Examples

### Trade Opened
```
🟢 TRADE OPENED

📊 Symbol: AAPL
📈 Strategy: IRON_CONDOR
💼 Contracts: 2
💰 Credit: $200.00
⚠️ Max Risk: $800.00

Opened at 2024-11-30 14:30:00
```

### Trade Closed
```
🟢 TRADE CLOSED

📊 Symbol: AAPL
📈 Strategy: IRON_CONDOR
💵 P/L: +$100.00
📝 Reason: PROFIT_TARGET

Closed at 2024-11-30 16:45:00
```

### VIX Panic Alert
```
🚨 VIX PANIC MODE

⚠️ VIX: 45.80
📊 Regime: EXTREME

🛑 Trading BLOCKED
New credit positions disabled until VIX < 30

Alert at 2024-11-30 09:35:00
```

### Watchdog Restart
```
🔄 BOT RESTARTED

⚙️ Reason: Log file stale
🔢 Restart #2

Watchdog detected issue and restarted service

Restart at 2024-11-30 12:00:00
```

## 🔧 Integration Points

### 1. Trade Execution
```python
# In order_executor.py
from notifications.telegram_notifier import get_telegram_notifier

async def execute_trade(...):
    # Execute trade
    result = await place_order(...)
    
    # Notify
    telegram = get_telegram_notifier()
    await telegram.notify_trade_opened(
        symbol=symbol,
        strategy=strategy,
        contracts=contracts,
        credit=credit,
        max_risk=max_risk
    )
```

### 2. Exit Manager
```python
# In exit_manager.py
async def close_position(...):
    # Close position
    result = await close_order(...)
    
    # Notify
    telegram = get_telegram_notifier()
    await telegram.notify_trade_closed(
        symbol=symbol,
        strategy=strategy,
        pnl=pnl,
        reason=reason
    )
```

### 3. VIX Monitor
```python
# In vix_monitor.py
def check_regime(self):
    if self.current_vix >= 30:
        # Notify panic
        telegram = get_telegram_notifier()
        await telegram.notify_vix_panic(
            vix=self.current_vix,
            regime="PANIC"
        )
    
    if self.vix_ratio > 1.0:
        # Notify backwardation
        await telegram.notify_vix_backwardation(
            vix=self.current_vix,
            vix3m=self.current_vix3m,
            ratio=self.vix_ratio
        )
```

### 4. Watchdog
```python
# In watchdog.py
def restart_service(self):
    # Restart
    subprocess.run(['systemctl', 'restart', 'gemini-trader'])
    
    # Notify
    telegram = get_telegram_notifier()
    await telegram.notify_watchdog_restart(
        reason="Health check failed",
        restart_count=self.restart_count
    )
```

### 5. Main Startup
```python
# In main.py
async def initialize(self):
    # ... initialization ...
    
    # Notify startup
    telegram = get_telegram_notifier()
    await telegram.notify_startup()
```

## 📊 Daily Summary

Schedule daily summary:
```python
# In scheduler or cron
async def send_daily_summary():
    # Get stats
    trades = len(today_trades)
    pnl = sum(t.pnl for t in today_trades)
    open_pos = len(open_positions)
    
    # Send summary
    telegram = get_telegram_notifier()
    await telegram.notify_daily_summary(
        trades=trades,
        pnl=pnl,
        open_positions=open_pos
    )

# Run at 4 PM daily
```

## ⚙️ Configuration

### Notification Levels

```python
# Critical (loud)
await telegram.notify_vix_panic(...)  # Sound + vibrate

# Important (normal)
await telegram.notify_trade_opened(...)  # Sound

# Info (silent)
await telegram.notify_daily_summary(..., disable_notification=True)
```

### Custom Messages

```python
telegram = get_telegram_notifier()

# Simple message
await telegram.send_message("Custom alert!")

# Markdown formatting
await telegram.send_message("""
*Bold text*
_Italic text_
`Code text`
[Link](https://example.com)
""")
```

## 🚨 Troubleshooting

### Not Receiving Messages

1. **Check bot token:**
   ```python
   import os
   print(os.getenv('TELEGRAM_BOT_TOKEN'))  # Should not be None
   ```

2. **Check chat ID:**
   ```python
   print(os.getenv('TELEGRAM_CHAT_ID'))  # Should be number
   ```

3. **Test manually:**
   ```bash
   curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
        -d "chat_id=<CHAT_ID>&text=Test"
   ```

### Bot Not Responding

1. Make sure you sent a message to bot first
2. Bot must be started (click "Start" button)
3. Check bot isn't blocked

### Rate Limits

Telegram limits:
- 30 messages/second per bot
- 20 messages/minute per chat

Our usage: ~10-20 messages/day (well within limits)

## ✅ Best Practices

1. **Don't spam:** Only critical events
2. **Use silent:** For informational messages
3. **Test first:** Before production
4. **Monitor:** Check logs for send failures
5. **Backup:** Keep email/SMS as backup

---

**Status:** Production-ready ✅  
**Setup time:** 5 minutes  
**Cost:** FREE (Telegram API) 🎯
