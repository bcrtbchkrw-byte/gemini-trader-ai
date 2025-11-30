"""
Telegram Notifier - Critical Event Alerts
Sends Telegram messages for important trading events.
"""
from typing import Optional
from loguru import logger
import os
import asyncio


class TelegramNotifier:
    """Send Telegram notifications for critical events"""
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            logger.warning(
                "Telegram notifications disabled - "
                "set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"
            )
        else:
            logger.info("Telegram notifications enabled")
    
    async def send_message(
        self,
        message: str,
        parse_mode: str = 'Markdown',
        disable_notification: bool = False
    ) -> bool:
        """
        Send Telegram message
        
        Args:
            message: Message text (supports Markdown)
            parse_mode: 'Markdown' or 'HTML'
            disable_notification: Silent notification
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            logger.debug(f"Telegram disabled, would send: {message[:100]}")
            return False
        
        try:
            import aiohttp
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_notification': disable_notification
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        logger.debug("Telegram message sent successfully")
                        return True
                    else:
                        logger.error(f"Telegram API error: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False
    
    async def notify_trade_opened(
        self,
        symbol: str,
        strategy: str,
        contracts: int,
        credit: float,
        max_risk: float
    ):
        """Notify when trade is opened"""
        message = f"""
🟢 *TRADE OPENED*

📊 Symbol: `{symbol}`
📈 Strategy: `{strategy}`
💼 Contracts: `{contracts}`
💰 Credit: `${credit:.2f}`
⚠️ Max Risk: `${max_risk:.2f}`

_Opened at {self._timestamp()}_
"""
        await self.send_message(message)
    
    async def notify_trade_closed(
        self,
        symbol: str,
        strategy: str,
        pnl: float,
        reason: str
    ):
        """Notify when trade is closed"""
        emoji = "🟢" if pnl > 0 else "🔴"
        
        message = f"""
{emoji} *TRADE CLOSED*

📊 Symbol: `{symbol}`
📈 Strategy: `{strategy}`
💵 P/L: `${pnl:+.2f}`
📝 Reason: `{reason}`

_Closed at {self._timestamp()}_
"""
        await self.send_message(message)
    
    async def notify_vix_panic(self, vix: float, regime: str):
        """Notify when VIX enters PANIC mode"""
        message = f"""
🚨 *VIX PANIC MODE*

⚠️ VIX: `{vix:.2f}`
📊 Regime: `{regime}`

🛑 *Trading BLOCKED*
New credit positions disabled until VIX < 30

_Alert at {self._timestamp()}_
"""
        await self.send_message(message, disable_notification=False)  # Loud alert!
    
    async def notify_vix_backwardation(
        self,
        vix: float,
        vix3m: float,
        ratio: float
    ):
        """Notify when VIX term structure shows backwardation"""
        message = f"""
⚠️ *VIX BACKWARDATION DETECTED*

📊 VIX: `{vix:.2f}`
📈 VIX3M: `{vix3m:.2f}`
📉 Ratio: `{ratio:.3f}` (>{1.0})

🚫 *SHORT VEGA DISABLED*
Market in stress - avoid selling premium

_Alert at {self._timestamp()}_
"""
        await self.send_message(message)
    
    async def notify_pipeline_error(self, error: str, phase: str):
        """Notify when pipeline has critical error"""
        message = f"""
❌ *PIPELINE ERROR*

🔧 Phase: `{phase}`
⚠️ Error: `{error[:200]}`

System continuing with caution

_Error at {self._timestamp()}_
"""
        await self.send_message(message)
    
    async def notify_position_reconciliation(
        self,
        closed_externally: int,
        symbols: list
    ):
        """Notify when positions were closed externally"""
        if closed_externally == 0:
            return  # No alert needed
        
        symbols_str = ", ".join(f"`{s}`" for s in symbols[:5])
        
        message = f"""
🔄 *POSITION RECONCILIATION*

⚠️ Found `{closed_externally}` positions closed externally:
{symbols_str}

Database updated automatically

_Detected at {self._timestamp()}_
"""
        await self.send_message(message)
    
    async def notify_watchdog_restart(self, reason: str, restart_count: int):
        """Notify when watchdog restarts bot"""
        message = f"""
🔄 *BOT RESTARTED*

⚙️ Reason: `{reason}`
🔢 Restart #{restart_count}

Watchdog detected issue and restarted service

_Restart at {self._timestamp()}_
"""
        await self.send_message(message)
    
    async def notify_daily_summary(
        self,
        trades: int,
        pnl: float,
        open_positions: int
    ):
        """Send daily trading summary"""
        emoji = "📈" if pnl >= 0 else "📉"
        
        message = f"""
{emoji} *DAILY SUMMARY*

📊 Trades: `{trades}`
💵 Total P/L: `${pnl:+.2f}`
📂 Open Positions: `{open_positions}`

_Summary for {self._date()}_
"""
        await self.send_message(message, disable_notification=True)  # Silent
    
    async def notify_startup(self):
        """Notify when bot starts"""
        message = f"""
✅ *BOT STARTED*

System initialized successfully
Ready for trading

_Started at {self._timestamp()}_
"""
        await self.send_message(message, disable_notification=True)
    
    async def notify_shutdown(self, reason: str = "Manual"):
        """Notify when bot stops"""
        message = f"""
🛑 *BOT STOPPED*

Reason: `{reason}`

_Stopped at {self._timestamp()}_
"""
        await self.send_message(message, disable_notification=True)
    
    def _timestamp(self) -> str:
        """Get formatted timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _date(self) -> str:
        """Get formatted date"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")


# Singleton
_telegram_notifier: Optional[TelegramNotifier] = None


def get_telegram_notifier() -> TelegramNotifier:
    """Get or create singleton Telegram notifier"""
    global _telegram_notifier
    if _telegram_notifier is None:
        _telegram_notifier = TelegramNotifier()
    return _telegram_notifier


# Convenience async functions
async def telegram_notify(message: str) -> bool:
    """Quick notification helper"""
    notifier = get_telegram_notifier()
    return await notifier.send_message(message)
