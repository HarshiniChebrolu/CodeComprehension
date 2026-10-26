import re
from typing import Tuple, List, Dict, Any

# Regular expression patterns for common sensitive credentials & keys
SECRET_PATTERNS = [
    {
        "type": "OpenAI / Cloud API Key",
        "pattern": r'\b(sk-[a-zA-Z0-9_\-]{20,})\b',
        "replacement": "[REDACTED_API_KEY]"
    },
    {
        "type": "AWS Access Key ID",
        "pattern": r'\b(AKIA[0-9A-Z]{16})\b',
        "replacement": "[REDACTED_AWS_KEY]"
    },
    {
        "type": "GitHub Access Token",
        "pattern": r'\b(gh[pousr]_[A-Za-z0-9_]{36,}|github_pat_[A-Za-z0-9_]{22,})\b',
        "replacement": "[REDACTED_GITHUB_TOKEN]"
    },
    {
        "type": "Generic Bearer / Auth Token",
        "pattern": r'(?i)\b(bearer\s+[a-zA-Z0-9\-_\.]{24,})\b',
        "replacement": "Bearer [REDACTED_TOKEN]"
    },
    {
        "type": "Private Cryptographic Key",
        "pattern": r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----',
        "replacement": "[REDACTED_PRIVATE_KEY]"
    },
    {
        "type": "Database Connection URI with Credentials",
        "pattern": r'(?i)\b((?:postgres|postgresql|mysql|mongodb|redis):\/\/[a-zA-Z0-9_\-\.]+:[^@\s]+@[a-zA-Z0-9_\-\.]+:[0-9]+(?:\/[^\s]*)?)\b',
        "replacement": "[REDACTED_DATABASE_URI]"
    },
    {
        "type": "Hardcoded Password Assignment",
        "pattern": r'(?i)\b((?:password|passwd|pwd|secret|api_key|apikey|auth_token)\s*=\s*["\'])([^"\']{4,})(["\'])',
        "is_grouped": True,
        "replacement": r'\g<1>[REDACTED_PASSWORD]\g<3>'
    }
]


def scan_and_redact_secrets(code: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Scans source code for sensitive tokens, passwords, and private keys.
    Returns:
        redacted_code (str): Safe copy with sensitive strings masked.
        findings (list): Metadata about detected secrets (type and line number),
                        NEVER including the actual secret value.
    """
    if not code:
        return "", []

    redacted = code
    findings = []
    lines = code.split("\n")

    for rule in SECRET_PATTERNS:
        # Check per-line to record line number for developer feedback
        for line_idx, line in enumerate(lines, start=1):
            if re.search(rule["pattern"], line):
                findings.append({
                    "type": rule["type"],
                    "line": line_idx,
                    "warning": f"Potential sensitive secret ({rule['type']}) detected on line {line_idx}. Redacted before storage."
                })

        # Apply global redaction to code string
        if rule.get("is_grouped"):
            redacted = re.sub(rule["pattern"], rule["replacement"], redacted)
        else:
            redacted = re.sub(rule["pattern"], rule["replacement"], redacted)

    return redacted, findings
