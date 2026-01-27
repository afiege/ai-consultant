"""Service for AI participants that generate ideas using LiteLLM (multi-provider)."""

from typing import List, Optional, Dict
from litellm import completion
import logging

from .default_prompts import get_prompt

logger = logging.getLogger(__name__)


class AIParticipant:
    """AI participant that generates ideas for 6-3-5 brainstorming using LiteLLM."""

    def __init__(
        self,
        model: str = "mistral/mistral-small-latest",
        custom_prompts: Optional[Dict[str, str]] = None,
        language: str = "en",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None
    ):
        """
        Initialize AI participant with LiteLLM model.

        Args:
            model: LiteLLM model string (e.g., "mistral/mistral-small-latest", "openai/gpt-4")
            custom_prompts: Optional dict of custom prompt overrides
            language: Language code ("en" or "de")
            api_key: Optional API key (uses provider's env var if not provided)
            api_base: Optional custom API base URL for OpenAI-compatible endpoints
        """
        self.model = model
        self.custom_prompts = custom_prompts or {}
        self.language = language
        self.api_key = api_key
        self.api_base = api_base

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
        system_prompt = self._build_system_prompt(company_context)
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
                "temperature": 0.7,  # Balanced temperature for creativity with consistency
                "max_tokens": 300  # Reduced to encourage concise responses
            }
            if self.api_key:
                completion_kwargs["api_key"] = self.api_key
            if self.api_base:
                completion_kwargs["api_base"] = self.api_base

            response = completion(**completion_kwargs)

            # Parse response (LiteLLM returns OpenAI-compatible format)
            content = response.choices[0].message.content
            ideas = self._parse_ideas(content)

            # Ensure we have exactly 3 ideas
            if len(ideas) < 3:
                ideas.extend([f"AI Idea {i+1} (unique) for round {round_number}" for i in range(len(ideas), 3)])
            elif len(ideas) > 3:
                ideas = ideas[:3]

            return ideas

        except Exception as e:
            # Fallback to generic ideas if API fails
            logger.error(f"AI participant error: {e}")
            return [
                f"AI Participant {participant_number} - Unique Idea {i+1} for round {round_number}" for i in range(3)
            ]

    def _build_system_prompt(self, company_context: str) -> str:
        """Build the system prompt with company context."""
        template = get_prompt(
            "brainstorming_system",
            self.language,
            self.custom_prompts
        )
        return template.format(company_context=company_context)

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
                uniqueness_note = f"""
Note: These ideas have been suggested by others in this session (avoid duplicating them):
{ideas_list}
{f"(and {len(other_ideas) - 10} more)" if len(other_ideas) > 10 else ""}
"""

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

        Args:
            content: AI response text

        Returns:
            List of ideas
        """
        ideas = []
        lines = content.strip().split('\n')

        for line in lines:
            line = line.strip()
            # Look for numbered ideas (1., 2., 3. or 1), 2), 3))
            if line and (line[0].isdigit() or line.startswith('-')):
                # Remove numbering and extract idea
                for prefix in ['1.', '2.', '3.', '1)', '2)', '3)', '-']:
                    if line.startswith(prefix):
                        idea = line[len(prefix):].strip()
                        if idea:
                            ideas.append(idea)
                        break

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
    custom_prompts: dict = None
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

    Returns:
        Dict with 'clusters' key containing list of cluster dicts
    """
    import json

    if not ideas:
        return {"clusters": []}

    # Build the ideas list for the prompt
    ideas_text = "\n".join([f"- ID {idea['id']}: {idea['content']}" for idea in ideas])

    # Get the clustering prompt
    system_prompt = get_prompt(
        "idea_clustering_system",
        language,
        custom_prompts or {}
    )

    user_prompt = f"""Please analyze and cluster the following {len(ideas)} ideas:

{ideas_text}

Return the clustering as JSON."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        # Build completion kwargs
        completion_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,  # Lower temperature for more consistent clustering
            "max_tokens": 1500
        }
        if api_key:
            completion_kwargs["api_key"] = api_key
        if api_base:
            completion_kwargs["api_base"] = api_base

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
        # Fallback: put all ideas in one cluster
        return {
            "clusters": [{
                "id": 1,
                "name": "All Ideas" if language == "en" else "Alle Ideen",
                "description": "All brainstormed ideas" if language == "en" else "Alle Brainstorming-Ideen",
                "idea_ids": [idea["id"] for idea in ideas]
            }]
        }
    except Exception as e:
        logger.error(f"Clustering error: {e}")
        # Fallback: put all ideas in one cluster
        return {
            "clusters": [{
                "id": 1,
                "name": "All Ideas" if language == "en" else "Alle Ideen",
                "description": "All brainstormed ideas" if language == "en" else "Alle Brainstorming-Ideen",
                "idea_ids": [idea["id"] for idea in ideas]
            }]
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
