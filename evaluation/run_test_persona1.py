#!/usr/bin/env python3
"""
Automated test run for Persona 1: Müller Metallbau GmbH (mfg_01_metal_quality)
Runs through all steps of the AI Consultant workflow via API calls.
Saves PDF report and session backup at the end.

Usage:
  python run_test_persona1.py [options]

Options:
  --consultant-model MODEL         LLM for the AI consultant (default: openai/mistral-large-3-675b-instruct-2512)
  --consultant-base URL            API base URL for consultant LLM (default: https://chat-ai.academiccloud.de/v1)
  --consultant-temperature FLOAT   Temperature for all consultant chat steps (default: backend default 0.7)
  --brainstorming-temperature FLOAT  Override temperature for brainstorming (Step 2)
  --consultation-temperature FLOAT   Override temperature for consultation (Step 4)
  --business-case-temperature FLOAT  Override temperature for business case (Step 5a)
  --cost-estimation-temperature FLOAT Override temperature for cost estimation (Step 5b)
  --extraction-temperature FLOAT     Override temperature for extraction/summaries
  --export-temperature FLOAT         Override temperature for SWOT/briefing export
  --reasoning-model MODEL          LLM for math-heavy extraction steps (business case + cost estimation).
                                   When set, the session LLM is temporarily swapped to this model for
                                   the extract calls, then restored to the consultant model.
                                   (default: same as consultant, i.e. no swap)
  --reasoning-base URL             API base URL for reasoning model (default: same as consultant)
  --reasoning-api-key KEY          API key for reasoning model (default: same as --api-key)
  --user-agent-model MODEL         LLM for the user agent / persona (default: same as consultant)
  --user-agent-base URL            API base URL for user agent LLM (default: same as consultant)
  --user-agent-temperature FLOAT   Temperature for user agent LLM (default: 0.7)
  --api-key KEY                    API key (default: SAIA_API_KEY env var)
  --user-agent-api-key KEY         Separate API key for user agent (default: same as --api-key)
  --rounds N                       Number of consultation rounds per step (default: 5/4/4)

Examples:
  # Same model for both (default):
  python run_test_persona1.py

  # Different models on SAIA - benchmark consultant while keeping user agent constant:
  python run_test_persona1.py \\
    --consultant-model openai/mistral-large-3-675b-instruct-2512 \\
    --user-agent-model openai/llama-3.3-70b-instruct

  # Use ScaDS.AI for consultant, SAIA for user agent:
  python run_test_persona1.py \\
    --consultant-model openai/deepseek-ai/DeepSeek-V3.2 \\
    --consultant-base https://llm.scads.ai/v1 --api-key $SCADS_API_KEY \\
    --user-agent-model openai/llama-3.3-70b-instruct \\
    --user-agent-base https://chat-ai.academiccloud.de/v1 --user-agent-api-key $SAIA_API_KEY

  # Hybrid: consultant on SAIA, reasoning model (DeepSeek-R1) for math extraction steps:
  python run_test_persona1.py \\
    --consultant-model openai/mistral-large-3-675b-instruct-2512 \\
    --reasoning-model openai/deepseek-r1-distill-llama-70b \\
    --reasoning-base https://chat-ai.academiccloud.de/v1
"""

import argparse
import requests
import json
import time
import sys
import os
from datetime import datetime

# =========================================
# CLI Arguments
# =========================================
parser = argparse.ArgumentParser(description="Automated test for Persona 1: Müller Metallbau GmbH")
parser.add_argument("--consultant-model", default="openai/mistral-large-3-675b-instruct-2512",
                    help="LLM model for the AI consultant (default: openai/mistral-large-3-675b-instruct-2512)")
parser.add_argument("--consultant-base", default="https://chat-ai.academiccloud.de/v1",
                    help="API base URL for consultant LLM")
parser.add_argument("--consultant-temperature", type=float, default=None,
                    help="Temperature for consultant LLM (default: backend default 0.7)")
parser.add_argument("--brainstorming-temperature", type=float, default=None,
                    help="Temperature for brainstorming/Step 2 (overrides --consultant-temperature)")
parser.add_argument("--consultation-temperature", type=float, default=None,
                    help="Temperature for consultation/Step 4 (overrides --consultant-temperature)")
parser.add_argument("--business-case-temperature", type=float, default=None,
                    help="Temperature for business case/Step 5a (overrides --consultant-temperature)")
parser.add_argument("--cost-estimation-temperature", type=float, default=None,
                    help="Temperature for cost estimation/Step 5b (overrides --consultant-temperature)")
parser.add_argument("--extraction-temperature", type=float, default=None,
                    help="Temperature for extraction/summary tasks (overrides --consultant-temperature)")
parser.add_argument("--export-temperature", type=float, default=None,
                    help="Temperature for export/SWOT/briefing generation (overrides --consultant-temperature)")
parser.add_argument("--user-agent-model", default=None,
                    help="LLM model for the user agent (default: same as consultant)")
parser.add_argument("--user-agent-base", default=None,
                    help="API base URL for user agent LLM (default: same as consultant)")
parser.add_argument("--user-agent-temperature", type=float, default=None,
                    help="Temperature for user agent LLM (default: 0.7)")
parser.add_argument("--api-key", default=os.environ.get("SAIA_API_KEY", "3cacddf7a7eac61dca578b537b186b17"),
                    help="API key for consultant LLM (default: SAIA_API_KEY env var)")
parser.add_argument("--user-agent-api-key", default=None,
                    help="API key for user agent LLM (default: same as --api-key)")
parser.add_argument("--reasoning-model", default=None,
                    help="LLM for math-heavy extraction steps (business case + cost estimation extract). "
                         "When set, session is temporarily swapped to this model for those calls. "
                         "(default: same as consultant)")
