"""Centralized application configuration.

Business logic imports the ``settings`` singleton from this package and
never reads environment variables directly. See ``settings.py`` for the
full settings model and ``backend/.env.example`` for the available
environment variables.
"""

from app.shared.config.settings import Settings, get_settings, settings

__all__ = ["Settings", "get_settings", "settings"]
