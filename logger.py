import json
import logging
import os

_logging_configured = False
_logging_enabled = False

def _configure_logging() -> None:
    global _logging_configured, _logging_enabled
    if _logging_configured:
        return

    try:
        with open("config.json", "r") as f:
            config = json.load(f)
        _logging_enabled = config.get("logging", False)
    except Exception:
        _logging_enabled = False

    if _logging_enabled:
        logging.basicConfig(
            filename="podplayer.log",
            level=logging.DEBUG,
            format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s"
        )
    _logging_configured = True

def get_logger(name: str) -> logging.Logger:
    """Get a logger configured for the application."""
    _configure_logging()
    logger = logging.getLogger(name)
    
    # If logging is disabled, ensure we don't output anything by using NullHandler
    if not _logging_enabled and not logger.hasHandlers():
        logger.addHandler(logging.NullHandler())
        logger.setLevel(logging.CRITICAL + 1)
        
    return logger
