"""
Human Evaluation Rubric for AI Consultation Quality

This rubric defines criteria for evaluating the quality of AI consultation advice
provided to SMEs with limited digitalization/AI knowledge.

Covers:
- Step 1b: Maturity Assessment (acatech Industry 4.0 Maturity Index)
- Step 4: AI Consultation (CRISP-DM framework)
- Step 5a: Business Case / Potentials (Value Framework)
- Step 5b: Cost Estimation (TCO, ROI analysis)
"""

RUBRIC = {
    # Maturity Assessment Criteria (Step 1b)
    "maturity_integration": {
        "name": "Maturity Assessment Integration",
        "description": "How well the consultation uses the company's maturity assessment results",
        "levels": {
            1: "Maturity assessment completely ignored in consultation",
            2: "Maturity mentioned but not used to tailor recommendations",
            3: "Some recommendations consider maturity level",
            4: "Recommendations well-adapted to company's maturity profile",
            5: "Deeply integrated - recommendations specifically address maturity gaps and build on strengths"
        },
        "weight": 1.0,
        "applies_to": "step4"
    },
    "maturity_appropriate_complexity": {
        "name": "Maturity-Appropriate Complexity",
        "description": "Whether recommended solutions match the company's digital maturity level",
        "levels": {
            1: "Solutions far beyond company's ability to implement given their maturity",
            2: "Some solutions too advanced for current maturity level",
            3: "Mixed - some appropriate, some stretch goals",
            4: "Solutions mostly appropriate with clear progression path",
            5: "Perfectly calibrated to maturity level with staged evolution roadmap"
        },
        "weight": 0.9,
        "applies_to": "step4"
    },
    "relevance": {
        "name": "Relevance to Company",
        "description": "How well the advice relates to the specific company profile",
        "levels": {
            1: "Generic advice that could apply to any company",
            2: "Mentions company details but advice is mostly generic",
            3: "Somewhat tailored to company situation",
            4: "Well-adapted to company's specific context",
            5: "Highly specific, demonstrates deep understanding of company needs"
        },
        "weight": 1.0
    },
    "actionability": {
        "name": "Practical Actionability",
        "description": "How concrete and implementable the recommendations are",
        "levels": {
            1: "Vague, abstract suggestions with no clear next steps",
            2: "Some ideas but unclear how to implement",
            3: "General direction with some concrete steps",
            4: "Clear recommendations with implementation guidance",
            5: "Specific, prioritized action plan with realistic steps for SME"
        },
        "weight": 1.2
    },
    "accuracy": {
        "name": "Technical Accuracy",
        "description": "Correctness of AI/digitalization concepts and feasibility",
        "levels": {
            1: "Contains significant factual errors or impossible suggestions",
            2: "Some inaccuracies or unrealistic recommendations",
            3: "Mostly accurate with minor issues",
            4: "Accurate and realistic for SME context",
            5: "Technically sound with appropriate complexity for SME"
        },
        "weight": 1.0
    },
    "clarity": {
        "name": "Clarity for Non-Experts",
        "description": "How understandable the advice is for people without AI background",
        "levels": {
            1: "Heavy jargon, confusing for non-technical readers",
            2: "Some jargon, requires technical knowledge to understand",
            3: "Understandable but could be clearer",
            4: "Clear explanations, minimal jargon",
            5: "Excellent clarity, explains concepts accessibly, good examples"
        },
        "weight": 1.1
    },
    "completeness": {
        "name": "Framework Completeness",
        "description": "Coverage of CRISP-DM phases (Step 4) or Value Framework (Step 5)",
        "levels": {
            1: "Misses most framework elements",
            2: "Covers few elements superficially",
            3: "Partial coverage of framework",
            4: "Good coverage with minor gaps",
            5: "Comprehensive coverage of all relevant framework elements"
        },
        "weight": 0.9
    },
    "sme_appropriateness": {
        "name": "SME Appropriateness",
        "description": "Suitability of recommendations for small/medium enterprise resources",
        "levels": {
            1: "Suggests enterprise-level solutions beyond SME capacity",
            2: "Some recommendations unrealistic for SME budget/team",
            3: "Mix of appropriate and overly ambitious suggestions",
            4: "Mostly appropriate for SME resources",
            5: "Perfectly scaled for SME constraints, cost-effective solutions"
        },
        "weight": 1.0
    },
    # Cost Estimation Criteria (Step 5b)
    "cost_realism": {
        "name": "Cost Estimate Realism",
        "description": "How realistic and well-grounded the cost estimates are",
        "levels": {
            1: "Wildly inaccurate or missing cost estimates",
            2: "Rough estimates with significant gaps or unrealistic assumptions",
            3: "Reasonable ballpark figures but lacks detail",
            4: "Well-researched estimates with clear assumptions stated",
            5: "Highly realistic estimates with industry benchmarks and justified ranges"
        },
        "weight": 1.0,
        "applies_to": "step5b"
    },
    "cost_completeness": {
        "name": "Cost Coverage Completeness",
        "description": "Coverage of all relevant cost categories (initial, recurring, maintenance, hidden)",
        "levels": {
            1: "Only mentions one cost type, misses major categories",
            2: "Covers basic costs but misses recurring or hidden costs",
            3: "Covers most cost categories with some gaps",
            4: "Comprehensive coverage including maintenance and training",
            5: "Complete TCO analysis including all direct and indirect costs"
        },
        "weight": 1.1,
        "applies_to": "step5b"
    },
    "roi_analysis": {
        "name": "ROI Analysis Quality",
        "description": "Quality of return on investment and payback period analysis",
        "levels": {
            1: "No ROI analysis or completely unrealistic projections",
            2: "Vague mentions of benefits without quantification",
            3: "Basic ROI framework but missing key factors",
            4: "Clear ROI analysis with payback timeline and assumptions",
            5: "Comprehensive ROI with sensitivity analysis and risk factors"
        },
        "weight": 1.0,
        "applies_to": "step5b"
    },
    "cost_transparency": {
        "name": "Cost Transparency",
        "description": "How clearly cost drivers and assumptions are explained",
        "levels": {
            1: "No explanation of how costs were derived",
            2: "Minimal explanation, unclear assumptions",
            3: "Some cost drivers identified but not fully explained",
            4: "Clear explanation of main cost drivers and assumptions",
            5: "Fully transparent with detailed breakdown and justification for each cost"
        },
        "weight": 0.9,
        "applies_to": "step5b"
    }
}


