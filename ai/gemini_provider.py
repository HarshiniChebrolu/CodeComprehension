import re
import json
import logging
import requests
from typing import Dict, Any, List, Optional
from ai.base import ReviewProvider
from ai.models import ExplanationModel
from ai.offline_provider import OfflineProvider
from config import Config

logger = logging.getLogger("codecomprehension.ai.gemini")


class GeminiProvider(ReviewProvider):
    """
    Google Gemini AI Mentor Provider.
    Communicates with Gemini API with low temperature, timeouts, retry backoff,
    and automatic structured validation via Pydantic.
    Falls back gracefully to OfflineProvider if API key is missing or service unavailable.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.GEMINI_API_KEY
        self.offline_fallback = OfflineProvider()

    @property
    def name(self) -> str:
        return "Google Gemini AI (Cloud LLM)"

    def generate_explanation(
        self,
        code: str,
        language: str = "python",
        context_issues: Optional[List[Dict[str, Any]]] = None
    ) -> ExplanationModel:
        if not self.api_key or not self.api_key.strip():
            logger.info("No Gemini API key configured. Falling back to offline rule provider.")
            return self.offline_fallback.generate_explanation(code, language, context_issues)

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key.strip()
        }

        prompt = f"""You are an educational programming mentor in CodeComprehension.
Explain this {language} code for a student developer.
Return ONLY a valid JSON object matching this schema:
{{
  "purpose": "A concise 1-2 sentence overview of what the program achieves.",
  "algorithm": "Name or classification of algorithm used.",
  "data_structures": ["list", "of", "data", "structures"],
  "key_functions": ["function names with params"],
  "key_variables": ["notable variables and their roles"],
  "step_by_step": ["step 1", "step 2", "step 3"],
  "mentor_note": "A thoughtful 1 sentence mentoring tip for the student."
}}

Code:
```{language}
{code[:4000]}
```
Do NOT wrap with markdown backticks or commentary. Return raw JSON string only."""

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.15,
                "maxOutputTokens": 1200
            }
        }

        # Attempt call with timeout and one structured retry
        for attempt in range(2):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=Config.AI_TIMEOUT_SECONDS)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    clean_json = re.sub(r'^```(?:json)?\s*', '', raw_text)
                    clean_json = re.sub(r'```$', '', clean_json).strip()
                    parsed = json.loads(clean_json)

                    # Extract usage metadata
                    usage = data.get("usageMetadata", {})
                    prompt_tokens = usage.get("promptTokenCount", len(prompt) // 4)
                    completion_tokens = usage.get("candidatesTokenCount", len(raw_text) // 4)
                    total_tokens = prompt_tokens + completion_tokens
                    # Approx Gemini Flash pricing: ~$0.075 per 1M input, $0.30 per 1M output
                    est_cost = round((prompt_tokens * 0.000000075) + (completion_tokens * 0.00000030), 6)

                    return ExplanationModel(
                        provider=self.name,
                        purpose=parsed.get("purpose", "Code routine"),
                        algorithm=parsed.get("algorithm", "Algorithmic procedure"),
                        data_structures=parsed.get("data_structures", []),
                        key_functions=parsed.get("key_functions", []),
                        key_variables=parsed.get("key_variables", []),
                        step_by_step=parsed.get("step_by_step", []),
                        mentor_note=parsed.get("mentor_note", "Mentor Tip: Write tests for edge cases."),
                        token_usage={
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens
                        },
                        estimated_cost_usd=est_cost
                    )
                else:
                    logger.warning("Gemini API error (HTTP %s): %s", resp.status_code, resp.text[:150])
            except Exception as e:
                logger.warning("Gemini API attempt %d failed: %s", attempt + 1, e)

        # Graceful fallback to offline engine
        logger.info("Falling back to offline rule provider after Gemini failure.")
        return self.offline_fallback.generate_explanation(code, language, context_issues)
