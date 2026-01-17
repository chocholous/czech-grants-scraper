"""Společné utility pro všechny scrapery."""

import logging
import os
from datetime import datetime


def setup_logging(name: str = "scraper", level: str | None = None) -> logging.Logger:
    """Nastaví logging pro scraper.

    Args:
        name: Název loggeru
        level: Úroveň logování (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Nakonfigurovaný logger
    """
    log_level = level or os.getenv("LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(name)


def ensure_dir(path: str) -> str:
    """Vytvoří adresář pokud neexistuje.

    Args:
        path: Cesta k adresáři

    Returns:
        Cesta k adresáři
    """
    os.makedirs(path, exist_ok=True)
    return path


def get_output_dir() -> str:
    """Vrátí výstupní adresář z env nebo default.

    Returns:
        Cesta k výstupnímu adresáři
    """
    return os.getenv("OUTPUT_DIR", "./data")


def timestamp() -> str:
    """Vrátí aktuální timestamp v ISO formátu.

    Returns:
        ISO timestamp string
    """
    return datetime.utcnow().isoformat() + "Z"
