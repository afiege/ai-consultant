"""
Human Evaluation Rubric for AI Consultation Quality

This rubric defines criteria for evaluating the quality of AI consultation advice
provided to SMEs with limited digitalization/AI knowledge.
"""

RUBRIC = {
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
    }
}


def calculate_weighted_score(scores: dict) -> float:
    """Calculate weighted average score from individual criterion scores."""
    total_weight = sum(RUBRIC[k]["weight"] for k in scores.keys())
    weighted_sum = sum(scores[k] * RUBRIC[k]["weight"] for k in scores.keys())
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


def print_rubric():
    """Print the full rubric for reference."""
    print("=" * 70)
    print("AI CONSULTATION QUALITY EVALUATION RUBRIC")
    print("=" * 70)

    for key, criterion in RUBRIC.items():
        print(f"\n{criterion['name']} (weight: {criterion['weight']})")
        print(f"  {criterion['description']}")
        print("-" * 50)
        for level, desc in criterion['levels'].items():
            print(f"  {level}: {desc}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    print_rubric()
