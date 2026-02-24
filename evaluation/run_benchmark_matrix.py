#!/usr/bin/env python3
"""
Benchmark Matrix Runner
=======================
Runs all combinations of consultant LLMs × personas sequentially.

9 consultant models × 6 personas = 54 runs
User agent: Gemma 3 27B on SAIA (temperature=0, fixed across all runs)

Usage:
    python run_benchmark_matrix.py
    python run_benchmark_matrix.py --dry-run          # Print commands without executing
    python run_benchmark_matrix.py --resume           # Skip already completed runs
    python run_benchmark_matrix.py --start-from 10   # Start from run #10
    python run_benchmark_matrix.py --consultant groq_kimi_k2  # Run only one consultant
    python run_benchmark_matrix.py --persona mfg_01_metal_quality  # Run only one persona

Required environment variables:
    GROQ_API_KEY            Groq API key (groq consultant models)
    SAIA_API_KEY            SAIA account 1 (user agent + saia consultant models)
    SCADS_API_KEY           ScaDS.AI API key
    GROQ_API_KEY            Groq API key
    SAIA_API_KEY            SAIA account 1 (chat-ai.academiccloud.de)
    SAIA_API_KEY2           SAIA account 2 (rotated on rate limit)
    MISTRAL_API_KEY         Mistral official API key

Output:
    evaluation/matrix_runs/<run_id>/   — outputs per run
    evaluation/matrix_runs/mapping.json — model→session mapping for de-anonymization
    evaluation/matrix_runs/progress.json — run status tracking
"""

import subprocess
import sys
import os
import json
import argparse
import time
import fcntl
from datetime import datetime
from pathlib import Path
import requests

# =========================================
# API endpoints
# =========================================

SAIA_BASE     = "https://chat-ai.academiccloud.de/v1"
SCADS_BASE    = "https://llm.scads.ai/v1"
GROQ_BASE     = "https://api.groq.com/openai/v1"
MISTRAL_BASE  = "https://api.mistral.ai/v1"
GOOGLE_BASE   = "https://generativelanguage.googleapis.com/v1beta"

# =========================================
# API keys — read exclusively from env
# =========================================

GOOGLE_API_KEY  = os.environ.get("GOOGLE_AI_STUDIO_KEY", "")
SCADS_API_KEY   = os.environ.get("SCADS_API_KEY",   "")
GROQ_API_KEY    = os.environ.get("GROQ_API_KEY",    "")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")

# Two SAIA accounts — quota is account-wide; rotate on rate limit
SAIA_API_KEYS = [
    os.environ.get("SAIA_API_KEY",  ""),   # Account 1
    os.environ.get("SAIA_API_KEY2", ""),   # Account 2
]

# Index of the SAIA key currently in use (rotated on rate limit)
_saia_key_index = 0

# =========================================
# User agent — fixed across all runs
# Different provider from all consultant models → no homophily bias
# temperature=0 → maximum reproducibility across runs
# =========================================

USER_AGENT_MODEL       = "openai/gemma-3-27b-it"
USER_AGENT_BASE        = SAIA_BASE
USER_AGENT_KEY_ENV     = "SAIA_API_KEY"
USER_AGENT_TEMPERATURE = 0.0

# =========================================
# Consultant LLMs to evaluate (9 models)
#
# model_id : LiteLLM prefix + provider model id
#            "openai/<name>" routes via OpenAI-compat client to api_base;
#            LiteLLM strips the first "openai/" and sends the rest as model name.
#            Groq model IDs that contain their own slashes (e.g. meta-llama/...)
#            are handled correctly: "openai/meta-llama/..." → Groq receives "meta-llama/..."
# api_key  : None means use the rotating SAIA key
# =========================================

