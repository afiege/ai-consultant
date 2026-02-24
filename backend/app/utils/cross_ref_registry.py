"""Cross-reference registry — single source of truth for wiki-link section IDs."""

# Canonical IDs (must match keys in WIKI_LINK_MAP in WikiLinkMarkdown.jsx)
SECTION_LABELS = {
    "en": {
        "company_profile": "Company Profile",
        "maturity_assessment": "Maturity Assessment",
        "business_objectives": "Business Objectives",
        "situation_assessment": "Situation Assessment",
        "ai_goals": "AI Goals",
        "project_plan": "Project Plan",
        "business_case": "Business Case",
        "cost_tco": "Cost Estimation",
        "swot_analysis": "SWOT Analysis",
        "technical_briefing": "Technical Briefing",
    },
    "de": {
        "company_profile": "Unternehmensprofil",
        "maturity_assessment": "Reifegradanalyse",
        "business_objectives": "Geschäftsziele",
        "situation_assessment": "Situationsanalyse",
        "ai_goals": "KI-Ziele",
        "project_plan": "Projektplan",
        "business_case": "Business Case",
        "cost_tco": "Kostenschätzung",
        "swot_analysis": "SWOT-Analyse",
        "technical_briefing": "Technical Briefing",
    },
}

# All valid navigable IDs
ALL_IDS = set(SECTION_LABELS["en"].keys())

# Step availability: only IDs that exist when the step runs
STEP_AVAILABLE_IDS = {
    "consultation": [
        "company_profile",
        "maturity_assessment",
    ],
    "business_case": [
        "company_profile",
        "maturity_assessment",
        "business_objectives",
        "situation_assessment",
        "ai_goals",
        "project_plan",
    ],
    "cost_estimation": [
        "company_profile",
        "maturity_assessment",
        "business_objectives",
        "situation_assessment",
        "ai_goals",
        "project_plan",
        "business_case",
    ],
    "swot": [
        "company_profile",
        "maturity_assessment",
        "business_objectives",
        "situation_assessment",
        "ai_goals",
        "project_plan",
        "business_case",
        "cost_tco",
    ],
    "technical_briefing": [
        "company_profile",
        "maturity_assessment",
        "business_objectives",
        "situation_assessment",
        "ai_goals",
        "project_plan",
        "business_case",
        "cost_tco",
        "swot_analysis",
    ],
}


def build_cross_ref_block(lang: str, step: str) -> str:
    """Generate the cross-reference instruction block for a prompt."""
    ids = STEP_AVAILABLE_IDS.get(step, [])
    labels = SECTION_LABELS.get(lang, SECTION_LABELS["en"])
    lines = [f"- [[{sid}|{labels[sid]}]]" for sid in ids if sid in labels]
    if lang == "de":
        header = "## QUERVERWEISE"
        instruction = "Verwende Wiki-Link-Syntax [[section_id|Anzeigetext]] für Verweise:"
    else:
        header = "## CROSS-REFERENCE LINKS"
        instruction = "Use wiki-link syntax [[section_id|Display Text]] when referencing:"
    return f"\n{header}\n{instruction}\n" + "\n".join(lines) + "\n"
