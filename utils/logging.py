import sys
import logging
from typing import Optional, Callable, Any
import functools
from datetime import datetime
from logging.handlers import RotatingFileHandler
import colorlog

def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = "app.log",
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """
    Set up logging configuration with colored console output and file logging.
    
    Args:
        log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file (str): Path to log file
        max_file_size (int): Maximum size of each log file in bytes
        backup_count (int): Number of backup files to keep
    """
    # Create logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Set up encoding for Windows
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    # Color scheme for different log levels
    colors = {
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
    
    # Create formatters
    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s%(reset)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors=colors,
        reset=True,
        style='%'
    )
    
    # Add formatter to console handler
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Set up file logging
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Log the initialization
    logging.info("🚀 Logging system initialized")
    logging.info(f"📊 Log level set to: {log_level}")
    logging.info(f"📝 Logging to file: {log_file}")

def log_execution(logger: logging.Logger = logging.getLogger(__name__)) -> Callable:
    """Decorator to log function execution details."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger.debug(
                f"Executing {func.__name__} with args: {args}, kwargs: {kwargs}"
            )
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Completed {func.__name__} successfully")
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
                raise

        return wrapper
    return decorator

# Initialize logging when module is imported
setup_logging()
