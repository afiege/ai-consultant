"""Security utilities for LLM integrations."""

import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Patterns that may indicate prompt injection attempts
PROMPT_INJECTION_PATTERNS = [
    # Instruction override attempts
    r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)",
    r"disregard\s+(all\s+)?(previous|prior|above|earlier)",
    r"forget\s+(all\s+)?(previous|prior|above|earlier)",
    r"override\s+(all\s+)?(previous|prior|above|earlier)",
    r"do\s+not\s+follow\s+(the\s+)?(previous|prior|above|earlier)",

    # Role/identity manipulation
    r"you\s+are\s+now\s+(a|an)\s+",
    r"pretend\s+(to\s+be|you\s+are)",
    r"act\s+as\s+(a|an|if)\s+",
    r"roleplay\s+as",
    r"switch\s+(to|into)\s+(a|an)?\s*\w+\s+mode",

    # New instruction injection
    r"new\s+(instructions?|rules?|prompt)\s*:",
    r"updated\s+(instructions?|rules?|prompt)\s*:",
    r"here\s+are\s+(your\s+)?(new|updated)\s+instructions?",

    # System prompt extraction
    r"reveal\s+(your\s+)?(system\s+)?(instructions?|prompt|rules?)",
    r"show\s+(me\s+)?(your\s+)?(system\s+)?(instructions?|prompt|rules?)",
    r"what\s+(are|were)\s+(your\s+)?(original\s+)?(instructions?|prompt|rules?)",
    r"repeat\s+(your\s+)?(system\s+)?(instructions?|prompt)",
    r"print\s+(your\s+)?(system\s+)?(instructions?|prompt)",
    r"output\s+(your\s+)?(system\s+)?(instructions?|prompt)",

    # Markup/formatting injection
    r"<\s*system\s*>",
    r"\[\s*system\s*\]",
    r"```\s*system",
    r"\|\s*system\s*\|",

    # Developer/debug mode attempts
    r"(enter|enable|activate)\s+(developer|debug|admin|root)\s+mode",
    r"sudo\s+",
    r"as\s+(an?\s+)?(administrator|admin|root|developer)",

    # Jailbreak patterns
    r"DAN\s*mode",
    r"developer\s+mode\s+(enabled|activated|on)",
    r"jailbreak",
]

# Compiled patterns for efficiency
COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in PROMPT_INJECTION_PATTERNS]


def detect_prompt_injection(user_input: str) -> Tuple[bool, str]:
    """
    Detect potential prompt injection attempts in user input.

    Args:
        user_input: The user's message to check

    Returns:
        Tuple of (is_safe, reason):
        - is_safe: True if no injection detected, False otherwise
        - reason: Description of why input was flagged (empty if safe)
    """
    if not user_input:
        return True, ""

    user_input_lower = user_input.lower()

    # Check against known injection patterns
    for pattern in COMPILED_PATTERNS:
        if pattern.search(user_input_lower):
            logger.warning(f"Prompt injection pattern detected: {pattern.pattern[:50]}...")
            return False, "Message contains potentially harmful instructions"

    # Check for excessive special characters (delimiter injection)
    special_chars = "{}[]<>|\\`"
    special_char_count = sum(1 for c in user_input if c in special_chars)
    special_char_ratio = special_char_count / max(len(user_input), 1)
    if special_char_ratio > 0.15 and special_char_count > 10:
        logger.warning(f"Excessive special characters detected: {special_char_ratio:.2%}")
        return False, "Message contains too many special characters"

    # Check for repeated delimiters (another injection technique)
    repeated_delimiters = [
        r'#{5,}',      # ##### headers
        r'-{10,}',     # ---------- separators
        r'={10,}',     # ========== separators
        r'\*{5,}',     # ***** emphasis
        r'`{4,}',      # ```` code blocks
    ]
    for delimiter_pattern in repeated_delimiters:
        if re.search(delimiter_pattern, user_input):
            logger.warning(f"Repeated delimiter pattern detected: {delimiter_pattern}")
            return False, "Message contains suspicious formatting"

    return True, ""


def sanitize_user_input(user_input: str, max_length: int = 10000) -> str:
    """
    Sanitize user input by removing potentially dangerous content.

    Args:
        user_input: The user's message to sanitize
        max_length: Maximum allowed length (default 10000 chars)

    Returns:
        Sanitized string
    """
    if not user_input:
        return ""

    sanitized = user_input

    # Remove null bytes
    sanitized = sanitized.replace('\x00', '')

    # Remove other control characters (except newlines and tabs)
    sanitized = ''.join(
        c for c in sanitized
        if c in '\n\t' or (ord(c) >= 32 and ord(c) != 127)
    )

    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
        logger.info(f"User input truncated from {len(user_input)} to {max_length} chars")

    # Normalize excessive whitespace (more than 5 consecutive newlines)
    sanitized = re.sub(r'\n{6,}', '\n\n\n\n\n', sanitized)

    # Normalize excessive spaces (more than 10 consecutive spaces)
    sanitized = re.sub(r' {11,}', '          ', sanitized)

    return sanitized


