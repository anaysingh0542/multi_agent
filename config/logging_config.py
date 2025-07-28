import logging
import sys
from typing import Optional
from .config import get_config


def setup_logging(level: Optional[str] = None, format_str: Optional[str] = None) -> None:
    """Setup logging configuration with optional overrides."""
    try:
        config = get_config()
        log_level = level or config.log_level
        log_format = format_str or config.log_format
        
        # Convert string level to logging constant
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        
        logging.basicConfig(
            level=numeric_level,
            format=log_format,
            handlers=[
                logging.StreamHandler(sys.stdout)
            ],
            force=True  # Override any existing configuration
        )
        
        # Set third-party library log levels to reduce noise
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        
    except Exception as e:
        # Fallback to basic configuration if config loading fails
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] [%(name)s] - %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        logging.error(f"Failed to setup logging from config: {e}")