import json
import logging
from datetime import datetime, timezone
from captivity.utils.logging import setup_logging, JSONFormatter

def test_json_formatter_standard_fields():
    formatter = JSONFormatter()
    record = logging.LogRecord("test_logger", logging.INFO, "test.py", 10, "Hello %s", ("World",), None)
    record.created = 1600000000.0
    
    formatted = formatter.format(record)
    data = json.loads(formatted)
    
    assert data["logger"] == "test_logger"
    assert data["level"] == "INFO"
    assert data["message"] == "Hello World"
    assert data["timestamp"] == datetime.fromtimestamp(1600000000.0, tz=timezone.utc).isoformat()
    assert "exception" not in data

def test_json_formatter_extra_fields():
    formatter = JSONFormatter()
    record = logging.LogRecord("test_logger", logging.WARNING, "test.py", 10, "User login", (), None)
    record.__dict__["user_id"] = 123
    record.__dict__["action"] = "login_attempt"
    
    formatted = formatter.format(record)
    data = json.loads(formatted)
    
    assert data["logger"] == "test_logger"
    assert data["message"] == "User login"
    assert data["user_id"] == 123
    assert data["action"] == "login_attempt"

def test_json_formatter_with_exception():
    formatter = JSONFormatter()
    try:
        1 / 0
    except ZeroDivisionError as e:
        import sys
        exc_info = sys.exc_info()
        
    record = logging.LogRecord("test_logger", logging.ERROR, "test.py", 10, "Math error", (), exc_info)
    
    formatted = formatter.format(record)
    data = json.loads(formatted)
    
    assert data["level"] == "ERROR"
    assert "ZeroDivisionError: division by zero" in data["exception"]

def test_setup_logging_text_format():
    logger = setup_logging(level="DEBUG", log_format="text")
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) > 0
    
    handler = logger.handlers[0]
    assert not isinstance(handler.formatter, JSONFormatter)
    
def test_setup_logging_json_format():
    logger = setup_logging(level="INFO", log_format="json")
    assert logger.level == logging.INFO
    assert len(logger.handlers) > 0
    
    handler = logger.handlers[0]
    assert isinstance(handler.formatter, JSONFormatter)
