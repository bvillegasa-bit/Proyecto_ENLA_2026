"""Structured JSON logging setup for ENLA pipeline."""

import logging
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_dict = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_dict['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_dict)


def setup_logging(log_level: str = 'INFO', log_file: str = 'logs/application.log',
                  use_json: bool = True) -> logging.Logger:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        use_json: Whether to use JSON formatter (True) or text formatter (False)
    
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger('enla')
    logger.setLevel(getattr(logging, log_level))
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Console Handler (INFO level)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File Handler (DEBUG level) with JSON formatting
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    
    if use_json:
        file_formatter = JSONFormatter()
    else:
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module."""
    return logging.getLogger(f'enla.{name}')
