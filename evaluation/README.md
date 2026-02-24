# Evaluation Tools for AI Consultant Application

This folder contains tools for evaluating the quality of AI consultation advice provided by the application.

## Prerequisites

```bash
pip install litellm requests
```

Set your LLM API key:
```bash
export MISTRAL_API_KEY="your-key"
# or
export OPENAI_API_KEY="your-key"
```

Ensure the backend is running:
```bash
cd ../backend
python -m uvicorn app.main:app --reload
```

---

## Tools Overview

| Tool | Purpose | Mode |
|------|---------|------|
| `benchmark_harness.py` | **Ground truth evaluation** against benchmark personas | Automated |
| `e2e_workflow_test.py` | End-to-end workflow test | Automated |
| `auto_evaluate.py` | LLM-as-judge quality evaluation | Automated |
| `evaluate.py` | Human evaluation with rubric | Interactive |
| `benchmark_personas.json` | Detailed SME company profiles with ground truth | Data |
| `test_cases.py` | Simpler test case profiles | Data |
| `rubric.py` | Quality evaluation criteria | Config |

---

## 1. Benchmark Harness (Ground Truth Evaluation)

**File:** `benchmark_harness.py`

**Primary evaluation tool** that tests consultation quality against ground truth expectations from benchmark personas. This is the recommended tool for systematic evaluation.

### What It Tests

1. **Seeds session** with persona data (company info, maturity assessment, focus idea)
2. **Runs CRISP-DM consultation** (Step 4) with LLM-simulated user responses
3. **Extracts findings** from the consultation
4. **Evaluates against ground truth** using LLM-as-Judge:
   - Value level classification (Budget Substitution, Process Efficiency, etc.)
   - Critical questions asked vs missed
   - Challenges identified vs missed
   - KPI impact discussion quality
   - Practical guidance quality

### Usage

```bash
# List available personas with their ground truth
python benchmark_harness.py --list

# Run benchmark for single persona
python benchmark_harness.py --persona mfg_01_metal_quality --api-key YOUR_KEY

# Run benchmarks for ALL personas
python benchmark_harness.py --all --api-key YOUR_KEY --save

# With specific model and more turns
python benchmark_harness.py --persona mfg_02_plastics_maintenance \
  --model gpt-4o \
  --turns 8 \
  --save

# Quiet mode with cleanup
python benchmark_harness.py --all --quiet --cleanup --save
```

### Options

| Flag | Description |
|------|-------------|
| `--persona ID` | Run benchmark for specific persona |
| `--all` | Run benchmarks for all personas |
| `--api-key KEY` | LLM API key (or use env var) |
| `--model MODEL` | LLM model (default: gpt-4o-mini) |
| `--turns N` | Consultation turns (default: 6) |
| `--save` | Save results to `results/benchmark/` |
| `--cleanup` | Delete test sessions after run |
| `--quiet` | Reduce output verbosity |
| `--list` | Show available personas with ground truth |

### Output Metrics

The benchmark evaluates and reports:

| Metric | Description |
|--------|-------------|
| `value_level_match` | Did consultant identify correct value level? |
| `critical_questions_asked` | Which expected questions were asked |
| `critical_questions_missed` | Which expected questions were NOT asked |
| `challenges_identified` | Which implementation challenges were discussed |
| `challenges_missed` | Which challenges were NOT discussed |
| `weighted_score` | Overall rubric score (1-5) |
| `grade` | Letter grade (A-D) |

### Example Output

```
BENCHMARK: Müller Metallbau GmbH
Persona: mfg_01_metal_quality
======================================================================
[1/4] Creating and seeding session...
  Session: a1b2c3d4...
  Company info added (2847 chars)
  Maturity: Connectivity (2.19)
  Focus idea injected: AI-based visual quality inspection...
  Focus idea prioritized

[2/4] Running consultation (6 turns)...
  AI: Welcome! I'm here to help you explore AI...
  Turn 1/6...
  Turn 2/6...
  ...

[3/4] Extracting findings...
  Extracted 8 findings

[4/4] Evaluating against ground truth...
  Value level match: True
  Critical questions asked: 3/4
  Challenges identified: 3/4
  Weighted score: 4.12
  Grade: B+ (Very Good)

======================================================================
BENCHMARK COMPLETED: B+ (Very Good) (4.12/5.0)
======================================================================
```

### Results JSON Structure

