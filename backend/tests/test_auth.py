"""Tests for authentication and session token validation."""

import pytest


class TestAuthentication:
    """Token-based session authentication."""

    def test_session_returns_access_token(self, client):
        res = client.post("/api/sessions/", json={"company_name": "AuthCo"})
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        assert len(data["access_token"]) > 20  # tokens are 43+ chars

    def test_valid_token_grants_access(self, create_session, client, auth_headers):
        uuid, token, _ = create_session("Secure")
        res = client.get(f"/api/sessions/{uuid}", headers=auth_headers(token))
        assert res.status_code == 200

    def test_wrong_token_denied(self, create_session, client):
        uuid, _, _ = create_session("Locked")
        res = client.get(
            f"/api/sessions/{uuid}",
            headers={"X-Session-Token": "wrong-token-value"},
        )
        assert res.status_code == 403

    def test_missing_token_denied(self, create_session, client):
        uuid, token, _ = create_session("NeedToken")
        # Access without any token header
        res = client.get(f"/api/sessions/{uuid}")
        assert res.status_code == 401

    def test_delete_requires_valid_token(self, create_session, client):
        uuid, _, _ = create_session("Protected")
        res = client.delete(
            f"/api/sessions/{uuid}",
            headers={"X-Session-Token": "bad"},
        )
        assert res.status_code == 403

    def test_list_sessions_no_auth_needed(self, create_session, client):
        """Listing sessions is a discovery endpoint — no token needed."""
        create_session("Public1")
        res = client.get("/api/sessions/")
        assert res.status_code == 200
        assert len(res.json()) >= 1
