"""LLM utility functions with retry logic and error handling."""

import logging
from typing import Dict, List, Generator, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from litellm import completion
from litellm.exceptions import (
    RateLimitError,
    APIConnectionError,
    Timeout,
    ServiceUnavailableError
)

from .security import SafeLogFilter, redact_api_key

logger = logging.getLogger(__name__)
# Install safe logging filter to prevent API keys from appearing in logs
logger.addFilter(SafeLogFilter())

# Exceptions that should trigger a retry
RETRYABLE_EXCEPTIONS = (
    RateLimitError,
    APIConnectionError,
    Timeout,
    ServiceUnavailableError,
    ConnectionError,
    TimeoutError,
)


def create_llm_caller(
    model: str,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    max_retries: int = 3
):
    """
    Create LLM call functions with retry logic.

    Args:
        model: The LLM model to use
        api_key: Optional API key
        api_base: Optional API base URL
        max_retries: Maximum number of retry attempts

    Returns:
        Tuple of (call_llm, call_llm_stream) functions
    """

    @retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def call_llm(
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: int = 120
    ):
        """Call LLM with automatic retry on transient failures."""
        completion_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout
        }
        if api_key:
            completion_kwargs["api_key"] = api_key
        if api_base:
            completion_kwargs["api_base"] = api_base

        try:
            return completion(**completion_kwargs)
        except RETRYABLE_EXCEPTIONS:
            # Let tenacity handle retry
            raise
        except Exception as e:
            # Log non-retryable errors without exposing sensitive data
            safe_config = {
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "has_api_key": bool(api_key),
                "has_api_base": bool(api_base)
            }
            logger.error(f"LLM call failed with non-retryable error: {e.__class__.__name__}: {e}. Config: {safe_config}")
            raise

    @retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def call_llm_stream(
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: int = 120
    ) -> Generator:
        """Call LLM with streaming and automatic retry on transient failures."""
        completion_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "timeout": timeout
        }
        if api_key:
            completion_kwargs["api_key"] = api_key
        if api_base:
            completion_kwargs["api_base"] = api_base

        try:
            return completion(**completion_kwargs)
        except RETRYABLE_EXCEPTIONS:
            # Let tenacity handle retry
            raise
        except Exception as e:
            # Log non-retryable errors without exposing sensitive data
            safe_config = {
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
                "has_api_key": bool(api_key),
                "has_api_base": bool(api_base)
            }
            logger.error(f"LLM stream call failed with non-retryable error: {e.__class__.__name__}: {e}. Config: {safe_config}")
            raise

    return call_llm, call_llm_stream


class LLMCaller:
    """
    Class-based LLM caller with retry logic.

    Usage:
        caller = LLMCaller(model="gpt-4", api_key="...")
        response = caller.call(messages)
        stream = caller.call_stream(messages)
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        max_retries: int = 3
    ):
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self._call, self._call_stream = create_llm_caller(
            model=model,
            api_key=api_key,
            api_base=api_base,
            max_retries=max_retries
        )

    def call(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: int = 120
    ):
        """Call LLM with automatic retry."""
        return self._call(messages, temperature, max_tokens, timeout)

    def call_stream(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: int = 120
    ) -> Generator:
        """Call LLM with streaming and automatic retry."""
        return self._call_stream(messages, temperature, max_tokens, timeout)

    def update_credentials(self, api_key: Optional[str] = None, api_base: Optional[str] = None):
        """Update API credentials and recreate callers."""
        if api_key is not None:
            self.api_key = api_key
        if api_base is not None:
            self.api_base = api_base
        self._call, self._call_stream = create_llm_caller(
            model=self.model,
            api_key=self.api_key,
            api_base=self.api_base
        )