```json
{
  "timestamp": "2025-01-29T10:30:00",
  "total_personas": 5,
  "successful": 5,
  "aggregate": {
    "average_score": 3.85,
    "average_grade": "B (Good)",
    "value_level_match_rate": 0.80,
    "avg_critical_questions_asked": 2.8,
    "avg_challenges_identified": 2.6
  },
  "results": [
    {
      "persona_id": "mfg_01_metal_quality",
      "company_name": "Müller Metallbau GmbH",
      "success": true,
      "weighted_score": 4.12,
      "grade": "B+ (Very Good)",
      "value_level_match": true,
      "critical_questions_asked": ["How many part geometries?", "..."],
      "critical_questions_missed": ["False positive rate tolerance?"],
      "challenges_identified": ["Training data collection", "..."],
      "ground_truth_comparison": {
        "strengths": "...",
        "weaknesses": "...",
        "summary": "..."
      }
    }
  ]
}
```

---

## 2. End-to-End Workflow Test

**File:** `e2e_workflow_test.py`

Tests the complete application workflow with an LLM-simulated user:

1. Create session with company profile
2. Human participant joins 6-3-5 brainstorming
3. AI participants generate ideas (2 rounds)
4. Prioritization voting
5. LLM-simulated consultation (4 turns)
6. CRISP-DM findings extraction
7. PDF export validation

### Usage

```bash
# List available personas
python e2e_workflow_test.py --list-personas

# Run with default persona (first one)
MISTRAL_API_KEY="your-key" python e2e_workflow_test.py --save

# Run with specific persona
MISTRAL_API_KEY="your-key" python e2e_workflow_test.py \
  --persona mfg_01_metal_quality \
  --model mistral/mistral-small-latest \
  --save

# With OpenAI
OPENAI_API_KEY="your-key" python e2e_workflow_test.py \
  --model gpt-4o-mini \
  --save

# Delete test session after completion
python e2e_workflow_test.py --save --cleanup

# Quiet mode
python e2e_workflow_test.py --quiet --save
```

### Options

| Flag | Description |
|------|-------------|
| `--persona ID` | Use specific benchmark persona |
| `--model MODEL` | LLM model (default: gpt-4o-mini) |
| `--api-key KEY` | Pass API key directly |
| `--save` | Save results to `results/e2e/` |
| `--cleanup` | Delete test session after run |
| `--quiet` | Reduce output verbosity |
| `--list-personas` | Show available personas |

### Output

- Console: Step-by-step progress with timing
- JSON: Full results saved to `results/e2e/`
- PDF: Generated report saved to `results/e2e/`

---

## 3. Automated LLM Evaluation

**File:** `auto_evaluate.py`

Uses LLM-as-User to simulate consultation and LLM-as-Judge to rate quality.

### Usage

```bash
# List test cases
python auto_evaluate.py --cases

# Run single evaluation
python auto_evaluate.py --case bakery_001 --save

# Run batch evaluation (all test cases)
python auto_evaluate.py --batch

# With specific model
python auto_evaluate.py --case bakery_001 --model gpt-4o --save

# Set max conversation turns
python auto_evaluate.py --case bakery_001 --turns 8
```

### Options

| Flag | Description |
|------|-------------|
| `--case ID` | Run specific test case |
| `--batch` | Run all test cases |
| `--model MODEL` | LLM model to use |
| `--turns N` | Max conversation turns (default: 6) |
| `--quiet` | Reduce output |
| `--save` | Save results to file |
| `--cases` | List available test cases |

### Output

Results include:
- Weighted score (1-5)
- Grade (A-D)
- Scores per criterion
- Themes covered
- Red flags found
- Strengths/weaknesses summary

---

## 4. Human Evaluation Tool

**File:** `evaluate.py`

Interactive tool for human evaluators to rate consultation quality.

### Usage

```bash
# Show evaluation rubric
python evaluate.py --rubric

# List test cases
python evaluate.py --cases

# Run interactive evaluation
python evaluate.py --case bakery_001

# Analyze saved results
python evaluate.py --analyze
```

### Interactive Flow

1. Select test case
2. View company profile
3. Conduct consultation (type responses)
4. Rate each criterion (1-5)
5. Add evaluator notes
6. Results saved to `results/`

### Commands During Consultation

| Command | Action |
|---------|--------|
| `/done` | End consultation, proceed to scoring |
| `/show` | Show full conversation |
| `/extract` | Extract findings now |

---

## 5. Benchmark Personas

**File:** `benchmark_personas.json`

Detailed SME company profiles for realistic testing.

### Available Personas

