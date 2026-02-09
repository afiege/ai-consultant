"""Tests for session CRUD endpoints."""

import pytest


class TestSessionCreate:
    """POST /api/sessions/"""

    def test_create_session_minimal(self, client):
        res = client.post("/api/sessions/", json={"company_name": "Acme"})
        assert res.status_code == 201
        data = res.json()
        assert data["company_name"] == "Acme"
        assert "session_uuid" in data
        assert "access_token" in data
        assert data["status"] == "active"
        assert data["current_step"] == 1

    def test_create_session_with_role(self, client):
        res = client.post("/api/sessions/", json={
            "company_name": "RoleCo",
            "user_role": "business_owner",
        })
        assert res.status_code == 201
        assert res.json()["user_role"] == "business_owner"

    def test_create_session_default_role(self, client):
        res = client.post("/api/sessions/", json={"company_name": "Default"})
        assert res.status_code == 201
        assert res.json()["user_role"] == "consultant"

    def test_create_session_returns_unique_uuids(self, client):
        ids = set()
        for _ in range(5):
            res = client.post("/api/sessions/", json={"company_name": "X"})
            ids.add(res.json()["session_uuid"])
        assert len(ids) == 5


class TestSessionGet:
    """GET /api/sessions/{uuid}"""

    def test_get_session(self, create_session, client, auth_headers):
        uuid, token, _ = create_session("GetMe")
        res = client.get(f"/api/sessions/{uuid}", headers=auth_headers(token))
        assert res.status_code == 200
        assert res.json()["company_name"] == "GetMe"

    def test_get_session_not_found(self, client):
        res = client.get("/api/sessions/nonexistent-uuid")
        assert res.status_code == 404


class TestSessionUpdate:
    """PUT /api/sessions/{uuid}"""

    def test_update_company_name(self, create_session, client, auth_headers):
        uuid, token, _ = create_session("Old")
        res = client.put(
            f"/api/sessions/{uuid}",
            json={"company_name": "New"},
            headers=auth_headers(token),
        )
        assert res.status_code == 200
        assert res.json()["company_name"] == "New"

    def test_update_step(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        res = client.put(
            f"/api/sessions/{uuid}",
            json={"current_step": 3},
            headers=auth_headers(token),
        )
        assert res.status_code == 200
        assert res.json()["current_step"] == 3

    def test_update_step_max_6(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        res = client.put(
            f"/api/sessions/{uuid}",
            json={"current_step": 6},
            headers=auth_headers(token),
        )
        assert res.status_code == 200
        assert res.json()["current_step"] == 6


class TestSessionDelete:
    """DELETE /api/sessions/{uuid}"""

    def test_delete_session(self, create_session, client, auth_headers):
        uuid, token, _ = create_session("Gone")
        res = client.delete(f"/api/sessions/{uuid}", headers=auth_headers(token))
        assert res.status_code == 204

        # Verify deleted
        res2 = client.get(f"/api/sessions/{uuid}", headers=auth_headers(token))
        assert res2.status_code == 404


class TestSessionList:
    """GET /api/sessions/"""

    def test_list_sessions_empty(self, client):
        res = client.get("/api/sessions/")
        assert res.status_code == 200
        assert res.json() == []

    def test_list_sessions_multiple(self, create_session, client):
        for name in ["A", "B", "C"]:
            create_session(name)
        res = client.get("/api/sessions/")
        assert res.status_code == 200
        assert len(res.json()) == 3


class TestReflections:
    """GET/PUT reflections endpoints."""

    def test_get_empty_reflections(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        res = client.get(f"/api/sessions/{uuid}/reflections", headers=auth_headers(token))
        assert res.status_code == 200
        assert res.json() == {}

    def test_save_and_get_reflection(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()

        # Save a reflection
        payload = {"surprised": "AI was helpful", "confidence": 4, "explore": "More ML"}
        res = client.put(
            f"/api/sessions/{uuid}/reflections/step3",
            json=payload,
            headers=auth_headers(token),
        )
        assert res.status_code == 200

        # Retrieve
        res2 = client.get(f"/api/sessions/{uuid}/reflections", headers=auth_headers(token))
        data = res2.json()
        assert "step3" in data
        assert data["step3"]["confidence"] == 4
