"""Prompt template system for the AI infrastructure."""

from app.shared.ai.prompts.loader import PromptLoader
from app.shared.ai.prompts.manager import PromptManager, manager

__all__ = ["PromptLoader", "PromptManager", "manager"]
