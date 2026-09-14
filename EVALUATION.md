# Evaluation methodology

This document defines what the synthetic benchmark tests, how its answers were established, how results are scored, and how to interpret the preserved first run.

The central deployment question is:

> **When is an enquiry safe to route automatically, and when should the system hand it to a human?**

The benchmark is deliberately stress-weighted toward boundaries and review cases. It is useful for comparing system behavior against known scenarios; it is **not** an estimate of Meridian's production case mix or production reliability.

## Preserved first run

The first classifier implementation was run once against the frozen 30-case benchmark before any tuning against its results.

| Metric | First run |
| --- | ---: |
| Automation coverage | **27 / 30 (90.0%)** |
| Selective route accuracy | **24 / 27 (88.9%)** |
| Unsafe automation rate | **3 / 30 (10.0%)** |
| Review recall | **3 / 6 (50.0%)** |
| Unnecessary review rate | **0 / 24 (0.0%)** |
| Service-line accuracy | **25 / 25 (100%)** |
| Complexity accuracy | **26 / 28 (92.9%)** |

The result is preserved at [`eval/results/initial.json`](eval/results/initial.json), including case-level predictions, expected semantics and routes, model metadata, timing/token usage, and provenance hashes.

The important pattern is that the system understood the requested work well but was too willing to route several cases that should have gone to review.

## Benchmark construction

The benchmark starts from authored client scenarios rather than from classifier output.

For each case:

1. Define the underlying client situation, form metadata, requested outcome, and intended semantic answer.
2. Give only the client situation and rendering guidance to a separate synthetic-writing model.
3. Generate realistic client-facing enquiry text without exposing the intended classification, rationale, or route.
4. Review the rendered wording once for fidelity to the authored scenario.
5. Freeze the resulting form input before classifier implementation/evaluation.

The synthetic renderer is configured separately from the classifier (`gpt-5.6-luna`, low reasoning effort in the submitted configuration). The classifier uses `gpt-5.6-terra` at low reasoning effort. Model IDs are configuration rather than benchmark semantics.

Two files preserve the construction:

- `eval/latent_cases.yaml` — authored scenario definitions, generation guidance, intended semantics, and rationale;
- `eval/cases.yaml` — the rendered, frozen enquiries used by the evaluator.

This separation prevents the classifier from defining its own test and prevents the renderer from generating prose toward the desired label.

## Benchmark composition

The 30 cases intentionally overrepresent situations that are likely to expose shortcut behavior.

| Cohort | Count | What it tests |
| --- | ---: | --- |
| Routine | 18 | One simple, moderate, and complex case for each of six service lines |
| Hard but routeable | 6 | Adjacent-practice vocabulary with one defensible primary owner |
| Ambiguous | 3 | Multiple plausible primary owners; human review expected |
| Insufficient / contradictory | 2 | Missing or conflicting routing-relevant information |
| Out of scope | 1 | Request is understood but not offered by Meridian |

The set includes, among other things:

- large-company work that is still simple;
- small-company work that is genuinely complex;
- regulated work that is still simple;
- urgent work whose urgency does not change complexity;
- an AI-enabled engagement owned by Operations rather than Data & AI;
- a systems request inside transaction diligence;
- cross-practice programs with no defensible single owner;
- conflicting company-size information between the form and free text;
- clearly unsupported creative/marketing work.

The purpose is not realism of frequency. The purpose is to make obvious heuristics fail.

## Expected semantic answer

The evaluator distinguishes the semantic assessment from the organizational routing decision.

The authored semantic fields are:

- `service_line` — primary Meridian practice where one is defensible;
- `complexity` — `simple`, `moderate`, or `complex` where inferable;
- `disposition` — whether the enquiry is safe to route automatically;
- `alternative_service_lines` — plausible alternatives for ambiguous cases;
- `review_reasons` — why human review is required.

Expected final routing is derived from those semantics plus the current `config/routing.yaml`; it is not hard-coded separately into the case answer key. That allows organizational ownership rules to change without rewriting what the enquiry means.

## Dispositions

| Disposition | Meaning | Routing behavior |
| --- | --- | --- |
| `clear` | One defensible primary practice and enough information to estimate complexity | Eligible for automatic routing |
| `ambiguous` | Two or more practices are genuinely plausible primary owners | Human review |
| `insufficient_information` | Missing or contradictory information makes automatic routing unsafe | Human review |
| `out_of_scope` | The request is understood but Meridian does not offer the work | Human review |

The last three all route to review in this prototype, but they remain distinct because a real intake process would follow up differently in each case.

A review disposition does not erase conclusions that remain supported. I02, for example, can still be Technology & Systems and moderate even though contradictory company-size information makes the final lead assignment unsafe.

## Validated output invariants

These relationships are enforced in code after structured model output:

| Disposition | Required state |
| --- | --- |
| `clear` | `service_line` and `complexity` are present |
| `ambiguous` | no primary `service_line`; at least two alternatives; review reason present |
| `insufficient_information` | review reason present; supported partial semantics may remain |
| `out_of_scope` | no primary `service_line`; scope/review reason present |

API errors, refusals, incomplete/invalid structured output, and other runtime failures are operational fallbacks to human review. They are not semantic dispositions the model is asked to invent.

