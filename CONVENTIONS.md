# CodeComprehension rules
- Flask app-factory architecture stays. Do not redesign working UI or add dependencies without need.
- Supported languages come from ONE registry (SUPPORTED_LANGUAGES in config.py). Never hardcode language lists elsewhere.
- No hardcoded sample/placeholder results. Every result derives from the submitted code + selected language.
- If a language/tool is unsupported or unavailable, return an explicit {"supported": false, "reason": "..."} instead of fake data.
- Submitted code NEVER runs inside the Flask process. Only via Docker sandbox (--network none, --read-only, --cap-drop ALL, non-root, cpu/mem/pids limits).
- Never log or return API keys. Render AI output as text, never raw HTML.
- Test results are PASS/FAIL/ERROR/TIMEOUT only after real execution; otherwise "UNVERIFIED".
- Add pytest regression tests for every fix. Do not claim tests pass unless run.