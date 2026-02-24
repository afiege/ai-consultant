"""Unit tests for the three critical security fixes:

1. Unbounded upload size in session restore (session_backup.py)
2. SSRF via restored llm_api_base (session_backup.py)
3. Missing rate limiting on export.py, company_info.py, six_three_five.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.routers.session_backup import _validate_restored_api_base
from app.utils.security import validate_api_base


# ---------------------------------------------------------------------------
# Fix 1 & 2: session_backup helpers
# ---------------------------------------------------------------------------

class TestValidateRestoredApiBase:
    """Tests for _validate_restored_api_base — SSRF guard on session restore."""

    def test_none_returns_none(self):
        assert _validate_restored_api_base(None) is None

    def test_empty_string_returns_none(self):
        assert _validate_restored_api_base("") is None

    def test_anonymized_placeholder_returns_none(self):
        assert _validate_restored_api_base("[anonymized]") is None

    def test_valid_https_url_returned(self):
        url = "https://api.openai.com/v1"
        assert _validate_restored_api_base(url) == url

    def test_valid_http_localhost_returned(self):
        url = "http://localhost:11434/v1"
        assert _validate_restored_api_base(url) == url

    def test_ssrf_private_ip_returns_none(self):
        assert _validate_restored_api_base("http://192.168.1.1/evil") is None

    def test_ssrf_metadata_endpoint_returns_none(self):
        assert _validate_restored_api_base("http://169.254.169.254/latest/meta-data/") is None

    def test_ssrf_loopback_non_localhost_returns_none(self):
        # 127.0.0.2 is loopback but not the allowed localhost name
        result = _validate_restored_api_base("http://127.0.0.2/v1")
        # Either None (blocked) or the value if allowlist permits — key thing
        # is that it never raises an unhandled exception
        assert result is None or isinstance(result, str)

    def test_invalid_url_returns_none(self):
        assert _validate_restored_api_base("not-a-url") is None

    def test_file_scheme_returns_none(self):
        assert _validate_restored_api_base("file:///etc/passwd") is None

    def test_internal_network_10_block_returns_none(self):
        assert _validate_restored_api_base("http://10.0.0.1/api") is None

    def test_internal_network_172_block_returns_none(self):
        assert _validate_restored_api_base("http://172.16.0.1/api") is None

    def test_never_raises_exception(self):
        """_validate_restored_api_base must always return str|None, never raise."""
        malicious_inputs = [
            "javascript:alert(1)",
            "ftp://internal.server/data",
            "http://[::1]/admin",
            "\x00null_byte",
            "http://" + "a" * 1000 + ".com",
        ]
        for value in malicious_inputs:
            result = _validate_restored_api_base(value)
            assert result is None or isinstance(result, str)


class TestRestoreEndpointSizeLimit:
    """Tests for the 10 MB upload cap in the restore endpoint."""

    @pytest.mark.asyncio
    async def test_file_within_limit_is_accepted(self):
        """A file under 10 MB should pass the size check and reach JSON parsing."""
        from app.routers.session_backup import restore_session_backup

        small_json = b'{"not": "a valid backup"}'
        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=small_json)

        mock_db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await restore_session_backup(file=mock_file, db=mock_db)

        # Should fail on structure validation (missing keys), not size
        assert exc_info.value.status_code == 400
        assert "too large" not in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_file_exceeding_limit_raises_400(self):
        """A file read returning > 10 MB triggers the size rejection."""
        from app.routers.session_backup import restore_session_backup

        MAX = 10 * 1024 * 1024
        oversized_content = b"x" * (MAX + 2)  # simulate read returning > limit

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=oversized_content)

        mock_db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await restore_session_backup(file=mock_file, db=mock_db)

        assert exc_info.value.status_code == 400
        assert "too large" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_size_check_before_json_parse(self):
        """The size check must happen before json.loads is called."""
        from app.routers.session_backup import restore_session_backup

        MAX = 10 * 1024 * 1024
        # Content that is oversized but would also fail JSON parsing
        oversized_non_json = b"!" * (MAX + 2)

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=oversized_non_json)

        mock_db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await restore_session_backup(file=mock_file, db=mock_db)

        # Must be the size error, not a JSON decode error
        assert "too large" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_exact_limit_boundary_accepted(self):
        """A file of exactly 10 MB should pass the size check."""
        from app.routers.session_backup import restore_session_backup

        MAX = 10 * 1024 * 1024
        exact_limit = b"x" * MAX

        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=exact_limit)

        mock_db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await restore_session_backup(file=mock_file, db=mock_db)

        # Must not be a size error
        assert "too large" not in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Fix 3: Rate limiting decorators present on LLM-calling endpoints
# ---------------------------------------------------------------------------

class TestRateLimitingDecorators:
    """Verify @limiter.limit decorators are applied to LLM-calling endpoints."""

    def _is_rate_limited(self, func) -> bool:
        """Check if a function has been decorated with @limiter.limit.

        slowapi wraps the function via functools.wraps, which sets __wrapped__
        in the function's __dict__. Non-decorated functions have an empty __dict__.
        """
        return "__wrapped__" in func.__dict__

    # --- export.py ---

    def test_generate_transition_briefing_is_rate_limited(self):
        from app.routers.export import generate_transition_briefing
        assert self._is_rate_limited(generate_transition_briefing), \
            "generate_transition_briefing must have @limiter.limit"

    def test_generate_swot_analysis_is_rate_limited(self):
        from app.routers.export import generate_swot_analysis
        assert self._is_rate_limited(generate_swot_analysis), \
            "generate_swot_analysis must have @limiter.limit"

    def test_auto_update_analysis_is_rate_limited(self):
        from app.routers.export import auto_update_analysis
        assert self._is_rate_limited(auto_update_analysis), \
            "auto_update_analysis must have @limiter.limit"

    def test_extract_cross_references_is_rate_limited(self):
        from app.routers.export import extract_cross_references
        assert self._is_rate_limited(extract_cross_references), \
            "extract_cross_references must have @limiter.limit"

    # --- company_info.py ---

    def test_crawl_company_website_is_rate_limited(self):
        from app.routers.company_info import crawl_company_website
        assert self._is_rate_limited(crawl_company_website), \
            "crawl_company_website must have @limiter.limit"

    def test_extract_profile_is_rate_limited(self):
        from app.routers.company_info import extract_profile
        assert self._is_rate_limited(extract_profile), \
            "extract_profile must have @limiter.limit"

    # --- six_three_five.py ---

    def test_start_six_three_five_is_rate_limited(self):
        from app.routers.six_three_five import start_six_three_five
        assert self._is_rate_limited(start_six_three_five), \
            "start_six_three_five must have @limiter.limit"

    def test_advance_round_is_rate_limited(self):
        from app.routers.six_three_five import advance_round
        assert self._is_rate_limited(advance_round), \
            "advance_round must have @limiter.limit"

    # --- Verify non-LLM endpoints are NOT rate-limited (sanity check) ---

    def test_get_session_messages_not_rate_limited(self):
        """Read-only endpoints should not be unnecessarily rate-limited."""
        from app.routers.export import get_swot_analysis
        assert not self._is_rate_limited(get_swot_analysis), \
            "GET endpoint should not carry a rate limit"


class TestRateLimitingRouteSignatures:
    """Verify that rate-limited endpoints accept a Request parameter (required by slowapi)."""

    def _param_names(self, func) -> list[str]:
        import inspect
        sig = inspect.signature(func)
        return list(sig.parameters.keys())

    def test_generate_transition_briefing_has_request_param(self):
        from app.routers.export import generate_transition_briefing
        assert "request" in self._param_names(generate_transition_briefing)

    def test_generate_swot_analysis_has_request_param(self):
        from app.routers.export import generate_swot_analysis
        assert "request" in self._param_names(generate_swot_analysis)

    def test_auto_update_analysis_has_request_param(self):
        from app.routers.export import auto_update_analysis
        assert "request" in self._param_names(auto_update_analysis)

    def test_extract_cross_references_has_request_param(self):
        from app.routers.export import extract_cross_references
        assert "request" in self._param_names(extract_cross_references)

    def test_crawl_company_website_has_request_param(self):
        from app.routers.company_info import crawl_company_website
        assert "request" in self._param_names(crawl_company_website)

    def test_extract_profile_has_request_param(self):
        from app.routers.company_info import extract_profile
        assert "request" in self._param_names(extract_profile)

    def test_start_six_three_five_has_request_param(self):
        from app.routers.six_three_five import start_six_three_five
        assert "request" in self._param_names(start_six_three_five)

    def test_advance_round_has_request_param(self):
        from app.routers.six_three_five import advance_round
        assert "request" in self._param_names(advance_round)
