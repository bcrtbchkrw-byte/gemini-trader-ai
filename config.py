"""
Centralized configuration management for Gemini Trader AI.
Loads settings from environment variables with sensible defaults.
"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class IBKRConfig:
    """IBKR API connection configuration"""
    host: str
    port: int
    client_id: int
    account: str
    
    @classmethod
    def from_env(cls) -> 'IBKRConfig':
        return cls(
            host=os.getenv('IBKR_HOST', '127.0.0.1'),
            port=int(os.getenv('IBKR_PORT', '7497')),
            client_id=int(os.getenv('IBKR_CLIENT_ID', '1')),
            account=os.getenv('IBKR_ACCOUNT', 'DU123456')
        )


@dataclass
class AIConfig:
    """AI API configuration"""
    gemini_api_key: Optional[str]
    anthropic_api_key: Optional[str]
    
    @classmethod
    def from_env(cls) -> 'AIConfig':
        gemini_key = os.getenv('GEMINI_API_KEY')
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        
        if not gemini_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        if not anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
            
        return cls(
            gemini_api_key=gemini_key,
            anthropic_api_key=anthropic_key
        )


@dataclass
class TradingParams:
    """Trading risk and position sizing parameters"""
    account_size: Optional[float]  # Fetched from IBKR API at runtime
    max_risk_per_trade: float
    max_allocation_percent: float
    
    @classmethod
    def from_env(cls) -> 'TradingParams':
        return cls(
            account_size=None,  # Will be fetched from IBKR API
            max_risk_per_trade=float(os.getenv('MAX_RISK_PER_TRADE', '120')),
            max_allocation_percent=float(os.getenv('MAX_ALLOCATION_PERCENT', '25'))
        )
    
    @property
    def max_position_size(self) -> float:
        """Maximum position size based on allocation percentage"""
        if self.account_size is None:
            raise ValueError("Account size not yet fetched from IBKR API")
        return self.account_size * (self.max_allocation_percent / 100)
    
    def update_account_size(self, size: float):
        """Update account size from IBKR API"""
        self.account_size = size


@dataclass
class VIXRegimes:
    """VIX regime thresholds"""
    panic_threshold: float
    high_threshold: float
    normal_threshold: float
    
    @classmethod
    def from_env(cls) -> 'VIXRegimes':
        return cls(
            panic_threshold=float(os.getenv('VIX_PANIC_THRESHOLD', '30')),
            high_threshold=float(os.getenv('VIX_HIGH_THRESHOLD', '20')),
            normal_threshold=float(os.getenv('VIX_NORMAL_THRESHOLD', '15'))
        )
    
    def get_regime(self, vix_value: float) -> str:
        """Determine market regime based on VIX value"""
        if vix_value >= self.panic_threshold:
            return "PANIC"
        elif vix_value >= self.high_threshold:
            return "HIGH_VOL"
        elif vix_value >= self.normal_threshold:
            return "NORMAL"
        else:
            return "LOW_VOL"


@dataclass
class GreeksThresholds:
    """Greeks validation thresholds"""
    # Credit Spreads
    credit_spread_min_delta: float
    credit_spread_max_delta: float
    
    # Debit Spreads
    debit_spread_min_delta: float
    debit_spread_max_delta: float
    
    # Theta
    min_theta_daily: float
    
    # Vanna
    max_vanna_delta_expansion: float
    
    @classmethod
    def from_env(cls) -> 'GreeksThresholds':
        return cls(
            credit_spread_min_delta=float(os.getenv('CREDIT_SPREAD_MIN_DELTA', '0.15')),
            credit_spread_max_delta=float(os.getenv('CREDIT_SPREAD_MAX_DELTA', '0.25')),
            debit_spread_min_delta=float(os.getenv('DEBIT_SPREAD_MIN_DELTA', '0.60')),
            debit_spread_max_delta=float(os.getenv('DEBIT_SPREAD_MAX_DELTA', '0.75')),
            min_theta_daily=float(os.getenv('MIN_THETA_DAILY', '1.00')),
            max_vanna_delta_expansion=float(os.getenv('MAX_VANNA_DELTA_EXPANSION', '0.15'))
        )


@dataclass
class LiquidityThresholds:
    """Liquidity validation thresholds"""
    max_bid_ask_spread: float
    min_volume_oi_ratio: float
    max_vega: float
    
    @classmethod
    def from_env(cls) -> 'LiquidityThresholds':
        return cls(
            max_bid_ask_spread=float(os.getenv('MAX_BID_ASK_SPREAD', '0.05')),
            min_volume_oi_ratio=float(os.getenv('MIN_VOLUME_OI_RATIO', '10')),
            max_vega=float(os.getenv('MAX_VEGA', '0.50'))
        )


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker safety thresholds"""
    daily_max_loss_pct: float  # Max daily loss % before halting
    consecutive_loss_limit: int  # Number of consecutive losses before halt
    halt_duration_hours: int  # Auto-reset duration
    
    @classmethod
    def from_env(cls) -> 'CircuitBreakerConfig':
        return cls(
            daily_max_loss_pct=float(os.getenv('DAILY_MAX_LOSS_PCT', '5.0')),
            consecutive_loss_limit=int(os.getenv('CONSECUTIVE_LOSS_LIMIT', '3')),
            halt_duration_hours=int(os.getenv('HALT_DURATION_HOURS', '24'))
        )


