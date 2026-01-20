#!/usr/bin/env python3
"""
Human Evaluation Tool for AI Consultation Quality

This script allows evaluators to:
1. Run test consultations using predefined company profiles
2. Interact with the AI consultant
3. Rate the consultation quality using the rubric
4. Save evaluation results for analysis
"""

import requests
import json
import time
import os
import sys
from datetime import datetime
from pathlib import Path

# Add evaluation directory to path
sys.path.insert(0, str(Path(__file__).parent))

from rubric import RUBRIC, calculate_weighted_score, get_grade, print_rubric
from test_cases import TEST_CASES, get_test_case, list_test_cases


# Configuration
RESULTS_DIR = Path(__file__).parent / "results"

# Global API URL (can be overridden via command line)
_api_base_url = os.environ.get("API_BASE_URL", "http://localhost:8000")


def get_api_url():
    """Get the current API base URL."""
    return _api_base_url


def update_api_url(url: str):
    """Update the API base URL."""
    global _api_base_url
    _api_base_url = url


def create_session() -> str:
    """Create a new consultation session."""
    response = requests.post(f"{get_api_url()}/api/sessions")
    response.raise_for_status()
    return response.json()["session_uuid"]


def add_company_info(session_uuid: str, company_info: str) -> dict:
    """Add company information to the session."""
    response = requests.post(
        f"{get_api_url()}/api/sessions/{session_uuid}/company-info",
        json={"info_text": company_info}
    )
    response.raise_for_status()
    return response.json()


def start_consultation(session_uuid: str) -> dict:
    """Start the consultation and get the first AI message."""
    response = requests.post(
        f"{get_api_url()}/api/sessions/{session_uuid}/consultation/start"
    )
    response.raise_for_status()
    return response.json()


def send_message(session_uuid: str, message: str) -> dict:
    """Send a message and get AI response."""
    response = requests.post(
        f"{get_api_url()}/api/sessions/{session_uuid}/consultation/message",
        json={"content": message}
    )
    response.raise_for_status()
    return response.json()


def get_messages(session_uuid: str) -> list:
    """Get all consultation messages."""
    response = requests.get(
        f"{get_api_url()}/api/sessions/{session_uuid}/consultation/messages"
    )
    response.raise_for_status()
    return response.json()


def get_findings(session_uuid: str) -> dict:
    """Get extracted findings from consultation."""
    response = requests.get(
        f"{get_api_url()}/api/sessions/{session_uuid}/consultation/findings"
    )
    response.raise_for_status()
    return response.json()


def extract_findings(session_uuid: str) -> dict:
    """Trigger extraction of findings."""
    response = requests.post(
        f"{get_api_url()}/api/sessions/{session_uuid}/consultation/summarize"
    )
    response.raise_for_status()
    return response.json()


def clear_screen():
    """Clear terminal screen."""
    os.system('clear' if os.name == 'posix' else 'cls')


def print_header(text: str, char: str = "="):
    """Print a formatted header."""
    print(f"\n{char * 70}")
    print(f"  {text}")
    print(f"{char * 70}\n")


def print_message(role: str, content: str):
    """Print a chat message with formatting."""
    if role == "assistant":
        print(f"\n🤖 AI Consultant:")
        print("-" * 50)
        # Wrap long lines
        for line in content.split('\n'):
            print(f"  {line}")
    else:
        print(f"\n👤 User:")
        print("-" * 50)
        for line in content.split('\n'):
            print(f"  {line}")


def run_interactive_consultation(session_uuid: str) -> list:
    """Run an interactive consultation session."""
    print_header("Starting Consultation")
    print("Type your responses. Commands:")
    print("  /done  - End consultation and proceed to evaluation")
    print("  /show  - Show full conversation so far")
    print("  /extract - Extract findings now")
    print("-" * 50)

    # Start consultation
    try:
        result = start_consultation(session_uuid)
        print_message("assistant", result.get("content", result.get("ai_response", "")))
    except Exception as e:
        print(f"Error starting consultation: {e}")
        return []

    messages = []

    while True:
        print()
        user_input = input("Your response (or /done): ").strip()

        if user_input.lower() == "/done":
            break
        elif user_input.lower() == "/show":
            msgs = get_messages(session_uuid)
            print_header("Conversation So Far", "-")
            for msg in msgs:
                print_message(msg["role"], msg["content"])
            continue
        elif user_input.lower() == "/extract":
            try:
                findings = extract_findings(session_uuid)
                print_header("Extracted Findings", "-")
                for key, value in findings.items():
                    if value:
                        print(f"\n{key.upper()}:")
                        print(f"  {value}")
            except Exception as e:
                print(f"Error extracting findings: {e}")
            continue
        elif not user_input:
            continue

        # Send message
        try:
            result = send_message(session_uuid, user_input)
            print_message("assistant", result.get("content", result.get("ai_response", "")))
        except Exception as e:
            print(f"Error sending message: {e}")

    # Get final conversation
    return get_messages(session_uuid)


def collect_scores() -> dict:
    """Interactively collect scores from evaluator."""
    print_header("Quality Evaluation")
    print("Rate each criterion on a scale of 1-5.")
    print("Enter 'h' for help on any criterion.\n")

    scores = {}

    for key, criterion in RUBRIC.items():
        while True:
            prompt = f"{criterion['name']} (1-5, h=help): "
            response = input(prompt).strip().lower()

            if response == 'h':
                print(f"\n  {criterion['description']}")
                print("-" * 40)
                for level, desc in criterion['levels'].items():
                    print(f"  {level}: {desc}")
                print()
                continue

            try:
                score = int(response)
                if 1 <= score <= 5:
                    scores[key] = score
                    break
                else:
                    print("  Please enter a number between 1 and 5.")
            except ValueError:
                print("  Invalid input. Enter 1-5 or 'h' for help.")

    return scores