CONSULTANT_MODELS = [
    # --- ScaDS ---
    {
        "id":      "scads_minimax_m2_5",
        "label":   "MiniMax M2.5 (ScaDS)",
        "model":   "openai/MiniMaxAI/MiniMax-M2.5",
        "base":    SCADS_BASE,
        "api_key": SCADS_API_KEY,
    },
    {
        "id":      "scads_deepseek_v3",
        "label":   "DeepSeek V3.2 (ScaDS)",
        "model":   "openai/deepseek-ai/DeepSeek-V3.2",
        "base":    SCADS_BASE,
        "api_key": SCADS_API_KEY,
    },

    # --- Groq (free tier) ---
    {
        "id":      "scads_llama33_70b",
        "label":   "Llama 3.3 70B (ScaDS)",
        "model":   "openai/meta-llama/Llama-3.3-70B-Instruct",
        "base":    SCADS_BASE,
        "api_key": SCADS_API_KEY,
    },
    {
        "id":      "groq_gpt_oss_120b",
        "label":   "GPT OSS 120B (Groq)",
        "model":   "openai/openai/gpt-oss-120b",
        "base":    GROQ_BASE,
        "api_key": GROQ_API_KEY,
    },
    {
        "id":      "groq_llama4_scout",
        "label":   "Llama 4 Scout (Groq)",
        "model":   "openai/meta-llama/llama-4-scout-17b-16e-instruct",
        "base":    GROQ_BASE,
        "api_key": GROQ_API_KEY,
    },
    {
        "id":      "groq_kimi_k2",
        "label":   "Kimi K2 (Groq)",
        "model":   "openai/moonshotai/kimi-k2-instruct",
        "base":    GROQ_BASE,
        "api_key": GROQ_API_KEY,
    },

    # --- SAIA ---
    {
        "id":      "saia_sauerkraut_70b",
        "label":   "SauerkrautLM 70B (SAIA)",
        "model":   "openai/llama-3.1-sauerkrautlm-70b-instruct",
        "base":    SAIA_BASE,
        "api_key": None,   # uses rotating SAIA key
    },
    {
        "id":      "saia_qwen3_235b",
        "label":   "Qwen3 235B (SAIA)",
        "model":   "openai/qwen3-235b-a22b",
        "base":    SAIA_BASE,
        "api_key": None,   # uses rotating SAIA key
    },

    # --- Mistral official API ---
    {
        "id":      "mistral_large",
        "label":   "Mistral Large (Mistral API)",
        "model":   "openai/mistral-large-latest",
        "base":    MISTRAL_BASE,
        "api_key": MISTRAL_API_KEY,
    },
]

# =========================================
# Personas to test (6 personas)
# =========================================

PERSONAS = [
    "mfg_01_metal_quality",
    "mfg_02_plastics_maintenance",
    "mfg_03_electronics_testing",
    "mfg_04_food_digitalization",
    "mfg_05_precision_design",
    "mfg_06_visual_quality",
]

SCRIPT        = Path(__file__).parent / "run_test_persona1.py"
MATRIX_DIR    = Path(__file__).parent / "matrix_runs"
MAPPING_FILE  = MATRIX_DIR / "mapping.json"
PROGRESS_FILE = MATRIX_DIR / "progress.json"

TOTAL_RUNS = len(CONSULTANT_MODELS) * len(PERSONAS)

# Seconds to wait after all SAIA keys are exhausted before retrying
RATE_LIMIT_WAIT = 3700  # ~1 hour + 100s buffer


# =========================================
# SAIA Rate Limit Helpers
# =========================================

def get_saia_quota(api_key: str) -> dict | None:
    """Read SAIA rate-limit headers with a minimal probe request (max_tokens=1)."""
    try:
        resp = requests.post(
            f"{SAIA_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/mistral-large-latest",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
            },
            timeout=15,
        )
        h = resp.headers
        return {
            "remaining_hour": int(h.get("x-ratelimit-remaining-hour", -1)),
            "limit_hour":     int(h.get("x-ratelimit-limit-hour",     -1)),
            "remaining_day":  int(h.get("x-ratelimit-remaining-day",  -1)),
            "limit_day":      int(h.get("x-ratelimit-limit-day",      -1)),
            "reset_seconds":  int(h.get("ratelimit-reset", RATE_LIMIT_WAIT)),
            "status_code":    resp.status_code,
        }
    except Exception as e:
        print(f"  [QUOTA] Network error: {e}")
        return None


def current_saia_key() -> str:
    return SAIA_API_KEYS[_saia_key_index]


