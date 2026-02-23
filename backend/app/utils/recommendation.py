"""Pure-function management recommendation generator.

This module is intentionally free of DB / LLM / PDF dependencies so it can be
imported from both pdf_generator.py and the consultation router without pulling
in heavy optional dependencies (WeasyPrint, etc.).
"""

from typing import Optional


def generate_management_recommendation(
    findings: dict,
    top_idea: Optional[str],
    company_name: str,
) -> str:
    """Generate a markdown recommendation string from available findings.

    Args:
        findings: Flat dict mapping factor_type → plain-text value (or None).
        top_idea: The top-voted idea text, used as fallback when no business case.
        company_name: The client company name shown in the recommendation.
    """
    company = company_name or "the organisation"
    has_bc = findings.get("business_case_classification") or findings.get("business_case_calculation")
    has_costs = findings.get("cost_tco") or findings.get("cost_initial")
    has_roi = findings.get("cost_roi")
    has_objectives = findings.get("business_objectives")

    parts = []
    if has_bc and has_costs and has_roi:
        parts.append(
            f"**Based on the comprehensive analysis conducted, we recommend {company} "
            "proceed with the proposed AI initiative.**"
        )
        parts.append(
            "\n\nThe business case demonstrates clear value potential, and the cost estimation "
            "provides a realistic investment framework. "
        )
        c = (findings.get("cost_complexity") or "").lower()
        if "quick win" in c:
            parts.append("As a **Quick Win** project, this initiative offers low risk and rapid time-to-value. ")
        elif "standard" in c:
            parts.append("As a **Standard** complexity project, this initiative balances ambition with manageable risk. ")
        elif "complex" in c or "enterprise" in c:
            parts.append("Given the project's complexity, we recommend a phased approach starting with a pilot. ")
        parts.append(
            "\n\n**Next Steps:** Validate assumptions with stakeholders, "
            "secure budget approval, and initiate the pilot phase."
        )
    elif has_bc and has_costs:
        parts.append(f"**The analysis indicates a viable AI opportunity for {company}.**")
        parts.append(
            "\n\nA clear business case has been established with cost estimates. We recommend conducting "
            "a detailed ROI analysis to strengthen the investment justification before proceeding."
        )
    elif has_bc:
        parts.append(f"**The identified AI opportunity shows promise for {company}.**")
        parts.append(
            "\n\nThe business case indicates potential value. We recommend completing the cost estimation "
            "(Step 5b) to understand the investment requirements before making a go/no-go decision."
        )
    elif has_objectives and top_idea:
        parts.append(f"**An AI opportunity has been identified for {company}.**")
        parts.append(
            f'\n\nThe focus project "{top_idea}" aligns with documented business objectives. '
            "We recommend completing the business case analysis (Step 5a) and cost estimation (Step 5b) "
            "to evaluate feasibility."
        )
    else:
        parts.append(f"**This report documents the initial AI/digitalisation exploration for {company}.**")
        parts.append(
            "\n\nTo generate a complete recommendation, please ensure all consultation phases are "
            "completed, including business case analysis and cost estimation."
        )
    return "".join(parts)
