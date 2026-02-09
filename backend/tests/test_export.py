"""Tests for the export / findings aggregation endpoints."""

import pytest


class TestAllFindings:
    """GET /api/sessions/{uuid}/all-findings"""

    def test_get_all_findings_empty_session(self, create_session, client, auth_headers):
        uuid, token, _ = create_session("EmptyCo")
        res = client.get(
            f"/api/sessions/{uuid}/all-findings",
            headers=auth_headers(token),
        )
        assert res.status_code == 200
        data = res.json()
        # Should return a dict structure even when empty
        assert isinstance(data, dict)


class TestExportData:
    """GET /api/sessions/{uuid}/export/data"""

    def test_export_data(self, create_session, client, auth_headers):
        uuid, token, _ = create_session("ExportCo")
        res = client.get(
            f"/api/sessions/{uuid}/export/data",
            headers=auth_headers(token),
        )
        assert res.status_code == 200
        data = res.json()
        assert "session" in data


class TestCrossReferences:
    """GET /api/sessions/{uuid}/cross-references"""

    def test_get_cross_refs_empty(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        res = client.get(
            f"/api/sessions/{uuid}/cross-references",
            headers=auth_headers(token),
        )
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, (list, dict))


class TestSwotAndBriefing:
    """GET existing SWOT / briefing (should be empty for fresh session)."""

    def test_get_swot_empty(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        res = client.get(
            f"/api/sessions/{uuid}/swot-analysis",
            headers=auth_headers(token),
        )
        assert res.status_code in (200, 404)

    def test_get_briefing_empty(self, create_session, client, auth_headers):
        uuid, token, _ = create_session()
        res = client.get(
            f"/api/sessions/{uuid}/transition-briefing",
            headers=auth_headers(token),
        )
        assert res.status_code in (200, 404)