parser.add_argument("--reasoning-base", default=None,
                    help="API base URL for reasoning model (default: same as --consultant-base)")
parser.add_argument("--reasoning-api-key", default=None,
                    help="API key for reasoning model (default: same as --api-key)")
parser.add_argument("--consultation-rounds", type=int, default=12,
                    help="Max consultation chat rounds; exits early if consultant signals completion (default: 12)")
parser.add_argument("--business-case-rounds", type=int, default=8,
                    help="Max business case chat rounds; exits early if consultant signals completion (default: 8)")
parser.add_argument("--cost-estimation-rounds", type=int, default=8,
                    help="Max cost estimation chat rounds; exits early if consultant signals completion (default: 8)")
parser.add_argument("--language", default="en", choices=["en", "de"],
                    help="Prompt language for the consultant (default: en)")
parser.add_argument("--base-url", default="http://localhost:8000",
                    help="Backend API base URL (default: http://localhost:8000)")
parser.add_argument("--persona", default="mfg_01_metal_quality",
                    help="Persona ID to run (default: mfg_01_metal_quality)")
parser.add_argument("--skip-ideation", action="store_true",
                    help="Skip Steps 2 & 3 (6-3-5 brainstorming + prioritization) and inject "
                         "the persona's focus idea directly. Saves ~10 API calls per run.")
parser.add_argument("--incremental-extraction", action="store_true", default=False,
                    help="Run incremental extraction every 2 rounds during consultation (Step 4). "
                         "Disabled by default to save API calls — final extraction at step end is sufficient.")
parser.add_argument("--no-analysis", action="store_true",
                    help="Skip SWOT analysis and transition briefing generation (2 LLM calls). "
                         "WARNING: the evaluation judge scores both outputs (SWOT Analysis Quality "
                         "and Technical Briefing Quality, weight 0.9 each). Using this flag will "
                         "mark those criteria as N/A and exclude them from the weighted score.")
parser.add_argument("--no-pdf", action="store_true",
                    help="Skip PDF report generation (JSON exports are still saved). "
                         "Use this for eval runs where only the JSON findings are needed.")
args = parser.parse_args()

BASE_URL = args.base_url
PERSONA_ID = args.persona

# Load persona metadata for display names
_personas_path = os.path.join(os.path.dirname(__file__), "benchmark_personas.json")
try:
    with open(_personas_path, "r", encoding="utf-8") as _f:
        _all_personas = json.load(_f).get("personas", [])
    _persona_meta = next((p for p in _all_personas if p.get("persona_id") == PERSONA_ID), None)
    PERSONA_COMPANY_NAME = _persona_meta["company"]["name"] if _persona_meta else PERSONA_ID
    PERSONA_FOCUS_TITLE = _persona_meta.get("focus_idea", {}).get("title", "N/A") if _persona_meta else "N/A"
except Exception:
    PERSONA_COMPANY_NAME = PERSONA_ID
    PERSONA_FOCUS_TITLE = "N/A"

# Consultant LLM config
CONSULTANT_MODEL = args.consultant_model
CONSULTANT_BASE = args.consultant_base
CONSULTANT_TEMPERATURE = args.consultant_temperature
# Build per-step temperature config
TEMPERATURE_CONFIG = {}
temp_fields = {
    'brainstorming': args.brainstorming_temperature,
    'consultation': args.consultation_temperature,
    'business_case': args.business_case_temperature,
    'cost_estimation': args.cost_estimation_temperature,
    'extraction': args.extraction_temperature,
    'export': args.export_temperature,
}
for key, val in temp_fields.items():
    if val is not None:
        TEMPERATURE_CONFIG[key] = val
    elif CONSULTANT_TEMPERATURE is not None:
        # --consultant-temperature sets all chat temperatures as fallback
        if key in ('brainstorming', 'consultation', 'business_case', 'cost_estimation'):
            TEMPERATURE_CONFIG[key] = CONSULTANT_TEMPERATURE
API_KEY = args.api_key

# User agent LLM config (defaults to consultant if not specified)
USER_AGENT_MODEL = args.user_agent_model or CONSULTANT_MODEL
USER_AGENT_BASE = args.user_agent_base or CONSULTANT_BASE
USER_AGENT_API_KEY = args.user_agent_api_key or API_KEY
USER_AGENT_TEMPERATURE = args.user_agent_temperature

# Reasoning model config (for business case + cost estimation extract steps)
REASONING_MODEL = args.reasoning_model  # None = no swap, use consultant model
REASONING_BASE = args.reasoning_base or args.consultant_base
REASONING_API_KEY = args.reasoning_api_key or args.api_key

# Build user_agent_config for test-mode endpoints (None if same as consultant)
USER_AGENT_CONFIG = None
if args.user_agent_model or args.user_agent_base or args.user_agent_api_key or args.user_agent_temperature is not None:
    USER_AGENT_CONFIG = {
        "model": USER_AGENT_MODEL,
        "api_base": USER_AGENT_BASE,
        "api_key": USER_AGENT_API_KEY
    }
    if USER_AGENT_TEMPERATURE is not None:
        USER_AGENT_CONFIG["temperature"] = USER_AGENT_TEMPERATURE

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_runs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Number of chat rounds per step
CONSULTATION_ROUNDS = args.consultation_rounds
BUSINESS_CASE_ROUNDS = args.business_case_rounds
COST_ESTIMATION_ROUNDS = args.cost_estimation_rounds


def log(msg, level="INFO"):
    prefix = {"INFO": "   ", "OK": "✅", "ERR": "❌", "WAIT": "⏳", "STEP": "\n🔷"}
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {prefix.get(level, '')} {msg}")


