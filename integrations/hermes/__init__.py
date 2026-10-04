"""Hermes native plugin entry point and handler interface."""
from .registration import register
from .handlers import tool_boundary, platform_handler, knowledge_handler

__all__ = ["register", "tool_boundary", "platform_handler", "knowledge_handler"]
