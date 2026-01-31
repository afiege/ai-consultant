"""Utility modules for the AI Consultant backend."""

from .sse import format_sse_data, format_sse_error, safe_stream_wrapper
from .llm import LLMCaller, create_llm_caller
from .db import (
    transaction_scope,
    with_transaction,
    with_transaction_async,
    safe_commit,
    safe_delete
)
from .security import (
    detect_prompt_injection,
    sanitize_user_input,
    validate_and_sanitize_message,
    SafeLogFilter,
    install_safe_log_filter,
    redact_api_key
)

__all__ = [
    # SSE utilities
    'format_sse_data',
    'format_sse_error',
    'safe_stream_wrapper',
    # LLM utilities
    'LLMCaller',
    'create_llm_caller',
    # Database utilities
    'transaction_scope',
    'with_transaction',
    'with_transaction_async',
    'safe_commit',
    'safe_delete',
    # Security utilities
    'detect_prompt_injection',
    'sanitize_user_input',
    'validate_and_sanitize_message',
    'SafeLogFilter',
    'install_safe_log_filter',
    'redact_api_key',
]