@dataclass
class ExitParams:
    """Exit strategy parameters"""
    take_profit_percent: float
    stop_loss_multiplier: float
    
    @classmethod
    def from_env(cls) -> 'ExitParams':
        return cls(
            take_profit_percent=float(os.getenv('TAKE_PROFIT_PERCENT', '50')),
            stop_loss_multiplier=float(os.getenv('STOP_LOSS_MULTIPLIER', '2.5'))
        )


@dataclass
class OrderTTLConfig:
    """Order time-to-live configuration"""
    ttl_minutes: int
    cleanup_interval_minutes: int
    
    @classmethod
    def from_env(cls) -> 'OrderTTLConfig':
        return cls(
            ttl_minutes=int(os.getenv('ORDER_TTL_MINUTES', '30')),
            cleanup_interval_minutes=int(os.getenv('ORDER_CLEANUP_INTERVAL', '5'))
        )


@dataclass
class SafetyParams:
    """Safety and risk control parameters"""
    earnings_blackout_hours: int
    paper_trading: bool
    auto_execute: bool
    
    @classmethod
    def from_env(cls) -> 'SafetyParams':
        return cls(
            earnings_blackout_hours=int(os.getenv('EARNINGS_BLACKOUT_HOURS', '48')),
            paper_trading=os.getenv('PAPER_TRADING', 'true').lower() == 'true',
            auto_execute=os.getenv('AUTO_EXECUTE', 'false').lower() == 'true'
        )


@dataclass
class LogConfig:
    """Logging configuration"""
    level: str
    rotation: str
    retention: int
    
    @classmethod
    def from_env(cls) -> 'LogConfig':
        return cls(
            level=os.getenv('LOG_LEVEL', 'INFO'),
            rotation=os.getenv('LOG_ROTATION', '100 MB'),
            retention=int(os.getenv('LOG_RETENTION', '10'))
        )


@dataclass
class Config:
    """Master configuration container"""
    ibkr: IBKRConfig
    ai: AIConfig
    trading: TradingParams
    vix: VIXRegimes
    greeks: GreeksThresholds
    liquidity: LiquidityThresholds
    circuit_breaker: CircuitBreakerConfig
    order_ttl: OrderTTLConfig
    exit_params: ExitParams
    safety: SafetyParams
    logging: LogConfig # Added this field based on the original __init__
    
    def __init__(self):
        self.ibkr = IBKRConfig.from_env()
        self.ai = AIConfig.from_env()
        self.trading = TradingParams.from_env()
        self.vix = VIXRegimes.from_env()
        self.greeks = GreeksThresholds.from_env()
        self.liquidity = LiquidityThresholds.from_env()
        self.circuit_breaker = CircuitBreakerConfig.from_env()
        self.order_ttl = OrderTTLConfig.from_env()
        self.exit_params = ExitParams.from_env()
        self.safety = SafetyParams.from_env()
        self.logging = LogConfig.from_env()
    
    def validate(self) -> bool:
        """Validate configuration integrity"""
        errors = []
        
        # Validate trading parameters
        # Skip account_size validation if not yet fetched from IBKR
        if self.trading.account_size is not None:
            if self.trading.max_risk_per_trade > self.trading.account_size:
                errors.append("Max risk per trade cannot exceed account size")
        
        if self.trading.max_allocation_percent > 100:
            errors.append("Max allocation percent cannot exceed 100%")
        
        # Validate VIX thresholds
        if not (self.vix_regimes.normal_threshold < self.vix_regimes.high_threshold < self.vix_regimes.panic_threshold):
            errors.append("VIX thresholds must be in ascending order: normal < high < panic")
        
        # Validate Greeks thresholds
        if self.greeks.credit_spread_min_delta >= self.greeks.credit_spread_max_delta:
            errors.append("Credit spread min delta must be less than max delta")
        
        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
        
        return True


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create global configuration instance"""
    global _config
    if _config is None:
        _config = Config()
        _config.validate()
    return _config


def reload_config() -> Config:
    """Force reload configuration from environment"""
    global _config
    load_dotenv(override=True)
    _config = Config()
    _config.validate()
    return _config