| ID | Company | Industry | Focus Idea |
|----|---------|----------|------------|
| `mfg_01_metal_quality` | Müller Metallbau GmbH | Metal fabrication | AI visual quality inspection |
| `mfg_02_plastics_maintenance` | Kunststofftechnik Berger KG | Plastics injection | Predictive mold maintenance |
| `mfg_03_electronics_testing` | ElektronikWerk Sachsen GmbH | Electronics assembly | Test optimization |
| `mfg_04_food_digitalization` | Bäckerei Konditorei Hofmann | Industrial bakery | Demand forecasting |
| `mfg_05_precision_design` | Feinmechanik Weber GmbH | Precision mechanics | Generative design |

Each persona includes:
- Company details (name, size, revenue)
- Business model and products
- KPIs with current values and targets
- Digitalization maturity level
- Current challenges
- Focus idea for AI/digitalization
- Ground truth for evaluation

---

## 6. Evaluation Rubric

**File:** `rubric.py`

Quality criteria with weighted scoring.

### Criteria

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Relevance | 1.0 | How well advice relates to company |
| Actionability | 1.2 | How concrete/implementable |
| Accuracy | 1.0 | Technical correctness |
| Clarity | 1.1 | Understandable for non-experts |
| Completeness | 0.9 | Framework coverage (CRISP-DM) |
| SME Appropriateness | 1.0 | Suitable for SME resources |

### Grading Scale

| Score | Grade |
|-------|-------|
| 4.5+ | A (Excellent) |
| 4.0+ | B+ (Very Good) |
| 3.5+ | B (Good) |
| 3.0+ | C+ (Adequate) |
| 2.5+ | C (Needs Improvement) |
| <2.5 | D (Poor) |

---

## 7. Simple Test Cases

**File:** `test_cases.py`

Lighter-weight company profiles for quick testing.

### Available Cases

| ID | Name | Language |
|----|------|----------|
| `bakery_001` | Small Family Bakery | en |
| `manufacturing_002` | Metal Parts Manufacturer | en |
| `retail_003` | Online Fashion Boutique | en |
| `healthcare_004` | Dental Practice | de |
| `logistics_005` | Regional Logistics Company | en |
| `restaurant_006` | Restaurant Chain | en |

---

## Results Directory Structure

```
results/
├── benchmark/              # Ground truth benchmark results
│   └── benchmark_*.json    # Aggregate results with ground truth comparison
├── e2e/                    # End-to-end test results
│   ├── e2e_mfg_01_*.json   # JSON results
│   └── e2e_test_*.pdf      # Generated PDFs
├── auto_*.json             # Auto-evaluation results
└── bakery_001_*.json       # Human evaluation results
```

---

## Example Workflows

### Quick Smoke Test
```bash
MISTRAL_API_KEY="your-key" python e2e_workflow_test.py --quiet --cleanup
```

### Full Benchmark Evaluation (Recommended)
```bash
# Run ground truth evaluation for all personas
OPENAI_API_KEY="your-key" python benchmark_harness.py --all --save --cleanup

# Or with Mistral
MISTRAL_API_KEY="your-key" python benchmark_harness.py \
  --all \
  --model mistral/mistral-small-latest \
  --save --cleanup
```

### Single Persona Deep Evaluation
```bash
# Verbose output for debugging
OPENAI_API_KEY="your-key" python benchmark_harness.py \
  --persona mfg_01_metal_quality \
  --turns 8 \
  --save
```

### Full E2E Workflow Suite
```bash
# Run e2e test for all personas
for persona in mfg_01_metal_quality mfg_02_plastics_maintenance mfg_03_electronics_testing; do
  MISTRAL_API_KEY="your-key" python e2e_workflow_test.py \
    --persona $persona --save --cleanup
done

# Run auto-evaluation batch
python auto_evaluate.py --batch --model gpt-4o-mini
```

### Compare Models
```bash
# Benchmark with Mistral Small
MISTRAL_API_KEY="your-key" python benchmark_harness.py \
  --all --model mistral/mistral-small-latest --save

# Benchmark with GPT-4o
OPENAI_API_KEY="your-key" python benchmark_harness.py \
  --all --model gpt-4o --save

# Benchmark with GPT-4o-mini
OPENAI_API_KEY="your-key" python benchmark_harness.py \
  --all --model gpt-4o-mini --save

# Compare results in results/benchmark/
```

### Continuous Integration
```bash
# Quick CI check (single persona, cleanup)
OPENAI_API_KEY="$CI_API_KEY" python benchmark_harness.py \
  --persona mfg_01_metal_quality \
  --quiet \
  --cleanup

# Check exit code (0 = success, 1 = failure)
echo "Exit code: $?"
```