def on_saia_rate_limit() -> str:
    """Rotate to next SAIA key. If all exhausted, wait for quota reset."""
    global _saia_key_index
    next_index = (_saia_key_index + 1) % len(SAIA_API_KEYS)

    if next_index != 0:
        next_key = SAIA_API_KEYS[next_index]
        print(f"  [QUOTA] SAIA rate limit — rotating to key ...{next_key[-6:]}")
        _saia_key_index = next_index
        return next_key

    # All keys tried — read reset time and wait
    print("  [QUOTA] All SAIA keys exhausted — checking reset time...")
    info = get_saia_quota(SAIA_API_KEYS[0])
    if info:
        wait = max(info["reset_seconds"] + 30, 60)
        print(f"  [QUOTA] hour {info['remaining_hour']}/{info['limit_hour']}  "
              f"day {info['remaining_day']}/{info['limit_day']}  "
              f"reset in {info['reset_seconds']}s — waiting {wait}s...")
    else:
        wait = RATE_LIMIT_WAIT
        print(f"  [QUOTA] Could not read headers — waiting {wait}s...")
    try:
        time.sleep(wait)
    except KeyboardInterrupt:
        print("\n  [INTERRUPTED] Quota wait interrupted.")
        raise
    _saia_key_index = 0
    return SAIA_API_KEYS[0]


# =========================================
# Helpers
# =========================================

def build_runs() -> list:
    runs = []
    run_id = 1
    for consultant in CONSULTANT_MODELS:
        for persona in PERSONAS:
            runs.append({
                "run_id":            run_id,
                "consultant_id":     consultant["id"],
                "consultant_label":  consultant["label"],
                "consultant_model":  consultant["model"],
                "consultant_base":   consultant["base"],
                "consultant_api_key": consultant.get("api_key"),  # None = use SAIA rotating key
            } | {"persona_id": persona})
            run_id += 1
    return runs


def build_command(run: dict, base_url: str, language: str,
                  skip_ideation: bool, no_pdf: bool,
                  saia_key: str) -> list:
    consultant_key = run["consultant_api_key"] or saia_key
    cmd = [
        sys.executable, str(SCRIPT),
        "--persona",              run["persona_id"],
        "--consultant-model",     run["consultant_model"],
        "--consultant-base",      run["consultant_base"],
        "--api-key",              consultant_key,
        "--user-agent-model",     USER_AGENT_MODEL,
        "--user-agent-base",      USER_AGENT_BASE,
        "--user-agent-api-key",   saia_key if USER_AGENT_BASE == SAIA_BASE else os.environ.get(USER_AGENT_KEY_ENV, ""),
        "--user-agent-temperature", str(USER_AGENT_TEMPERATURE),
        "--language",             language,
        "--base-url",             base_url,
    ]
    if skip_ideation:
        cmd.append("--skip-ideation")
    if no_pdf:
        cmd.append("--no-pdf")
    return cmd


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {}


