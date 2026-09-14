# Intake Triage — AIVC Technical Case Study

AI-assisted triage for inbound professional-services enquiries.

A fictional consultancy, **Meridian Advisory**, receives an enquiry with four inputs: description, industry, company size, and urgency. AI interprets the requested work and its complexity; ordinary company workflow rules then assign the enquiry to the appropriate practice lead or send it to human review.

**Start with the [two-page case study](CASE_STUDY.pdf).** For the exact methodology, see [EVALUATION.md](EVALUATION.md); for the business and system contract, see [SPEC.md](SPEC.md).

## First-pass result

The first classifier implementation was run once against a 30-case synthetic benchmark designed before classifier implementation and deliberately weighted toward difficult routing and review cases.

| Metric | First run |
| --- | ---: |
| Automatically routed | **27 / 30 (90.0%)** |
| Correct automatic routes | **24 / 27 (88.9%)** |
| Unsafe automatic routes | **3 / 30 (10.0%)** |
| Review cases caught | **3 / 6 (50.0%)** |
| Unnecessary reviews | **0 / 24 (0.0%)** |
| Primary service lines correct¹ | **25 / 25 (100%)** |
| Complexity labels correct² | **26 / 28 (92.9%)** |

¹ Cases with an intended primary service line.  
² Cases where complexity was inferable in the answer key.

The main weakness was not understanding the requested work; it was recognizing when the available information was unsafe to act on. On this evidence, I would start in **shadow mode** rather than turn on autonomous production routing.

The preserved first run is committed at [`eval/results/initial.json`](eval/results/initial.json). Live model calls are stochastic and may differ from that historical run.

## What the system does

```text
client enquiry
    │
    ▼
AI assessment
service line · complexity · disposition · review reasons
    │
    ▼
Meridian workflow rules
practice ownership · seniority · urgency / response target
    ├──────────────► practice lead
    └──────────────► Central Intake Review
```

Meridian is a fictional six-practice consultancy:

- Strategy & Transformation
- Operations & Process
- Data & AI
- Technology & Systems
- Risk & Compliance
- Finance & Transactions

The AI decides what kind of work the enquiry represents. Routing is ordinary, configurable business logic. For example, complex work and enterprise accounts route to a practice's senior lead; ambiguous, insufficient-information, out-of-scope, or operationally failed cases go to human review.

The assumptions are kept separate by reason for change:

```text
config/firm.yaml       submitted fields and firm context
config/taxonomy.yaml   practice scope, boundaries, complexity guidance
config/routing.yaml    leads, escalation, review queue, urgency / SLA
config/economics.yaml  manual baseline and cost sensitivity
config/models.yaml     model and reasoning settings
```

## Inspect it without an API key

