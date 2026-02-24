#!/usr/bin/env python3
"""
Automated LLM Evaluation Tool for AI Consultation Quality

Fully automated evaluation pipeline:
1. LLM-as-User: Simulates an SME employee answering consultation questions
2. LLM-as-Judge: Rates the consultation quality using the rubric

Can run standalone (direct LLM calls) or via the backend API.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Generator

# Add evaluation directory to path
sys.path.insert(0, str(Path(__file__).parent))

from rubric import RUBRIC, calculate_weighted_score, get_grade
from test_cases import TEST_CASES, get_test_case, list_test_cases

try:
    import litellm
    from litellm import completion
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    print("Warning: litellm not installed. Install with: pip install litellm")

# Configuration
RESULTS_DIR = Path(__file__).parent / "results"
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

# Load prompts from backend if available
BACKEND_PROMPTS_PATH = Path(__file__).parent.parent / "backend" / "app" / "services" / "default_prompts.py"


def load_consultation_prompt() -> str:
    """Load the consultation system prompt from backend."""
    if BACKEND_PROMPTS_PATH.exists():
        # Import the prompts module
        sys.path.insert(0, str(BACKEND_PROMPTS_PATH.parent.parent.parent))
        try:
            from app.services.default_prompts import DEFAULT_PROMPTS
            return DEFAULT_PROMPTS.get("consultation_system_en", get_fallback_consultation_prompt())
        except ImportError:
            pass
    return get_fallback_consultation_prompt()


def get_fallback_consultation_prompt() -> str:
    """Fallback consultation prompt if backend not available."""
    return """You are an AI consultant helping SMEs (small and medium enterprises) understand how AI and digitalization can benefit their business.

Your role is to:
1. Understand the company's current situation and challenges
2. Identify opportunities for AI/digital solutions
3. Provide practical, actionable recommendations
4. Explain concepts in simple terms for non-technical users

Use the CRISP-DM framework to structure your analysis:
- Business Understanding: What are the business objectives?
- Data Understanding: What data is available?
- Data Preparation: What would need to be done with the data?
- Modeling: What AI/ML approaches could help?
- Evaluation: How would success be measured?
- Deployment: How would solutions be implemented?

Be conversational, ask clarifying questions, and provide recommendations appropriate for SME budgets and capabilities."""


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

IMPORTANT:
- Stay in character as an SME employee
- Don't make up information not implied by the company profile
- Express realistic concerns about budget, time, and complexity
- Be open but somewhat skeptical about AI promises

Respond to the AI consultant's message."""


JUDGE_PROMPT = """You are an expert evaluator assessing the quality of AI consultation advice given to SMEs.

EVALUATION RUBRIC:
{rubric_text}

COMPANY PROFILE (what the consultation was about):
{company_info}

EXPECTED THEMES (good advice should cover):
{expected_themes}

RED FLAGS (poor advice would include):
{red_flags}

CONSULTATION TRANSCRIPT:
{transcript}

---

Evaluate this consultation using the rubric above. For each criterion, provide:
1. A score from 1-5
2. A brief justification (1-2 sentences)

Also note:
- Which expected themes were covered
- Any red flags that appeared
- Overall strengths and weaknesses

Respond in this exact JSON format:
{{
    "scores": {{
        "relevance": <1-5>,
        "actionability": <1-5>,
        "accuracy": <1-5>,
        "clarity": <1-5>,
        "completeness": <1-5>,
        "sme_appropriateness": <1-5>
    }},
    "justifications": {{
        "relevance": "<explanation>",
        "actionability": "<explanation>",
        "accuracy": "<explanation>",
        "clarity": "<explanation>",
        "completeness": "<explanation>",
        "sme_appropriateness": "<explanation>"
    }},
    "themes_covered": ["<theme1>", "<theme2>"],
    "red_flags_found": ["<flag1>"] or [],
    "strengths": "<overall strengths>",
    "weaknesses": "<overall weaknesses>",
    "summary": "<2-3 sentence overall assessment>"
}}"""