def save_progress(progress: dict):
    """Atomic read-modify-write under exclusive lock."""
    PROGRESS_FILE.touch(exist_ok=True)
    with open(PROGRESS_FILE, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            content = f.read().strip()
            existing = json.loads(content) if content else {}
            existing.update(progress)
            f.seek(0)
            f.truncate()
            json.dump(existing, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def save_mapping(entry: dict):
    """Atomic append under exclusive lock."""
    MAPPING_FILE.touch(exist_ok=True)
    with open(MAPPING_FILE, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            content = f.read().strip()
            existing = json.loads(content) if content else []
            if not isinstance(existing, list):
                existing = []
            existing.append(entry)
            f.seek(0)
            f.truncate()
            json.dump(existing, f, indent=2, ensure_ascii=False)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m{s:02d}s" if m else f"{s}s"


def validate_env():
    required = {
        "SCADS_API_KEY",
        "GROQ_API_KEY",
        "SAIA_API_KEY",
        "MISTRAL_API_KEY",
    }
    missing = [k for k in sorted(required) if not os.environ.get(k)]
    if missing:
        print(f"ERROR: Missing environment variables: {', '.join(missing)}")
        print("Add them to ~/.zshrc and run: source ~/.zshrc")
        sys.exit(1)
    if not os.environ.get("SAIA_API_KEY2"):
        print("WARNING: SAIA_API_KEY2 not set — SAIA rate-limit key rotation disabled")


def print_run_header(run: dict, run_index: int, total: int):
    print("\n" + "=" * 70)
    print(f"  Run {run_index}/{total}  (ID #{run['run_id']})")
    print(f"  Consultant: {run['consultant_label']}")
    print(f"  Persona:    {run['persona_id']}")
    print(f"  Started:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


# =========================================
# Main
# =========================================

def main():
    parser = argparse.ArgumentParser(description=f"Benchmark Matrix Runner ({TOTAL_RUNS} runs)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print commands without executing")
    parser.add_argument("--resume", action="store_true",
                        help="Skip runs already marked completed in progress.json")
    parser.add_argument("--start-from", type=int, default=1, metavar="N",
                        help="Start from run #N (1-indexed, across full matrix order)")
    parser.add_argument("--consultant", type=str, default=None, metavar="ID",
                        help=f"Run only this consultant id. Valid: {[c['id'] for c in CONSULTANT_MODELS]}")
    parser.add_argument("--persona", type=str, default=None, metavar="ID",
                        help=f"Run only this persona id. Valid: {PERSONAS}")
    parser.add_argument("--language", default="de", choices=["en", "de"],
                        help="Prompt language (default: de)")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="Backend API URL (default: http://localhost:8000)")
    parser.add_argument("--skip-ideation", action="store_true",
                        help="Skip Steps 2 & 3 (6-3-5 + prioritization). "
                             "Recommended for eval runs — saves ~10 API calls per run.")
    parser.add_argument("--no-pdf", action="store_true",
                        help="Skip PDF export (JSON findings sufficient for judge).")
    args = parser.parse_args()

    if not args.dry_run:
        validate_env()

    MATRIX_DIR.mkdir(parents=True, exist_ok=True)

    all_runs = build_runs()

    # Apply filters
    if args.consultant:
        all_runs = [r for r in all_runs if r["consultant_id"] == args.consultant]
        if not all_runs:
            print(f"ERROR: Unknown consultant id '{args.consultant}'")
            print(f"Valid ids: {[c['id'] for c in CONSULTANT_MODELS]}")
            sys.exit(1)
    if args.persona:
        all_runs = [r for r in all_runs if r["persona_id"] == args.persona]
        if not all_runs:
            print(f"ERROR: Unknown persona '{args.persona}'")
            sys.exit(1)
    if args.start_from > 1:
        all_runs = [r for r in all_runs if r["run_id"] >= args.start_from]

    progress = load_progress()

    # ── Print plan ──────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  BENCHMARK MATRIX  —  {len(all_runs)} runs")
    print(f"  User agent  : {USER_AGENT_MODEL}  (temp={USER_AGENT_TEMPERATURE})")
    print(f"  Language    : {args.language}")
    print(f"  Backend     : {args.base_url}")
    if args.dry_run:   print("  Mode        : DRY RUN")
    if args.resume:    print("  Mode        : RESUME (skipping completed)")
    print(f"{'='*70}")
    print(f"\n  Consultant models ({len(CONSULTANT_MODELS)}):")
    for c in CONSULTANT_MODELS:
        print(f"    [{c['id']}]  {c['label']}")
    print(f"\n  Personas ({len(PERSONAS)}):")
    for p in PERSONAS:
        print(f"    {p}")

    if args.dry_run:
        print(f"\n{'='*70}")
        print("  Commands that would be executed:")
        print(f"{'='*70}")
        for i, run in enumerate(all_runs, 1):
            cmd = build_command(run, args.base_url, args.language,
                                args.skip_ideation, args.no_pdf,
                                saia_key="<SAIA_API_KEY>")
            print(f"\n  Run {i}: [{run['consultant_id']}] × [{run['persona_id']}]")
            print("  " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
        return

    # ── Execute ─────────────────────────────────────────────────
    succeeded = failed = skipped = 0
    saia_key = current_saia_key()
    exhausted_consultants: set = set()  # consultant_ids with daily quota exhausted

    for run_index, run in enumerate(all_runs, 1):
        run_key = f"{run['consultant_id']}__{run['persona_id']}"

        if args.resume and progress.get(run_key, {}).get("status") == "completed":
            print(f"\n  [SKIP] Run #{run['run_id']}: {run['consultant_id']} × {run['persona_id']}")
            skipped += 1
            continue

        if run["consultant_id"] in exhausted_consultants:
            print(f"\n  [SKIP-TPD] Run #{run['run_id']}: {run['consultant_id']} daily quota exhausted — skipping")
            progress[run_key] = {
                "status":           "skipped_tpd",
                "run_id":           run["run_id"],
                "consultant_id":    run["consultant_id"],
                "consultant_model": run["consultant_model"],
                "persona_id":       run["persona_id"],
                "timestamp":        datetime.now().isoformat(),
            }
            save_progress(progress)
            skipped += 1
            continue

        print_run_header(run, run_index, len(all_runs))

        cmd = build_command(run, args.base_url, args.language,
                            args.skip_ideation, args.no_pdf,
                            saia_key=saia_key)
        start_time = time.time()

        try:
            result = subprocess.run(cmd, check=False)
            elapsed = time.time() - start_time
            success = result.returncode == 0
            status  = "completed" if success else "failed"

            progress[run_key] = {
                "status":           status,
                "run_id":           run["run_id"],
                "consultant_id":    run["consultant_id"],
                "consultant_model": run["consultant_model"],
                "persona_id":       run["persona_id"],
                "timestamp":        datetime.now().isoformat(),
                "elapsed_seconds":  round(elapsed),
                "returncode":       result.returncode,
            }
            save_progress(progress)
            save_mapping({
                "run_id":            run["run_id"],
                "consultant_id":     run["consultant_id"],
                "consultant_label":  run["consultant_label"],
                "consultant_model":  run["consultant_model"],
                "persona_id":        run["persona_id"],
                "status":            status,
                "timestamp":         datetime.now().isoformat(),
            })

            if success:
                succeeded += 1
                print(f"\n  ✅  Run #{run['run_id']} completed in {fmt_duration(elapsed)}")
            else:
                if result.returncode == 3:
                    # User agent rate limit — rotate SAIA key and relaunch same run
                    print(f"\n  ♻️   Run #{run['run_id']} user agent rate limit — rotating key and retrying...")
                    saia_key = on_saia_rate_limit()
                    cmd = build_command(run, args.base_url, args.language,
                                        args.skip_ideation, args.no_pdf,
                                        saia_key=saia_key)
                    start_time = time.time()
                    result = subprocess.run(cmd, check=False)
                    elapsed = time.time() - start_time
                    success = result.returncode == 0
                    status = "completed" if success else "failed"
                    if success:
                        succeeded += 1
                        print(f"\n  ✅  Run #{run['run_id']} completed after retry in {fmt_duration(elapsed)}")
                    else:
                        failed += 1
                        print(f"\n  ❌  Run #{run['run_id']} FAILED after retry (returncode={result.returncode})")
                elif result.returncode == 2:
                    failed += 1
                    print(f"\n  ❌  Run #{run['run_id']} FAILED (returncode=2)")
                    if run["consultant_api_key"] is None:
                        # SAIA consultant rate limit — rotate key
                        saia_key = on_saia_rate_limit()
                    else:
                        # Daily token quota (TPD) exhausted for this consultant
                        print(f"  [TPD] Daily quota exhausted for {run['consultant_id']} — skipping remaining runs for this model")
                        exhausted_consultants.add(run["consultant_id"])
                else:
                    failed += 1
                    print(f"\n  ❌  Run #{run['run_id']} FAILED (returncode={result.returncode})")

        except KeyboardInterrupt:
            print("\n\n  [INTERRUPTED] Saving progress and exiting...")
            save_progress(progress)
            break
        except Exception as e:
            elapsed = time.time() - start_time
            failed += 1
            print(f"\n  ❌  Run #{run['run_id']} EXCEPTION: {e}")
            progress[run_key] = {
                "status":        "error",
                "run_id":        run["run_id"],
                "consultant_id": run["consultant_id"],
                "persona_id":    run["persona_id"],
                "error":         str(e),
                "timestamp":     datetime.now().isoformat(),
            }
            save_progress(progress)

    # ── Summary ──────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  MATRIX COMPLETE")
    print(f"  Succeeded : {succeeded}")
    print(f"  Failed    : {failed}")
    print(f"  Skipped   : {skipped}")
    print(f"  Progress  : {PROGRESS_FILE}")
    print(f"  Mapping   : {MAPPING_FILE}  (for post-judging de-anonymization)")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