Python 3.13 and [`uv`](https://docs.astral.sh/uv/) are used for the prototype.

```sh
uv sync --locked
uv run python -m meridian.validate_data
uv run python -m unittest discover -s tests -v
```

These commands validate the frozen benchmark/configuration and run the offline test suite. No OpenAI API key is required.

You can also start the local site without a key and inspect the fictional firm and preserved evaluation:

```sh
uv run python -m meridian.workbench
```

Then open `http://127.0.0.1:8000`.

Useful pages:

- `/` — Meridian Advisory homepage, practices, and people derived from configuration
- `/evaluation` — read-only explorer for the preserved first run
- `/workbench` — live intake workbench; benchmark cases can also be inspected here

Browsing and the frozen evaluation are read-only. Interactive enquiries and results are not persisted.

## Run a live enquiry

Live triage and fictional-example generation require `OPENAI_API_KEY`. Export it or place it in an ignored `.env` file at the project root:

```sh
export OPENAI_API_KEY=...
uv run python -m meridian.workbench
```

Or call the triage CLI directly:

```sh
uv run python -m meridian.triage \
  --industry retail \
  --company-size small \
  --urgency normal \
  --description "We need a dashboard showing agreed sales metrics from our existing reporting table."
```

The command returns the AI assessment, routing decision, and basic call metadata as JSON.

## Reproduce the benchmark

The committed first run is evidence and is never overwritten. To run the same frozen inputs again, choose a new output path:

```sh
uv run python -m meridian.evaluate \
  --output eval/results/reproduction.json
```

This requires an API key and will make 30 model calls. Because the classifier is stochastic, a reproduction need not match `initial.json` case-for-case.

The preserved first run used `gpt-5.6-terra` at low reasoning effort. All 30 calls completed without operational fallback; mean call latency was **1.74 s**, with **74,907 input tokens / 2,109 output tokens** observed across the run.

## How the benchmark was built

The benchmark is synthetic, small, and intentionally difficult. It is designed to probe routing behavior, not estimate the frequency of different cases in production.

| Case type | Count | Purpose |
| --- | ---: | --- |
| Routine | 18 | Simple, moderate, and complex work across all six practices |
| Hard but routeable | 6 | Overlapping vocabulary with one defensible primary owner |
| Ambiguous | 3 | More than one plausible primary owner; review expected |
| Insufficient / contradictory | 2 | Missing or conflicting routing-relevant information |
| Out of scope | 1 | Understood request that Meridian does not offer |

For each case, the underlying client scenario and intended answer were authored first. A separate `gpt-5.6-luna` call generated realistic client-facing wording without seeing the intended classification or rationale. That wording was reviewed for fidelity before the benchmark was frozen.

The set deliberately includes shortcuts that should fail: large-but-simple work, small-but-complex work, regulated-but-simple work, AI used inside a non-AI engagement, cross-practice ownership, and conflicting structured/free-text information.

See [EVALUATION.md](EVALUATION.md) for the scoring contract and economic model.

## What failed

The five scored mismatches in the first run split into two operationally different groups.

### Unsafe automatic routes

- **A01 — claims modernization:** the system chose Strategy & Transformation for a multi-practice program that the benchmark expected to send to review.
- **A02 — post-acquisition integration:** the system chose Finance & Transactions for an integrated operating-model / ERP / finance program that the benchmark expected to send to review.
- **I02 — conflicting company size:** the system correctly identified Technology & Systems and moderate complexity, but missed that `1–99 employees` in the form contradicted prose describing a roughly 15,000-person enterprise. Since company size changes which lead receives moderate work, the safe action was review.

A01 and A02 also surface a real organizational question: a production implementation should learn from the actual firm who owns integrated cross-practice programs rather than silently invent that policy.

### Semantic mismatches without routing impact

- **H02:** complexity was predicted `complex` instead of `moderate`; the enterprise account routed to the same senior Operations lead either way.
- **A03:** the system correctly recognized ambiguity and sent the enquiry to review, but left complexity unset where the benchmark expected `complex`.

The evaluation explorer at `/evaluation` makes these distinctions visible case by case.

## Economics and production posture

At the midpoint of the brief's volume, eight analyst-hours over 50 enquiries implies **9.6 analyst-minutes per enquiry**.

The evaluator treats the benchmark as a sensitivity exercise rather than a production ROI estimate. If one human review costs one original manual triage, the preserved first run gives:

| Assumed cost of a wrong automatic route | Modeled system cost vs. manual |
| --- | ---: |
| 1× manual triage | 20% |
| 3× manual triage | 40% |
| 10× manual triage | 110% |

The simplified break-even misroute penalty is **9×** one manual triage. Real economics require observed production case mix, actual review time, downstream cost of reassignment, model cost, and ideally response-time / conversion outcomes.

I would initially run the system beside the existing analyst process and record:

- AI route vs. analyst route;
- analyst override and final accepting team;
- later reassignment;
- review rate and automation coverage;
- routing-relevant metadata conflicts;
- latency and API/schema failures;
- response time and, where available, downstream lead outcomes.

Automation can then expand only for kinds of cases whose observed error rate and downstream cost are acceptable. API failures, invalid structured output, ambiguity, insufficient information, and unsupported work fall back to the existing intake queue.

## Repository map

```text
CASE_STUDY.pdf          two-page case-study summary
README.md               technical front door and run instructions
EVALUATION.md           benchmark, scoring, and economic methodology
SPEC.md                 Meridian and system contract
config/                 firm, taxonomy, routing, economics, model settings
eval/latent_cases.yaml  authored scenarios and answer keys
eval/cases.yaml         rendered frozen benchmark
eval/results/initial.json
                        preserved first classifier run
src/meridian/           classifier, router, evaluator, API, and local site
tests/                  offline invariants and behavior tests
```
