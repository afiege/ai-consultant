"""Service for AI participants that generate ideas using LiteLLM (multi-provider)."""

from typing import List, Optional, Dict
from litellm import completion
import logging

from .default_prompts import get_prompt
from ..utils.llm import apply_model_params

logger = logging.getLogger(__name__)

# Each of the 6 AI participants gets a distinct strategic perspective to prevent
# all participants from converging on the same theme (e.g., predictive maintenance).
PARTICIPANT_PERSPECTIVES = {
    "en": [
        {
            "name": "Operations & Process Automation",
            "description": "Focus on automating repetitive manual tasks, improving production workflows, scheduling, and operational efficiency using AI and digital tools.",
        },
        {
            "name": "Quality, Safety & Compliance",
            "description": "Focus on AI-driven quality control, defect detection, inspection automation, compliance monitoring, and error prevention.",
        },
        {
            "name": "Employee Empowerment & Knowledge",
            "description": "Focus on AI-assisted training, knowledge management systems, employee productivity tools, safety monitoring, and skill development.",
        },
        {
            "name": "Analytics & Business Intelligence",
            "description": "Focus on KPI dashboards, predictive analytics, data-driven decision-making, reporting automation, and business performance monitoring.",
        },
        {
            "name": "Supply Chain & Procurement",
            "description": "Focus on inventory optimization, demand forecasting, supplier management, logistics automation, and reducing procurement costs.",
        },
    ],
    "de": [
        {
            "name": "Betrieb & Prozessautomatisierung",
            "description": "Konzentrieren Sie sich auf die Automatisierung repetitiver manueller Aufgaben, Verbesserung von Produktionsabläufen, Planung und Betriebseffizienz mit KI und digitalen Werkzeugen.",
        },
        {
            "name": "Qualität, Sicherheit & Compliance",
            "description": "Konzentrieren Sie sich auf KI-gestützte Qualitätskontrolle, Fehlererkennung, Inspektionsautomatisierung, Compliance-Überwachung und Fehlervermeidung.",
        },
        {
            "name": "Mitarbeiterempowerment & Wissen",
            "description": "Konzentrieren Sie sich auf KI-gestützte Schulungen, Wissensmanagement, Mitarbeiterproduktivitätswerkzeuge, Sicherheitsüberwachung und Kompetenzentwicklung.",
        },
        {
            "name": "Analytics & Business Intelligence",
            "description": "Konzentrieren Sie sich auf KPI-Dashboards, prädiktive Analysen, datengestützte Entscheidungsfindung, Berichtsautomatisierung und Unternehmensleistungsüberwachung.",
        },
        {
            "name": "Lieferkette & Einkauf",
            "description": "Konzentrieren Sie sich auf Bestandsoptimierung, Nachfrageprognosen, Lieferantenmanagement, Logistikautomatisierung und Senkung der Beschaffungskosten.",
        },
    ],
}


