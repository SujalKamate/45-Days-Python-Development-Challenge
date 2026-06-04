"""Configures Python's ``logging`` module with a standard format.

Usage::

    from .log_setup import setup_logger
    self.logger = setup_logger(self.__class__.__name__)
    self.logger.info('message')
    self.logger.error('message')
    self.logger.exception('message')  # includes traceback
"""

import logging
import sys


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)-7s %(name)s - %(message)s',
            datefmt='%H:%M:%S',
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
