"""Tests for maturity assessment endpoints."""

import pytest


class TestMaturityAssessment:
    """Maturity assessment CRUD."""

    def test_create_maturity_assessment(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        payload = {
            "resources_score": 3.5,
            "resources_details": {"level": 3.5, "notes": 3.0},
            "information_systems_score": 2.0,
            "information_systems_details": {"level": 2.0},
            "culture_score": 4.0,
            "culture_details": {"level": 4.0},
            "organizational_structure_score": 3.0,
            "organizational_structure_details": {"level": 3.0},
        }
        res = client.post(
            f"/api/sessions/{uuid}/maturity",
            json=payload,
            headers=auth_headers(token),
        )
        assert res.status_code == 200
        data = res.json()
        # Server calculates overall_score = avg(3.5, 2.0, 4.0, 3.0) = 3.1
        assert data["overall_score"] == 3.1
        assert "maturity_level" in data

    def test_get_maturity_assessment(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        # Create
        client.post(
            f"/api/sessions/{uuid}/maturity",
            json={
                "resources_score": 2.0,
                "information_systems_score": 2.0,
                "culture_score": 2.0,
                "organizational_structure_score": 2.0,
            },
            headers=auth_headers(token),
        )
        # Retrieve
        res = client.get(f"/api/sessions/{uuid}/maturity", headers=auth_headers(token))
        assert res.status_code == 200
        assert "maturity_level" in res.json()

    def test_get_maturity_levels(self, client):
        res = client.get("/api/sessions/maturity/levels")
        assert res.status_code == 200
        levels = res.json()
        assert isinstance(levels, list)
        assert len(levels) > 0

    def test_update_maturity_assessment(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        # Create initial
        client.post(
            f"/api/sessions/{uuid}/maturity",
            json={
                "resources_score": 1.0,
                "information_systems_score": 1.0,
                "culture_score": 1.0,
                "organizational_structure_score": 1.0,
                "overall_score": 1.0,
                "maturity_level": "Computerization",
            },
            headers=auth_headers(token),
        )
        # Update
        res = client.post(
            f"/api/sessions/{uuid}/maturity",
            json={
                "resources_score": 5.0,
                "information_systems_score": 5.0,
                "culture_score": 5.0,
                "organizational_structure_score": 5.0,
                "overall_score": 5.0,
                "maturity_level": "Adaptability",
            },
            headers=auth_headers(token),
        )
        assert res.status_code in (200, 201)
        assert res.json()["overall_score"] == 5.0
