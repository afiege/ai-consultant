"""Tests for maturity assessment scoring logic."""

import pytest
from pydantic import ValidationError
from app.schemas.maturity_assessment import get_maturity_level_name, MaturityAssessmentCreate


class TestGetMaturityLevelName:
    """Tests for score-to-level-name mapping."""

    def test_computerization_low(self):
        assert get_maturity_level_name(1.0) == "Computerization"

    def test_computerization_boundary(self):
        assert get_maturity_level_name(1.49) == "Computerization"

    def test_connectivity_at_boundary(self):
        assert get_maturity_level_name(1.5) == "Connectivity"

    def test_connectivity_mid(self):
        assert get_maturity_level_name(2.0) == "Connectivity"

    def test_connectivity_upper(self):
        assert get_maturity_level_name(2.49) == "Connectivity"

    def test_visibility_at_boundary(self):
        assert get_maturity_level_name(2.5) == "Visibility"

    def test_visibility_mid(self):
        assert get_maturity_level_name(3.0) == "Visibility"

    def test_transparency_at_boundary(self):
        assert get_maturity_level_name(3.5) == "Transparency"

    def test_transparency_mid(self):
        assert get_maturity_level_name(4.0) == "Transparency"

    def test_predictive_at_boundary(self):
        assert get_maturity_level_name(4.5) == "Predictive Capacity"

    def test_predictive_mid(self):
        assert get_maturity_level_name(5.0) == "Predictive Capacity"

    def test_adaptability_at_boundary(self):
        assert get_maturity_level_name(5.5) == "Adaptability"

    def test_adaptability_max(self):
        assert get_maturity_level_name(6.0) == "Adaptability"


class TestMaturityAssessmentCreate:
    """Tests for Pydantic validation of maturity assessment input."""

    def test_valid_scores(self):
        assessment = MaturityAssessmentCreate(
            resources_score=3.0,
            information_systems_score=2.5,
            culture_score=4.0,
            organizational_structure_score=1.5,
        )
        assert assessment.resources_score == 3.0
        assert assessment.culture_score == 4.0

    def test_min_valid_score(self):
        assessment = MaturityAssessmentCreate(
            resources_score=1.0,
            information_systems_score=1.0,
            culture_score=1.0,
            organizational_structure_score=1.0,
        )
        assert assessment.resources_score == 1.0

    def test_max_valid_score(self):
        assessment = MaturityAssessmentCreate(
            resources_score=6.0,
            information_systems_score=6.0,
            culture_score=6.0,
            organizational_structure_score=6.0,
        )
        assert assessment.resources_score == 6.0

    def test_score_too_low(self):
        with pytest.raises(ValidationError):
            MaturityAssessmentCreate(
                resources_score=0.5,
                information_systems_score=3.0,
                culture_score=3.0,
                organizational_structure_score=3.0,
            )

    def test_score_too_high(self):
        with pytest.raises(ValidationError):
            MaturityAssessmentCreate(
                resources_score=3.0,
                information_systems_score=6.5,
                culture_score=3.0,
                organizational_structure_score=3.0,
            )

    def test_optional_details(self):
        assessment = MaturityAssessmentCreate(
            resources_score=3.0,
            resources_details={"q1": 3.0, "q2": 3.0},
            information_systems_score=2.0,
            culture_score=4.0,
            organizational_structure_score=2.0,
        )
        assert assessment.resources_details == {"q1": 3.0, "q2": 3.0}
        assert assessment.information_systems_details is None


class TestOverallScoreCalculation:
    """Tests for overall score computation (avg of 4 dimensions, 1 decimal)."""

    @pytest.mark.parametrize("scores,expected", [
        ((2.0, 2.25, 2.5, 2.0), 2.2),
        ((1.0, 1.0, 1.0, 1.0), 1.0),
        ((6.0, 6.0, 6.0, 6.0), 6.0),
        ((3.0, 4.0, 5.0, 2.0), 3.5),
        ((1.5, 2.5, 3.5, 4.5), 3.0),
    ])
    def test_overall_score(self, scores, expected):
        r, i, c, o = scores
        result = round((r + i + c + o) / 4, 1)
        assert result == expected
