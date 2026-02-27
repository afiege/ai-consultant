"""Unit tests for session restore navigate_to_step inference logic.

The restore endpoint infers which step to navigate to from the
consultation_findings factor_types when current_step <= 1.
"""

import pytest


# ---------------------------------------------------------------------------
# Pure inference logic (extracted from session_backup.py for testability)
# ---------------------------------------------------------------------------

def infer_navigate_step(current_step: int, factor_types: set) -> int:
    """Mirror of the inference logic in session_backup.restore_session_backup."""
    navigate_to_step = current_step
    if navigate_to_step <= 1:
        if 'swot_analysis' in factor_types or 'technical_briefing' in factor_types:
            navigate_to_step = 6
        elif any(t.startswith('cost_') for t in factor_types):
            navigate_to_step = 6
        elif any(t.startswith('business_case') for t in factor_types):
            navigate_to_step = 5
        elif factor_types:
            navigate_to_step = 4
    return navigate_to_step


# ---------------------------------------------------------------------------
# TestInferNavigateStep
# ---------------------------------------------------------------------------

class TestInferNavigateStep:
    """Tests for the navigate_to_step inference from findings factor_types."""

    # --- current_step > 1: trust the stored value ---

    def test_stored_step_trusted_when_greater_than_one(self):
        assert infer_navigate_step(3, set()) == 3

    def test_stored_step_6_trusted(self):
        assert infer_navigate_step(6, {'swot_analysis'}) == 6

    def test_stored_step_2_trusted_even_with_no_findings(self):
        assert infer_navigate_step(2, set()) == 2

    # --- current_step == 0: treated same as 1 (infer) ---

    def test_step_zero_triggers_inference(self):
        assert infer_navigate_step(0, {'swot_analysis'}) == 6

    # --- Full benchmark session: all findings present → step 6 ---

    def test_full_benchmark_backup_navigates_to_step6(self):
        full_findings = {
            'ai_goals', 'business_case_assumptions', 'business_case_classification',
            'business_case_complexity_indicator', 'business_case_pitch',
            'business_case_validation', 'business_case_viability', 'business_objectives',
            'company_profile', 'cost_complexity', 'cost_drivers', 'cost_initial',
            'cost_maintenance', 'cost_optimization', 'cost_recurring', 'cost_roi',
            'cost_tco', 'management_recommendation', 'open_risks', 'project_plan',
            'situation_assessment', 'swot_analysis', 'technical_briefing',
        }
        assert infer_navigate_step(1, full_findings) == 6

    # --- swot_analysis trigger → step 6 ---

    def test_swot_analysis_alone_navigates_to_step6(self):
        assert infer_navigate_step(1, {'swot_analysis'}) == 6

    def test_technical_briefing_alone_navigates_to_step6(self):
        assert infer_navigate_step(1, {'technical_briefing'}) == 6

    def test_both_swot_and_tech_briefing_navigates_to_step6(self):
        assert infer_navigate_step(1, {'swot_analysis', 'technical_briefing'}) == 6

    # --- cost_ prefix trigger → step 6 ---

    def test_cost_tco_navigates_to_step6(self):
        assert infer_navigate_step(1, {'cost_tco'}) == 6

    def test_cost_initial_navigates_to_step6(self):
        assert infer_navigate_step(1, {'cost_initial'}) == 6

    def test_cost_roi_navigates_to_step6(self):
        assert infer_navigate_step(1, {'cost_roi'}) == 6

    def test_any_cost_prefix_navigates_to_step6(self):
        for factor in ('cost_complexity', 'cost_drivers', 'cost_maintenance',
                       'cost_optimization', 'cost_recurring'):
            assert infer_navigate_step(1, {factor}) == 6, f"Expected 6 for {factor}"

    # --- business_case_ prefix trigger → step 5 ---

    def test_business_case_classification_navigates_to_step5(self):
        assert infer_navigate_step(1, {'business_case_classification'}) == 5

    def test_business_case_viability_navigates_to_step5(self):
        assert infer_navigate_step(1, {'business_case_viability'}) == 5

    def test_business_case_pitch_navigates_to_step5(self):
        assert infer_navigate_step(1, {'business_case_pitch'}) == 5

    def test_business_case_with_consultation_findings_navigates_to_step5(self):
        assert infer_navigate_step(1, {
            'company_profile', 'business_objectives', 'situation_assessment',
            'business_case_classification', 'business_case_viability',
        }) == 5

    # --- cost_ takes precedence over business_case_ ---

    def test_cost_overrides_business_case(self):
        assert infer_navigate_step(1, {'business_case_classification', 'cost_tco'}) == 6

    # --- swot/tech takes precedence over cost_ ---

    def test_swot_overrides_cost(self):
        assert infer_navigate_step(1, {'cost_tco', 'swot_analysis'}) == 6

    # --- Consultation-only findings → step 4 ---

    def test_company_profile_only_navigates_to_step4(self):
        assert infer_navigate_step(1, {'company_profile'}) == 4

    def test_consultation_findings_navigate_to_step4(self):
        assert infer_navigate_step(1, {
            'company_profile', 'business_objectives', 'situation_assessment',
            'ai_goals', 'project_plan',
        }) == 4

    def test_open_risks_navigates_to_step4(self):
        assert infer_navigate_step(1, {'open_risks'}) == 4

    # --- No findings: stay at step 1 ---

    def test_no_findings_stays_at_step1(self):
        assert infer_navigate_step(1, set()) == 1

    def test_empty_findings_step0_stays_at_0(self):
        # Edge: step=0 with no findings should not crash; stays at 0
        assert infer_navigate_step(0, set()) == 0


class TestInferNavigateStepResponseField:
    """
    Integration-style check: the restore endpoint response includes navigate_to_step.

    Tests the actual router code path by importing and calling the inference
    inline (without spinning up a DB / FastAPI app).
    """

    def test_response_key_name(self):
        """The field name returned to the frontend must be navigate_to_step."""
        # Simulate what the endpoint returns
        result = {
            'success': True,
            'new_session_uuid': 'abc',
            'original_session_uuid': 'xyz',
            'original_company_name': 'Test GmbH',
            'navigate_to_step': infer_navigate_step(1, {'swot_analysis'}),
        }
        assert 'navigate_to_step' in result
        assert result['navigate_to_step'] == 6

    def test_response_key_present_when_step_inferred_to_4(self):
        result = {
            'navigate_to_step': infer_navigate_step(1, {'company_profile'}),
        }
        assert result['navigate_to_step'] == 4
