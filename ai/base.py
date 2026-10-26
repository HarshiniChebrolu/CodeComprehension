from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ai.models import ExplanationModel


class ReviewProvider(ABC):
    """
    Abstract Base Class for CodeComprehension Review & Mentoring Providers.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the human-readable identifier of this provider."""
        pass

    @abstractmethod
    def generate_explanation(
        self,
        code: str,
        language: str = "python",
        context_issues: Optional[List[Dict[str, Any]]] = None
    ) -> ExplanationModel:
        """Generates structured code explanation and mentor guidance."""
        pass