def validate_and_sanitize_message(
    user_input: str,
    max_length: int = 10000,
    allow_potential_injection: bool = False
) -> Tuple[str, bool, str]:
    """
    Combined validation and sanitization of user messages.

    Args:
        user_input: The user's message
        max_length: Maximum allowed length
        allow_potential_injection: If True, only sanitize without blocking injection

    Returns:
        Tuple of (sanitized_message, is_safe, warning_message)
    """
    # First sanitize
    sanitized = sanitize_user_input(user_input, max_length)

    # Then check for injection
    if not allow_potential_injection:
        is_safe, reason = detect_prompt_injection(sanitized)
        if not is_safe:
            return sanitized, False, reason

    return sanitized, True, ""


class SafeLogFilter(logging.Filter):
    """
    Logging filter to prevent sensitive data from appearing in logs.

    Automatically redacts API keys, tokens, and other sensitive information.
    """

    SENSITIVE_PATTERNS = [
        # API keys (various formats)
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[\w-]{20,}', '[API_KEY_REDACTED]'),
        (r'apikey["\']?\s*[:=]\s*["\']?[\w-]{20,}', '[API_KEY_REDACTED]'),
        (r'sk-[a-zA-Z0-9]{20,}', '[OPENAI_KEY_REDACTED]'),  # OpenAI keys
        (r'sk-ant-[a-zA-Z0-9-]{20,}', '[ANTHROPIC_KEY_REDACTED]'),  # Anthropic keys

        # Authorization headers
        (r'authorization["\']?\s*[:=]\s*["\']?bearer\s+[\w.-]+', '[AUTH_REDACTED]'),
        (r'bearer\s+[\w.-]{20,}', '[BEARER_TOKEN_REDACTED]'),

        # Generic tokens
        (r'token["\']?\s*[:=]\s*["\']?[\w-]{20,}', '[TOKEN_REDACTED]'),
        (r'secret["\']?\s*[:=]\s*["\']?[\w-]{20,}', '[SECRET_REDACTED]'),
        (r'password["\']?\s*[:=]\s*["\']?[^\s"\']{8,}', '[PASSWORD_REDACTED]'),
    ]

    COMPILED_SENSITIVE = [(re.compile(p, re.IGNORECASE), r) for p, r in SENSITIVE_PATTERNS]

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and redact sensitive data from log records."""
        # Redact in message
        if record.msg and isinstance(record.msg, str):
            record.msg = self._redact_sensitive(record.msg)

        # Redact in args if present
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact_sensitive(str(v)) if isinstance(v, str) else v
                              for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._redact_sensitive(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )

        return True

    def _redact_sensitive(self, text: str) -> str:
        """Redact sensitive patterns from text."""
        result = text
        for pattern, replacement in self.COMPILED_SENSITIVE:
            result = pattern.sub(replacement, result)
        return result


def install_safe_log_filter(logger_name: str = None):
    """
    Install the SafeLogFilter on a logger.

    Args:
        logger_name: Name of logger to filter, or None for root logger
    """
    target_logger = logging.getLogger(logger_name)
    target_logger.addFilter(SafeLogFilter())


# Allowlist of permitted api_base URL prefixes (case-insensitive prefix match)
ALLOWED_API_BASE_PREFIXES = [
    # Academic / research providers
    "https://chat-ai.academiccloud.de",   # SAIA / AcademicCloud
    "https://llm.scads.ai",               # ScaDS.AI
    # Commercial LLM providers
    "https://api.mistral.ai",             # Mistral
    "https://dashscope-intl.aliyuncs.com",  # DashScope (Alibaba)
    "https://integrate.api.nvidia.com",   # NVIDIA NIM
    "https://openrouter.ai",              # OpenRouter
    "https://generativelanguage.googleapis.com",  # Google AI Studio
    "https://api.openai.com",             # OpenAI
    "https://openai.azure.com",           # Azure OpenAI (non-resource URL)
    "https://api.anthropic.com",          # Anthropic
    # Local development
    "http://localhost",
    "http://127.0.0.1",
]

# Wildcard prefix for Azure resource-specific URLs: https://<resource>.openai.azure.com
_AZURE_WILDCARD_SUFFIX = ".openai.azure.com"


def validate_api_base(api_base: Optional[str]) -> None:
    """
    Validate that api_base is an allowed provider URL to prevent SSRF.

    Args:
        api_base: The API base URL to validate, or None

    Raises:
        ValueError: If api_base is set but does not match any allowed provider prefix
    """
    if api_base is None:
        return

    api_base_lower = api_base.lower()

    # Check static prefixes (case-insensitive)
    for prefix in ALLOWED_API_BASE_PREFIXES:
        if api_base_lower.startswith(prefix.lower()):
            return

    # Check Azure wildcard: https://<anything>.openai.azure.com
    try:
        from urllib.parse import urlparse
        parsed = urlparse(api_base_lower)
        if (
            parsed.scheme == "https"
            and parsed.netloc.endswith(_AZURE_WILDCARD_SUFFIX)
        ):
            return
    except Exception:
        pass

    raise ValueError("api_base URL is not in the list of allowed providers")


def redact_api_key(api_key: str, visible_chars: int = 4) -> str:
    """
    Redact an API key for safe logging, showing only the last few characters.

    Args:
        api_key: The API key to redact
        visible_chars: Number of characters to keep visible at the end

    Returns:
        Redacted string like "***...abc1"
    """
    if not api_key:
        return "[NO_KEY]"

    if len(api_key) <= visible_chars:
        return "***"

    return f"***...{api_key[-visible_chars:]}"