# Phrases that indicate the consultant is wrapping up a step and proposing to move on.
# Used for early exit from conversation loops.
_STEP_COMPLETE_SIGNALS_DE = [
    # Expliziter Schrittwechsel
    "nächsten schritt", "nächste schritt", "nächsten phase", "nächste phase",
    "weiter zu schritt", "kommen wir zu", "gehen wir zu", "gehen wir weiter",
    "möchten sie weitergehen", "bereit für den nächsten", "bereit weiterzugehen",
    "zu schritt 5", "zu schritt 6", "zum nächsten thema",
    # Zusammenfassung geben
    "lassen sie mich zusammenfassen", "ich möchte kurz zusammenfassen",
    "zusammenfassend", "fassen wir zusammen", "fassen wir die wichtigsten",
    "ich fasse zusammen", "kurz zusammengefasst", "abschließend",
    "überblick über das, was wir", "überblick über unsere",
    # Zusammenfassung anbieten
    "soll ich eine zusammenfassung", "soll ich kurz zusammenfassen",
    "möchten sie eine zusammenfassung", "kann ich gerne zusammenfassen",
    "ich kann zusammenfassen",
    # Business Case / nächste Phase empfehlen
    "business case", "wirtschaftlichkeit", "kosten und nutzen",
    "kosten-nutzen", "rentabilität", "return on investment",
    "lohnt sich das", "lohnt sich die investition",
    "empfehle ich, den business case", "würde ich vorschlagen, die kosten",
]
_STEP_COMPLETE_SIGNALS_EN = [
    # Explicit step transition
    "next step", "move on to", "proceed to", "let's move to",
    "ready to move", "shall we proceed", "step 5", "step 6", "next topic",
    # Giving a summary
    "to summarize", "in summary", "let me summarize", "summarizing",
    "to wrap up", "in conclusion", "let me recap",
    # Offering a summary
    "shall i summarize", "would you like a summary", "i can summarize",
    # Business case recommendation
    "business case", "return on investment", "cost-benefit",
    "costs and benefits", "financial viability", "roi",
]

def is_step_complete(ai_response: str) -> bool:
    """Return True if the AI consultant signals it's ready to move to the next step."""
    lowered = ai_response.lower()
    signals = _STEP_COMPLETE_SIGNALS_DE + _STEP_COMPLETE_SIGNALS_EN
    return any(signal in lowered for signal in signals)


def api_get(path, **kwargs):
    r = requests.get(f"{BASE_URL}{path}", **kwargs)
    if r.status_code >= 400:
        log(f"GET {path} → {r.status_code}: {r.text[:300]}", "ERR")
    return r


def api_post(path, json_data=None, _retries=3, _retry_wait=120, **kwargs):
    for attempt in range(1, _retries + 1):
        r = requests.post(f"{BASE_URL}{path}", json=json_data, **kwargs)
        if r.status_code == 429:
            # Backend rate limit — wait for retry_after or 15s
            wait = 15
            log(f"POST {path} → 429 backend rate limit (attempt {attempt}/{_retries}), "
                f"retrying in {wait}s...", "WARN")
            time.sleep(wait)
            continue
        if r.status_code == 500 and (
            "RateLimitError" in r.text or "overloaded_error" in r.text
            or "ServiceUnavailableError" in r.text or "UNAVAILABLE" in r.text
            or "high demand" in r.text
        ):
            if attempt < _retries:
                if "RateLimitError" in r.text:
                    label = "RateLimitError"
                elif "overloaded_error" in r.text:
                    label = "overloaded_error"
                else:
                    label = "ServiceUnavailableError"
                log(f"POST {path} → 500 {label} (attempt {attempt}/{_retries}), "
                    f"retrying in {_retry_wait}s...", "WARN")
                time.sleep(_retry_wait)
                continue
        if r.status_code == 500 and "Connection error" in r.text:
            if attempt < _retries:
                log(f"POST {path} → 500 Connection error (attempt {attempt}/{_retries}), "
                    f"retrying in 30s...", "WARN")
                time.sleep(30)
                continue
        if r.status_code >= 400 and "credit balance is too low" in r.text:
            log(f"POST {path} → {r.status_code}: Anthropic credit balance exhausted — aborting run", "ERR")
            sys.exit(1)
        if r.status_code == 500 and (
            "tokens per day" in r.text.lower() or "TPD" in r.text
        ):
            log(f"POST {path} → 500: Daily token limit (TPD) exhausted for consultant model — skipping consultant", "ERR")
            sys.exit(2)  # returncode 2 = rate limit / quota exhausted, skip consultant
        if r.status_code >= 400:
            log(f"POST {path} → {r.status_code}: {r.text[:300]}", "ERR")
        return r
    return r


def check_user_agent_rate_limit(r):
    """Exit with returncode 3 if the user agent hit a rate limit — signals matrix runner to rotate key."""
    if r.status_code == 500 and (
        "RateLimitError" in r.text or "tokens per day" in r.text.lower()
        or "TPD" in r.text or "UNAVAILABLE" in r.text
        or "ServiceUnavailableError" in r.text
    ):
        log("User agent rate limit hit — signaling matrix runner to rotate key (exit 3)", "ERR")
        sys.exit(3)


def api_put(path, json_data=None, **kwargs):
    r = requests.put(f"{BASE_URL}{path}", json=json_data, **kwargs)
    if r.status_code >= 400:
        log(f"PUT {path} → {r.status_code}: {r.text[:300]}", "ERR")
    return r


