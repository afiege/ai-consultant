# Manual PDF Evaluation Prompt for Gemini

Use this prompt when uploading a consultation PDF to Gemini for evaluation.

---

## Step 1: Upload the PDF

Upload the exported consultation PDF to Gemini (via AI Studio or the web interface).

---

## Step 2: Use This Evaluation Prompt

Copy and paste the following prompt, replacing the `[PLACEHOLDER]` sections with the persona's ground truth data:

---

```
You are an expert evaluator assessing an AI consultation report for an SME digitalization project.

## EVALUATION CONTEXT

**Company Focus Idea:** [PASTE FOCUS IDEA TITLE AND DESCRIPTION]

**Expected Value Level:** [PASTE: e.g., "Process Efficiency" or "Risk Mitigation"]

**Expected KPI Impacts:**
[PASTE KPI IMPACTS, e.g.:
- scrap_rate: "Reduce from 4.2% to <2%"
- inspection_fte: "Redeploy 1.5 FTE from manual inspection"]

**Critical Questions That Should Be Addressed:**
[PASTE QUESTIONS, e.g.:
- How many distinct part geometries need inspection?
- Is there historical defect image data or will collection start from scratch?
- What is the acceptable false positive rate before operators lose trust?]

**Expected Challenges To Identify:**
[PASTE CHALLENGES, e.g.:
- Training data collection for high-mix environment
- Integrating with production flow without adding cycle time
- Change management - inspectors transitioning to oversight role]

**Realistic First Step:**
[PASTE, e.g.: "Pilot on single high-volume part family with existing reject samples for training"]

---

## EVALUATION TASK

Please analyze the uploaded PDF consultation report and evaluate it against the criteria below.

### A. Ground Truth Comparison

1. **Value Level Match**: Did the consultation correctly identify the primary value level? (Yes/No/Partial)
   - What value level was identified (if any)?

2. **Critical Questions Coverage**:
   - Which of the expected critical questions were addressed in the consultation?
   - Which were missed?

3. **Challenges Identification**:
   - Which of the expected implementation challenges were discussed?
   - Which were missed?

4. **KPI Discussion Quality**:
   - Were the relevant KPIs discussed with specific targets or impacts?
   - Rate: Poor / Partial / Good / Excellent

5. **Practical Guidance**:
   - Was a realistic first step or similar practical guidance provided?
   - Rate: Poor / Partial / Good / Excellent

### B. Rubric Scoring (1-5 scale)

For each criterion, provide a score from 1-5 and a brief justification:

| Criterion | Score (1-5) | Justification |
|-----------|-------------|---------------|
| **Relevance** - How well the advice relates to the specific company profile | | |
| **Actionability** - How concrete and implementable the recommendations are | | |
| **Accuracy** - Technical correctness of AI/digitalization concepts | | |
| **Clarity** - Understandable for non-experts, minimal jargon | | |
| **Completeness** - Coverage of CRISP-DM phases | | |
| **SME Appropriateness** - Suitable for SME resources and constraints | | |
| **Maturity Integration** - Uses maturity assessment to tailor recommendations | | |
| **Maturity-Appropriate Complexity** - Solutions match company's digital maturity | | |

### C. Scoring Guide

**1 - Poor**: Fails to meet basic expectations
**2 - Below Average**: Some attempt but significant gaps
**3 - Adequate**: Meets basic expectations with room for improvement
**4 - Good**: Solid performance with minor gaps
**5 - Excellent**: Exceeds expectations, comprehensive coverage

### D. Overall Assessment

Please provide:
1. **Weighted Score**: Calculate average of the 8 rubric scores
2. **Grade**:
   - 4.5+ = A (Excellent)
   - 4.0+ = B+ (Very Good)
   - 3.5+ = B (Good)
   - 3.0+ = C+ (Adequate)
   - 2.5+ = C (Needs Improvement)
   - <2.5 = D (Poor)
3. **Key Strengths**: (2-3 points)
4. **Key Weaknesses**: (2-3 points)
5. **Summary**: (2-3 sentences overall assessment)

---

## OUTPUT FORMAT

Please respond in this JSON format for easy parsing:

```json
{
  "ground_truth_comparison": {
    "value_level_identified": "<identified value level or 'Not identified'>",
    "value_level_match": true/false,
    "critical_questions_addressed": ["<question1>", "<question2>"],
    "critical_questions_missed": ["<question1>", "<question2>"],
    "challenges_identified": ["<challenge1>", "<challenge2>"],
    "challenges_missed": ["<challenge1>", "<challenge2>"],
    "kpi_discussion_quality": "Poor/Partial/Good/Excellent",
    "practical_guidance_quality": "Poor/Partial/Good/Excellent"
  },
  "rubric_scores": {
    "relevance": <1-5>,
    "actionability": <1-5>,
    "accuracy": <1-5>,
    "clarity": <1-5>,
    "completeness": <1-5>,
    "sme_appropriateness": <1-5>,
    "maturity_integration": <1-5>,
    "maturity_appropriate_complexity": <1-5>
  },
  "rubric_justifications": {
    "relevance": "<brief justification>",
    "actionability": "<brief justification>",
    "accuracy": "<brief justification>",
    "clarity": "<brief justification>",
    "completeness": "<brief justification>",
    "sme_appropriateness": "<brief justification>",
    "maturity_integration": "<brief justification>",
    "maturity_appropriate_complexity": "<brief justification>"
  },
  "weighted_score": <average of 8 scores>,
  "grade": "<A/B+/B/C+/C/D>",
  "strengths": ["<strength1>", "<strength2>"],
  "weaknesses": ["<weakness1>", "<weakness2>"],
  "summary": "<2-3 sentence overall assessment>"
}
```
```

---

## Ground Truth Data for Each Persona

