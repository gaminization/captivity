"""
Structured logging for Captivity.

Provides journal-compatible log output with ISO timestamps and levels.
"""

import logging
import sys
from typing import Optional


LOG_FORMAT = "%(asctime)s [captivity] %(levelname)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO", quiet: bool = False) -> logging.Logger:
    """Configure and return the captivity logger.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
        quiet: If True, suppress all output except errors.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger("captivity")

    if logger.handlers:
        return logger

    log_level = getattr(logging, level.upper(), logging.INFO)
    if quiet:
        log_level = logging.ERROR

    logger.setLevel(log_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a child logger for a specific module.

    Args:
        name: Module name for the child logger.

    Returns:
        Logger instance.
    """
    base = logging.getLogger("captivity")
    if name:
        return base.getChild(name)
    return base