class AIParticipant:
    """AI participant that generates ideas for 6-3-5 brainstorming using LiteLLM."""

    def __init__(
        self,
        model: str = "mistral/mistral-small-latest",
        custom_prompts: Optional[Dict[str, str]] = None,
        language: str = "en",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        temperature: Optional[float] = None
    ):
        """
        Initialize AI participant with LiteLLM model.

        Args:
            model: LiteLLM model string (e.g., "mistral/mistral-small-latest", "openai/gpt-4")
            custom_prompts: Optional dict of custom prompt overrides
            language: Language code ("en" or "de")
            api_key: Optional API key (uses provider's env var if not provided)
            api_base: Optional custom API base URL for OpenAI-compatible endpoints
            temperature: Optional temperature override for generation
        """
        self.model = model
        self.custom_prompts = custom_prompts or {}
        self.language = language
        self.api_key = api_key
        self.api_base = api_base
        self.temperature = temperature

    def generate_ideas(
        self,
        company_context: str,
        previous_ideas: List[str],
        round_number: int,
        participant_number: int,
        all_session_ideas: Optional[List[str]] = None
    ) -> List[str]:
        """
        Generate 3 new ideas for the brainstorming session.

        Args:
            company_context: Summary of company information from Step 1
            previous_ideas: Ideas from previous rounds on this sheet
            round_number: Current round number (1-6)
            participant_number: AI participant number (1-6)
            all_session_ideas: All ideas already created in this session (to avoid duplicates)

        Returns:
            List of 3 ideas
        """
        # Build the prompt
        system_prompt = self._build_system_prompt(company_context, participant_number, round_number)
        user_prompt = self._build_user_prompt(
            previous_ideas,
            round_number,
            participant_number,
            all_session_ideas or []
        )

        # Call LLM via LiteLLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            # Build completion kwargs
            completion_kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature or 0.7,  # Balanced temperature for creativity with consistency
                "max_tokens": 600  # Each idea is 2 sentences; 3 ideas need more room
            }
            if self.api_key:
                completion_kwargs["api_key"] = self.api_key
            if self.api_base:
                completion_kwargs["api_base"] = self.api_base
            apply_model_params(completion_kwargs)

            response = completion(**completion_kwargs)

            # Parse response (LiteLLM returns OpenAI-compatible format)
            content = response.choices[0].message.content
            ideas = self._parse_ideas(content)

            # Ensure we have exactly 3 ideas
            if len(ideas) < 3:
                if self.language == "de":
                    ideas.extend([f"KI-Idee {i+1} (einzigartig) für Runde {round_number}" for i in range(len(ideas), 3)])
                else:
                    ideas.extend([f"AI Idea {i+1} (unique) for round {round_number}" for i in range(len(ideas), 3)])
            elif len(ideas) > 3:
                ideas = ideas[:3]

            return ideas

        except Exception as e:
            # Fallback to generic ideas if API fails
            logger.error(f"AI participant error: {e}")
            if self.language == "de":
                return [f"KI-Teilnehmer {participant_number} - Idee {i+1} für Runde {round_number}" for i in range(3)]
            return [
                f"AI Participant {participant_number} - Unique Idea {i+1} for round {round_number}" for i in range(3)
            ]

    def _build_system_prompt(self, company_context: str, participant_number: int = 1, round_number: int = 1) -> str:
        """Build the system prompt with company context and participant-specific perspective."""
        template = get_prompt(
            "brainstorming_system",
            self.language,
            self.custom_prompts
        )
        base = template.format(company_context=company_context)

        # Round 1 only: inject a unique perspective per participant to seed diversity.
        # Subsequent rounds freely build on the rotating sheet (that's the 6-3-5 spirit).
        if round_number == 1:
            perspectives = PARTICIPANT_PERSPECTIVES.get(self.language, PARTICIPANT_PERSPECTIVES["en"])
            idx = (participant_number - 1) % len(perspectives)
            p = perspectives[idx]
            if self.language == "de":
                perspective_section = (
                    f"\n## Ihre Perspektive für Runde 1\n"
                    f"**{p['name']}**: {p['description']}\n\n"
                    f"Starten Sie mit Ideen aus diesem Bereich, um thematische Vielfalt "
                    f"in der Sitzung zu gewährleisten."
                )
            else:
                perspective_section = (
                    f"\n## Your Perspective for Round 1\n"
                    f"**{p['name']}**: {p['description']}\n\n"
                    f"Start with ideas from this domain to ensure thematic diversity across the session."
                )
            return base + perspective_section
        return base

    def _build_user_prompt(
        self,
        previous_ideas: List[str],
        round_number: int,
        participant_number: int,
        all_session_ideas: List[str]
    ) -> str:
        """Build the user prompt based on previous ideas and context."""
        # Build the uniqueness constraint section (ideas to avoid repeating)
        uniqueness_note = ""
        if all_session_ideas and len(all_session_ideas) > len(previous_ideas):
            # Other ideas from the session (not on this sheet) to avoid duplicating
            other_ideas = [i for i in all_session_ideas if i not in previous_ideas]
            if other_ideas:
                sample = other_ideas[:10]
                ideas_list = "\n".join([f"  - {idea}" for idea in sample])
                if self.language == "de":
                    note_header = "Hinweis: Diese Ideen wurden bereits von anderen in dieser Sitzung vorgeschlagen (Wiederholungen vermeiden):"
                    more_suffix = f"(und {len(other_ideas) - 10} weitere)" if len(other_ideas) > 10 else ""
                else:
                    note_header = "Note: These ideas have been suggested by others in this session (avoid duplicating them):"
                    more_suffix = f"(and {len(other_ideas) - 10} more)" if len(other_ideas) > 10 else ""
                uniqueness_note = f"\n{note_header}\n{ideas_list}\n{more_suffix}\n"

        if round_number == 1 or not previous_ideas:
            # First round - generate fresh ideas based on company context
            template = get_prompt(
                "brainstorming_round1",
                self.language,
                self.custom_prompts
            )
            return template.format(
                round_number=round_number,
                uniqueness_note=uniqueness_note
            )
        else:
            # Subsequent rounds - read and build on previous ideas like a human would
            previous_ideas_numbered = "\n".join([f"  {i+1}. {idea}" for i, idea in enumerate(previous_ideas)])

            template = get_prompt(
                "brainstorming_subsequent",
                self.language,
                self.custom_prompts
            )
            return template.format(
                round_number=round_number,
                previous_ideas_numbered=previous_ideas_numbered,
                uniqueness_note=uniqueness_note
            )

    def _parse_ideas(self, content: str) -> List[str]:
        """
        Parse ideas from AI response.

        Each idea spans two lines: a numbered title line followed by an
        explanation sentence (possibly indented). Both are concatenated
        into a single string separated by a space.

        Returns:
            List of ideas (each idea = title + " " + explanation)
        """
        ideas = []
        lines = content.strip().split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            matched = False
            for prefix in ['1.', '2.', '3.', '1)', '2)', '3)']:
                if line.startswith(prefix):
                    title = line[len(prefix):].strip()
                    # Look ahead for the explanation sentence (non-empty, non-numbered)
                    explanation = ''
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()
                        if not next_line:
                            j += 1
                            continue
                        # Stop if we hit the next numbered idea
                        if next_line and next_line[0].isdigit():
                            break
                        explanation = next_line
                        i = j  # advance past the explanation line
                        break
                    if title:
                        idea = f"{title} {explanation}".strip() if explanation else title
                        ideas.append(idea)
                    matched = True
                    break
            i += 1

        # Fallback: if structured parsing found nothing, grab non-empty lines
        if not ideas:
            for line in lines:
                line = line.strip()
                if line and not line[0].isdigit():
                    ideas.append(line)

        return ideas