def wait_for_ai(seconds=12, label="AI generation"):
    """Wait for background AI tasks to complete."""
    log(f"Waiting {seconds}s for {label}...", "WAIT")
    time.sleep(seconds)


def swap_llm(session_uuid, model, api_base, label=""):
    """Temporarily update the session's LLM model + api_base via expert-settings."""
    r = api_put(f"/api/sessions/{session_uuid}/expert-settings", {
        "expert_mode": True,
        "llm_config": {"model": model, "api_base": api_base}
    })
    if r.status_code == 200:
        log(f"LLM swapped to {model}{' (' + label + ')' if label else ''}", "OK")
    else:
        log(f"LLM swap failed ({r.status_code}) — continuing with current model", "ERR")


def with_reasoning_model(session_uuid, fn):
    """
    Run fn() with the session temporarily using the reasoning model.
    Restores the consultant model afterwards. No-op if no reasoning model configured.
    """
    if not REASONING_MODEL:
        return fn()
    swap_llm(session_uuid, REASONING_MODEL, REASONING_BASE, label="reasoning")
    try:
        return fn()
    finally:
        swap_llm(session_uuid, CONSULTANT_MODEL, CONSULTANT_BASE, label="consultant")


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    log(f"AUTOMATED TEST: {PERSONA_ID} - {PERSONA_COMPANY_NAME}", "STEP")
    log(f"Focus: {PERSONA_FOCUS_TITLE}")
    log(f"Consultant LLM: {CONSULTANT_MODEL} @ {CONSULTANT_BASE}")
    if REASONING_MODEL:
        log(f"Reasoning LLM:  {REASONING_MODEL} @ {REASONING_BASE} (business case + cost extraction)")
    if TEMPERATURE_CONFIG:
        log(f"Temperature config: {TEMPERATURE_CONFIG}")
    log(f"User Agent LLM: {USER_AGENT_MODEL} @ {USER_AGENT_BASE}")
    if USER_AGENT_TEMPERATURE is not None:
        log(f"User Agent Temperature: {USER_AGENT_TEMPERATURE}")
    if USER_AGENT_CONFIG:
        log("(separate user agent config active)")

    # =========================================
    # STEP 0: Create Session
    # =========================================
    log("STEP 0: Create Session", "STEP")

    r = api_post("/api/sessions/", {"company_name": PERSONA_COMPANY_NAME})
    if r.status_code != 201:
        log("Failed to create session", "ERR")
        sys.exit(1)

    session = r.json()
    session_uuid = session["session_uuid"]
    log(f"Session created: {session_uuid}", "OK")

    # Configure LLM settings for the consultant
    llm_config = {
        "model": CONSULTANT_MODEL,
        "api_base": CONSULTANT_BASE
    }
    if TEMPERATURE_CONFIG:
        llm_config["temperature_config"] = TEMPERATURE_CONFIG
    r = api_put(f"/api/sessions/{session_uuid}/expert-settings", {
        "expert_mode": True,
        "prompt_language": args.language,
        "llm_config": llm_config
    })
    if r.status_code == 200:
        log(f"Consultant LLM configured: {CONSULTANT_MODEL}", "OK")
        if TEMPERATURE_CONFIG:
            log(f"Temperature config: {TEMPERATURE_CONFIG}", "OK")
    else:
        log(f"Expert settings: {r.status_code} - continuing with defaults", "INFO")

    # =========================================
    # STEP 1a: Company Profile
    # =========================================
    log("STEP 1a: Fill Company Profile from Persona", "STEP")

    r = api_get(f"/api/test-mode/personas/{PERSONA_ID}/company-profile")
    if r.status_code != 200:
        log(f"Failed to load company profile ({r.status_code}) — aborting run", "ERR")
        sys.exit(1)
    profile = r.json()
    log(f"Company: {profile['company_name']}", "OK")

    r = api_post(f"/api/sessions/{session_uuid}/company-info/text", {
        "content": profile["profile_text"]
    })
    if r.status_code in (200, 201):
        log("Company profile text submitted", "OK")

    log("Extracting structured profile via LLM...", "WAIT")
    r = api_post(f"/api/sessions/{session_uuid}/company-profile/extract", {
        "api_key": API_KEY
    })
    if r.status_code == 200:
        extracted = r.json()
        log(f"Profile extracted - quality: {extracted.get('extraction_quality', 'N/A')}", "OK")
    else:
        log(f"Profile extraction failed ({r.status_code}) — aborting run", "ERR")
        sys.exit(1)

    # =========================================
    # STEP 1b: Maturity Assessment
    # =========================================
    log("STEP 1b: Fill Maturity Assessment from Persona", "STEP")

    r = api_get(f"/api/test-mode/personas/{PERSONA_ID}/maturity-assessment")
    maturity_data = r.json()
    scores = maturity_data["scores"]

    def avg_score(dim_scores):
        vals = [dim_scores[f"q{i}"] for i in range(1, 5)]
        return sum(vals) / len(vals)

    maturity_payload = {
        "resources_score": avg_score(scores["resources"]),
        "resources_details": scores["resources"],
        "information_systems_score": avg_score(scores["informationSystems"]),
        "information_systems_details": {
            "q1": scores["informationSystems"]["q1"],
            "q2": scores["informationSystems"]["q2"],
            "q3": scores["informationSystems"]["q3"],
            "q4": scores["informationSystems"]["q4"]
        },
        "culture_score": avg_score(scores["culture"]),
        "culture_details": scores["culture"],
        "organizational_structure_score": avg_score(scores["organizationalStructure"]),
        "organizational_structure_details": {
            "q1": scores["organizationalStructure"]["q1"],
            "q2": scores["organizationalStructure"]["q2"],
            "q3": scores["organizationalStructure"]["q3"],
            "q4": scores["organizationalStructure"]["q4"]
        }
    }

    r = api_post(f"/api/sessions/{session_uuid}/maturity", maturity_payload)
    if r.status_code in (200, 201):
        mat = r.json()
        log(f"Maturity: Level {mat.get('maturity_level', 'N/A')} (score: {mat.get('overall_score', 'N/A')})", "OK")

    # =========================================
    # STEP 2 & 3: Ideation (6-3-5 + Prioritization)
    # =========================================
    if args.skip_ideation:
        log("STEP 2 & 3: Skipped (--skip-ideation) — injecting focus idea directly", "STEP")
        r = api_post(
            f"/api/test-mode/{session_uuid}/inject-focus-idea"
            f"?persona_id={PERSONA_ID}"
        )
        if r.status_code == 200:
            log(f"Focus idea injected: {r.json().get('focus_idea', '')[:100]}...", "OK")
        else:
            log(f"Focus idea injection failed: {r.text[:200]}", "ERR")
            sys.exit(1)
    else:
        log("STEP 2: 6-3-5 Brainwriting", "STEP")

        r = api_post(f"/api/sessions/{session_uuid}/six-three-five/join", {
            "name": f"Test User ({PERSONA_COMPANY_NAME})"
        })
        if r.status_code not in (200, 201):
            log("Failed to join 6-3-5", "ERR")
            sys.exit(1)

        human_participant = r.json()
        human_uuid = human_participant["participant_uuid"]
        log(f"Joined as participant: {human_uuid[:12]}...", "OK")

        log("Starting 6-3-5 session...", "WAIT")
        r = api_post(f"/api/sessions/{session_uuid}/six-three-five/start", {
            "api_key": API_KEY
        })
        if r.status_code == 200:
            start_result = r.json()
            log(f"6-3-5 started: {start_result.get('total_participants')} participants "
                f"({start_result.get('ai_participants')} AI)", "OK")
        else:
            log(f"Failed to start 6-3-5: {r.text[:200]}", "ERR")
            sys.exit(1)

        wait_for_ai(15, "AI idea generation (round 1)")

        for round_num in range(1, 7):
            log(f"--- Round {round_num}/6 ---", "INFO")

            # Get human's current sheet
            r = api_get(f"/api/sessions/{session_uuid}/six-three-five/my-sheet/{human_uuid}")
            if r.status_code != 200:
                log(f"Failed to get sheet for round {round_num}", "ERR")
                break

            sheet_data = r.json()
            sheet_id = sheet_data["sheet_id"]
            existing_ideas = [i["content"] for i in sheet_data.get("all_ideas", [])]

            # Generate ideas using test-mode persona agent
            ideas_body = {"previous_ideas": existing_ideas}
            if USER_AGENT_CONFIG:
                ideas_body["user_agent_config"] = USER_AGENT_CONFIG
            r = api_post(
                f"/api/test-mode/{session_uuid}/generate-ideas"
                f"?persona_id={PERSONA_ID}&round_number={round_num}",
                ideas_body,
                headers={"X-API-Key": USER_AGENT_API_KEY} if USER_AGENT_API_KEY else {}
            )

            if r.status_code == 200:
                ideas_result = r.json()
                generated_ideas = ideas_result["ideas"]
                log(f"Generated {len(generated_ideas)} ideas", "OK")
                for i, idea in enumerate(generated_ideas):
                    log(f"  {i+1}. {idea[:80]}{'...' if len(idea) > 80 else ''}", "INFO")
            else:
                log(f"Idea generation failed, using fallback ideas", "ERR")
                generated_ideas = [
                    "Camera-based inline defect detection at CNC exits",
                    "ML surface quality classification for automated QC",
                    "Digital quality dashboard with real-time reject alerts"
                ]

            # Submit ideas (participant_uuid is query param, body has sheet_id + round_number + ideas)
            r = api_post(
                f"/api/sessions/{session_uuid}/six-three-five/ideas"
                f"?participant_uuid={human_uuid}",
                {
                    "sheet_id": sheet_id,
                    "round_number": round_num,
                    "ideas": generated_ideas[:3]
                }
            )
            if r.status_code == 200:
                log(f"Ideas submitted for round {round_num}", "OK")
            else:
                log(f"Submit failed: {r.text[:200]}", "ERR")

            # Advance round (except after last)
            if round_num < 6:
                r = api_post(f"/api/sessions/{session_uuid}/six-three-five/advance-round", {
                    "api_key": API_KEY
                })
                if r.status_code == 200:
                    log(f"Advanced to round {round_num + 1}", "OK")
                else:
                    log(f"Advance failed: {r.text[:200]}", "ERR")
                wait_for_ai(12, f"AI ideas (round {round_num + 1})")

        # Total ideas
        r = api_get(f"/api/sessions/{session_uuid}/six-three-five/ideas")
        if r.status_code == 200:
            all_ideas = r.json()
            log(f"Total ideas generated: {len(all_ideas)}", "OK")

        # =========================================
        # STEP 3a: Clustering & Cluster Voting
        # =========================================
        log("STEP 3a: Idea Clustering & Voting", "STEP")

        log("Generating clusters via LLM...", "WAIT")
        r = api_post(f"/api/sessions/{session_uuid}/prioritization/cluster", {
            "api_key": API_KEY
        })

        if r.status_code != 200:
            log(f"Clustering failed: {r.text[:300]}", "ERR")
            sys.exit(1)

        clusters_result = r.json()
        clusters = clusters_result.get("clusters", [])
        log(f"Generated {len(clusters)} clusters", "OK")

        # Find cluster containing focus idea keywords
        focus_cluster_id = None
        focus_keywords = ["quality", "inspection", "visual", "defect", "camera", "vision"]

        for cluster in clusters:
            cluster_text = f"{cluster['name']} {cluster.get('description', '')}".lower()
            ideas_text = " ".join([str(i.get("content", "")).lower() for i in cluster.get("ideas", [])])
            combined = f"{cluster_text} {ideas_text}"
            matches = sum(1 for kw in focus_keywords if kw in combined)
            log(f"  Cluster {cluster['id']}: {cluster['name']} "
                f"({len(cluster.get('idea_ids', []))} ideas, keyword matches: {matches})", "INFO")
            if matches >= 2 and focus_cluster_id is None:
                focus_cluster_id = cluster["id"]

        if focus_cluster_id is None:
            focus_cluster_id = clusters[0]["id"] if clusters else None
            log(f"No keyword match, defaulting to cluster {focus_cluster_id}", "INFO")

        log(f"Focus cluster selected: {focus_cluster_id}", "OK")

        # Get participants for voting
        r = api_get(f"/api/sessions/{session_uuid}/six-three-five/status")
        participants = r.json().get("participants", [])

        # All participants vote for focus cluster
        for p in participants:
            r = api_post(f"/api/sessions/{session_uuid}/prioritization/cluster-vote", {
                "participant_uuid": p["uuid"],
                "votes": {str(focus_cluster_id): 3}
            })
            if r.status_code == 200:
                log(f"  {p['name']}: 3 pts → cluster {focus_cluster_id}", "OK")

        # Select focus cluster
        r = api_post(f"/api/sessions/{session_uuid}/prioritization/select-cluster", {
            "cluster_id": focus_cluster_id
        })
        log(f"Cluster {focus_cluster_id} selected for Phase 2", "OK")

        # =========================================
        # STEP 3b: Idea Voting within Cluster
        # =========================================
        log("STEP 3b: Idea Assessment & Voting", "STEP")

        log("Assessing ideas...", "WAIT")
        r = api_post(f"/api/sessions/{session_uuid}/prioritization/assess-cluster-ideas", {
            "api_key": API_KEY
        })
        if r.status_code == 200:
            assessed = r.json()
            log(f"Assessed {len(assessed.get('ideas', []))} ideas", "OK")

        # Get ideas in cluster
        r = api_get(f"/api/sessions/{session_uuid}/prioritization/cluster-ideas")
        ideas_in_cluster = r.json().get("ideas", [])
        log(f"Ideas in cluster: {len(ideas_in_cluster)}", "OK")

        # Find best matching focus idea
        focus_idea_id = None
        best_score = 0
        focus_kw = ["visual", "quality", "inspection", "camera", "defect", "surface", "inline", "vision"]

        for idea in ideas_in_cluster:
            content_lower = idea["content"].lower()
            score = sum(1 for kw in focus_kw if kw in content_lower)
            log(f"  Idea {idea['id']}: {idea['content'][:70]}... (match: {score})", "INFO")
            if score > best_score:
                best_score = score
                focus_idea_id = idea["id"]

        if focus_idea_id is None and ideas_in_cluster:
            focus_idea_id = ideas_in_cluster[0]["id"]

        log(f"Focus idea: {focus_idea_id} (match score: {best_score})", "OK")

        # All participants vote for focus idea
        for p in participants:
            r = api_post(f"/api/sessions/{session_uuid}/prioritization/idea-vote", {
                "participant_uuid": p["uuid"],
                "votes": {str(focus_idea_id): 3}
            })
            if r.status_code == 200:
                log(f"  {p['name']}: 3 pts → idea {focus_idea_id}", "OK")

        r = api_get(f"/api/sessions/{session_uuid}/prioritization/idea-results")
        if r.status_code == 200:
            top = r.json().get("top_ideas", [])
            if top:
                log(f"Top idea: {top[0]['idea_content'][:80]}... ({top[0]['total_points']} pts)", "OK")

    # =========================================
    # STEP 4: Consultation Chat
    # =========================================
    log("STEP 4: AI Consultation Chat", "STEP")

    log("Starting consultation...", "WAIT")
    r = api_post(f"/api/sessions/{session_uuid}/consultation/start", {
        "api_key": API_KEY
    })
    if r.status_code == 200:
        log(f"AI: {r.json().get('content', '')[:150]}...", "OK")
    else:
        log(f"Failed: {r.text[:200]}", "ERR")
        sys.exit(1)

    msg_count = 1  # AI greeting counts as 1
    for rnd in range(1, CONSULTATION_ROUNDS + 1):
        log(f"--- Consultation Round {rnd}/{CONSULTATION_ROUNDS} ---", "INFO")

        # Generate persona response (user agent LLM)
        ua_body = {"user_agent_config": USER_AGENT_CONFIG} if USER_AGENT_CONFIG else None
        r = api_post(
            f"/api/test-mode/{session_uuid}/generate-response"
            f"?persona_id={PERSONA_ID}&message_type=consultation",
            ua_body,
            headers={"X-API-Key": USER_AGENT_API_KEY} if USER_AGENT_API_KEY else {}
        )
        if r.status_code != 200:
            check_user_agent_rate_limit(r)
            log(f"Persona response failed: {r.text[:200]}", "ERR")
            break
        ua_data = r.json()
        persona_msg = ua_data["response"]
        log(f"Persona: {persona_msg[:120]}...", "INFO")

        # Send to consultant
        r = api_post(f"/api/sessions/{session_uuid}/consultation/message", {
            "content": persona_msg,
            "api_key": API_KEY
        })
        if r.status_code == 200:
            ai_resp = r.json().get("ai_response", {}).get("content", "")
            log(f"AI: {ai_resp[:150]}...", "INFO")
            msg_count += 2  # user + AI
            if rnd >= 7 and is_step_complete(ai_resp):
                log(f"Consultant signaled step completion — stopping after round {rnd}", "OK")
                break
        else:
            log(f"Message failed: {r.text[:200]}", "ERR")
            break

        # Incremental extraction every 4 messages (like frontend does)
        # Skipped by default in eval runs to save API calls — use --incremental-extraction to enable
        if args.incremental_extraction and msg_count >= 4 and rnd % 2 == 0:
            log("Running incremental extraction...", "WAIT")
            api_post(f"/api/sessions/{session_uuid}/consultation/extract-incremental", {
                "api_key": API_KEY
            })

    # Final full extraction
    log("Extracting consultation findings (full summary)...", "WAIT")
    r = api_post(f"/api/sessions/{session_uuid}/consultation/summarize", {"api_key": API_KEY})
    if r.status_code == 200:
        log("Consultation findings extracted", "OK")

    # =========================================
    # STEP 5a: Business Case
    # =========================================
    log("STEP 5a: Business Case", "STEP")

    r = api_post(f"/api/sessions/{session_uuid}/business-case/start", {"api_key": API_KEY})
    if r.status_code == 200:
        log(f"AI: {r.json().get('content', '')[:150]}...", "OK")

    for rnd in range(1, BUSINESS_CASE_ROUNDS + 1):
        log(f"--- Business Case Round {rnd}/{BUSINESS_CASE_ROUNDS} ---", "INFO")

        ua_body = {"user_agent_config": USER_AGENT_CONFIG} if USER_AGENT_CONFIG else None
        r = api_post(
            f"/api/test-mode/{session_uuid}/generate-response"
            f"?persona_id={PERSONA_ID}&message_type=business_case",
            ua_body,
            headers={"X-API-Key": USER_AGENT_API_KEY} if USER_AGENT_API_KEY else {}
        )
        if r.status_code != 200:
            check_user_agent_rate_limit(r)
            log(f"Persona response failed: {r.text[:300]}", "ERR")
            break
        ua_data = r.json()
        persona_msg = ua_data["response"]
        log(f"Persona: {persona_msg[:120]}...", "INFO")

        r = api_post(f"/api/sessions/{session_uuid}/business-case/message", {
            "content": persona_msg, "api_key": API_KEY
        })
        if r.status_code == 200:
            ai_resp = r.json().get("ai_response", {}).get("content", "")
            log(f"AI: {ai_resp[:150]}...", "INFO")
            if rnd >= 5 and is_step_complete(ai_resp):
                log(f"Consultant signaled step completion — stopping after round {rnd}", "OK")
                break
        else:
            log(f"Message failed", "ERR")
            break

    log("Extracting business case findings...", "WAIT")
    def _do_business_case_extract():
        return api_post(f"/api/sessions/{session_uuid}/business-case/extract",
                        {"api_key": REASONING_API_KEY if REASONING_MODEL else API_KEY})
    r = with_reasoning_model(session_uuid, _do_business_case_extract)
    if r.status_code == 200:
        log("Business case findings extracted", "OK")
    else:
        log(f"Business case extraction failed ({r.status_code}) — aborting run", "ERR")
        sys.exit(1)

    # =========================================
    # STEP 5b: Cost Estimation
    # =========================================
    log("STEP 5b: Cost Estimation", "STEP")

    r = api_post(f"/api/sessions/{session_uuid}/cost-estimation/start", {"api_key": API_KEY})
    if r.status_code == 200:
        log(f"AI: {r.json().get('content', '')[:150]}...", "OK")

    for rnd in range(1, COST_ESTIMATION_ROUNDS + 1):
        log(f"--- Cost Estimation Round {rnd}/{COST_ESTIMATION_ROUNDS} ---", "INFO")

        ua_body = {"user_agent_config": USER_AGENT_CONFIG} if USER_AGENT_CONFIG else None
        r = api_post(
            f"/api/test-mode/{session_uuid}/generate-response"
            f"?persona_id={PERSONA_ID}&message_type=cost_estimation",
            ua_body,
            headers={"X-API-Key": USER_AGENT_API_KEY} if USER_AGENT_API_KEY else {}
        )
        if r.status_code != 200:
            check_user_agent_rate_limit(r)
            log(f"Persona response failed: {r.text[:300]}", "ERR")
            break
        ua_data = r.json()
        persona_msg = ua_data["response"]
        log(f"Persona: {persona_msg[:120]}...", "INFO")

        r = api_post(f"/api/sessions/{session_uuid}/cost-estimation/message", {
            "content": persona_msg, "api_key": API_KEY
        })
        if r.status_code == 200:
            ai_resp = r.json().get("ai_response", {}).get("content", "")
            log(f"AI: {ai_resp[:150]}...", "INFO")
            if rnd >= 5 and is_step_complete(ai_resp):
                log(f"Consultant signaled step completion — stopping after round {rnd}", "OK")
                break
        else:
            log(f"Message failed", "ERR")
            break

    log("Extracting cost estimation findings...", "WAIT")
    def _do_cost_estimation_extract():
        return api_post(f"/api/sessions/{session_uuid}/cost-estimation/extract",
                        {"api_key": REASONING_API_KEY if REASONING_MODEL else API_KEY})
    r = with_reasoning_model(session_uuid, _do_cost_estimation_extract)
    if r.status_code == 200:
        log("Cost estimation findings extracted", "OK")
    else:
        log(f"Cost estimation extraction failed ({r.status_code}) — aborting run", "ERR")
        sys.exit(1)

    # =========================================
    # Generate SWOT & Transition Briefing
    # =========================================
    if args.no_analysis:
        log("SWOT & Transition Briefing: skipped (--no-analysis)", "INFO")
    else:
        log("Generating SWOT Analysis & Transition Briefing", "STEP")

        r = api_post(f"/api/sessions/{session_uuid}/swot-analysis/generate", {
            "api_key": API_KEY, "language": args.language
        })
        if r.status_code == 200:
            log("SWOT analysis generated", "OK")

        r = api_post(f"/api/sessions/{session_uuid}/transition-briefing/generate", {
            "api_key": API_KEY, "language": args.language
        })
        if r.status_code == 200:
            log("Transition briefing generated", "OK")
        else:
            log(f"Transition briefing failed ({r.status_code}) — continuing", "ERR")

    # =========================================
    # EXPORT: PDF Report
    # =========================================
    if args.no_pdf:
        log("EXPORT: PDF generation skipped (--no-pdf)", "INFO")
        pdf_path = None
    else:
        log("EXPORT: Generating PDF Report", "STEP")
        r = api_post(f"/api/sessions/{session_uuid}/export/pdf")
        if r.status_code == 200:
            pdf_path = os.path.join(OUTPUT_DIR, f"{PERSONA_ID}_{timestamp}_{session_uuid[:8]}.pdf")
            with open(pdf_path, "wb") as f:
                f.write(r.content)
            log(f"PDF saved: {pdf_path}", "OK")
        else:
            log(f"PDF generation failed: {r.text[:200]}", "ERR")
            pdf_path = None

    # =========================================
    # EXPORT: Session Backup (JSON)
    # =========================================
    log("EXPORT: Saving Session Backup", "STEP")

    r = api_get(f"/api/sessions/{session_uuid}/backup?anonymize=true")
    if r.status_code == 200:
        backup_path = os.path.join(OUTPUT_DIR, f"{PERSONA_ID}_{timestamp}_{session_uuid[:8]}_backup.json")
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(r.json(), f, indent=2, ensure_ascii=False)
        log(f"Session backup saved: {backup_path}", "OK")
    else:
        log(f"Backup failed: {r.text[:200]}", "ERR")
        backup_path = None

    # =========================================
    # EXPORT: All Findings (JSON)
    # =========================================
    r = api_get(f"/api/sessions/{session_uuid}/all-findings")
    if r.status_code == 200:
        findings_path = os.path.join(OUTPUT_DIR, f"{PERSONA_ID}_{timestamp}_{session_uuid[:8]}_findings.json")
        with open(findings_path, "w", encoding="utf-8") as f:
            json.dump(r.json(), f, indent=2, ensure_ascii=False)
        log(f"All findings saved: {findings_path}", "OK")
    else:
        findings_path = None

    # =========================================
    # EXPORT: Ground Truth (JSON)
    # =========================================
    try:
        ground_truth_source = os.path.join(os.path.dirname(__file__), "benchmark_personas.json")
        with open(ground_truth_source, "r", encoding="utf-8") as f:
            benchmarks = json.load(f)

        persona = None
        for p in benchmarks.get("personas", []):
            if p.get("persona_id") == PERSONA_ID:
                persona = p
                break

        if persona:
            ground_truth_path = os.path.join(OUTPUT_DIR, f"{PERSONA_ID}_{timestamp}_{session_uuid[:8]}_ground_truth.json")
            with open(ground_truth_path, "w", encoding="utf-8") as f:
                json.dump(persona, f, indent=2, ensure_ascii=False)
            log(f"Ground truth snapshot saved: {ground_truth_path}", "OK")
        else:
            log(f"Persona {PERSONA_ID} not found in benchmark_personas.json", "ERR")
            ground_truth_path = None
    except Exception as e:
        log(f"Failed to export ground truth: {str(e)}", "ERR")
        ground_truth_path = None

    # =========================================
    # SUMMARY
    # =========================================
    log("TEST COMPLETE", "STEP")
    print("\n" + "=" * 60)
    print(f"  Session UUID:    {session_uuid}")
    print(f"  Company:         {PERSONA_COMPANY_NAME}")
    print(f"  Focus Idea:      {PERSONA_FOCUS_TITLE}")
    print(f"  Persona ID:      {PERSONA_ID}")
    print(f"  Timestamp:       {timestamp}")
    print(f"  ---")
    print(f"  Consultant LLM:  {CONSULTANT_MODEL}")
    print(f"  Consultant Base: {CONSULTANT_BASE}")
    print(f"  Consultant Temp: {TEMPERATURE_CONFIG or 'default (0.7)'}")
    if REASONING_MODEL:
        print(f"  Reasoning LLM:   {REASONING_MODEL}")
        print(f"  Reasoning Base:  {REASONING_BASE}")
    print(f"  User Agent LLM:  {USER_AGENT_MODEL}")
    print(f"  User Agent Base: {USER_AGENT_BASE}")
    print(f"  User Agent Temp: {USER_AGENT_TEMPERATURE or 'default (0.7)'}")
    print(f"  ---")
    print(f"  PDF Report:      {pdf_path or ('skipped' if args.no_pdf else 'FAILED')}")
    print(f"  Session Backup:  {backup_path or 'FAILED'}")
    print(f"  Findings JSON:   {findings_path or 'FAILED'}")
    print(f"  Ground Truth:    {ground_truth_path or 'FAILED'}")
    print(f"  ---")
    print(f"  Restore command:")
    print(f"    curl -X POST {BASE_URL}/api/sessions/restore \\")
    print(f"      -F 'file=@{backup_path}'")
    print("=" * 60)

    return session_uuid


if __name__ == "__main__":
    session_uuid = main()