### Persona 1: mfg_01_metal_quality (Müller Metallbau GmbH)

**Focus Idea:** AI-based visual quality inspection for CNC machined parts

**Expected Value Level:** Process Efficiency

**Expected KPI Impacts:**
- scrap_rate: Reduce from 4.2% to <2%
- inspection_fte: Redeploy 1.5 FTE from manual inspection
- customer_complaints: Target zero escapes

**Critical Questions:**
- How many distinct part geometries need inspection?
- Is there historical defect image data or will collection start from scratch?
- What is the acceptable false positive rate before operators lose trust?
- What lighting/surface finish variations exist across the shop floor?
- Can inspection be integrated inline or must it be offline station?
- What is the cost of a missed defect reaching the customer?

**Expected Challenges:**
- Training data collection for high-mix environment
- Integrating with production flow without adding cycle time
- ROI justification given batch sizes
- Change management - inspectors transitioning to oversight role
- Amortization across part families

**Realistic First Step:** Pilot on single high-volume part family with existing reject samples for training

---

### Persona 2: mfg_02_plastics_maintenance (Kunststofftechnik Berger KG)

**Focus Idea:** AI-powered predictive mold maintenance

**Expected Value Level:** Risk Mitigation

**Expected KPI Impacts:**
- unplanned_downtime: Reduce from 18% to <8%
- mold_lifetime: Extend average by 15%
- emergency_repairs: Reduce from 12/year to <4

**Critical Questions:**
- How many mold failures in the past 2 years have process data history?
- What is the cost difference between emergency repair and planned maintenance?
- Are failure modes consistent or highly variable across mold types?
- What prediction horizon is needed for maintenance planning (hours, days, weeks)?

**Expected Challenges:**
- Labeling historical data - matching sensor data to failure events
- Different mold types may need different models
- False positives causing unnecessary maintenance stops
- Integration with maintenance planning workflows

**Realistic First Step:** Instrument 3-5 most critical molds with additional sensors, collect 6 months baseline data

---

### Persona 3: mfg_03_electronics_testing (ElektronikWerk Sachsen GmbH)

**Focus Idea:** AI-assisted test optimization and coverage analysis

**Expected Value Level:** Risk Mitigation + Project Acceleration

**Expected KPI Impacts:**
- field_return_ppm: Reduce from 1200 to <500 ppm
- test_development_time: Reduce by 30% for new products
- test_coverage_score: Achieve quantified coverage metric

**Critical Questions:**
- How well are field returns traced back to specific production lots and test data?
- What percentage of products share similar test requirements?
- Is there a taxonomy/classification of test types and failure modes?
- How are test sequences currently designed - rule-based, experience, copy-paste?
- What is the cost of a field return vs cost of additional testing?
- How much test data is available per product variant?
- Are test limits static or do they adapt to process drift?
- What's the relationship between AOI findings and functional test coverage?
- Who would trust/validate AI-generated test recommendations?
- What's the acceptable risk level for reducing test coverage?

**Expected Challenges:**
- Data quality - linking field returns to factory data across systems
- Test engineer buy-in - AI augments rather than replaces expertise
- Validation of AI-suggested test cases before production use
- Handling product variety - generic model vs product-specific
- Quantifying test coverage without ground truth
- Legacy test equipment integration
- Regulatory requirements for test documentation changes

**Realistic First Step:** Analyze correlation between existing test data and field returns for top 3 products to establish baseline

---

### Persona 4: mfg_04_food_digitalization (Bäckerei Konditorei Hofmann e.K.)

**Focus Idea:** Production planning digitalization with demand forecasting

**Expected Value Level:** Process Efficiency + Budget Substitution

**Expected KPI Impacts:**
- waste_rate: Reduce from 12% to <5%
- forecast_accuracy: Achieve >85% next-day accuracy
- planning_time: Reduce owner planning time by 70%

**Critical Questions:**
- Can POS systems be upgraded to capture product-level sales?
- How much historical sales data exists in any form?
- What external data sources are available (weather, local events)?
- Is the owner willing to trust system recommendations?
- What is the value of reduced waste vs cost of stockout?
- How variable is demand by day-of-week, season, weather?
- Which product categories have most predictable vs volatile demand?

**Expected Challenges:**
- No digital sales data foundation - need to start data collection
- Change management - transitioning from intuition to data-driven
- Cold start problem - building accurate forecasts without history
- Integration with manual production processes

**Realistic First Step:** Deploy simple POS with product tracking for 3 months to establish baseline data

---

### Persona 5: mfg_05_precision_design (Feinmechanik Weber GmbH)

**Focus Idea:** AI-assisted generative design for part optimization

**Expected Value Level:** Project Acceleration + Strategic Scaling

**Expected KPI Impacts:**
- design_cycle_time: Reduce from 14 to 8 weeks
- engineer_capacity: Increase throughput by 40%
- material_efficiency: Improve by 15-25% on redesigned parts

**Critical Questions:**
- What percentage of new designs are variants vs truly novel geometries?
- Are manufacturing constraints well-documented for generative tools?
- Do engineers have capacity to learn new tools given current overload?
- Which customers would pay premium for topology-optimized parts?

**Expected Challenges:**
- Learning curve for generative design tools
- Manufacturability validation of generative outputs
- Integration with existing SolidWorks workflow
- Identifying suitable projects for generative approach

**Realistic First Step:** Select 2-3 existing parts with weight/performance requirements for generative redesign proof-of-concept

---

## Workflow Summary

1. **Run the consultation** for a persona using the e2e workflow test
2. **Export the PDF** from the session
3. **Upload to Gemini** (AI Studio or web)
4. **Paste the evaluation prompt** with the relevant persona's ground truth
5. **Collect the JSON response** and save for analysis
6. **Repeat** for each persona/model combination
