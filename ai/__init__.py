from ai.base import ReviewProvider
from ai.factory import get_ai_provider
from ai.models import ExplanationModel, IssueModel, HintSet, SolutionDetail


def get_ai_explanation(code: str, language: str = "python", context_issues: list = None):
    provider = get_ai_provider()
    res = provider.generate_explanation(code, language, context_issues)
    return res.model_dump()