def get_criteria_for_step(step: str = None) -> dict:
    """
    Get rubric criteria for a specific step.

    Args:
        step: One of 'step1b', 'step4', 'step5a', 'step5b', or None for all criteria

    Returns:
        Dictionary of criteria applicable to the step
    """
    if step is None:
        return RUBRIC

    result = {}
    for key, criterion in RUBRIC.items():
        applies_to = criterion.get("applies_to")
        # Include if no specific step is set (general criteria) or if it matches
        if applies_to is None or applies_to == step:
            result[key] = criterion
    return result


def calculate_weighted_score(scores: dict, step: str = None) -> float:
    """
    Calculate weighted average score from individual criterion scores.

    Args:
        scores: Dictionary mapping criterion keys to scores (1-5)
        step: Optional step filter ('step4', 'step5a', 'step5b')

    Returns:
        Weighted average score
    """
    criteria = get_criteria_for_step(step)
    valid_keys = [k for k in scores.keys() if k in criteria]

    if not valid_keys:
        return 0.0

    total_weight = sum(criteria[k]["weight"] for k in valid_keys)
    weighted_sum = sum(scores[k] * criteria[k]["weight"] for k in valid_keys)
    return weighted_sum / total_weight


def get_grade(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 4.5:
        return "A (Excellent)"
    elif score >= 4.0:
        return "B+ (Very Good)"
    elif score >= 3.5:
        return "B (Good)"
    elif score >= 3.0:
        return "C+ (Adequate)"
    elif score >= 2.5:
        return "C (Needs Improvement)"
    else:
        return "D (Poor)"


def print_rubric(step: str = None):
    """
    Print the rubric for reference.

    Args:
        step: Optional filter - 'step1b', 'step4', 'step5a', 'step5b', or None for all
    """
    print("=" * 70)
    print("AI CONSULTATION QUALITY EVALUATION RUBRIC")
    print("=" * 70)

    # Group criteria by step
    general_criteria = []
    step4_maturity_criteria = []
    step5b_criteria = []

    for key, criterion in RUBRIC.items():
        applies_to = criterion.get("applies_to")
        if applies_to == "step5b":
            step5b_criteria.append((key, criterion))
        elif applies_to == "step4" and "maturity" in key:
            step4_maturity_criteria.append((key, criterion))
        elif applies_to is None:
            general_criteria.append((key, criterion))

    # Print maturity-related criteria (Step 1b integration into Step 4)
    if step is None or step in ("step1b", "step4"):
        print("\n" + "-" * 70)
        print("MATURITY ASSESSMENT CRITERIA (Step 1b Integration)")
        print("-" * 70)
        print("These criteria evaluate how well the maturity assessment informs")
        print("the consultation recommendations.")
        for key, criterion in step4_maturity_criteria:
            print(f"\n{criterion['name']} (weight: {criterion['weight']})")
            print(f"  {criterion['description']}")
            print("-" * 50)
            for level, desc in criterion['levels'].items():
                print(f"  {level}: {desc}")

    # Print general criteria (Steps 4 & 5a)
    if step is None or step in ("step4", "step5a"):
        print("\n" + "-" * 70)
        print("GENERAL CRITERIA (Steps 4 & 5a: Consultation & Business Case)")
        print("-" * 70)
        for key, criterion in general_criteria:
            print(f"\n{criterion['name']} (weight: {criterion['weight']})")
            print(f"  {criterion['description']}")
            print("-" * 50)
            for level, desc in criterion['levels'].items():
                print(f"  {level}: {desc}")

    # Print cost estimation criteria (Step 5b)
    if step is None or step == "step5b":
        print("\n" + "-" * 70)
        print("COST ESTIMATION CRITERIA (Step 5b)")
        print("-" * 70)
        for key, criterion in step5b_criteria:
            print(f"\n{criterion['name']} (weight: {criterion['weight']})")
            print(f"  {criterion['description']}")
            print("-" * 50)
            for level, desc in criterion['levels'].items():
                print(f"  {level}: {desc}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    print_rubric()
