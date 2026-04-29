"""
Structured logging for Captivity.

Provides journal-compatible log output with ISO timestamps and levels.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

LOG_FORMAT = "%(asctime)s [captivity] %(levelname)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class JSONFormatter(logging.Formatter):
    """Format logs as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include any extra kwargs passed to the logger
        # Standard LogRecord attributes to ignore
        standard_attrs = {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "id",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "taskName",
        }

        for key, value in record.__dict__.items():
            if key not in standard_attrs:
                log_obj[key] = value

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logging(
    level: str = "INFO", quiet: bool = False, log_format: str = "text"
) -> logging.Logger:
    """Configure and return the captivity logger.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
        quiet: If True, suppress all output except errors.
        log_format: Format of the logs ("text" or "json").

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger("captivity")

    if logger.handlers:
        # Update existing handlers if setup_logging is called again
        for handler in logger.handlers:
            logger.removeHandler(handler)

    log_level = getattr(logging, level.upper(), logging.INFO)
    if quiet:
        log_level = logging.ERROR

    logger.setLevel(log_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if log_format.lower() == "json":
        formatter = JSONFormatter()
    else:
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
