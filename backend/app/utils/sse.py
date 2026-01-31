"""SSE (Server-Sent Events) utility functions."""

import json
import logging
from typing import Generator, Callable, Any

logger = logging.getLogger(__name__)


def format_sse_data(content: str) -> str:
    """Format content for SSE, handling newlines properly.

    SSE spec requires multi-line data to use multiple 'data:' lines.
    Each line becomes 'data: line\n' and they're joined with newlines by the client.

    Args:
        content: The content to format for SSE transmission

    Returns:
        Properly formatted SSE data string
    """
    if '\n' in content:
        lines = content.split('\n')
        return ''.join(f"data: {line}\n" for line in lines) + '\n'
    else:
        return f"data: {content}\n\n"


def format_sse_error(error_message: str, error_type: str = "error") -> str:
    """Format an error message for SSE transmission.

    Args:
        error_message: The error message to send
        error_type: Type of error (error, timeout, connection_error)

    Returns:
        Formatted SSE error event
    """
    error_data = json.dumps({
        "error": error_message,
        "type": error_type,
        "recoverable": error_type in ("timeout", "connection_error")
    })
    return f"data: {error_data}\n\n"


def safe_stream_wrapper(
    stream_generator: Callable[[], Generator],
    on_chunk: Callable[[str], None] = None,
    on_complete: Callable[[str], None] = None,
    on_error: Callable[[Exception], None] = None
) -> Generator[str, None, None]:
    """Wrap a stream generator with error handling.

    Args:
        stream_generator: Function that returns the LLM stream
        on_chunk: Optional callback for each chunk
        on_complete: Optional callback when complete with full response
        on_error: Optional callback when an error occurs

    Yields:
        SSE-formatted data chunks or error messages
    """
    full_response = ""

    try:
        stream = stream_generator()

        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                if on_chunk:
                    on_chunk(content)
                yield format_sse_data(content)

        if on_complete:
            on_complete(full_response)

        yield "data: [DONE]\n\n"

    except (ConnectionError, TimeoutError) as e:
        logger.warning(f"Stream connection error (recoverable): {e}")
        if on_error:
            on_error(e)
        yield format_sse_error(
            f"Connection interrupted: {str(e)}. Please try again.",
            error_type="connection_error"
        )

    except Exception as e:
        logger.error(f"Stream error: {e}")
        if on_error:
            on_error(e)
        # Send partial response if we have one
        if full_response:
            logger.info(f"Partial response collected before error: {len(full_response)} chars")
            if on_complete:
                on_complete(full_response)
        yield format_sse_error(f"Stream error: {str(e)}", error_type="error")
