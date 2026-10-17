"""Optional Gemini-backed investigation over application-owned evidence."""

from .agent import ToolBackend, investigate
from .client import GeminiSettings, gemini_completion

__all__ = ["GeminiSettings", "ToolBackend", "gemini_completion", "investigate"]
