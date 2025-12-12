"""
Logging Configuration for Shift Planner
Provides structured logging with JSON formatting for production
"""

import logging
import sys
import os
from datetime import datetime
from typing import Optional
import json

# Configuration from environment
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
LOG_FORMAT = os.getenv('LOG_FORMAT', 'json')  # 'json' or 'text'
APP_ENV = os.getenv('APP_ENV', 'development')

class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    Outputs logs in JSON format for better parsing by log aggregators.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        
        # Add environment
        log_data['environment'] = APP_ENV
        
        return json.dumps(log_data)

class ColoredFormatter(logging.Formatter):
    """
    Colored formatter for console output in development.
    """
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        if APP_ENV == 'production':
            # No colors in production
            return super().format(record)
        
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        record.levelname = f"{color}{record.levelname}{reset}"
        record.name = f"{color}{record.name}{reset}"
        
        return super().format(record)

def setup_logging(
    level: Optional[str] = None,
    format_type: Optional[str] = None,
    log_file: Optional[str] = None
):
    """
    Configure logging for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: 'json' for structured logging, 'text' for human-readable
        log_file: Optional file path for file logging
    """
    level = level or LOG_LEVEL
    format_type = format_type or LOG_FORMAT
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    if format_type == 'json':
        console_handler.setFormatter(JSONFormatter())
    else:
        text_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        console_handler.setFormatter(ColoredFormatter(text_format))
    
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(JSONFormatter())  # Always use JSON for files
        root_logger.addHandler(file_handler)
    
    # Set level for third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    
    # Log startup
    root_logger.info(f"Logging configured - Level: {level}, Format: {format_type}, Environment: {APP_ENV}")

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)

# Request ID tracking for correlation
class RequestIDFilter(logging.Filter):
    """
    Filter that adds request ID to log records.
    Useful for tracing requests across services.
    """
    
    def __init__(self, request_id: Optional[str] = None):
        super().__init__()
        self.request_id = request_id
    
    def filter(self, record: logging.LogRecord) -> bool:
        if self.request_id:
            record.request_id = self.request_id
        return True

# Convenience functions
def log_error(logger: logging.Logger, message: str, exception: Optional[Exception] = None, **kwargs):
    """
    Log an error with optional exception and extra context.
    """
    extra = kwargs if kwargs else {}
    if exception:
        logger.error(message, exc_info=exception, extra=extra)
    else:
        logger.error(message, extra=extra)

def log_performance(logger: logging.Logger, operation: str, duration_ms: float, **kwargs):
    """
    Log performance metrics.
    """
    logger.info(
        f"Performance: {operation} completed in {duration_ms:.2f}ms",
        extra={'operation': operation, 'duration_ms': duration_ms, **kwargs}
    )

# Initialize logging on import
if __name__ != '__main__':
    setup_logging()
