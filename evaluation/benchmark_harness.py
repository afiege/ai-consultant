#!/usr/bin/env python3
"""
Benchmark Test Harness for AI Consultant Evaluation

This harness uses the benchmark personas to evaluate consultation quality against
ground truth expectations. It:

1. Seeds a session with persona data (company info, maturity, focus idea)
2. Runs CRISP-DM consultation (Step 4) with simulated user responses
3. Extracts findings and compares against ground truth
4. Uses LLM-as-Judge to score consultation quality
5. Outputs detailed evaluation results

Usage:
    python benchmark_harness.py --persona mfg_01_metal_quality --api-key YOUR_KEY
    python benchmark_harness.py --all --api-key YOUR_KEY --save
"""

import json
import os
import sys
import time
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

# Add evaluation directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from litellm import completion
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    print("Warning: litellm not installed. Install with: pip install litellm")

from rubric import RUBRIC, calculate_weighted_score, get_grade

# Configuration
API_BASE_URL = os.environ.get("API_URL", "http://localhost:8000")
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
LLM_API_BASE = os.environ.get("LLM_API_BASE", None)  # Custom OpenAI-compatible endpoint
PERSONAS_PATH = Path(__file__).parent / "benchmark_personas.json"
RESULTS_DIR = Path(__file__).parent / "results" / "benchmark"


def llm_completion(model: str, messages: list, temperature: float, api_key: str, api_base: str = None):
    """Wrapper for litellm completion with custom API base support."""
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "api_key": api_key
    }

    # Only apply custom API base for openai/ prefixed models (e.g., academic cloud)
    # Other providers like gemini/, anthropic/ use their native endpoints
    if model.startswith("openai/"):
        effective_api_base = api_base or LLM_API_BASE
        if effective_api_base:
            kwargs["api_base"] = effective_api_base

    return completion(**kwargs)


@dataclass
class EvaluationResult:
    """Container for evaluation results."""
    persona_id: str
    company_name: str
    timestamp: str
    success: bool

    # Session info
    session_uuid: Optional[str] = None
    maturity_level: Optional[str] = None
    maturity_score: Optional[float] = None

    # Model info
    consultation_model: Optional[str] = None
    judge_model: Optional[str] = None
    user_model: Optional[str] = None

    # Consultation metrics
    consultation_turns: int = 0
    total_messages: int = 0
    findings_extracted: int = 0

    # Ground truth comparison
    ground_truth_comparison: Dict[str, Any] = field(default_factory=dict)
    critical_questions_asked: List[str] = field(default_factory=list)
    critical_questions_missed: List[str] = field(default_factory=list)
    challenges_identified: List[str] = field(default_factory=list)
    challenges_missed: List[str] = field(default_factory=list)
    value_level_match: bool = False

    # LLM-as-Judge scores
    rubric_scores: Dict[str, int] = field(default_factory=dict)
    rubric_justifications: Dict[str, str] = field(default_factory=dict)
    weighted_score: float = 0.0
    grade: str = ""

    # Timing
    total_time_seconds: float = 0.0

    # Error info
    error: Optional[str] = None
    error_step: Optional[str] = None


