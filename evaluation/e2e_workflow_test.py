#!/usr/bin/env python3
"""
End-to-End Workflow Test for AI Consultant Application

Tests the complete workflow:
1a. Create session with company info from benchmark persona
1b. Submit maturity assessment from persona's acatech assessment
2. Single human participant joins 6-3-5 brainstorming
3. 5 AI participants generate ideas through 2 rounds
4. Prioritization step - human's first idea is selected
5a. Business Case Consultation (potentials) - LLM persona mimics SME employee
5b. Cost Estimation Consultation - LLM persona discusses implementation costs
6. PDF export validation

Requires: Backend running at localhost:8000, valid LLM API key
"""

import json
import os
import sys
import time
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add evaluation directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import litellm
    from litellm import completion
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    print("Warning: litellm not installed. Install with: pip install litellm")

# Configuration
API_BASE_URL = os.environ.get("API_URL", "http://localhost:8000")
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
RESULTS_DIR = Path(__file__).parent / "results" / "e2e"

# Load benchmark personas
PERSONAS_PATH = Path(__file__).parent / "benchmark_personas.json"


def load_personas() -> List[Dict]:
    """Load benchmark personas from JSON file."""
    if PERSONAS_PATH.exists():
        with open(PERSONAS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("personas", [])
    return []


def format_company_info(persona: Dict) -> str:
    """Format persona company info as text for Step 1."""
    company = persona.get("company", {})

    lines = [
        f"Company: {company.get('name', 'Unknown')}",
        f"Industry: {company.get('sub_industry', 'Unknown')}",
        f"Employees: {company.get('size_employees', 'Unknown')}",
        f"Revenue: €{company.get('size_revenue_eur', 0):,}",
        "",
        "Business Model:",
        company.get("business_model", ""),
        "",
        "Products/Services:",
        company.get("products_services", ""),
        "",
        "Target Market:",
        company.get("target_market", ""),
        "",
        "Team Structure:",
        company.get("team_structure", ""),
        "",
        "Strategic Goals:",
        company.get("strategic_goals", ""),
        "",
        "Current Challenges:",
    ]

    for challenge in company.get("current_challenges", []):
        lines.append(f"- {challenge}")

    lines.extend([
        "",
        "Key Performance Indicators:",
    ])

    for kpi_name, kpi_data in company.get("kpis", {}).items():
        lines.append(f"- {kpi_name}: {kpi_data.get('value')} {kpi_data.get('unit', '')} (target: {kpi_data.get('target')})")

    digitalization = company.get("digitalization_maturity", {})
    lines.extend([
        "",
        f"Digitalization Maturity: Level {digitalization.get('level', 'Unknown')} - {digitalization.get('level_name', '')}",
    ])

    for system, desc in digitalization.get("details", {}).items():
        lines.append(f"- {system}: {desc}")

    return "\n".join(lines)


def extract_maturity_assessment(persona: Dict) -> Dict[str, Any]:
    """Extract acatech maturity assessment data from persona for API submission."""
    maturity = persona.get("company", {}).get("digitalization_maturity", {})
    acatech = maturity.get("acatech_assessment", {})

    # Map persona acatech structure to API structure
    def get_dimension_data(dim_key: str, default_score: float = 2.0) -> tuple:
        dim = acatech.get(dim_key, {})
        score = dim.get("score", default_score)
        details = {
            "q1": dim.get("q1", round(score)),
            "q2": dim.get("q2", round(score)),
            "q3": dim.get("q3", round(score)),
            "q4": dim.get("q4", round(score)),
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


def generate_human_ideas(persona: Dict, model: str = None, api_key: str = None) -> List[str]:
    """Generate 3 initial ideas as if from a human participant based on persona."""
    if not LITELLM_AVAILABLE or not api_key:
        # Fallback to static ideas based on focus_idea
        focus = persona.get("focus_idea", {})
        return [
            focus.get("title", "AI-based process optimization"),
            f"Improve {persona['company'].get('current_challenges', ['efficiency'])[0].split(' - ')[0].lower()}",
            "Digitalize documentation and reporting"
        ]

    company = persona.get("company", {})
    challenges = company.get("current_challenges", [])

    prompt = f"""You are an employee at {company.get('name', 'a company')} participating in a brainstorming session about AI and digitalization opportunities.

Company challenges:
{chr(10).join('- ' + c for c in challenges)}

Generate exactly 3 short, practical AI/digitalization ideas (one sentence each) that could help address these challenges. Focus on realistic SME-level solutions.

Return ONLY a JSON array of 3 strings, nothing else:
["idea 1", "idea 2", "idea 3"]"""

    response = completion(
        model=model or DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        api_key=api_key
    )

    try:
        content = response.choices[0].message.content
        # Extract JSON array
        start = content.find('[')
        end = content.rfind(']') + 1
        if start >= 0 and end > start:
            ideas = json.loads(content[start:end])
            return ideas[:3]
    except Exception as e:
        print(f"  Warning: Failed to parse LLM ideas: {e}")

    # Fallback
    return [
        persona.get("focus_idea", {}).get("title", "AI-based process optimization"),
        "Automate manual data entry processes",
        "Implement digital dashboards for KPI tracking"
    ]


USER_SIMULATION_PROMPT = """You are simulating an employee at a small/medium enterprise (SME) who is participating in an AI consultation session.

COMPANY PROFILE:
{company_info}

YOUR ROLE:
- You are a {role} at this company
- You have LIMITED knowledge about AI and digitalization
- You answer questions based on the company profile above
- You can elaborate on challenges mentioned in the profile
- You may express uncertainty about technical topics
- You respond naturally, sometimes asking for clarification
- Keep responses concise (2-4 sentences typically)

FOCUS IDEA BEING DISCUSSED:
{focus_idea}

IMPORTANT:
- Stay in character as an SME employee
- Don't make up information not implied by the company profile
- Express realistic concerns about budget, time, and complexity
- Be open but somewhat skeptical about AI promises

Respond to the AI consultant's message."""


COST_ESTIMATION_SIMULATION_PROMPT = """You are simulating an employee at a small/medium enterprise (SME) who is discussing implementation costs for a digitalization/AI project.

COMPANY PROFILE:
{company_info}

YOUR ROLE:
- You are a {role} at this company
- You have LIMITED knowledge about IT implementation costs
- You need to understand costs to make budget decisions
- You ask practical questions about cost drivers and ROI
- Keep responses concise (2-4 sentences typically)

PROJECT BEING DISCUSSED:
{focus_idea}

IMPORTANT:
- Stay in character as an SME employee
- Ask about specific costs (setup, recurring, maintenance)
- Express concerns about budget constraints
- Ask about return on investment and payback period
- Request clarification on technical cost items you don't understand

Respond to the AI cost estimation consultant's message."""


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

    company_info = format_company_info(persona)
    focus_idea = persona.get("focus_idea", {})

    system_prompt = USER_SIMULATION_PROMPT.format(
        company_info=company_info,
        role="production manager" if "manufacturing" in persona.get("company", {}).get("sub_industry", "").lower() else "manager",
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

    response = completion(
        model=model or DEFAULT_MODEL,
        messages=messages,
        temperature=0.8,
        api_key=api_key
    )

    return response.choices[0].message.content


def simulate_cost_estimation_response(
    persona: Dict,
    consultant_message: str,
    conversation_history: List[Dict],
    model: str = None,
    api_key: str = None
) -> str:
    """Generate a simulated user response for the cost estimation discussion."""
    if not LITELLM_AVAILABLE or not api_key:
        return "What would be the initial investment needed, and what kind of return could we expect?"

    company_info = format_company_info(persona)
    focus_idea = persona.get("focus_idea", {})

    system_prompt = COST_ESTIMATION_SIMULATION_PROMPT.format(
        company_info=company_info,
        role="finance manager" if "manufacturing" in persona.get("company", {}).get("sub_industry", "").lower() else "operations manager",
        focus_idea=f"{focus_idea.get('title', '')}: {focus_idea.get('description', '')}"
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    for msg in conversation_history:
        if msg["role"] == "assistant":
            messages.append({"role": "user", "content": f"Cost Consultant: {msg['content']}"})
        else:
            messages.append({"role": "assistant", "content": msg["content"]})

    # Add current consultant message
    messages.append({"role": "user", "content": f"Cost Consultant: {consultant_message}"})

    response = completion(
        model=model or DEFAULT_MODEL,
        messages=messages,
        temperature=0.8,
        api_key=api_key
    )

    return response.choices[0].message.content


class E2EWorkflowTest:
    """End-to-end workflow test runner."""

    def __init__(self, api_key: str, model: str = None, verbose: bool = True):
        self.api_key = api_key
        self.model = model or DEFAULT_MODEL
        self.verbose = verbose
        self.session_uuid = None
        self.participant_uuid = None
        self.results = {}

    def log(self, message: str):
        """Print message if verbose mode enabled."""
        if self.verbose:
            print(message)

    def api_call(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make an API call to the backend."""
        url = f"{API_BASE_URL}{endpoint}"
        response = requests.request(method, url, **kwargs)
        return response

    def run_full_workflow(self, persona: Dict) -> Dict[str, Any]:
        """Run the complete workflow for a given persona."""
        self.log("\n" + "="*70)
        self.log(f"E2E WORKFLOW TEST: {persona.get('company', {}).get('name', 'Unknown')}")
        self.log("="*70)

        start_time = time.time()

        try:
            # Step 1a: Create session and add company info
            self.log("\n📋 STEP 1a: Create session and add company info")
            self._step1a_create_session(persona)

            # Step 1b: Submit maturity assessment
            self.log("\n📊 STEP 1b: Submit maturity assessment")
            self._step1b_maturity_assessment(persona)

            # Step 2: Join 6-3-5 as human participant
            self.log("\n🧠 STEP 2: Join 6-3-5 brainstorming")
            self._step2_join_brainstorming()

            # Step 2b: Start 6-3-5 with AI participants
            self.log("\n🤖 STEP 2b: Start 6-3-5 session")
            self._step2b_start_session()

            # Step 2c: Submit human ideas and run 2 rounds
            self.log("\n💡 STEP 2c: Submit ideas and run rounds")
            self._step2c_run_brainstorming(persona)

            # Step 3: Prioritization - vote for human's first idea
            self.log("\n⭐ STEP 3: Prioritization")
            self._step3_prioritization()

            # Step 4: Consultation with LLM persona
            self.log("\n💬 STEP 4: AI Consultation")
            self._step4_consultation(persona)

            # Step 5a: Business Case (potentials) - summarize consultation
            self.log("\n📊 STEP 5a: Business Case (Potentials)")
            self._step5a_business_case()

            # Step 5b: Cost Estimation
            self.log("\n💰 STEP 5b: Cost Estimation")
            self._step5b_cost_estimation(persona)

            # Step 6: PDF Export
            self.log("\n📄 STEP 6: PDF Export")
            self._step6_pdf_export()

            total_time = time.time() - start_time

            self.results["success"] = True
            self.results["total_time_seconds"] = round(total_time, 2)
            self.results["persona_id"] = persona.get("persona_id")
            self.results["company_name"] = persona.get("company", {}).get("name")
            self.results["maturity_level"] = persona.get("company", {}).get("digitalization_maturity", {}).get("level_name", "Unknown")

            self.log("\n" + "="*70)
            self.log(f"✅ WORKFLOW COMPLETED SUCCESSFULLY in {total_time:.1f}s")
            self.log("="*70)

        except Exception as e:
            self.results["success"] = False
            self.results["error"] = str(e)
            self.results["error_step"] = self.results.get("current_step", "unknown")
            self.log(f"\n❌ WORKFLOW FAILED: {e}")
            raise

        return self.results

    def _step1a_create_session(self, persona: Dict):
        """Create session and add company information."""
        self.results["current_step"] = "step1a_create_session"

        company = persona.get("company", {})
        company_name = company.get("name", "Test Company")

        # Create session
        response = self.api_call("POST", "/api/sessions/", json={
            "company_name": company_name
        })

        if response.status_code not in (200, 201):
            raise Exception(f"Failed to create session: {response.text}")

        session_data = response.json()
        self.session_uuid = session_data["session_uuid"]
        self.log(f"  ✓ Session created: {self.session_uuid[:8]}...")

        # Add company info as text
        company_info_text = format_company_info(persona)
        response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/company-info/text", json={
            "content": company_info_text
        })

        if response.status_code not in (200, 201):
            raise Exception(f"Failed to add company info: {response.text}")

        self.log(f"  ✓ Company info added ({len(company_info_text)} chars)")
        self.results["step1a"] = {
            "session_uuid": self.session_uuid,
            "company_info_length": len(company_info_text)
        }

    def _step1b_maturity_assessment(self, persona: Dict):
        """Submit maturity assessment from persona's acatech data."""
        self.results["current_step"] = "step1b_maturity_assessment"

        # Extract maturity assessment from persona
        assessment_data = extract_maturity_assessment(persona)

        # Submit maturity assessment
        response = self.api_call(
            "POST",
            f"/api/sessions/{self.session_uuid}/maturity",
            json=assessment_data
        )

        if response.status_code not in (200, 201):
            self.log(f"  ⚠ Failed to submit maturity assessment: {response.text}")
            self.results["step1b"] = {"success": False, "error": response.text}
            return

        maturity_data = response.json()
        overall_score = maturity_data.get("overall_score", 0)
        maturity_level = maturity_data.get("maturity_level", "Unknown")

        self.log(f"  ✓ Maturity assessment submitted")
        self.log(f"    Overall Score: {overall_score:.2f} ({maturity_level})")
        self.log(f"    - Resources: {assessment_data['resources_score']:.2f}")
        self.log(f"    - Information Systems: {assessment_data['information_systems_score']:.2f}")
        self.log(f"    - Culture: {assessment_data['culture_score']:.2f}")
        self.log(f"    - Organizational Structure: {assessment_data['organizational_structure_score']:.2f}")

        self.results["step1b"] = {
            "success": True,
            "overall_score": overall_score,
            "maturity_level": maturity_level,
            "dimension_scores": {
                "resources": assessment_data["resources_score"],
                "information_systems": assessment_data["information_systems_score"],
                "culture": assessment_data["culture_score"],
                "organizational_structure": assessment_data["organizational_structure_score"],
            }
        }

    def _step2_join_brainstorming(self):
        """Join 6-3-5 as human participant."""
        self.results["current_step"] = "step2_join_brainstorming"

        # Join as human participant
        response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/six-three-five/join", json={
            "name": "Test Participant"
        })

        if response.status_code not in (200, 201):
            raise Exception(f"Failed to join 6-3-5: {response.text}")

        participant_data = response.json()
        self.participant_uuid = participant_data["participant_uuid"]
        self.log(f"  ✓ Joined as participant: {self.participant_uuid[:8]}...")

        self.results["step2"] = {
            "participant_uuid": self.participant_uuid
        }

    def _step2b_start_session(self):
        """Start 6-3-5 session (creates AI participants and assigns sheets)."""
        self.results["current_step"] = "step2b_start_session"

        # Start 6-3-5 (adds AI participants and creates sheets)
        response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/six-three-five/start", json={
            "api_key": self.api_key
        })

        if response.status_code not in (200, 201):
            raise Exception(f"Failed to start 6-3-5: {response.text}")

        start_data = response.json()
        ai_participants = start_data.get("ai_participants", 0)
        self.log(f"  ✓ 6-3-5 started with {ai_participants} AI participants")

        # Wait for AI to generate initial ideas
        self.log(f"  ⏳ Waiting for AI initial idea generation...")
        time.sleep(5)

        self.results["step2b"] = {
            "ai_participants": ai_participants,
            "status": start_data.get("status")
        }

    def _step2c_run_brainstorming(self, persona: Dict):
        """Submit human ideas and run 2 rounds of brainstorming."""
        self.results["current_step"] = "step2c_run_brainstorming"

        # Get assigned sheet for human participant
        response = self.api_call(
            "GET",
            f"/api/sessions/{self.session_uuid}/six-three-five/my-sheet/{self.participant_uuid}"
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get sheet: {response.text}")

        sheet_data = response.json()
        sheet_id = sheet_data["sheet_id"]
        current_round = sheet_data.get("current_round", 1)
        self.log(f"  ✓ Assigned to sheet {sheet_id}, round {current_round}")

        # Generate and submit initial ideas
        ideas = generate_human_ideas(persona, self.model, self.api_key)
        self.log(f"  ✓ Generated {len(ideas)} initial ideas")

        for idea in ideas:
            self.log(f"    - {idea[:60]}...")

        response = self.api_call(
            "POST",
            f"/api/sessions/{self.session_uuid}/six-three-five/ideas?participant_uuid={self.participant_uuid}",
            json={
                "sheet_id": sheet_id,
                "round_number": current_round,
                "ideas": ideas
            }
        )

        if response.status_code not in (200, 201):
            raise Exception(f"Failed to submit ideas: {response.text}")

        self.log(f"  ✓ Human ideas submitted")
        self.results["step2"]["human_ideas"] = ideas
        self.results["step2"]["sheet_id"] = sheet_id

        # Run 2 rounds (advance round triggers AI idea generation)
        for round_num in range(2):
            self.log(f"  ⏳ Advancing to round {round_num + 2}...")

            response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/six-three-five/advance-round", json={
                "api_key": self.api_key
            })

            if response.status_code not in (200, 201):
                raise Exception(f"Failed to advance round: {response.text}")

            round_data = response.json()
            self.log(f"    ✓ {round_data.get('message', 'Round advanced')}")

            # Wait for AI idea generation
            time.sleep(3)

        # Get all ideas
        response = self.api_call("GET", f"/api/sessions/{self.session_uuid}/six-three-five/ideas")

        all_ideas = []
        if response.status_code == 200:
            all_ideas = response.json()
            self.log(f"  ✓ Total ideas generated: {len(all_ideas)}")

        self.results["step2c"] = {
            "rounds_completed": 2,
            "total_ideas": len(all_ideas)
        }

    def _step3_prioritization(self):
        """Vote for the human participant's first idea."""
        self.results["current_step"] = "step3_prioritization"

        # Get all ideas to find human's first idea
        response = self.api_call("GET", f"/api/sessions/{self.session_uuid}/six-three-five/ideas")

        if response.status_code != 200:
            raise Exception(f"Failed to get ideas: {response.text}")

        # API returns list directly
        all_ideas = response.json()
        if isinstance(all_ideas, dict):
            all_ideas = all_ideas.get("ideas", [])

        # Find the human participant's ideas (from round 1)
        human_ideas = [i for i in all_ideas if i.get("participant_name") == "Test Participant"]

        if not human_ideas:
            self.log("  ⚠ No human ideas found, skipping prioritization")
            self.results["step3"] = {"voted_idea": None}
            return

        first_idea = human_ideas[0]
        self.log(f"  ✓ Found human's first idea: {first_idea.get('content', '')[:50]}...")

        # Vote for the first idea (give it all 3 points - API requires exactly 3 total)
        response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/prioritization/vote", json={
            "participant_uuid": self.participant_uuid,
            "votes": {
                str(first_idea["id"]): 3  # Dict mapping idea_id -> points, must sum to 3
            }
        })

        if response.status_code not in (200, 201):
            self.log(f"  ⚠ Prioritization vote failed: {response.text}")
        else:
            self.log(f"  ✓ Voted for human's first idea (3 points)")

        self.results["step3"] = {
            "voted_idea_id": first_idea.get("id"),
            "voted_idea_content": first_idea.get("content")
        }

    def _step4_consultation(self, persona: Dict, max_turns: int = 4):
        """Run consultation with LLM persona simulating user responses."""
        self.results["current_step"] = "step4_consultation"

        # Start consultation
        response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/consultation/start", json={
            "api_key": self.api_key
        })

        if response.status_code not in (200, 201):
            raise Exception(f"Failed to start consultation: {response.text}")

        start_data = response.json()
        initial_message = start_data.get("message", "")
        self.log(f"  ✓ Consultation started")
        self.log(f"    AI: {initial_message[:100]}...")

        conversation = [{"role": "assistant", "content": initial_message}]

        # Run conversation turns
        for turn in range(max_turns):
            self.log(f"  ⏳ Turn {turn + 1}/{max_turns}...")

            # Generate user response using LLM persona
            user_response = simulate_user_response(
                persona=persona,
                consultant_message=conversation[-1]["content"],
                conversation_history=conversation[:-1],
                model=self.model,
                api_key=self.api_key
            )

            self.log(f"    User: {user_response[:80]}...")
            conversation.append({"role": "user", "content": user_response})

            # Send message to consultation
            response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/consultation/message", json={
                "content": user_response,
                "api_key": self.api_key
            })

            if response.status_code not in (200, 201):
                raise Exception(f"Failed to send consultation message: {response.text}")

            ai_response = response.json().get("message", "")
            self.log(f"    AI: {ai_response[:80]}...")
            conversation.append({"role": "assistant", "content": ai_response})

            # Small delay for API stability
            time.sleep(0.5)

        self.log(f"  ✓ Consultation completed ({len(conversation)} messages)")
        self.results["step4"] = {
            "turns": max_turns,
            "total_messages": len(conversation),
            "conversation_preview": [
                {"role": m["role"], "content": m["content"][:200] + "..." if len(m["content"]) > 200 else m["content"]}
                for m in conversation[:4]
            ]
        }

    def _step5a_business_case(self):
        """Generate business case consultation summary/findings."""
        self.results["current_step"] = "step5a_business_case"

        response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/consultation/summarize", json={
            "api_key": self.api_key
        })

        if response.status_code != 200:
            self.log(f"  ⚠ Business case summary generation failed: {response.text}")
            self.results["step5a"] = {"success": False}
            return

        summary_data = response.json()
        findings = summary_data.get("findings", [])

        # Handle both list and dict formats
        if isinstance(findings, dict):
            findings_list = list(findings.values()) if findings else []
            findings_keys = list(findings.keys())
        else:
            findings_list = findings
            findings_keys = [f.get("factor_type") for f in findings_list] if findings_list else []

        self.log(f"  ✓ Business case summary generated with {len(findings_list)} findings")

        for finding in findings_list[:3]:
            if isinstance(finding, dict):
                self.log(f"    - {finding.get('factor_type', 'unknown')}: {str(finding.get('finding_text', ''))[:50]}...")
            else:
                self.log(f"    - {str(finding)[:50]}...")

        self.results["step5a"] = {
            "success": True,
            "findings_count": len(findings_list),
            "finding_types": findings_keys
        }

    def _step5b_cost_estimation(self, persona: Dict, max_turns: int = 3):
        """Run cost estimation consultation with LLM persona simulating user responses."""
        self.results["current_step"] = "step5b_cost_estimation"

        # Start cost estimation
        response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/cost-estimation/start", json={
            "api_key": self.api_key
        })

        if response.status_code not in (200, 201):
            self.log(f"  ⚠ Failed to start cost estimation: {response.text}")
            self.results["step5b"] = {"success": False, "error": response.text}
            return

        start_data = response.json()
        initial_message = start_data.get("message", "")
        self.log(f"  ✓ Cost estimation started")
        self.log(f"    AI: {initial_message[:100]}...")

        conversation = [{"role": "assistant", "content": initial_message}]

        # Run conversation turns for cost estimation
        for turn in range(max_turns):
            self.log(f"  ⏳ Turn {turn + 1}/{max_turns}...")

            # Generate user response using LLM persona
            user_response = simulate_cost_estimation_response(
                persona=persona,
                consultant_message=conversation[-1]["content"],
                conversation_history=conversation[:-1],
                model=self.model,
                api_key=self.api_key
            )

            self.log(f"    User: {user_response[:80]}...")
            conversation.append({"role": "user", "content": user_response})

            # Send message to cost estimation
            response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/cost-estimation/message", json={
                "content": user_response,
                "api_key": self.api_key
            })

            if response.status_code not in (200, 201):
                self.log(f"  ⚠ Failed to send cost estimation message: {response.text}")
                break

            ai_response = response.json().get("message", "")
            self.log(f"    AI: {ai_response[:80]}...")
            conversation.append({"role": "assistant", "content": ai_response})

            # Small delay for API stability
            time.sleep(0.5)

        # Extract cost estimation findings
        self.log(f"  ⏳ Extracting cost findings...")
        response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/cost-estimation/extract", json={
            "api_key": self.api_key
        })

        cost_findings = {}
        if response.status_code == 200:
            cost_findings = response.json()
            self.log(f"  ✓ Cost findings extracted")
            # Log available findings
            for key, value in cost_findings.items():
                if value:
                    self.log(f"    - {key}: {str(value)[:50]}...")
        else:
            self.log(f"  ⚠ Cost extraction failed: {response.text}")

        self.log(f"  ✓ Cost estimation completed ({len(conversation)} messages)")
        self.results["step5b"] = {
            "success": True,
            "turns": max_turns,
            "total_messages": len(conversation),
            "cost_findings": {k: bool(v) for k, v in cost_findings.items()},
            "conversation_preview": [
                {"role": m["role"], "content": m["content"][:200] + "..." if len(m["content"]) > 200 else m["content"]}
                for m in conversation[:4]
            ]
        }

    def _step6_pdf_export(self):
        """Generate and validate PDF export."""
        self.results["current_step"] = "step6_pdf_export"

        # Generate PDF (returns PDF bytes directly)
        response = self.api_call("POST", f"/api/sessions/{self.session_uuid}/export/pdf")

        if response.status_code not in (200, 201):
            raise Exception(f"Failed to generate PDF: {response.text}")

        pdf_content = response.content
        pdf_size = len(pdf_content)
        self.log(f"  ✓ PDF generated: {pdf_size:,} bytes")

        # Validate PDF header
        if pdf_content[:4] != b'%PDF':
            raise Exception("Invalid PDF format - missing PDF header")

        self.log(f"  ✓ PDF format validated")

        # Save PDF if results directory exists
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = RESULTS_DIR / f"e2e_test_{timestamp}.pdf"

        with open(pdf_path, 'wb') as f:
            f.write(pdf_content)

        self.log(f"  ✓ PDF saved: {pdf_path}")

        self.results["step6"] = {
            "pdf_size_bytes": pdf_size,
            "pdf_path": str(pdf_path)
        }

    def cleanup(self):
        """Delete the test session."""
        if self.session_uuid:
            try:
                response = self.api_call("DELETE", f"/api/sessions/{self.session_uuid}")
                if response.status_code == 204:
                    self.log(f"  ✓ Test session deleted")
            except Exception as e:
                self.log(f"  ⚠ Failed to delete session: {e}")


