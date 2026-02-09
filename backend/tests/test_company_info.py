"""Tests for company info and profile endpoints."""

import pytest


class TestCompanyInfoText:
    """POST text, GET, DELETE company info."""

    def test_submit_text(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        res = client.post(
            f"/api/sessions/{uuid}/company-info/text",
            json={"content": "We are a manufacturing company with 200 employees."},
            headers=auth_headers(token),
        )
        assert res.status_code in (200, 201)
        data = res.json()
        assert data["info_type"] == "text"
        assert "manufacturing" in data["content"]

    def test_get_company_info(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        # Submit first
        client.post(
            f"/api/sessions/{uuid}/company-info/text",
            json={"content": "Test content here"},
            headers=auth_headers(token),
        )
        # Retrieve
        res = client.get(f"/api/sessions/{uuid}/company-info", headers=auth_headers(token))
        assert res.status_code == 200
        items = res.json()
        assert len(items) >= 1
        assert items[0]["content"] == "Test content here"

    def test_delete_company_info(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        # Create
        cr = client.post(
            f"/api/sessions/{uuid}/company-info/text",
            json={"content": "Temp"},
            headers=auth_headers(token),
        )
        info_id = cr.json()["id"]
        # Delete
        res = client.delete(
            f"/api/sessions/{uuid}/company-info/{info_id}",
            headers=auth_headers(token),
        )
        assert res.status_code == 204

    def test_submit_multiple_texts(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        for text in ["Info 1", "Info 2", "Info 3"]:
            client.post(
                f"/api/sessions/{uuid}/company-info/text",
                json={"content": text},
                headers=auth_headers(token),
            )
        res = client.get(f"/api/sessions/{uuid}/company-info", headers=auth_headers(token))
        assert len(res.json()) == 3


class TestCompanyProfile:
    """GET/PUT/DELETE company profile endpoints."""

    def test_get_profile_empty(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        res = client.get(f"/api/sessions/{uuid}/company-profile", headers=auth_headers(token))
        # Should return 200 with null/empty or 404
        assert res.status_code in (200, 404)

    def test_update_profile(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        profile = {
            "name": "Test Corp",
            "industry": "Manufacturing",
            "employee_count": "200",
        }
        res = client.put(
            f"/api/sessions/{uuid}/company-profile",
            json=profile,
            headers=auth_headers(token),
        )
        assert res.status_code == 200

        # Verify
        res2 = client.get(f"/api/sessions/{uuid}/company-profile", headers=auth_headers(token))
        assert res2.status_code == 200
        data = res2.json()
        assert data["name"] == "Test Corp"
        assert data["industry"] == "Manufacturing"
