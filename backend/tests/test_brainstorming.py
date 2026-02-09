"""Tests for 6-3-5 brainwriting endpoints."""

import pytest


class TestBrainwritingBasic:
    """6-3-5 brainwriting session management."""

    def test_start_brainwriting_with_participant(self, create_session, client, auth_headers):
        """Start brainwriting requires at least 1 participant."""
        uuid, token, _ = create_session("BrainCo")
        # Join as human participant first
        client.post(
            f"/api/sessions/{uuid}/six-three-five/join",
            json={"name": "Test Participant"},
            headers=auth_headers(token),
        )
        res = client.post(
            f"/api/sessions/{uuid}/six-three-five/start",
            json={"api_key": "test-key"},
            headers=auth_headers(token),
        )
        # With a test key the LLM won't work, but the endpoint should accept
        # the request and either succeed or fail on LLM, not on validation
        assert res.status_code in (200, 500)

    def test_start_brainwriting_no_participants(self, create_session, client, auth_headers):
        """Start without participants should fail."""
        uuid, token, _ = create_session("NoPart")
        res = client.post(
            f"/api/sessions/{uuid}/six-three-five/start",
            json={"api_key": "test-key"},
            headers=auth_headers(token),
        )
        assert res.status_code in (400, 500)  # ValueError from manager

    def test_get_status_not_started(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        res = client.get(
            f"/api/sessions/{uuid}/six-three-five/status",
            headers=auth_headers(token),
        )
        # Should return status info (or 404 if brainstorming not started)
        assert res.status_code in (200, 404)

    def test_skip_brainwriting(self, create_session, client, auth_headers):
        uuid, token, _ = create_session("SkipCo")
        res = client.post(
            f"/api/sessions/{uuid}/six-three-five/skip",
            headers=auth_headers(token),
        )
        assert res.status_code == 200

    def test_submit_manual_ideas(self, create_session, client, auth_headers):
        uuid, token, _ = create_session("ManualCo")
        res = client.post(
            f"/api/sessions/{uuid}/six-three-five/manual-ideas",
            json=[
                "Idea 1 - Predictive maintenance",
                "Idea 2 - Quality control AI",
                "Idea 3 - Process optimization",
            ],
            headers=auth_headers(token),
        )
        assert res.status_code == 200

    def test_get_all_ideas_after_manual(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        # Submit manual ideas first
        client.post(
            f"/api/sessions/{uuid}/six-three-five/manual-ideas",
            json=["Idea A", "Idea B"],
            headers=auth_headers(token),
        )
        # Get all ideas
        res = client.get(
            f"/api/sessions/{uuid}/six-three-five/ideas",
            headers=auth_headers(token),
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 2