class AIParticipantFactory:
    """Factory for creating AI participants."""

    @staticmethod
    def create_ai_participants(api_key: str, num_ai_participants: int, company_context: str) -> List[dict]:
        """
        Create AI participant records.

        Args:
            api_key: Mistral API key
            num_ai_participants: Number of AI participants to create
            company_context: Company information context

        Returns:
            List of AI participant info dictionaries
        """
        ai_participants = []

        ai_names = [
            "AI Assistant Alpha",
            "AI Assistant Beta",
            "AI Assistant Gamma",
            "AI Assistant Delta",
            "AI Assistant Epsilon",
            "AI Assistant Zeta"
        ]

        for i in range(num_ai_participants):
            ai_participants.append({
                "name": ai_names[i] if i < len(ai_names) else f"AI Assistant {i+1}",
                "is_ai": True,
                "participant_number": i + 1
            })

        return ai_participants


def cluster_ideas(
    ideas: list,
    model: str = "mistral/mistral-small-latest",
    language: str = "en",
    api_key: str = None,
    api_base: str = None,
    custom_prompts: dict = None,
    maturity_level: int = None,
    maturity_level_name: str = None,
    company_context: str = None
) -> dict:
    """
    Cluster brainstorming ideas by technology/concept using LLM.

    Args:
        ideas: List of idea dicts with 'id' and 'content' keys
        model: LLM model string
        language: Language code ("en" or "de")
        api_key: Optional API key
        api_base: Optional custom API base URL
        custom_prompts: Optional custom prompt overrides
        maturity_level: Optional company maturity level (1-6)
        maturity_level_name: Optional maturity level name
        company_context: Optional company context summary

    Returns:
        Dict with 'clusters' key containing list of cluster dicts
    """
    import json

    if not ideas:
        return {"clusters": []}

    # Early check: if no API key provided, raise to trigger fallback
    if not api_key:
        raise ValueError("No API key provided for clustering")

    # Build the ideas list for the prompt
    ideas_text = "\n".join([f"- ID {idea['id']}: {idea['content']}" for idea in ideas])

    # Get the clustering prompt
    system_prompt = get_prompt(
        "idea_clustering_system",
        language,
        custom_prompts or {}
    )

    # Build maturity context if provided
    maturity_context = ""
    if maturity_level is not None:
        maturity_name = maturity_level_name or f"Level {maturity_level}"
        if language == "de":
            maturity_context = f"""
## Unternehmens-Reifegrad
Das Unternehmen befindet sich auf **Digitalisierungsreifegrad {maturity_level} ({maturity_name})**.

Bitte bewerten Sie für jeden Cluster, wie gut er zum aktuellen Reifegrad des Unternehmens passt:
- **high**: Gut geeignet für den aktuellen Reifegrad - realistisch umsetzbar
- **medium**: Machbar mit etwas Aufwand - erfordert moderate Entwicklung
- **low**: Ambitioniert für den aktuellen Reifegrad - erfordert signifikante Entwicklung

"""
        else:
            maturity_context = f"""
## Company Maturity Level
The company is at **digitalization maturity level {maturity_level} ({maturity_name})**.

Please assess for each cluster how appropriate it is for the company's current maturity level:
- **high**: Well-suited for current maturity - realistically implementable
- **medium**: Achievable with some effort - requires moderate capability building
- **low**: Ambitious for current maturity - requires significant capability development

"""

    # Build company context if provided
    company_section = ""
    if company_context:
        if language == "de":
            company_section = f"""
## Unternehmenskontext
{company_context[:1500]}

"""
        else:
            company_section = f"""
## Company Context
{company_context[:1500]}

"""

    user_prompt = f"""Please analyze and cluster the following {len(ideas)} ideas:

{ideas_text}
{maturity_context}{company_section}
Return the clustering as JSON."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        # Calculate max_tokens based on idea count (more ideas = more clusters = more tokens needed)
        # Estimate: ~400 tokens per cluster, ~1 cluster per 5-10 ideas
        estimated_clusters = max(3, len(ideas) // 7)
        max_tokens = min(4000, max(1500, estimated_clusters * 400))

        # Build completion kwargs
        completion_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,  # Lower temperature for more consistent clustering
            "max_tokens": max_tokens
        }
        if api_key:
            completion_kwargs["api_key"] = api_key
        if api_base:
            completion_kwargs["api_base"] = api_base
        apply_model_params(completion_kwargs)

        response = completion(**completion_kwargs)
        content = response.choices[0].message.content

        # Parse JSON from response (handle potential markdown code blocks and extra text)
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Try to find JSON object in the response (in case there's extra text)
        json_start = content.find('{')
        json_end = content.rfind('}')
        if json_start != -1 and json_end != -1 and json_end > json_start:
            content = content[json_start:json_end + 1]

        result = json.loads(content)

        # Validate that all returned idea_ids exist in the input
        input_ids = {idea["id"] for idea in ideas}
        for cluster in result.get("clusters", []):
            valid_ids = [id for id in cluster.get("idea_ids", []) if id in input_ids]
            invalid_ids = [id for id in cluster.get("idea_ids", []) if id not in input_ids]
            if invalid_ids:
                logger.warning(f"Cluster '{cluster.get('name')}' contains invalid idea IDs: {invalid_ids}")
            cluster["idea_ids"] = valid_ids

        # Validate that all ideas are assigned
        assigned_ids = set()
        for cluster in result.get("clusters", []):
            assigned_ids.update(cluster.get("idea_ids", []))

        all_ids = {idea["id"] for idea in ideas}
        missing_ids = all_ids - assigned_ids

        # If some ideas weren't assigned, create an "Other" cluster
        if missing_ids:
            result["clusters"].append({
                "id": len(result["clusters"]) + 1,
                "name": "Other" if language == "en" else "Sonstige",
                "description": "Ideas that didn't fit into other clusters" if language == "en" else "Ideen, die nicht in andere Cluster passten",
                "idea_ids": list(missing_ids)
            })

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse clustering response as JSON: {e}")
        logger.debug(f"Raw LLM response that failed to parse: {content[:500] if content else 'empty'}")
        return _create_fallback_clusters(ideas, language)
    except Exception as e:
        logger.error(f"Clustering error: {e}")
        return _create_fallback_clusters(ideas, language)


def _create_fallback_clusters(ideas: list, language: str = "en") -> dict:
    """
    Create fallback clusters when LLM clustering fails.
    Groups ideas into clusters of ~5 ideas each.
    """
    if not ideas:
        return {"clusters": []}

    # Target ~5 ideas per cluster, minimum 3 clusters for variety
    cluster_size = 5
    num_clusters = max(3, (len(ideas) + cluster_size - 1) // cluster_size)
    # Recalculate cluster size based on number of clusters
    cluster_size = (len(ideas) + num_clusters - 1) // num_clusters

    clusters = []
    for i in range(num_clusters):
        start_idx = i * cluster_size
        end_idx = min(start_idx + cluster_size, len(ideas))
        cluster_ideas_subset = ideas[start_idx:end_idx]

        if not cluster_ideas_subset:
            continue

        if language == "de":
            cluster_name = f"Ideengruppe {i + 1}"
            cluster_desc = f"Ideen {start_idx + 1} bis {end_idx} aus dem Brainstorming"
            rationale = "Automatisch gruppiert (KI-Clustering nicht verfügbar)"
        else:
            cluster_name = f"Idea Group {i + 1}"
            cluster_desc = f"Ideas {start_idx + 1} to {end_idx} from brainstorming"
            rationale = "Auto-grouped (LLM clustering unavailable)"

        clusters.append({
            "id": i + 1,
            "name": cluster_name,
            "description": cluster_desc,
            "idea_ids": [idea["id"] for idea in cluster_ideas_subset],
            "maturity_fit": "medium",
            "maturity_rationale": rationale,
            "implementation_effort": "medium",
            "effort_rationale": rationale,
            "business_impact": "medium",
            "impact_rationale": rationale
        })

    return {"clusters": clusters}


def assess_ideas(
    ideas: list,
    cluster_info: dict,
    model: str = "mistral/mistral-small-latest",
    language: str = "en",
    api_key: str = None,
    api_base: str = None,
    company_context: str = None
) -> dict:
    """
    Assess individual ideas within a cluster for effort and impact.

    Args:
        ideas: List of idea dicts with 'id' and 'content' keys
        cluster_info: Dict with cluster name and description
        model: LLM model string
        language: Language code ("en" or "de")
        api_key: Optional API key
        api_base: Optional custom API base URL
        company_context: Optional company context summary

    Returns:
        Dict with 'ideas' key containing list of assessed idea dicts
    """
    import json

    if not ideas:
        return {"ideas": []}

    # Build the ideas list for the prompt
    ideas_text = "\n".join([f"- ID {idea['id']}: {idea['content']}" for idea in ideas])

    # Build company context section
    company_section = ""
    if company_context:
        if language == "de":
            company_section = f"""