def run_e2e_test(
    persona_id: str = None,
    api_key: str = None,
    model: str = None,
    verbose: bool = True,
    cleanup: bool = False
) -> Dict[str, Any]:
    """Run end-to-end workflow test."""

    # Load personas
    personas = load_personas()
    if not personas:
        raise ValueError("No benchmark personas found")

    # Select persona
    if persona_id:
        persona = next((p for p in personas if p.get("persona_id") == persona_id), None)
        if not persona:
            available = [p.get("persona_id") for p in personas]
            raise ValueError(f"Persona '{persona_id}' not found. Available: {available}")
    else:
        # Use first persona by default
        persona = personas[0]

    # Get API key
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("MISTRAL_API_KEY")

    if not api_key:
        raise ValueError("API key required. Set OPENAI_API_KEY or MISTRAL_API_KEY environment variable, or pass api_key parameter")

    # Run test
    test = E2EWorkflowTest(api_key=api_key, model=model, verbose=verbose)

    try:
        results = test.run_full_workflow(persona)
    finally:
        if cleanup:
            test.cleanup()

    return results


def save_results(results: Dict[str, Any]) -> str:
    """Save test results to file."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    persona_id = results.get("persona_id", "unknown")
    filename = f"e2e_{persona_id}_{timestamp}.json"
    filepath = RESULTS_DIR / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    return str(filepath)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="End-to-End Workflow Test for AI Consultant Application"
    )
    parser.add_argument(
        "--persona", type=str,
        help="Persona ID to use (default: first persona)"
    )
    parser.add_argument(
        "--api-key", type=str,
        help="LLM API key (or set OPENAI_API_KEY/MISTRAL_API_KEY env var)"
    )
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL,
        help=f"LLM model to use (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Reduce output verbosity"
    )
    parser.add_argument(
        "--cleanup", action="store_true",
        help="Delete test session after completion"
    )
    parser.add_argument(
        "--list-personas", action="store_true",
        help="List available personas"
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save results to file"
    )

    args = parser.parse_args()

    if args.list_personas:
        personas = load_personas()
        print("\nAvailable Personas:")
        print("-" * 50)
        for p in personas:
            company = p.get("company", {})
            print(f"  {p.get('persona_id')}")
            print(f"    Company: {company.get('name')}")
            print(f"    Industry: {company.get('sub_industry')}")
            print(f"    Focus: {p.get('focus_idea', {}).get('title', 'N/A')}")
            print()
        return

    # Check backend availability
    try:
        response = requests.get(f"{API_BASE_URL}/api/sessions/", timeout=5)
        if response.status_code != 200:
            print(f"Warning: Backend returned status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to backend at {API_BASE_URL}")
        print("Make sure the backend is running: cd backend && python -m uvicorn app.main:app --reload")
        sys.exit(1)

    try:
        results = run_e2e_test(
            persona_id=args.persona,
            api_key=args.api_key,
            model=args.model,
            verbose=not args.quiet,
            cleanup=args.cleanup
        )

        if args.save:
            filepath = save_results(results)
            print(f"\nResults saved to: {filepath}")

        # Print summary
        print("\n" + "="*50)
        print("TEST SUMMARY")
        print("="*50)
        print(f"Success: {results.get('success', False)}")
        print(f"Total Time: {results.get('total_time_seconds', 0):.1f}s")
        print(f"Session UUID: {results.get('step1a', {}).get('session_uuid', 'N/A')}")
        step1b = results.get('step1b', {})
        print(f"Maturity Level: {step1b.get('maturity_level', 'N/A')} (Score: {step1b.get('overall_score', 0):.2f})")
        print(f"Ideas Generated: {results.get('step2c', {}).get('total_ideas', 0)}")
        print(f"Consultation Messages: {results.get('step4', {}).get('total_messages', 0)}")
        print(f"Business Case Findings: {results.get('step5a', {}).get('findings_count', 0)}")
        print(f"Cost Estimation Messages: {results.get('step5b', {}).get('total_messages', 0)}")
        print(f"PDF Size: {results.get('step6', {}).get('pdf_size_bytes', 0):,} bytes")

        sys.exit(0 if results.get("success") else 1)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