def format_rubric_for_prompt() -> str:
    """Format the rubric for inclusion in the judge prompt."""
    lines = []
    for key, criterion in RUBRIC.items():
        lines.append(f"\n{criterion['name']} (weight: {criterion['weight']})")
        lines.append(f"  {criterion['description']}")
        for level, desc in criterion['levels'].items():
            lines.append(f"  {level}: {desc}")
    return "\n".join(lines)


def call_llm(messages: list, model: str = None, temperature: float = 0.7) -> str:
    """Call LLM and return response content."""
    if not LITELLM_AVAILABLE:
        raise RuntimeError("litellm is required. Install with: pip install litellm")

    model = model or DEFAULT_MODEL

    response = completion(
        model=model,
        messages=messages,
        temperature=temperature
    )

    return response.choices[0].message.content


def simulate_user_response(
    company_info: str,
    consultant_message: str,
    conversation_history: list,
    model: str = None,
    role: str = "manager"
) -> str:
    """Generate a simulated user response."""

    system_prompt = USER_SIMULATION_PROMPT.format(
        company_info=company_info,
        role=role
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    for msg in conversation_history:
        if msg["role"] == "assistant":
            messages.append({"role": "user", "content": f"AI Consultant: {msg['content']}"})
        else:
            messages.append({"role": "assistant", "content": msg['content']})

    # Add current consultant message
    messages.append({"role": "user", "content": f"AI Consultant: {consultant_message}"})

    return call_llm(messages, model=model, temperature=0.8)


def run_consultation(
    company_info: str,
    model: str = None,
    max_turns: int = 6,
    verbose: bool = True
) -> list:
    """Run a full consultation with simulated user."""

    consultation_prompt = load_consultation_prompt()

    # Replace placeholder with actual company info
    system_content = consultation_prompt
    if "{company_info_text}" in system_content:
        system_content = system_content.replace("{company_info_text}", company_info)
    else:
        system_content = f"{system_content}\n\nCOMPANY INFORMATION:\n{company_info}"

    messages = [{"role": "system", "content": system_content}]
    conversation = []

    if verbose:
        print("\n" + "="*60)
        print("STARTING AUTOMATED CONSULTATION")
        print("="*60)

    # Initial consultant message
    initial_prompt = "Please begin the consultation by introducing yourself and asking your first question about the company."
    messages.append({"role": "user", "content": initial_prompt})

    consultant_response = call_llm(messages, model=model, temperature=0.7)
    messages.append({"role": "assistant", "content": consultant_response})
    conversation.append({"role": "assistant", "content": consultant_response})

    if verbose:
        print(f"\n🤖 Consultant:\n{consultant_response[:500]}...")

    # Conversation loop
    for turn in range(max_turns):
        if verbose:
            print(f"\n--- Turn {turn + 1}/{max_turns} ---")

        # Simulate user response
        user_response = simulate_user_response(
            company_info=company_info,
            consultant_message=consultant_response,
            conversation_history=conversation[:-1],  # Exclude current consultant message
            model=model
        )

        messages.append({"role": "user", "content": user_response})
        conversation.append({"role": "user", "content": user_response})

        if verbose:
            print(f"\n👤 User:\n{user_response}")

        # Get consultant response
        consultant_response = call_llm(messages, model=model, temperature=0.7)
        messages.append({"role": "assistant", "content": consultant_response})
        conversation.append({"role": "assistant", "content": consultant_response})

        if verbose:
            print(f"\n🤖 Consultant:\n{consultant_response[:500]}{'...' if len(consultant_response) > 500 else ''}")

        # Check if consultation seems complete
        if any(phrase in consultant_response.lower() for phrase in [
            "summarize our discussion",
            "to summarize",
            "in conclusion",
            "final recommendation",
            "next steps would be"
        ]):
            if verbose:
                print("\n[Consultation appears complete]")
            break

    return conversation


def evaluate_consultation(
    conversation: list,
    test_case: dict,
    model: str = None,
    verbose: bool = True
) -> dict:
    """Use LLM to evaluate the consultation quality."""

    # Format transcript
    transcript_lines = []
    for msg in conversation:
        role = "AI Consultant" if msg["role"] == "assistant" else "User"
        transcript_lines.append(f"{role}: {msg['content']}")
    transcript = "\n\n".join(transcript_lines)

    # Build judge prompt
    judge_prompt = JUDGE_PROMPT.format(
        rubric_text=format_rubric_for_prompt(),
        company_info=test_case["company_info"],
        expected_themes=", ".join(test_case["expected_themes"]),
        red_flags=", ".join(test_case["red_flags"]),
        transcript=transcript
    )

    if verbose:
        print("\n" + "="*60)
        print("EVALUATING CONSULTATION")
        print("="*60)

    messages = [
        {"role": "system", "content": "You are an expert evaluator. Respond only with valid JSON."},
        {"role": "user", "content": judge_prompt}
    ]

    # Use lower temperature for more consistent evaluation
    response = call_llm(messages, model=model, temperature=0.3)

    # Parse JSON response
    try:
        # Try to extract JSON from response
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            evaluation = json.loads(json_str)
        else:
            raise ValueError("No JSON found in response")
    except json.JSONDecodeError as e:
        if verbose:
            print(f"Warning: Failed to parse evaluation JSON: {e}")
            print(f"Raw response: {response[:500]}")
        # Return default evaluation on parse error
        evaluation = {
            "scores": {k: 3 for k in RUBRIC.keys()},
            "justifications": {k: "Parse error" for k in RUBRIC.keys()},
            "themes_covered": [],
            "red_flags_found": [],
            "strengths": "Unable to parse evaluation",
            "weaknesses": "Unable to parse evaluation",
            "summary": "Evaluation parsing failed"
        }

    return evaluation


def run_automated_evaluation(
    test_case_id: str,
    model: str = None,
    max_turns: int = 6,
    verbose: bool = True
) -> dict:
    """Run a complete automated evaluation."""

    test_case = get_test_case(test_case_id)
    if not test_case:
        raise ValueError(f"Test case '{test_case_id}' not found")

    model = model or DEFAULT_MODEL

    if verbose:
        print(f"\nTest Case: {test_case['name']}")
        print(f"Model: {model}")
        print(f"Max turns: {max_turns}")

    start_time = time.time()

    # Run consultation
    conversation = run_consultation(
        company_info=test_case["company_info"],
        model=model,
        max_turns=max_turns,
        verbose=verbose
    )

    consultation_time = time.time() - start_time

    # Evaluate consultation
    eval_start = time.time()
    evaluation = evaluate_consultation(
        conversation=conversation,
        test_case=test_case,
        model=model,
        verbose=verbose
    )
    evaluation_time = time.time() - eval_start

    # Calculate weighted score
    scores = evaluation.get("scores", {})
    weighted_score = calculate_weighted_score(scores) if scores else 0
    grade = get_grade(weighted_score)

    # Build result
    result = {
        "evaluation_timestamp": datetime.now().isoformat(),
        "test_case_id": test_case["id"],
        "test_case_name": test_case["name"],
        "model": model,
        "max_turns": max_turns,
        "actual_turns": len([m for m in conversation if m["role"] == "user"]),
        "consultation_time_seconds": round(consultation_time, 2),
        "evaluation_time_seconds": round(evaluation_time, 2),
        "conversation": conversation,
        "evaluation": evaluation,
        "scores": scores,
        "weighted_score": round(weighted_score, 2),
        "grade": grade
    }

    if verbose:
        print("\n" + "="*60)
        print("EVALUATION RESULTS")
        print("="*60)
        print(f"\nWeighted Score: {weighted_score:.2f} / 5.00")
        print(f"Grade: {grade}")
        print("\nScores by criterion:")
        for key, score in scores.items():
            just = evaluation.get("justifications", {}).get(key, "")
            print(f"  {RUBRIC[key]['name']}: {score}/5")
            if just:
                print(f"    → {just}")

        print(f"\nThemes covered: {', '.join(evaluation.get('themes_covered', []))}")
        print(f"Red flags found: {', '.join(evaluation.get('red_flags_found', [])) or 'None'}")
        print(f"\nStrengths: {evaluation.get('strengths', 'N/A')}")
        print(f"Weaknesses: {evaluation.get('weaknesses', 'N/A')}")
        print(f"\nSummary: {evaluation.get('summary', 'N/A')}")

    return result


def save_result(result: dict) -> str:
    """Save evaluation result to file."""
    RESULTS_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_slug = result["model"].replace("/", "-").replace(":", "-")
    filename = f"auto_{result['test_case_id']}_{model_slug}_{timestamp}.json"
    filepath = RESULTS_DIR / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return str(filepath)


def run_batch_evaluation(
    test_case_ids: list = None,
    model: str = None,
    max_turns: int = 6,
    verbose: bool = False
) -> list:
    """Run evaluations for multiple test cases."""

    if test_case_ids is None:
        test_case_ids = [tc["id"] for tc in TEST_CASES]

    results = []

    print(f"\nRunning batch evaluation for {len(test_case_ids)} test cases...")
    print(f"Model: {model or DEFAULT_MODEL}")
    print("-" * 50)

    for i, case_id in enumerate(test_case_ids, 1):
        print(f"\n[{i}/{len(test_case_ids)}] Evaluating: {case_id}")

        try:
            result = run_automated_evaluation(
                test_case_id=case_id,
                model=model,
                max_turns=max_turns,
                verbose=verbose
            )

            filepath = save_result(result)
            results.append(result)

            print(f"  Score: {result['weighted_score']:.2f} ({result['grade']})")
            print(f"  Saved: {filepath}")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"test_case_id": case_id, "error": str(e)})

    # Summary
    successful = [r for r in results if "weighted_score" in r]
    if successful:
        avg_score = sum(r["weighted_score"] for r in successful) / len(successful)
        print("\n" + "="*50)
        print("BATCH EVALUATION SUMMARY")
        print("="*50)
        print(f"Successful: {len(successful)}/{len(test_case_ids)}")
        print(f"Average Score: {avg_score:.2f}")
        print(f"Grade: {get_grade(avg_score)}")

    return results


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Automated LLM Evaluation Tool for AI Consultation Quality"
    )
    parser.add_argument(
        "--case", type=str,
        help="Run evaluation for specific test case ID"
    )
    parser.add_argument(
        "--batch", action="store_true",
        help="Run evaluation for all test cases"
    )
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL,
        help=f"LLM model to use (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--turns", type=int, default=6,
        help="Maximum conversation turns (default: 6)"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Reduce output verbosity"
    )
    parser.add_argument(
        "--cases", action="store_true",
        help="List available test cases"
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save results to file"
    )

    args = parser.parse_args()

    if not LITELLM_AVAILABLE:
        print("Error: litellm is required. Install with: pip install litellm")
        sys.exit(1)

    if args.cases:
        list_test_cases()
        return

    if args.batch:
        results = run_batch_evaluation(
            model=args.model,
            max_turns=args.turns,
            verbose=not args.quiet
        )
    elif args.case:
        result = run_automated_evaluation(
            test_case_id=args.case,
            model=args.model,
            max_turns=args.turns,
            verbose=not args.quiet
        )
        if args.save:
            filepath = save_result(result)
            print(f"\nResult saved to: {filepath}")
    else:
        # Interactive mode - pick a test case
        list_test_cases()
        case_id = input("\nEnter test case ID (or 'all' for batch): ").strip()

        if case_id.lower() == 'all':
            run_batch_evaluation(
                model=args.model,
                max_turns=args.turns,
                verbose=not args.quiet
            )
        else:
            result = run_automated_evaluation(
                test_case_id=case_id,
                model=args.model,
                max_turns=args.turns,
                verbose=True
            )

            if input("\nSave result? (y/n): ").strip().lower() == 'y':
                filepath = save_result(result)
                print(f"Saved to: {filepath}")


if __name__ == "__main__":
    main()
