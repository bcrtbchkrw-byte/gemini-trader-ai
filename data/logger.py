"""
Advanced logging setup using loguru.
Provides structured logging with rotation, retention, and different log levels.
"""
import sys
from pathlib import Path
from loguru import logger
from config import get_config


def setup_logger():
    """Configure loguru logger with rotation and structured output"""
    
    config = get_config()
    
    # Remove default logger
    logger.remove()
    
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Console output - colorized for readability
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=config.logging.level,
        colorize=True
    )
    
    # General application log - JSON format
    logger.add(
        logs_dir / "gemini_trader_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=config.logging.level,
        rotation=config.logging.rotation,
        retention=f"{config.logging.retention} days",
        compression="zip",
        serialize=False
    )
    
    # Trade execution log - Critical audit trail
    logger.add(
        logs_dir / "trades_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}",
        level="INFO",
        rotation="00:00",  # Rotate daily at midnight
        retention="90 days",  # Keep trade logs for 90 days
        compression="zip",
        filter=lambda record: "TRADE" in record["extra"]
    )
    
    # Error log - Separate file for errors only
    logger.add(
        logs_dir / "errors_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line}\n{message}\n{exception}\n",
        level="ERROR",
        rotation=config.logging.rotation,
        retention="30 days",
        compression="zip",
        backtrace=True,
        diagnose=True
    )
    
    # AI decisions log - For audit and analysis
    logger.add(
        logs_dir / "ai_decisions_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
        level="INFO",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        filter=lambda record: "AI" in record["extra"]
    )
    
    logger.info("Logger initialized successfully")
    return logger


def get_trade_logger():
    """Get logger configured for trade execution logging"""
    return logger.bind(TRADE=True)


def get_ai_logger():
    """Get logger configured for AI decision logging"""
    return logger.bind(AI=True)


# Initialize logger on module import
setup_logger()
