import logging
from typing import Optional
from ai.base import ReviewProvider
from ai.offline_provider import OfflineProvider
from ai.gemini_provider import GeminiProvider
from ai.openai_provider import OpenAIProvider
from config import Config

logger = logging.getLogger("codecomprehension.ai.factory")


def get_ai_provider(provider_name: Optional[str] = None) -> ReviewProvider:
    """
    Factory function returning the configured ReviewProvider.
    Validates provider name and falls back safely to OfflineProvider.
    """
    selected = (provider_name or Config.DEFAULT_AI_PROVIDER or "offline").lower().strip()

    if selected == "gemini":
        return GeminiProvider()
    elif selected == "openai":
        return OpenAIProvider()
    elif selected == "offline":
        return OfflineProvider()
    else:
        logger.warning("Unrecognized AI provider '%s'. Defaulting to offline rule engine.", selected)
        return OfflineProvider()
