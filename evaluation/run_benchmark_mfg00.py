#!/usr/bin/env python3
"""
Benchmark Runner — mfg_00_wood_scheduling (all models, 3 reps each)
====================================================================
mfg_00 is the replacement blind test persona for mfg_01 (which was
used as a development/smoke-test persona and is excluded from the
comparative benchmark to avoid train/test leakage).

8 consultant models × 3 repetitions = 24 runs.
Run IDs 145–168 — no collision with:
  r1 (1–42), r2 (43–84), r3 (85–126),
  r4 (127–132), r4b (133–138), r4c (139–144)

Models match the full benchmark matrix:
  - 7 models from r1/r2/r3 (ScaDS + SAIA)
  - DeepSeek-R1-Distill-Llama-70B from r4/r4b/r4c

--skip-ideation and --no-pdf are ON by default (benchmark only needs the
consultation + analysis steps, not the 6-3-5 ideation or PDF export).

Usage:
    python run_benchmark_mfg00.py
    python run_benchmark_mfg00.py --dry-run
    python run_benchmark_mfg00.py --resume
    python run_benchmark_mfg00.py --consultant saia_qwen3_235b
    python run_benchmark_mfg00.py --rep 2
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

SAIA_BASE    = "https://chat-ai.academiccloud.de/v1"
SCADS_BASE   = "https://llm.scads.ai/v1"
GOOGLE_BASE  = "https://generativelanguage.googleapis.com/v1beta"

# =========================================
# API keys
# =========================================

GOOGLE_API_KEY = os.environ.get("GOOGLE_AI_STUDIO_KEY", "")
SCADS_API_KEY  = os.environ.get("SCADS_API_KEY", "")

SAIA_API_KEYS = [
    os.environ.get("SAIA_API_KEY",  ""),
    os.environ.get("SAIA_API_KEY2", ""),
]

_saia_key_index = 0
_ua_fallback_active = False

# =========================================
# User agent — same as all other rounds
# =========================================

USER_AGENT_MODEL       = "openai/gemma-3-27b-it"
USER_AGENT_BASE        = SAIA_BASE
USER_AGENT_TEMPERATURE = 0.0

UA_FALLBACK_MODEL = "gemini/gemma-3-27b-it"
UA_FALLBACK_BASE  = GOOGLE_BASE
UA_FALLBACK_KEY   = GOOGLE_API_KEY

# =========================================
# Consultant models — all 8 from full matrix
# =========================================

CONSULTANT_MODELS = [
    # --- 7 models from r1/r2/r3 (ScaDS) ---
    {
        "id":      "scads_minimax_m2_5",
        "label":   "MiniMax M2.5 (ScaDS)",
        "model":   "openai/MiniMaxAI/MiniMax-M2.5",
        "base":    SCADS_BASE,
        "api_key": SCADS_API_KEY,
    },
    {
        "id":      "scads_llama33_70b",
        "label":   "Llama 3.3 70B (ScaDS)",
        "model":   "openai/meta-llama/Llama-3.3-70B-Instruct",
        "base":    SCADS_BASE,
        "api_key": SCADS_API_KEY,
    },
    {
        "id":      "scads_gpt_oss_120b",
        "label":   "GPT OSS 120B (ScaDS)",
        "model":   "openai/openai/gpt-oss-120b",
        "base":    SCADS_BASE,
        "api_key": SCADS_API_KEY,
    },
    {
        "id":      "scads_llama4_scout",
        "label":   "Llama 4 Scout (ScaDS)",
        "model":   "openai/meta-llama/Llama-4-Scout-17B-16E-Instruct",
        "base":    SCADS_BASE,
        "api_key": SCADS_API_KEY,
    },
    # --- 3 models from r1/r2/r3 (SAIA) ---
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
        "api_key": None,
    },
    {
        "id":      "saia_mistral_large3",
        "label":   "Mistral Large 3 675B (SAIA)",
        "model":   "openai/mistral-large-3-675b-instruct-2512",
        "base":    SAIA_BASE,
        "api_key": None,
    },
    # --- DeepSeek from r4/r4b/r4c (SAIA) ---
    {
        "id":      "saia_deepseek_r1_distill_llama_70b",
        "label":   "DeepSeek-R1-Distill-Llama-70B (SAIA)",
        "model":   "openai/deepseek-r1-distill-llama-70b",
        "base":    SAIA_BASE,
        "api_key": None,
    },
]

# =========================================
# Single persona + repetitions
# =========================================

PERSONA      = "mfg_00_wood_scheduling"
REPETITIONS  = 3   # match 3× repetitions used for all other personas

# =========================================
# Run ID range
# =========================================

RUN_ID_BASE   = 145   # r4c ends at 144
SCRIPT        = Path(__file__).parent / "run_test_persona1.py"
MATRIX_DIR    = Path(__file__).parent / "matrix_runs_mfg00"
MAPPING_FILE  = MATRIX_DIR / "mapping.json"
PROGRESS_FILE = MATRIX_DIR / "progress.json"

TOTAL_RUNS = len(CONSULTANT_MODELS) * REPETITIONS   # 24

RATE_LIMIT_WAIT = 3700


# =========================================
# SAIA Rate Limit Helpers
# =========================================

def get_saia_quota(api_key: str) -> dict | None:
    try:
        resp = requests.post(
            f"{SAIA_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "openai/mistral-large-latest", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
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


def on_saia_rate_limit() -> tuple:
    global _saia_key_index, _ua_fallback_active
    next_index = (_saia_key_index + 1) % len(SAIA_API_KEYS)
    if next_index != 0:
        next_key = SAIA_API_KEYS[next_index]
        print(f"  [QUOTA] SAIA rate limit — rotating to key ...{next_key[-6:]}")
        _saia_key_index = next_index
        return SAIA_BASE, next_key
    if not _ua_fallback_active:
        print("  [QUOTA] All SAIA keys exhausted — switching user agent to Google AI Studio fallback")
        _ua_fallback_active = True
        return UA_FALLBACK_BASE, UA_FALLBACK_KEY
    print("  [QUOTA] Google AI fallback also rate limited — checking SAIA reset time...")
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
    _ua_fallback_active = False
    return SAIA_BASE, SAIA_API_KEYS[0]


# =========================================
# Helpers
# =========================================

def build_runs() -> list:
    """Build list of 24 runs: rep 1 of all 8 models, then rep 2, then rep 3."""
    runs = []
    run_id = RUN_ID_BASE
    for rep in range(1, REPETITIONS + 1):
        for consultant in CONSULTANT_MODELS:
            runs.append({
                "run_id":             run_id,
                "rep":                rep,
                "consultant_id":      consultant["id"],
                "consultant_label":   consultant["label"],
                "consultant_model":   consultant["model"],
                "consultant_base":    consultant["base"],
                "consultant_api_key": consultant.get("api_key"),
                "persona_id":         PERSONA,
            })
            run_id += 1
    return runs


def build_command(run: dict, base_url: str, language: str,
                  skip_ideation: bool, no_pdf: bool,
                  saia_key: str, verbose: bool = False) -> list:
    consultant_key  = run["consultant_api_key"] or saia_key
    all_saia_keys   = ",".join(k for k in SAIA_API_KEYS if k)
    consultant_keys = all_saia_keys if run["consultant_api_key"] is None else consultant_key
    cmd = [
        sys.executable, str(SCRIPT),
        "--persona",                   run["persona_id"],
        "--consultant-model",          run["consultant_model"],
        "--consultant-base",           run["consultant_base"],
        "--api-key",                   consultant_key,
        "--consultant-api-keys",       consultant_keys,
        "--user-agent-model",          USER_AGENT_MODEL,
        "--user-agent-base",           USER_AGENT_BASE,
        "--user-agent-api-keys",       all_saia_keys,
        "--user-agent-temperature",    str(USER_AGENT_TEMPERATURE),
        "--user-agent-fallback-model", UA_FALLBACK_MODEL,
        "--user-agent-fallback-base",  UA_FALLBACK_BASE,
        "--user-agent-fallback-key",   UA_FALLBACK_KEY,
        "--language",                  language,
        "--base-url",                  base_url,
        "--run-id",                    str(run["run_id"]),
    ]
    if skip_ideation: cmd.append("--skip-ideation")
    if no_pdf:        cmd.append("--no-pdf")
    if verbose:       cmd.append("--verbose")
    return cmd


def run_key_for(run: dict) -> str:
    """Unique key per (consultant, rep) — allows --resume to distinguish repetitions."""
    return f"{run['consultant_id']}__mfg_00_wood_scheduling__rep{run['rep']}"


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {}


def save_progress(progress: dict):
    PROGRESS_FILE.touch(exist_ok=True)
    with open(PROGRESS_FILE, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            content = f.read().strip()
            existing = json.loads(content) if content else {}
            existing.update(progress)
            f.seek(0); f.truncate()
            json.dump(existing, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def save_mapping(entry: dict):
    MAPPING_FILE.touch(exist_ok=True)
    with open(MAPPING_FILE, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            content = f.read().strip()
            existing = json.loads(content) if content else []
            if not isinstance(existing, list): existing = []
            existing.append(entry)
            f.seek(0); f.truncate()
            json.dump(existing, f, indent=2, ensure_ascii=False)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m{s:02d}s" if m else f"{s}s"


def validate_env():
    missing = [k for k in ["SAIA_API_KEY", "SCADS_API_KEY", "GOOGLE_AI_STUDIO_KEY"] if not os.environ.get(k)]
    if missing:
        print(f"ERROR: Missing environment variables: {', '.join(missing)}")
        sys.exit(1)
    if not os.environ.get("SAIA_API_KEY2"):
        print("WARNING: SAIA_API_KEY2 not set — rate-limit key rotation disabled")


def print_run_header(run: dict, run_index: int, total: int):
    print("\n" + "=" * 70)
    print(f"  Run {run_index}/{total}  (ID #{run['run_id']},  rep {run['rep']}/{REPETITIONS})")
    print(f"  Consultant: {run['consultant_label']}")
    print(f"  Persona:    {run['persona_id']}")
    print(f"  Started:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


# =========================================
# Main
# =========================================

def main():
    parser = argparse.ArgumentParser(
        description=f"Benchmark Runner — mfg_00 / all models / {REPETITIONS} reps "
                    f"({TOTAL_RUNS} runs, IDs {RUN_ID_BASE}–{RUN_ID_BASE+TOTAL_RUNS-1})"
    )
    parser.add_argument("--dry-run",       action="store_true", help="Print commands without executing")
    parser.add_argument("--resume",        action="store_true", help="Skip runs already completed in progress.json")
    parser.add_argument("--consultant",    type=str, default=None,
                        help=f"Run only this consultant id. Valid: {[c['id'] for c in CONSULTANT_MODELS]}")
    parser.add_argument("--rep",           type=int, default=None, choices=range(1, REPETITIONS + 1),
                        help="Run only this repetition number (1, 2, or 3)")
    parser.add_argument("--language",      default="de", choices=["en", "de"])
    parser.add_argument("--base-url",      default="http://localhost:8000")
    parser.add_argument("--skip-ideation", action="store_true", default=True)
    parser.add_argument("--no-pdf",        action="store_true", default=True)
    parser.add_argument("--verbose",       action="store_true")
    args = parser.parse_args()

    if not args.dry_run:
        validate_env()

    MATRIX_DIR.mkdir(parents=True, exist_ok=True)

    all_runs = build_runs()

    if args.consultant:
        all_runs = [r for r in all_runs if r["consultant_id"] == args.consultant]
        if not all_runs:
            print(f"ERROR: Unknown consultant id '{args.consultant}'"); sys.exit(1)
    if args.rep:
        all_runs = [r for r in all_runs if r["rep"] == args.rep]

    progress = load_progress()

    print(f"\n{'='*70}")
    print(f"  BENCHMARK — mfg_00_wood_scheduling  ({len(all_runs)} runs)")
    print(f"  Run IDs   : {RUN_ID_BASE}–{RUN_ID_BASE+TOTAL_RUNS-1}")
    print(f"  Reps      : {REPETITIONS}× per model")
    print(f"  Output    : {MATRIX_DIR}")
    print(f"  User agent: {USER_AGENT_MODEL}  (temp={USER_AGENT_TEMPERATURE})")
    print(f"  Language  : {args.language}")
    print(f"  Backend   : {args.base_url}")
    if args.dry_run: print("  Mode      : DRY RUN")
    if args.resume:  print("  Mode      : RESUME (skipping completed)")
    print(f"{'='*70}")
    print(f"\n  Consultant models ({len(CONSULTANT_MODELS)}):")
    for c in CONSULTANT_MODELS:
        print(f"    [{c['id']}]  {c['label']}")

    if args.dry_run:
        print(f"\n{'='*70}")
        print("  Commands that would be executed:")
        print(f"{'='*70}")
        for i, run in enumerate(all_runs, 1):
            cmd = build_command(run, args.base_url, args.language,
                                args.skip_ideation, args.no_pdf, "<SAIA_KEY>")
            print(f"\n  Run {i}: [{run['consultant_id']}] rep {run['rep']}  (ID #{run['run_id']})")
            print("  " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
        return

    succeeded = failed = skipped = 0
    saia_key = current_saia_key()
    exhausted_consultants: set = set()

    for run_index, run in enumerate(all_runs, 1):
        rkey = run_key_for(run)

        if args.resume and progress.get(rkey, {}).get("status") == "completed":
            print(f"\n  [SKIP] #{run['run_id']}: {run['consultant_id']} rep {run['rep']}")
            skipped += 1
            continue

        if run["consultant_id"] in exhausted_consultants:
            print(f"\n  [SKIP-TPD] #{run['run_id']}: {run['consultant_id']} daily quota exhausted")
            progress[rkey] = {
                "status": "skipped_tpd", "run_id": run["run_id"],
                "consultant_id": run["consultant_id"], "rep": run["rep"],
                "persona_id": run["persona_id"], "timestamp": datetime.now().isoformat(),
            }
            save_progress(progress)
            skipped += 1
            continue

        print_run_header(run, run_index, len(all_runs))
        cmd = build_command(run, args.base_url, args.language,
                            args.skip_ideation, args.no_pdf,
                            saia_key=saia_key, verbose=args.verbose)
        start_time = time.time()

        try:
            result = subprocess.run(cmd, check=False)
            elapsed = time.time() - start_time
            success = result.returncode == 0
            status  = "completed" if success else "failed"

            progress[rkey] = {
                "status":           status,
                "run_id":           run["run_id"],
                "rep":              run["rep"],
                "consultant_id":    run["consultant_id"],
                "consultant_model": run["consultant_model"],
                "persona_id":       run["persona_id"],
                "timestamp":        datetime.now().isoformat(),
                "elapsed_seconds":  round(elapsed),
                "returncode":       result.returncode,
            }
            save_progress(progress)
            save_mapping({
                "run_id":           run["run_id"],
                "rep":              run["rep"],
                "consultant_id":    run["consultant_id"],
                "consultant_label": run["consultant_label"],
                "consultant_model": run["consultant_model"],
                "persona_id":       run["persona_id"],
                "status":           status,
                "timestamp":        datetime.now().isoformat(),
            })

            if success:
                succeeded += 1
                print(f"\n  ✅  Run #{run['run_id']} (rep {run['rep']}) completed in {fmt_duration(elapsed)}")
            else:
                if result.returncode == 3:
                    print(f"\n  ♻️   Run #{run['run_id']} — all UA keys exhausted, waiting for quota reset...")
                    on_saia_rate_limit()
                    saia_key = current_saia_key()
                    cmd = build_command(run, args.base_url, args.language,
                                        args.skip_ideation, args.no_pdf,
                                        saia_key=saia_key, verbose=args.verbose)
                    start_time = time.time()
                    result = subprocess.run(cmd, check=False)
                    elapsed = time.time() - start_time
                    success = result.returncode == 0
                    status = "completed" if success else "failed"
                    if success:
                        succeeded += 1
                        print(f"\n  ✅  Run #{run['run_id']} completed after quota-wait retry in {fmt_duration(elapsed)}")
                    else:
                        failed += 1
                        print(f"\n  ❌  Run #{run['run_id']} FAILED after retry (returncode={result.returncode})")
                elif result.returncode == 2:
                    failed += 1
                    print(f"\n  ❌  Run #{run['run_id']} FAILED (returncode=2)")
                    if run["consultant_api_key"] is None:
                        _, saia_key = on_saia_rate_limit()
                    else:
                        print(f"  [TPD] Daily quota exhausted for {run['consultant_id']} — skipping remaining runs")
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
            progress[rkey] = {
                "status": "error", "run_id": run["run_id"], "rep": run["rep"],
                "consultant_id": run["consultant_id"], "persona_id": run["persona_id"],
                "error": str(e), "timestamp": datetime.now().isoformat(),
            }
            save_progress(progress)

    print(f"\n{'='*70}")
    print(f"  mfg_00 BENCHMARK COMPLETE")
    print(f"  Succeeded : {succeeded}")
    print(f"  Failed    : {failed}")
    print(f"  Skipped   : {skipped}")
    print(f"  Progress  : {PROGRESS_FILE}")
    print(f"  Mapping   : {MAPPING_FILE}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