def save_evaluation(test_case: dict, session_uuid: str, messages: list,
                    scores: dict, notes: str) -> str:
    """Save evaluation results to file."""
    RESULTS_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{test_case['id']}_{timestamp}.json"
    filepath = RESULTS_DIR / filename

    result = {
        "evaluation_timestamp": datetime.now().isoformat(),
        "test_case_id": test_case["id"],
        "test_case_name": test_case["name"],
        "session_uuid": session_uuid,
        "company_info": test_case["company_info"],
        "expected_themes": test_case["expected_themes"],
        "red_flags": test_case["red_flags"],
        "conversation": messages,
        "scores": scores,
        "weighted_score": calculate_weighted_score(scores),
        "grade": get_grade(calculate_weighted_score(scores)),
        "evaluator_notes": notes
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return str(filepath)


def run_evaluation(test_case_id: str = None):
    """Run a full evaluation session."""
    clear_screen()
    print_header("AI Consultation Quality Evaluation")

    # Select test case
    if test_case_id:
        test_case = get_test_case(test_case_id)
        if not test_case:
            print(f"Test case '{test_case_id}' not found.")
            list_test_cases()
            return
    else:
        list_test_cases()
        case_id = input("\nEnter test case ID: ").strip()
        test_case = get_test_case(case_id)
        if not test_case:
            print(f"Test case '{case_id}' not found.")
            return

    print(f"\nSelected: {test_case['name']}")
    print(f"Language: {test_case['language']}")
    print("\nCompany Profile:")
    print("-" * 50)
    print(test_case['company_info'].strip())
    print("-" * 50)

    input("\nPress Enter to start the evaluation...")

    # Create session and add company info
    try:
        print("\nCreating session...")
        session_uuid = create_session()
        print(f"Session: {session_uuid}")

        print("Adding company information...")
        add_company_info(session_uuid, test_case["company_info"])

    except Exception as e:
        print(f"Error setting up session: {e}")
        print("Make sure the backend is running at", get_api_url())
        return

    # Run consultation
    messages = run_interactive_consultation(session_uuid)

    if not messages:
        print("No conversation recorded. Exiting.")
        return

    # Show expected themes and red flags
    print_header("Evaluation Checklist")
    print("Expected themes to cover:")
    for theme in test_case["expected_themes"]:
        print(f"  [ ] {theme}")

    print("\nRed flags (should NOT appear):")
    for flag in test_case["red_flags"]:
        print(f"  [ ] {flag}")

    input("\nReview the conversation and press Enter to score...")

    # Collect scores
    scores = collect_scores()

    # Calculate results
    weighted = calculate_weighted_score(scores)
    grade = get_grade(weighted)

    print_header("Evaluation Summary")
    print(f"Weighted Score: {weighted:.2f} / 5.00")
    print(f"Grade: {grade}")
    print("\nScores by criterion:")
    for key, score in scores.items():
        print(f"  {RUBRIC[key]['name']}: {score}/5")

    # Collect notes
    print("\nAdd any notes about this evaluation (press Enter twice to finish):")
    notes_lines = []
    while True:
        line = input()
        if line == "":
            break
        notes_lines.append(line)
    notes = "\n".join(notes_lines)

    # Save results
    filepath = save_evaluation(test_case, session_uuid, messages, scores, notes)
    print(f"\nEvaluation saved to: {filepath}")


def analyze_results():
    """Analyze all saved evaluation results."""
    if not RESULTS_DIR.exists():
        print("No results directory found.")
        return

    results = list(RESULTS_DIR.glob("*.json"))
    if not results:
        print("No evaluation results found.")
        return

    print_header("Evaluation Results Analysis")

    all_scores = []
    by_test_case = {}

    for filepath in results:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        all_scores.append(data["weighted_score"])

        case_id = data["test_case_id"]
        if case_id not in by_test_case:
            by_test_case[case_id] = []
        by_test_case[case_id].append(data["weighted_score"])

    print(f"Total evaluations: {len(all_scores)}")
    print(f"Average score: {sum(all_scores)/len(all_scores):.2f}")
    print(f"Min: {min(all_scores):.2f}, Max: {max(all_scores):.2f}")

    print("\nBy test case:")
    for case_id, scores in by_test_case.items():
        avg = sum(scores) / len(scores)
        print(f"  {case_id}: {avg:.2f} (n={len(scores)})")

    # Criterion analysis
    print("\nAverage by criterion:")
    criterion_totals = {k: [] for k in RUBRIC.keys()}

    for filepath in results:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for k, v in data["scores"].items():
            criterion_totals[k].append(v)

    for k, values in criterion_totals.items():
        avg = sum(values) / len(values)
        print(f"  {RUBRIC[k]['name']}: {avg:.2f}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Human Evaluation Tool for AI Consultation Quality"
    )
    parser.add_argument(
        "--rubric", action="store_true",
        help="Print the evaluation rubric"
    )
    parser.add_argument(
        "--cases", action="store_true",
        help="List available test cases"
    )
    parser.add_argument(
        "--analyze", action="store_true",
        help="Analyze saved evaluation results"
    )
    parser.add_argument(
        "--case", type=str,
        help="Run evaluation with specific test case ID"
    )
    parser.add_argument(
        "--api", type=str, default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)"
    )

    args = parser.parse_args()

    # Update API URL if provided
    if args.api != "http://localhost:8000":
        update_api_url(args.api)

    if args.rubric:
        print_rubric()
    elif args.cases:
        list_test_cases()
    elif args.analyze:
        analyze_results()
    else:
        run_evaluation(args.case)


if __name__ == "__main__":
    main()