def load_personas() -> List[Dict]:
    """Load benchmark personas from JSON file."""
    if PERSONAS_PATH.exists():
        with open(PERSONAS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("personas", [])
    return []


def get_persona(persona_id: str) -> Optional[Dict]:
    """Get a specific persona by ID."""
    personas = load_personas()
    return next((p for p in personas if p.get("persona_id") == persona_id), None)


def format_company_info_detailed(persona: Dict) -> str:
    """
    Format persona company info as detailed text for Step 1.
    Includes all available information for comprehensive testing.
    """
    company = persona.get("company", {})

    lines = [
        f"# Company Profile: {company.get('name', 'Unknown')}",
        "",
        f"**Industry:** {company.get('sub_industry', 'Unknown')}",
        f"**Employees:** {company.get('size_employees', 'Unknown')}",
        f"**Annual Revenue:** €{company.get('size_revenue_eur', 0):,}",
        "",
        "## Business Model",
        company.get("business_model", ""),
        "",
        "## Products and Services",
        company.get("products_services", ""),
        "",
        "## Target Market",
        company.get("target_market", ""),
        "",
        "## Team Structure",
        company.get("team_structure", ""),
        "",
        "## Strategic Goals",
        company.get("strategic_goals", ""),
        "",
        "## Current Challenges",
    ]

    for challenge in company.get("current_challenges", []):
        lines.append(f"- {challenge}")

    lines.extend(["", "## Key Performance Indicators (KPIs)"])

    for kpi_name, kpi_data in company.get("kpis", {}).items():
        value = kpi_data.get('value', 'N/A')
        unit = kpi_data.get('unit', '')
        target = kpi_data.get('target', 'N/A')
        note = kpi_data.get('note', '')
        lines.append(f"- **{kpi_name}:** {value} {unit} (target: {target}) - {note}")

    # Include digitalization details
    digitalization = company.get("digitalization_maturity", {})
    lines.extend([
        "",
        "## Current IT/Digitalization Infrastructure",
    ])

    for system, desc in digitalization.get("details", {}).items():
        lines.append(f"- **{system}:** {desc}")

    return "\n".join(lines)


def extract_maturity_assessment(persona: Dict) -> Dict[str, Any]:
    """Extract acatech maturity assessment data from persona for API submission."""
    maturity = persona.get("company", {}).get("digitalization_maturity", {})
    acatech = maturity.get("acatech_assessment", {})

    def get_dimension_data(dim_key: str, default_score: float = 2.0) -> Tuple[float, Dict]:
        dim = acatech.get(dim_key, {})
        score = dim.get("score", default_score)
        # Only include q1-q4 scores, not notes (API expects numeric values only)
        details = {
            "q1": dim.get("q1", round(score)),
            "q2": dim.get("q2", round(score)),
            "q3": dim.get("q3", round(score)),
            "q4": dim.get("q4", round(score))
        }
        return score, details

    resources_score, resources_details = get_dimension_data("resources", 2.0)
    info_score, info_details = get_dimension_data("information_systems", 2.0)
    culture_score, culture_details = get_dimension_data("culture", 2.0)
    org_score, org_details = get_dimension_data("organizational_structure", 2.0)

    return {
        "resources_score": resources_score,
        "resources_details": resources_details,
        "information_systems_score": info_score,
        "information_systems_details": info_details,
        "culture_score": culture_score,
        "culture_details": culture_details,
        "organizational_structure_score": org_score,
        "organizational_structure_details": org_details,
    }


# User simulation prompt for consultation
USER_SIMULATION_PROMPT = """You are simulating an employee at a small/medium enterprise (SME) participating in an AI consultation session.

COMPANY PROFILE:
{company_info}

YOUR ROLE:
- You are a {role} at this company with {years} years of experience
- You have LIMITED knowledge about AI and digitalization
- You answer questions based on the company profile above
- You can elaborate on challenges mentioned in the profile
- You may express uncertainty about technical topics
- You respond naturally, sometimes asking for clarification
- Keep responses concise (2-4 sentences typically)

FOCUS PROJECT BEING DISCUSSED:
{focus_idea}

IMPORTANT BEHAVIORS:
- Stay in character as an SME employee
- Don't make up information not implied by the company profile
- Express realistic concerns about budget, time, and complexity
- Be open but somewhat skeptical about AI promises
- When asked about data, describe what's realistically available given the company's IT infrastructure
- When asked about budget, be cautious and ask about ROI

Respond to the AI consultant's message."""


def simulate_user_response(
    persona: Dict,
    consultant_message: str,
    conversation_history: List[Dict],
    model: str = None,
    api_key: str = None
) -> str:
    """Generate a simulated user response for the consultation."""
    if not LITELLM_AVAILABLE or not api_key:
        return "That sounds interesting. Can you tell me more about how we could implement this practically given our limited IT resources?"

    company_info = format_company_info_detailed(persona)
    focus_idea = persona.get("focus_idea", {})
    company = persona.get("company", {})

    # Determine role based on company type
    sub_industry = company.get("sub_industry", "").lower()
    if "manufacturing" in sub_industry or "metal" in sub_industry or "plastic" in sub_industry:
        role = "production manager"
    elif "electronics" in sub_industry:
        role = "operations director"
    elif "food" in sub_industry or "bakery" in sub_industry:
        role = "owner-manager"
    elif "precision" in sub_industry or "medical" in sub_industry:
        role = "engineering manager"
    else:
        role = "operations manager"

    system_prompt = USER_SIMULATION_PROMPT.format(
        company_info=company_info,
        role=role,
        years=str(8 + hash(persona.get("persona_id", "")) % 15),
        focus_idea=f"{focus_idea.get('title', '')}: {focus_idea.get('description', '')}"
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    for msg in conversation_history:
        if msg["role"] == "assistant":
            messages.append({"role": "user", "content": f"AI Consultant: {msg['content']}"})
        else:
            messages.append({"role": "assistant", "content": msg["content"]})

    # Add current consultant message
    messages.append({"role": "user", "content": f"AI Consultant: {consultant_message}"})

    response = llm_completion(
        model=model or DEFAULT_MODEL,
        messages=messages,
        temperature=0.8,
        api_key=api_key
    )

    return response.choices[0].message.content


# Ground truth evaluation prompt
GROUND_TRUTH_EVAL_PROMPT = """You are an expert evaluator assessing an AI consultation for an SME digitalization project.

COMPANY PROFILE:
{company_info}

FOCUS PROJECT:
{focus_idea_title}: {focus_idea_description}

EXPECTED GROUND TRUTH (what a good consultation should identify):

Expected Value Level: {expected_value_level}
(Value levels: Budget Substitution, Process Efficiency, Project Acceleration, Risk Mitigation, Strategic Scaling)

Expected KPI Impacts:
{expected_kpi_impacts}

Critical Questions That Should Be Asked:
{critical_questions}

Expected Challenges To Identify:
{expected_challenges}

Realistic First Step:
{realistic_first_step}

---

CONSULTATION TRANSCRIPT:
{transcript}

EXTRACTED FINDINGS:
{findings}

---

EVALUATION TASK:
Analyze the consultation against the ground truth expectations. Provide:

1. **Value Level Assessment**: Did the consultant correctly identify the primary value level?
2. **Critical Questions**: Which critical questions were asked vs missed?
3. **Challenges Identification**: Which expected challenges were discussed vs missed?
4. **KPI Impact Analysis**: Were relevant KPIs and impacts discussed?
5. **Practical Guidance**: Was the realistic first step or similar practical guidance provided?

Also evaluate using the standard rubric criteria.

Respond in this exact JSON format:
{{
    "value_level_identified": "<the value level the consultant identified, if any>",
    "value_level_match": <true/false>,
    "critical_questions_asked": ["<question1>", "<question2>"],
    "critical_questions_missed": ["<missed1>", "<missed2>"],
    "challenges_identified": ["<challenge1>", "<challenge2>"],
    "challenges_missed": ["<missed1>", "<missed2>"],
    "kpi_discussion_quality": "<assessment of KPI discussion>",
    "practical_guidance_quality": "<assessment of practical next steps>",
    "scores": {{
        "relevance": <1-5>,
        "actionability": <1-5>,
        "accuracy": <1-5>,
        "clarity": <1-5>,
        "completeness": <1-5>,
        "sme_appropriateness": <1-5>,
        "maturity_integration": <1-5>,
        "maturity_appropriate_complexity": <1-5>
    }},
    "justifications": {{
        "relevance": "<explanation>",
        "actionability": "<explanation>",
        "accuracy": "<explanation>",
        "clarity": "<explanation>",
        "completeness": "<explanation>",
        "sme_appropriateness": "<explanation>",
        "maturity_integration": "<explanation>",
        "maturity_appropriate_complexity": "<explanation>"
    }},
    "strengths": "<overall strengths>",
    "weaknesses": "<overall weaknesses>",
    "summary": "<2-3 sentence overall assessment>"
}}"""


def evaluate_against_ground_truth(
    persona: Dict,
    conversation: List[Dict],
    findings: Dict,
    model: str = None,
    api_key: str = None
) -> Dict[str, Any]:
    """Evaluate consultation against persona's ground truth."""
    if not LITELLM_AVAILABLE or not api_key:
        return {"error": "LiteLLM not available for evaluation"}

    company_info = format_company_info_detailed(persona)
    focus_idea = persona.get("focus_idea", {})
    ground_truth = persona.get("ground_truth", {})

    # Format transcript
    transcript_lines = []
    for msg in conversation:
        role = "AI Consultant" if msg["role"] == "assistant" else "User"
        transcript_lines.append(f"{role}: {msg['content']}")
    transcript = "\n\n".join(transcript_lines)

    # Format expected KPI impacts
    kpi_impacts = ground_truth.get("expected_kpi_impact", {})
    kpi_text = "\n".join([f"- {k}: {v}" for k, v in kpi_impacts.items()])

    # Format critical questions
    critical_questions = ground_truth.get("critical_questions", [])
    questions_text = "\n".join([f"- {q}" for q in critical_questions])

    # Format expected challenges
    expected_challenges = ground_truth.get("expected_challenges", [])
    challenges_text = "\n".join([f"- {c}" for c in expected_challenges])

    # Format findings
    findings_text = json.dumps(findings, indent=2, default=str) if findings else "No findings extracted"

    prompt = GROUND_TRUTH_EVAL_PROMPT.format(
        company_info=company_info,
        focus_idea_title=focus_idea.get("title", "Unknown"),
        focus_idea_description=focus_idea.get("description", ""),
        expected_value_level=ground_truth.get("value_level", "Unknown"),
        expected_kpi_impacts=kpi_text,
        critical_questions=questions_text,
        expected_challenges=challenges_text,
        realistic_first_step=ground_truth.get("realistic_first_step", "Not specified"),
        transcript=transcript,
        findings=findings_text
    )

    messages = [
        {"role": "system", "content": "You are an expert evaluator. Respond only with valid JSON."},
        {"role": "user", "content": prompt}
    ]

    response = llm_completion(
        model=model or DEFAULT_MODEL,
        messages=messages,
        temperature=0.2,
        api_key=api_key
    )

    # Parse JSON response
    try:
        content = response.choices[0].message.content
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            return json.loads(content[json_start:json_end])
    except (json.JSONDecodeError, Exception) as e:
        return {"error": f"Failed to parse evaluation: {e}"}

    return {"error": "No valid JSON in response"}


class BenchmarkHarness:
    """Test harness for running benchmark evaluations."""

    def __init__(self, api_key: str, model: str = None, judge_model: str = None,
                 judge_api_key: str = None, user_model: str = None, verbose: bool = True):
        self.api_key = api_key
        self.model = model or DEFAULT_MODEL
        self.judge_model = judge_model or self.model  # Default to same model if not specified
        self.user_model = user_model or self.model  # Default to same model if not specified
        # For judge, use separate API key if provided, otherwise same as consultation
        self.judge_api_key = judge_api_key or api_key
        self.verbose = verbose
        self.session_uuid = None
        self.participant_uuid = None

    def log(self, message: str):
        """Print message if verbose mode enabled."""
        if self.verbose:
            print(message)

    def api_call(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make an API call to the backend."""
        url = f"{API_BASE_URL}{endpoint}"
        return requests.request(method, url, **kwargs)

    def run_benchmark(self, persona: Dict, max_turns: int = 6) -> EvaluationResult:
        """Run complete benchmark for a persona."""
        result = EvaluationResult(
            persona_id=persona.get("persona_id", "unknown"),
            company_name=persona.get("company", {}).get("name", "Unknown"),
            timestamp=datetime.now().isoformat(),
            success=False,
            consultation_model=self.model,
            judge_model=self.judge_model,
            user_model=self.user_model
        )

        start_time = time.time()

        try:
            self.log("\n" + "=" * 70)
            self.log(f"BENCHMARK: {result.company_name}")
            self.log(f"Persona: {result.persona_id}")
            self.log("=" * 70)

            # Step 1: Create session and seed data
            self._create_and_seed_session(persona, result)

            # Step 2: Run consultation
            conversation = self._run_consultation(persona, result, max_turns)

            # Step 3: Extract findings
            findings = self._extract_findings(result)

            # Step 4: Evaluate against ground truth
            self._evaluate_ground_truth(persona, conversation, findings, result)

            result.success = True
            result.total_time_seconds = round(time.time() - start_time, 2)

            self.log("\n" + "=" * 70)
            self.log(f"BENCHMARK COMPLETED: {result.grade} ({result.weighted_score:.2f}/5.0)")
            self.log("=" * 70)

        except Exception as e:
            result.error = str(e)
            result.total_time_seconds = round(time.time() - start_time, 2)
            self.log(f"\nBENCHMARK FAILED: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _create_and_seed_session(self, persona: Dict, result: EvaluationResult):
        """Create session and seed with persona data."""
        self.log("\n[1/4] Creating and seeding session...")

        company = persona.get("company", {})

        # Create session
        response = self.api_call("POST", "/api/sessions/", json={
            "company_name": company.get("name", "Test Company")
        })

        if response.status_code not in (200, 201):
            raise Exception(f"Failed to create session: {response.text}")

        session_data = response.json()
        self.session_uuid = session_data["session_uuid"]
        result.session_uuid = self.session_uuid
        self.log(f"  Session: {self.session_uuid[:8]}...")

        # Add company info
        company_info_text = format_company_info_detailed(persona)
        response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/company-info/text", json={
            "content": company_info_text
        })

        if response.status_code not in (200, 201):
            raise Exception(f"Failed to add company info: {response.text}")

        self.log(f"  Company info added ({len(company_info_text)} chars)")

        # Submit maturity assessment
        assessment_data = extract_maturity_assessment(persona)
        response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/maturity", json=assessment_data)

        if response.status_code in (200, 201):
            maturity_data = response.json()
            result.maturity_level = maturity_data.get("maturity_level", "Unknown")
            result.maturity_score = maturity_data.get("overall_score", 0)
            self.log(f"  Maturity: {result.maturity_level} ({result.maturity_score:.2f})")
        else:
            self.log(f"  Warning: Maturity assessment failed: {response.text}")

        # Skip 6-3-5 and directly inject focus idea
        # First, join as participant
        response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/six-three-five/join", json={
            "name": "Test Evaluator"
        })

        if response.status_code in (200, 201):
            self.participant_uuid = response.json().get("participant_uuid")

        # Mark 6-3-5 as skipped and set focus idea directly
        focus_idea = persona.get("focus_idea", {})

        # We need to create the idea through the normal flow but abbreviated
        # Start the 6-3-5 session
        response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/six-three-five/start", json={
            "api_key": self.api_key
        })

        if response.status_code in (200, 201):
            # Get assigned sheet
            response = self.api_call("GET", f"/api/sessions/{self.session_uuid}/six-three-five/my-sheet/{self.participant_uuid}")

            if response.status_code == 200:
                sheet_data = response.json()
                sheet_id = sheet_data.get("sheet_id")

                # Submit focus idea as the first idea
                focus_title = focus_idea.get("title", "AI-based process improvement")
                focus_desc = focus_idea.get("description", "")
                idea_content = f"{focus_title}: {focus_desc}"

                response = self.api_call(
                    "POST",
                    f"/api/sessions/{self.session_uuid}/six-three-five/ideas?participant_uuid={self.participant_uuid}",
                    json={
                        "sheet_id": sheet_id,
                        "round_number": 1,
                        "ideas": [idea_content, "Process automation", "Data-driven decision making"]
                    }
                )

                if response.status_code in (200, 201):
                    self.log(f"  Focus idea injected: {focus_title[:50]}...")

                    # Vote for the focus idea
                    response = self.api_call("GET", f"/api/sessions/{self.session_uuid}/six-three-five/ideas")
                    if response.status_code == 200:
                        ideas = response.json()
                        if ideas:
                            first_idea = ideas[0]
                            response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/prioritization/vote", json={
                                "participant_uuid": self.participant_uuid,
                                "votes": {str(first_idea["id"]): 3}
                            })
                            if response.status_code in (200, 201):
                                self.log("  Focus idea prioritized")

    def _run_consultation(self, persona: Dict, result: EvaluationResult, max_turns: int) -> List[Dict]:
        """Run the CRISP-DM consultation with simulated user."""
        self.log(f"\n[2/4] Running consultation ({max_turns} turns)...")

        # Start consultation
        response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/consultation/start", json={
            "api_key": self.api_key
        })

        if response.status_code not in (200, 201):
            raise Exception(f"Failed to start consultation: {response.text}")

        start_data = response.json()
        initial_message = start_data.get("message", "")
        self.log(f"  AI: {initial_message[:80]}...")

        conversation = [{"role": "assistant", "content": initial_message}]

        # Run conversation turns
        for turn in range(max_turns):
            self.log(f"  Turn {turn + 1}/{max_turns}...")

            # Generate simulated user response (using separate user model for independence)
            user_response = simulate_user_response(
                persona=persona,
                consultant_message=conversation[-1]["content"],
                conversation_history=conversation[:-1],
                model=self.user_model,
                api_key=self.api_key  # Uses same API key (academic cloud)
            )

            self.log(f"    User: {user_response[:60]}...")
            conversation.append({"role": "user", "content": user_response})

            # Send to consultation API
            response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/consultation/message", json={
                "content": user_response,
                "api_key": self.api_key
            })

            if response.status_code not in (200, 201):
                raise Exception(f"Consultation message failed: {response.text}")

            ai_response = response.json().get("message", "")
            self.log(f"    AI: {ai_response[:60]}...")
            conversation.append({"role": "assistant", "content": ai_response})

            time.sleep(0.3)  # Rate limiting

        result.consultation_turns = max_turns
        result.total_messages = len(conversation)
        self.log(f"  Consultation complete: {len(conversation)} messages")

        return conversation

    def _extract_findings(self, result: EvaluationResult) -> Dict:
        """Extract consultation findings."""
        self.log("\n[3/4] Extracting findings...")

        response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/consultation/summarize", json={
            "api_key": self.api_key
        })

        if response.status_code != 200:
            self.log(f"  Warning: Finding extraction failed: {response.text}")
            return {}

        summary_data = response.json()
        findings = summary_data.get("findings", {})

        # Count findings
        if isinstance(findings, dict):
            result.findings_extracted = len([v for v in findings.values() if v])
        elif isinstance(findings, list):
            result.findings_extracted = len(findings)

        self.log(f"  Extracted {result.findings_extracted} findings")

        return findings

    def _evaluate_ground_truth(
        self,
        persona: Dict,
        conversation: List[Dict],
        findings: Dict,
        result: EvaluationResult
    ):
        """Evaluate consultation against ground truth using LLM-as-Judge."""
        self.log(f"\n[4/4] Evaluating against ground truth (judge: {self.judge_model})...")

        evaluation = evaluate_against_ground_truth(
            persona=persona,
            conversation=conversation,
            findings=findings,
            model=self.judge_model,
            api_key=self.judge_api_key
        )

        if "error" in evaluation:
            self.log(f"  Warning: Evaluation error: {evaluation['error']}")
            return

        # Extract results
        result.value_level_match = evaluation.get("value_level_match", False)
        result.critical_questions_asked = evaluation.get("critical_questions_asked", [])
        result.critical_questions_missed = evaluation.get("critical_questions_missed", [])
        result.challenges_identified = evaluation.get("challenges_identified", [])
        result.challenges_missed = evaluation.get("challenges_missed", [])

        # Rubric scores
        result.rubric_scores = evaluation.get("scores", {})
        result.rubric_justifications = evaluation.get("justifications", {})

        # Calculate weighted score
        if result.rubric_scores:
            result.weighted_score = round(calculate_weighted_score(result.rubric_scores), 2)
            result.grade = get_grade(result.weighted_score)

        # Store full comparison
        result.ground_truth_comparison = {
            "value_level_identified": evaluation.get("value_level_identified"),
            "kpi_discussion_quality": evaluation.get("kpi_discussion_quality"),
            "practical_guidance_quality": evaluation.get("practical_guidance_quality"),
            "strengths": evaluation.get("strengths"),
            "weaknesses": evaluation.get("weaknesses"),
            "summary": evaluation.get("summary")
        }

        # Log results
        self.log(f"  Value level match: {result.value_level_match}")
        self.log(f"  Critical questions asked: {len(result.critical_questions_asked)}/{len(result.critical_questions_asked) + len(result.critical_questions_missed)}")
        self.log(f"  Challenges identified: {len(result.challenges_identified)}/{len(result.challenges_identified) + len(result.challenges_missed)}")
        self.log(f"  Weighted score: {result.weighted_score:.2f}")
        self.log(f"  Grade: {result.grade}")

    def cleanup(self):
        """Delete test session."""
        if self.session_uuid:
            try:
                self.api_call("DELETE", f"/api/sessions/{self.session_uuid}")
                self.log("  Session cleaned up")
            except Exception:
                pass


def run_benchmark(
    persona_id: str,
    api_key: str,
    model: str = None,
    judge_model: str = None,
    judge_api_key: str = None,
    user_model: str = None,
    max_turns: int = 6,
    verbose: bool = True,
    cleanup: bool = False
) -> EvaluationResult:
    """Run benchmark for a single persona."""
    persona = get_persona(persona_id)
    if not persona:
        available = [p.get("persona_id") for p in load_personas()]
        raise ValueError(f"Persona '{persona_id}' not found. Available: {available}")

    harness = BenchmarkHarness(
        api_key=api_key,
        model=model,
        judge_model=judge_model,
        judge_api_key=judge_api_key,
        user_model=user_model,
        verbose=verbose
    )

    try:
        result = harness.run_benchmark(persona, max_turns=max_turns)
    finally:
        if cleanup:
            harness.cleanup()

    return result


def run_all_benchmarks(
    api_key: str,
    model: str = None,
    judge_model: str = None,
    judge_api_key: str = None,
    user_model: str = None,
    max_turns: int = 6,
    verbose: bool = False,
    cleanup: bool = True
) -> List[EvaluationResult]:
    """Run benchmarks for all personas."""
    personas = load_personas()
    results = []

    print(f"\nRunning benchmarks for {len(personas)} personas...")
    print(f"Consultation model: {model or DEFAULT_MODEL}")
    print(f"User simulation model: {user_model or model or DEFAULT_MODEL}")
    print(f"Judge model: {judge_model or model or DEFAULT_MODEL}")
    print("-" * 50)

    for i, persona in enumerate(personas, 1):
        persona_id = persona.get("persona_id", "unknown")
        print(f"\n[{i}/{len(personas)}] {persona_id}")

        try:
            result = run_benchmark(
                persona_id=persona_id,
                api_key=api_key,
                model=model,
                judge_model=judge_model,
                judge_api_key=judge_api_key,
                user_model=user_model,
                max_turns=max_turns,
                verbose=verbose,
                cleanup=cleanup
            )
            results.append(result)
            print(f"  Score: {result.weighted_score:.2f} ({result.grade})")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append(EvaluationResult(
                persona_id=persona_id,
                company_name=persona.get("company", {}).get("name", "Unknown"),
                timestamp=datetime.now().isoformat(),
                success=False,
                consultation_model=model,
                judge_model=judge_model or model,
                user_model=user_model or model,
                error=str(e)
            ))

    # Summary
    successful = [r for r in results if r.success]
    if successful:
        avg_score = sum(r.weighted_score for r in successful) / len(successful)
        print("\n" + "=" * 50)
        print("BENCHMARK SUMMARY")
        print("=" * 50)
        print(f"Successful: {len(successful)}/{len(results)}")
        print(f"Average Score: {avg_score:.2f}")
        print(f"Average Grade: {get_grade(avg_score)}")

        # Per-persona breakdown
        print("\nPer-Persona Results:")
        for r in results:
            status = f"{r.weighted_score:.2f} ({r.grade})" if r.success else f"FAILED: {r.error}"
            print(f"  {r.persona_id}: {status}")

    return results


def save_results(results: List[EvaluationResult], filename: str = None) -> str:
    """Save benchmark results to JSON file."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = filename or f"benchmark_{timestamp}.json"
    filepath = RESULTS_DIR / filename

    # Get model info from first successful result
    consultation_model = None
    judge_model = None
    user_model = None
    for r in results:
        if r.consultation_model:
            consultation_model = r.consultation_model
            judge_model = r.judge_model
            user_model = r.user_model
            break

    # Convert to dict for JSON serialization
    data = {
        "timestamp": datetime.now().isoformat(),
        "consultation_model": consultation_model,
        "user_model": user_model,
        "judge_model": judge_model,
        "total_personas": len(results),
        "successful": len([r for r in results if r.success]),
        "results": [asdict(r) for r in results]
    }

    # Calculate aggregate stats
    successful = [r for r in results if r.success]
    if successful:
        data["aggregate"] = {
            "average_score": round(sum(r.weighted_score for r in successful) / len(successful), 2),
            "average_grade": get_grade(sum(r.weighted_score for r in successful) / len(successful)),
            "value_level_match_rate": round(sum(1 for r in successful if r.value_level_match) / len(successful), 2),
            "avg_critical_questions_asked": round(sum(len(r.critical_questions_asked) for r in successful) / len(successful), 1),
            "avg_challenges_identified": round(sum(len(r.challenges_identified) for r in successful) / len(successful), 1)
        }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    return str(filepath)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Benchmark Test Harness for AI Consultant Evaluation"
    )
    parser.add_argument(
        "--persona", type=str,
        help="Run benchmark for specific persona ID"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run benchmarks for all personas"
    )
    parser.add_argument(
        "--api-key", type=str,
        help="LLM API key (or set OPENAI_API_KEY/MISTRAL_API_KEY env var)"
    )
    parser.add_argument(
        "--api-base", type=str,
        help="Custom API base URL for OpenAI-compatible endpoints (or set LLM_API_BASE env var)"
    )
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL,
        help=f"LLM model for consultation (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--judge-model", type=str,
        help="LLM model for evaluation/judging (default: same as --model)"
    )
    parser.add_argument(
        "--judge-api-key", type=str,
        help="API key for judge model if different from consultation (or set GEMINI_API_KEY env var)"
    )
    parser.add_argument(
        "--user-model", type=str,
        help="LLM model for simulating user responses (default: same as --model). Use a different model for independent evaluation."
    )
    parser.add_argument(
        "--turns", type=int, default=6,
        help="Number of consultation turns (default: 6)"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Reduce output verbosity"
    )
    parser.add_argument(
        "--cleanup", action="store_true",
        help="Delete test sessions after completion"
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save results to file"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List available personas"
    )

    args = parser.parse_args()

    if args.list:
        personas = load_personas()
        print("\nAvailable Benchmark Personas:")
        print("-" * 60)
        for p in personas:
            company = p.get("company", {})
            gt = p.get("ground_truth", {})
            print(f"\n  {p.get('persona_id')}")
            print(f"    Company: {company.get('name')}")
            print(f"    Industry: {company.get('sub_industry')}")
            print(f"    Maturity: Level {company.get('digitalization_maturity', {}).get('level')} ({company.get('digitalization_maturity', {}).get('level_name')})")
            print(f"    Focus: {p.get('focus_idea', {}).get('title', 'N/A')}")
            print(f"    Expected Value: {gt.get('value_level', 'N/A')}")
        return

    # Get API key
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        print("Error: API key required. Set OPENAI_API_KEY/MISTRAL_API_KEY or use --api-key")
        sys.exit(1)

    # Get judge API key (for models like Gemini that use different providers)
    judge_api_key = args.judge_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if args.judge_model and args.judge_model.startswith("gemini/") and not judge_api_key:
        print("Error: Gemini judge model requires GEMINI_API_KEY or --judge-api-key")
        sys.exit(1)

    # Set custom API base if provided
    global LLM_API_BASE
    if args.api_base:
        LLM_API_BASE = args.api_base
        print(f"Using custom API base: {LLM_API_BASE}")

    # Check backend
    try:
        response = requests.get(f"{API_BASE_URL}/api/sessions/", timeout=5)
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to backend at {API_BASE_URL}")
        print("Start the backend: cd backend && python -m uvicorn app.main:app --reload")
        sys.exit(1)

    if args.all:
        results = run_all_benchmarks(
            api_key=api_key,
            model=args.model,
            judge_model=args.judge_model,
            judge_api_key=judge_api_key,
            user_model=args.user_model,
            max_turns=args.turns,
            verbose=not args.quiet,
            cleanup=args.cleanup
        )

        if args.save:
            filepath = save_results(results)
            print(f"\nResults saved to: {filepath}")

    elif args.persona:
        result = run_benchmark(
            persona_id=args.persona,
            api_key=api_key,
            model=args.model,
            judge_model=args.judge_model,
            judge_api_key=judge_api_key,
            user_model=args.user_model,
            max_turns=args.turns,
            verbose=not args.quiet,
            cleanup=args.cleanup
        )

        if args.save:
            filepath = save_results([result])
            print(f"\nResult saved to: {filepath}")

        # Print detailed result
        print("\n" + "=" * 50)
        print("DETAILED RESULTS")
        print("=" * 50)
        print(f"Persona: {result.persona_id}")
        print(f"Success: {result.success}")
        print(f"Score: {result.weighted_score:.2f}")
        print(f"Grade: {result.grade}")
        print(f"\nValue Level Match: {result.value_level_match}")
        print(f"Critical Questions Asked: {result.critical_questions_asked}")
        print(f"Critical Questions Missed: {result.critical_questions_missed}")
        print(f"Challenges Identified: {result.challenges_identified}")
        print(f"Challenges Missed: {result.challenges_missed}")

        if result.ground_truth_comparison:
            print(f"\nStrengths: {result.ground_truth_comparison.get('strengths', 'N/A')}")
            print(f"Weaknesses: {result.ground_truth_comparison.get('weaknesses', 'N/A')}")
            print(f"Summary: {result.ground_truth_comparison.get('summary', 'N/A')}")

        sys.exit(0 if result.success else 1)

    else:
        # Interactive mode
        personas = load_personas()
        print("\nAvailable Personas:")
        for p in personas:
            print(f"  {p.get('persona_id')}: {p.get('company', {}).get('name')}")

        persona_id = input("\nEnter persona ID (or 'all'): ").strip()

        if persona_id.lower() == 'all':
            results = run_all_benchmarks(
                api_key=api_key,
                model=args.model,
                judge_model=args.judge_model,
                judge_api_key=judge_api_key,
                user_model=args.user_model,
                max_turns=args.turns,
                verbose=True,
                cleanup=args.cleanup
            )
        else:
            result = run_benchmark(
                persona_id=persona_id,
                api_key=api_key,
                model=args.model,
                judge_model=args.judge_model,
                judge_api_key=judge_api_key,
                user_model=args.user_model,
                max_turns=args.turns,
                verbose=True,
                cleanup=args.cleanup
            )


if __name__ == "__main__":
    main()