## Unternehmenskontext
{company_context[:1000]}
"""
        else:
            company_section = f"""
## Company Context
{company_context[:1000]}
"""

    if language == "de":
        system_prompt = """Sie sind ein Experte für KI und digitale Transformation in KMUs.
Ihre Aufgabe ist es, einzelne Ideen innerhalb eines Clusters nach Implementierungsaufwand und Business Impact zu bewerten.

## Bewertungskriterien

**Implementierungsaufwand (implementation_effort)**:
- "low": Fertige Lösungen verfügbar, minimale Anpassung, wenige Wochen zur Umsetzung
- "medium": Anpassungen nötig, moderate Integrationsarbeit, 1-3 Monate
- "high": Eigenentwicklung nötig, komplexe Integration, 3+ Monate

**Business Impact (business_impact)**:
- "low": Inkrementelle Verbesserungen, Nice-to-have, begrenzter ROI
- "medium": Spürbare Effizienzgewinne oder Kosteneinsparungen, guter ROI
- "high": Signifikanter Wettbewerbsvorteil, große Kostensenkung oder Umsatzpotenzial

## Ausgabeformat (JSON)

Geben Sie Ihre Antwort als valides JSON zurück:
```json
{
  "ideas": [
    {
      "id": 1,
      "implementation_effort": "medium",
      "effort_rationale": "Kurze Begründung des Aufwands",
      "business_impact": "high",
      "impact_rationale": "Kurze Begründung des Impacts"
    }
  ]
}
```

