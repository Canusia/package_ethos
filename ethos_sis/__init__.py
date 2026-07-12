"""Standalone, Django-free CLI client for the Ellucian Ethos Integration API."""

from .config import Config, load_config

__version__ = "2026.0.18"
__all__ = ["Config", "load_config", "__version__"]
