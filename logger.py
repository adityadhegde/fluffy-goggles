import json
import logging
import os
from config import APP_DIR

_logging_configured = False
_logging_enabled = False

def _configure_logging() -> None:
    global _logging_configured, _logging_enabled
    if _logging_configured:
        return

    try:
        config_path = APP_DIR / "config.json"
        if config_path.exists():
            with open(config_path, "r") as f:
                config = json.load(f)
        else:
            config = {}
        _logging_enabled = config.get("logging", False)
    except Exception:
        _logging_enabled = False

    if _logging_enabled:
        logging.basicConfig(
            filename=str(APP_DIR / "podplayer.log"),
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