Wichtig:
- Verwenden Sie die exakten Ideen-IDs aus der Eingabe
- implementation_effort muss eines von: "low", "medium", "high" sein
- business_impact muss eines von: "low", "medium", "high" sein
- Geben Sie NUR das JSON zurück, keinen zusätzlichen Text"""
    else:
        system_prompt = """You are an expert in AI and digital transformation for SMEs.
Your task is to assess individual ideas within a cluster for implementation effort and business impact.

## Assessment Criteria

**Implementation Effort (implementation_effort)**:
- "low": Off-the-shelf solutions available, minimal customization, can be deployed in weeks
- "medium": Some customization needed, moderate integration work, 1-3 months
- "high": Custom development required, complex integration, 3+ months

**Business Impact (business_impact)**:
- "low": Incremental improvements, nice-to-have, limited ROI
- "medium": Noticeable efficiency gains or cost savings, good ROI
- "high": Significant competitive advantage, major cost reduction, or revenue potential

## Output Format (JSON)

Return your response as valid JSON:
```json
{
  "ideas": [
    {
      "id": 1,
      "implementation_effort": "medium",
      "effort_rationale": "Brief explanation of effort assessment",
      "business_impact": "high",
      "impact_rationale": "Brief explanation of impact assessment"
    }
  ]
}
```

