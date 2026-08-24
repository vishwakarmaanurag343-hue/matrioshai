import logging
import sys
from pathlib import Path
from app.core.config import settings

def setup_logging() -> logging.Logger:
    logger = logging.getLogger("matrioshai")
    logger.setLevel(getattr(logging, settings.APP_LOG_LEVEL.upper(), logging.INFO))
    
    if not logger.handlers:
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
        )
        
        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # File handler
        log_file = Path(settings.LOGS_PATH) / "app.log"
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
    return logger

logger = setup_logging()
