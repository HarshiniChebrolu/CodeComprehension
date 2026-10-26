import json
import logging
import requests
from typing import Dict, Any, List, Optional
from ai.base import ReviewProvider
from ai.models import ExplanationModel
from ai.offline_provider import OfflineProvider
from config import Config

logger = logging.getLogger("codecomprehension.ai.openai")


class OpenAIProvider(ReviewProvider):
    """
    OpenAI GPT Mentor Provider.
    Uses json_object response format, low temperature, and timeout.
    Falls back gracefully to OfflineProvider if key is missing or call fails.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.OPENAI_API_KEY
        self.offline_fallback = OfflineProvider()

    @property
    def name(self) -> str:
        return "OpenAI GPT-4o-mini (Cloud LLM)"

    def generate_explanation(
        self,
        code: str,
        language: str = "python",
        context_issues: Optional[List[Dict[str, Any]]] = None
    ) -> ExplanationModel:
        if not self.api_key or not self.api_key.strip():
            logger.info("No OpenAI API key configured. Falling back to offline rule provider.")
            return self.offline_fallback.generate_explanation(code, language, context_issues)

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        prompt = f"""You are a programming mentor in CodeComprehension.
Explain this {language} code for a student developer.
Return a valid JSON object matching:
{{
  "purpose": "A concise 1-2 sentence overview of what the program achieves.",
  "algorithm": "Name or classification of algorithm used.",
  "data_structures": ["list", "of", "data", "structures"],
  "key_functions": ["function names with params"],
  "key_variables": ["notable variables and their roles"],
  "step_by_step": ["step 1", "step 2", "step 3"],
  "mentor_note": "A thoughtful 1 sentence mentoring tip."
}}

Code:
```{language}
{code[:4000]}
```"""

        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.15
        }

        for attempt in range(2):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=Config.AI_TIMEOUT_SECONDS)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)

                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", len(prompt) // 4)
                    completion_tokens = usage.get("completion_tokens", len(content) // 4)
                    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
                    # gpt-4o-mini approx pricing: $0.15 / 1M prompt, $0.60 / 1M completion
                    est_cost = round((prompt_tokens * 0.00000015) + (completion_tokens * 0.00000060), 6)

                    return ExplanationModel(
                        provider=self.name,
                        purpose=parsed.get("purpose", "Code routine"),
                        algorithm=parsed.get("algorithm", "Algorithmic procedure"),
                        data_structures=parsed.get("data_structures", []),
                        key_functions=parsed.get("key_functions", []),
                        key_variables=parsed.get("key_variables", []),
                        step_by_step=parsed.get("step_by_step", []),
                        mentor_note=parsed.get("mentor_note", "Mentor Tip: Check edge cases."),
                        token_usage={
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens
                        },
                        estimated_cost_usd=est_cost
                    )
                else:
                    logger.warning("OpenAI API error (HTTP %s): %s", resp.status_code, resp.text[:150])
            except Exception as e:
                logger.warning("OpenAI API attempt %d failed: %s", attempt + 1, e)

        # Fallback to offline provider
        logger.info("Falling back to offline rule provider after OpenAI failure.")
        return self.offline_fallback.generate_explanation(code, language, context_issues)
