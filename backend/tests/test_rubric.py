"""Tests for evaluation rubric scoring logic."""

import sys
import os
import pytest

# Add evaluation dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'evaluation'))

from rubric import RUBRIC, get_criteria_for_step, calculate_weighted_score, get_grade


class TestRubricIntegrity:
    """Tests that the RUBRIC dict is well-formed."""

    def test_all_criteria_have_required_keys(self):
        required_keys = {"name", "description", "levels", "weight"}
        for key, criterion in RUBRIC.items():
            for rk in required_keys:
                assert rk in criterion, f"Criterion '{key}' missing key '{rk}'"

    def test_all_criteria_have_five_levels(self):
        for key, criterion in RUBRIC.items():
            assert set(criterion["levels"].keys()) == {1, 2, 3, 4, 5}, \
                f"Criterion '{key}' does not have levels 1-5"

    def test_weights_are_positive(self):
        for key, criterion in RUBRIC.items():
            assert criterion["weight"] > 0, f"Criterion '{key}' has non-positive weight"

    def test_total_criteria_count(self):
        assert len(RUBRIC) == 12


class TestGetCriteriaForStep:
    """Tests for step-based criteria filtering."""

    def test_none_returns_all(self):
        result = get_criteria_for_step(None)
        assert len(result) == 12

    def test_step4_includes_general_and_maturity(self):
        result = get_criteria_for_step("step4")
        assert "relevance" in result  # general (no applies_to)
        assert "maturity_integration" in result  # step4 specific
        assert "maturity_appropriate_complexity" in result

    def test_step4_excludes_cost_criteria(self):
        result = get_criteria_for_step("step4")
        assert "cost_realism" not in result
        assert "cost_completeness" not in result
        assert "roi_analysis" not in result
        assert "cost_transparency" not in result

    def test_step5b_includes_general_and_cost(self):
        result = get_criteria_for_step("step5b")
        assert "relevance" in result  # general
        assert "cost_realism" in result
        assert "cost_completeness" in result
        assert "roi_analysis" in result
        assert "cost_transparency" in result

    def test_step5b_excludes_maturity(self):
        result = get_criteria_for_step("step5b")
        assert "maturity_integration" not in result
        assert "maturity_appropriate_complexity" not in result

    def test_step5a_includes_general_only(self):
        result = get_criteria_for_step("step5a")
        assert "relevance" in result
        assert "actionability" in result
        # Should exclude step-specific criteria
        assert "maturity_integration" not in result
        assert "cost_realism" not in result


class TestCalculateWeightedScore:
    """Tests for weighted score calculation."""

    def test_perfect_scores(self):
        scores = {k: 5 for k in RUBRIC.keys()}
        result = calculate_weighted_score(scores)
        assert result == 5.0

    def test_minimum_scores(self):
        scores = {k: 1 for k in RUBRIC.keys()}
        result = calculate_weighted_score(scores)
        assert result == 1.0

    def test_empty_scores(self):
        result = calculate_weighted_score({})
        assert result == 0.0

    def test_partial_scores(self):
        scores = {"relevance": 4, "actionability": 3}
        result = calculate_weighted_score(scores)
        # relevance: 4 * 1.0 = 4.0, actionability: 3 * 1.2 = 3.6
        # total weight: 1.0 + 1.2 = 2.2
        # expected: 7.6 / 2.2 ≈ 3.4545
        assert abs(result - 7.6 / 2.2) < 0.001

    def test_step_filter(self):
        scores = {"cost_realism": 4, "relevance": 3}
        result = calculate_weighted_score(scores, step="step5b")
        # Both should be included in step5b
        assert result > 0

    def test_unknown_keys_ignored(self):
        scores = {"relevance": 4, "fake_criterion": 5}
        result = calculate_weighted_score(scores)
        # Only relevance should count: 4 * 1.0 / 1.0 = 4.0
        assert result == 4.0


class TestGetGrade:
    """Tests for score-to-grade mapping."""

    def test_excellent(self):
        assert "A" in get_grade(4.5)
        assert "A" in get_grade(5.0)

    def test_very_good(self):
        assert "B+" in get_grade(4.0)
        assert "B+" in get_grade(4.49)

    def test_good(self):
        assert get_grade(3.5).startswith("B ")
        assert get_grade(3.99).startswith("B ")

    def test_adequate(self):
        assert "C+" in get_grade(3.0)
        assert "C+" in get_grade(3.49)

    def test_needs_improvement(self):
        assert get_grade(2.5) == "C (Needs Improvement)"
        assert get_grade(2.99) == "C (Needs Improvement)"

    def test_poor(self):
        assert "D" in get_grade(2.4)
        assert "D" in get_grade(1.0)
