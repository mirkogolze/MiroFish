"""
Log-Konfigurationsmodul
Bietet einheitliche Log-Verwaltung und Ausgabe sowohl auf der Konsole als auch in Dateien.
"""

import os
import sys
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler


def _ensure_utf8_stdout():
    """
    Stellen Sie sicher, dass stdout/stderr UTF-8 kodiert ist
    Lösen Sie das Problem mit dem unleserlichen chinesischen Text auf Windows-Konsolen.
    """
    if sys.platform == 'win32':
        # Konfiguriere die Standardausgabe unter Windows neu auf UTF-8.
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# Log-Verzeichnis
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')


def setup_logger(name: str = 'mirofish', level: int = logging.DEBUG) -> logging.Logger:
    """
    Konfigurieren Sie den Logger
    
    Args:
        name: Logger-Name
        level: Log-Level
        
    Returns:
        Der konfigurierte Logger.
    """
    # Stellen Sie sicher, dass der Log-Verzeichnis existiert.
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # Erstelle Logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Verhindert, dass die Logs zum Stammlogger hochgestuft werden, um doppelte Ausgaben zu vermeiden.
    logger.propagate = False
    
    # Falls bereits ein Processor vorhanden ist, wird nicht wiederholt hinzugefügt.
    if logger.handlers:
        return logger
    
    # Log-Format
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 1. Dateiverarbeiter - detaillierte Logdateien (nach Datum benannt, mit Rotation)
    log_filename = datetime.now().strftime('%Y-%m-%d') + '.log'
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, log_filename),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    # 2. Konsolen-Handler - Kurze Log-Einträge.
    # Level: DEBUG bei GRAPHITI_LOG_LEVEL=DEBUG (oder LOG_LEVEL=DEBUG), sonst INFO.
    _env_level_str = (
        os.environ.get("GRAPHITI_LOG_LEVEL")
        or os.environ.get("LOG_LEVEL")
        or "INFO"
    ).upper()
    _console_level = getattr(logging, _env_level_str, logging.INFO)

    # Unter Windows UTF-8 für stdout/stderr erzwingen.
    _ensure_utf8_stdout()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(_console_level)
    console_handler.setFormatter(simple_formatter if _console_level >= logging.INFO else detailed_formatter)
    
    # Füge Prozessor hinzu
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str = 'mirofish') -> logging.Logger:
    """
    Holen Sie sich den Logger (erstellt, wenn er nicht existiert)
    
    Args:
        name: Logger-Name
        
    Returns:
        Logger-Instanz.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


# Erstelle den Standard-Logger
logger = setup_logger()


# Kurzwegmethode
def debug(msg, *args, **kwargs):
    logger.debug(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    logger.info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    logger.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    logger.error(msg, *args, **kwargs)

def critical(msg, *args, **kwargs):
    logger.critical(msg, *args, **kwargs)