## Headline metrics

The benchmark emphasizes selective automation rather than a single accuracy number. Routing nothing is safe but useless; routing everything can be efficient but unsafe.

### Automation coverage

```text
automatic routes / all cases
```

How much of the manual triage step the system attempts to replace.

### Selective route accuracy

```text
correct automatic routes / automatic routes
```

An automatic route is correct only if:

1. the case is expected to be safe to automate; and
2. the resulting lead matches the lead mechanically implied by the authored semantics plus the current routing policy.

Automatically routing a case that should be reviewed is therefore incorrect even when the selected practice is individually plausible.

### Unsafe automation rate

```text
incorrect automatic routes / all cases
```

Makes over-automation visible rather than hiding it inside overall accuracy.

### Review recall

```text
correctly reviewed cases / cases expected to require review
```

Measures whether the system catches cases where automatic routing is unsafe.

### Unnecessary review rate

```text
clear cases sent to review / clear cases
```

Measures whether review recall is being purchased simply by sending ordinary routeable work back to humans.

### Service-line accuracy

```text
correct primary service line / cases with an authored primary service line
```

Cases intentionally authored without a primary owner are excluded. Review cases remain in the denominator when a primary practice is still inferable.

### Complexity accuracy

```text
correct complexity / cases with an authored complexity label
```

Cases where complexity cannot reasonably be inferred are excluded.

Any metric with a zero denominator is reported as `n/a`.

## What is not auto-scored

`summary`, `review_reasons`, and `alternative_service_lines` are structured and inspected qualitatively, but the prototype does not ask another language model to invent a numeric quality score for them.

The directly observable operational decision is more important: did the system route a case that should have been routed, send an unsafe case to review, and choose the correct destination when it acted?

## Interpreting the first run

Five cases contain scored semantic or routing mismatches, but they are not equally serious.

### Unsafe automatic routes

- **A01 — claims modernization:** expected review because no single practice was established as the clear owner; the system automatically selected Strategy & Transformation.
- **A02 — post-acquisition integration:** expected review for an integrated program spanning operating model, ERP, finance integration, and synergy capture; the system automatically selected Finance & Transactions.
- **I02 — conflicting company size:** Technology & Systems and moderate complexity were correctly inferred, but the system failed to treat the contradiction between a `1–99 employees` form value and prose describing roughly 15,000 employees as routing-relevant. The two sizes select different leads.

A01 and A02 expose both model behavior and an organizational-policy question: in a real implementation, ownership of integrated cross-practice programs should be learned from the firm rather than inferred from the synthetic taxonomy.

I02 is the cleaner automation-boundary failure: the work was understood, but conflicting evidence should have forced review before the workflow acted on it.

### Semantic mismatches without a wrong route

- **H02:** expected `moderate`, predicted `complex`; both map to the same senior Operations lead because the client is enterprise-sized.
- **A03:** ambiguity/review was correctly identified, but complexity was left unset where the answer key expected `complex`.

These matter for semantic quality without creating the same downstream risk as an unsafe automatic assignment.

## Economic sensitivity

The brief supplies a useful manual baseline: 40–60 enquiries per week consume about eight analyst-hours. At the midpoint of 50 enquiries:

```text
m = 8 * 60 / 50 = 9.6 analyst-minutes per enquiry
```

Let:

- `N` = evaluated cases;
- `R` = cases sent to human review;
- `W` = incorrectly auto-routed cases;
- `r` = review cost as a multiple of one manual triage (default `1.0`);
- `k` = downstream cost of a wrong automatic route, also expressed as a multiple of manual triage.

The simple sensitivity model is:

```text
manual_cost = N * m
system_cost = (R * r * m) + (W * k * m)
estimated_savings = manual_cost - system_cost
```

Normalized by the manual baseline:

```text
system_cost / manual_cost = (R*r + W*k) / N
```

When `W > 0`, the break-even wrong-route multiple is:

```text
k* = (N - R*r) / W
```

For the preserved first run (`N=30`, `R=3`, `W=3`, `r=1`):

| Assumed wrong-route cost | Modeled system cost vs. manual |
| --- | ---: |
| 1× manual triage | 20% |
| 3× manual triage | 40% |
| 10× manual triage | 110% |

The break-even value is **9×** one manual triage.

This is **sensitivity analysis, not a production ROI forecast**. The benchmark deliberately oversamples hard/review cases, and the cost multiple is an assumption. Production economics require observed case mix, actual review time, inference cost, downstream reassignment cost, and ideally response-time and conversion outcomes.

## Reproduction and provenance

The committed historical result is never overwritten. To run the frozen inputs again:

```sh
uv run python -m meridian.evaluate \
  --output eval/results/reproduction.json
```

The evaluator builds model requests from the four submitted intake fields and configuration; benchmark labels/rationales are not included in classifier input. Predictions are written before scoring against expected semantics.

The preserved run used `gpt-5.6-terra` with low reasoning effort. All 30 calls completed without operational fallback. Observed totals were **74,907 input tokens**, **2,109 output tokens**, **1.74 s mean call latency**, and **2.585 s maximum call latency**.

A new run may differ because model outputs are stochastic. `eval/results/initial.json` is the submitted historical evidence; a reproduction is a new experiment, not a replacement for it.
