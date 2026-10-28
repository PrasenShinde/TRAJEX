"""
Logging utilities for the ANPR simulation.
"""

import logging
import sys
from typing import Optional


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Create or retrieve a logger with a consistent format.

    Args:
        name: Logger name (typically __name__).
        level: Logging level; defaults to INFO.

    Returns:
        Configured Logger instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)

    logger.setLevel(level or logging.INFO)
    return logger
