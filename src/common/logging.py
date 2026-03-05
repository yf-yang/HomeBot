"""简单日志封装，可替换为更复杂的日志系统（如 structlog）。"""
import logging

def get_logger(name: str) -> logging.Logger:
    import os
    # determine log level from config if available
    level = os.environ.get("HOMEBOT_LOG_LEVEL")
    if level is None:
        try:
            from common.config import Config
            level = Config().logging.level
        except Exception:
            level = "DEBUG"
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        try:
            logger.setLevel(getattr(logging, level.upper()))
        except Exception:
            logger.setLevel(logging.DEBUG)
    return logger