Important:
- Use the exact idea IDs from the input
- implementation_effort must be one of: "low", "medium", "high"
- business_impact must be one of: "low", "medium", "high"
- Return ONLY the JSON, no additional text"""

    cluster_name = cluster_info.get('name', 'Selected Cluster')
    cluster_desc = cluster_info.get('description', '')

    if language == "de":
        user_prompt = f"""Bitte bewerten Sie die folgenden {len(ideas)} Ideen aus dem Cluster "{cluster_name}":

Cluster-Beschreibung: {cluster_desc}
{company_section}
Ideen:
{ideas_text}

Geben Sie die Bewertung als JSON zurück."""
    else:
        user_prompt = f"""Please assess the following {len(ideas)} ideas from the cluster "{cluster_name}":

Cluster description: {cluster_desc}
{company_section}
Ideas:
{ideas_text}

Return the assessment as JSON."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        # Build completion kwargs
        completion_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 1500
        }
        if api_key:
            completion_kwargs["api_key"] = api_key
        if api_base:
            completion_kwargs["api_base"] = api_base
        apply_model_params(completion_kwargs)

        response = completion(**completion_kwargs)
        content = response.choices[0].message.content

        # Parse JSON from response (handle potential markdown code blocks)
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        result = json.loads(content)

        # Create a lookup dict from the result
        assessed_dict = {item["id"]: item for item in result.get("ideas", [])}

        # Merge assessment data back into original ideas
        assessed_ideas = []
        for idea in ideas:
            assessment = assessed_dict.get(idea["id"], {})
            assessed_ideas.append({
                **idea,
                "implementation_effort": assessment.get("implementation_effort", "medium"),
                "effort_rationale": assessment.get("effort_rationale", ""),
                "business_impact": assessment.get("business_impact", "medium"),
                "impact_rationale": assessment.get("impact_rationale", "")
            })

        return {"ideas": assessed_ideas}

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse idea assessment response as JSON: {e}")
        # Fallback: return ideas with default medium ratings
        return {
            "ideas": [
                {
                    **idea,
                    "implementation_effort": "medium",
                    "effort_rationale": "",
                    "business_impact": "medium",
                    "impact_rationale": ""
                }
                for idea in ideas
            ]
        }
    except Exception as e:
        logger.error(f"Idea assessment error: {e}")
        return {
            "ideas": [
                {
                    **idea,
                    "implementation_effort": "medium",
                    "effort_rationale": "",
                    "business_impact": "medium",
                    "impact_rationale": ""
                }
                for idea in ideas
            ]
        }


def get_company_context_summary(company_infos, max_total_chars: int = 4000) -> str:
    """
    Create a comprehensive summary of company information for AI context.

    Args:
        company_infos: List of CompanyInfo objects
        max_total_chars: Maximum total characters for the context

    Returns:
        Formatted string with company context
    """
    if not company_infos:
        return "No company information provided yet."

    summaries = []
    total_chars = 0

    for info in company_infos:
        if info.content:
            # Add source type header
            info_type = info.info_type if hasattr(info, 'info_type') else 'text'
            header = f"[{info_type.upper()}]"

            # Calculate how much space we have left
            remaining = max_total_chars - total_chars
            if remaining <= 100:
                break

            # Truncate if needed, but allow more content per entry
            max_for_this = min(1500, remaining - 50)  # Reserve space for header
            content = info.content[:max_for_this]
            if len(info.content) > max_for_this:
                content += "..."

            formatted = f"{header}\n{content}"
            summaries.append(formatted)
            total_chars += len(formatted)

    return "\n\n".join(summaries)
