from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class HintSet(BaseModel):
    hint1: str = Field(description="Gentle clue pointing to suspicious area without giving answer")
    hint2: str = Field(description="Directional hint detailing the condition or edge scenario")
    hint3: str = Field(description="Strong hint explaining the exact logic adjustment")


class SolutionDetail(BaseModel):
    corrected_code: str
    why_failed: str
    why_works: str
    edge_cases: str


class IssueModel(BaseModel):
    id: str
    rule_id: str
    severity: str  # critical, high, medium, low
    category: str
    line: int
    column: Optional[int] = 1
    problem: str
    explanation: str
    hints: HintSet
    solution: SolutionDetail
    confidence: Optional[str] = "High"


class ExplanationModel(BaseModel):
    provider: str
    purpose: str
    algorithm: str
    data_structures: List[str]
    key_functions: List[str]
    key_variables: List[str]
    step_by_step: List[str]
    mentor_note: str
    token_usage: Optional[Dict[str, int]] = None
    estimated_cost_usd: Optional[float] = None


class ComplexityModel(BaseModel):
    time_complexity: str
    space_complexity: str
    reasoning: str
    best_case: str
    average_case: str
    worst_case: str
    confidence: str
    limitations: str
