# Meridian v0 specification

This document records the assumptions and system contract behind the intake-triage
prototype. The fictional firm exists because the exercise intentionally omits the
business taxonomy and routing policy that would normally be learned from the client.
Those assumptions are configuration, not hidden prompt lore.

## 1. Problem

Meridian Advisory receives an inbound enquiry with four submitted fields:

- free-text description,
- industry,
- company size,
- urgency.

The existing manual step assigns a service line, estimates engagement complexity
(simple / moderate / complex), and routes the enquiry to a team lead. The prototype
replaces that triage step where it can do so safely and explicitly abstains where it
cannot.

The brief gives a volume of 40–60 enquiries per week and roughly eight analyst-hours
of manual triage. At a midpoint of 50 enquiries/week, that implies 9.6 analyst-minutes
per enquiry. That number is useful as an operating baseline, not as proof that labor
savings are the only or largest source of business value.

## 2. Design thesis

This is intentionally **not an agentic workflow**.

```text
validated intake
    -> one structured semantic assessment
    -> validated assessment
    -> deterministic routing policy
    -> team lead or human review
```

The model answers **what is this enquiry?** Ordinary code answers **what should
Meridian do with an enquiry like this?**

That separation is useful only because it is observable:

- changing taxonomy / scope can change classification;
- changing team ownership can reroute an unchanged saved assessment without a model call;
- changing economic assumptions can change the reported value without changing either.

The implementation should remain small enough that these boundaries are obvious.

## 3. Meridian operating model

The formal configuration is split by reason-for-change:

- `config/firm.yaml` — firm identity, submitted fields, company-size bands, and metadata semantics;
- `config/taxonomy.yaml` — service-line scope, boundaries, eligibility, and global + practice-specific complexity guidance;
- `config/routing.yaml` — lead ownership, escalation, review queue, and urgency/SLA policy;
- `config/economics.yaml` — manual baseline and sensitivity assumptions used by evaluation.

### Service lines

Meridian is a fictional generalist consultancy with six practices:

| Service line | Primary ownership boundary |
| --- | --- |
| Strategy & Transformation | Growth, operating models, transformation roadmaps, organizational change; deciding what/how to transform. |
| Operations & Process | Workflow redesign, service operations, supply chain, operational efficiency; the business process is primary. |
| Data & AI | Analytics, AI/ML, data strategy/governance/platforms; data or model capability is primary. |
| Technology & Systems | ERP/CRM, cloud, integrations, migrations, applications; software/system delivery is primary. |
| Risk & Compliance | Cybersecurity, privacy, controls, regulatory readiness, risk governance; assurance/control outcome is primary. |
| Finance & Transactions | FP&A, financial modeling, diligence, valuation, transaction support; finance/transaction outcome is primary. |

These practices intentionally overlap. Ownership follows the client's **requested
outcome**, not keywords. AI can be a means inside an Operations engagement; an ERP
can be used by Finance without making Finance the implementation owner; AI governance
can primarily be a Risk engagement.

### Complexity

The global rubric is:

- **Simple** — bounded, well-defined work with about one deliverable/workstream and few dependencies.
- **Moderate** — meaningful discovery/customization or coordination across stakeholders, workflows, data sources, or systems while remaining reasonably bounded.
- **Complex** — enterprise/multi-unit scope, several major systems/workstreams, substantial organizational change, material regulatory exposure, significant requirements ambiguity, transaction/integration programs, or dependencies across several functions.

Each service line also supplies domain-specific complexity evidence. For example,
Technology treats global multi-system migration as complex; Risk treats multi-
jurisdiction remediation as complex. These are model guidance, not a second hidden
rules engine.

Company size is evidence, not a complexity label. Urgency is not complexity. A
regulated industry is not automatically complex.

Cross-practice work has two distinct interpretations:

- if one practice clearly owns the outcome, other-practice dependencies may increase complexity;
- if multiple practices are equally plausible primary owners, the disposition is `ambiguous` and the system abstains.

Eligibility / out-of-scope policy is separate from complexity. A future rule such as
"this practice does not serve industry X" should change scope, not pretend that
industry X is unusually complex.

## 4. Semantic assessment contract

The model returns one structured object with these semantic fields:

- `summary` — concise enrichment grounded in submitted information;
- `service_line` — configured service-line identifier or null;
- `complexity` — `simple`, `moderate`, `complex`, or null;
- `disposition` — `clear`, `ambiguous`, `insufficient_information`, or `out_of_scope`;
- `alternative_service_lines` — plausible alternatives where useful;
- `review_reasons` — explicit reasons an enquiry should not be auto-routed.

There is deliberately **no model-generated numeric confidence**. The system measures
whether the model's claim that an enquiry is safe to route is actually reliable.

### Disposition invariants

- `clear` requires a primary service line and complexity.
- `ambiguous` has no primary line, at least two plausible alternatives, and a review reason.
- `insufficient_information` requires a review reason but may retain partial semantic conclusions that remain supported.
- `out_of_scope` has no primary line and an explicit scope reason.

Schema/API/model failures are operational fallbacks to human review rather than
semantic dispositions.

A useful edge case is contradictory metadata: a one-business-unit CRM migration
with two ordinary integrations can remain moderate even at an enterprise-sized
company. If the submitted size is small but prose states about 15,000 employees,
Technology + moderate remain inferable while small would select the default lead
and enterprise the senior lead. The assessment should preserve those semantics
while abstaining until the routing-relevant company-size contradiction is resolved.

## 5. Routing contract

Routing is ordinary deterministic code consuming the validated assessment and
`config/routing.yaml`.

Baseline policy:

1. Any review disposition goes to the central human-review queue.
2. Otherwise, complex work goes to the service line's senior lead.
3. Otherwise, enterprise accounts go to the service line's senior lead.
4. Other clear work goes to the default lead.
5. Urgency changes priority / target response time, never semantic ownership.

Expected route is **not** hard-coded into benchmark answer keys. It is derived from
the frozen expected semantic assessment plus the current routing config. This lets
organizational policy change without invalidating the semantic benchmark.

## 6. Evaluation contract

`EVALUATION.md` defines the scoring semantics. `eval/latent_cases.yaml` freezes the
30 latent cases and answer keys before classifier implementation.

The benchmark is deliberately stress-weighted:

| Cohort | Count |
| --- | ---: |
| Straightforward: one simple/moderate/complex case per practice | 18 |
| Hard but routeable practice-boundary cases | 6 |
| Genuinely ambiguous | 3 |
| Insufficient / contradictory | 2 |
| Out of scope | 1 |

Natural-language descriptions are generated from **form + latent seed only**. The
renderer never sees expected labels or rationale. Generated wording is reviewed for
fidelity and then frozen before classifier tuning.

Headline evaluation emphasizes selective automation:

- automation coverage,
- selective route accuracy,
- unsafe automation rate,
- review recall,
- unnecessary review rate,
- service-line accuracy,
- complexity accuracy.

Summary prose, review reasons, and alternative lines are schema-validated and
inspected qualitatively rather than scored by a second LLM pretending to be a ruler.

### Economic sensitivity

The stress-weighted benchmark must not be mistaken for a production case-frequency
sample. Economics are therefore a separate configurable sensitivity calculation.

For `N` cases, `R` human reviews, `W` wrong automatic routes, manual minutes `m`,
review multiple `r`, and misroute multiple `k`:

```text
manual_cost = N * m
system_cost = (R * r * m) + (W * k * m)
```

The evaluator reports several `k` assumptions and, when possible, the break-even
misroute penalty. It explicitly does **not** call this production ROI. Real ROI would
need observed case mix, review time, API cost, downstream misroute cost, and ideally
response-time / conversion outcomes.

## 7. Model/runtime choice

The runtime classifier should use the ordinary OpenAI Responses API with Structured
Outputs validated into Pydantic models. The model ID and reasoning effort are
configuration, not business logic. Requests should be stateless for this use case;
no conversation/thread is required, and response storage should be disabled where
supported.

Do **not** use Codex SDK as the production inference harness. Codex SDK is designed to
control local coding agents; using an agent runtime for one structured semantic
classification would add lifecycle/state/filesystem machinery that this problem does
not need and would weaken the design thesis above.

Likewise, an additional agent framework such as PydanticAI is optional rather than
necessary. The default implementation should prefer the official OpenAI SDK +
Pydantic because the problem needs one structured call, not orchestration. Add an
abstraction only if it earns its place through observed requirements.

The API credential is supplied through the environment and never committed.
API-backed commands and the local workbench load the selected project root’s
ignored `.env` file at startup, preserving any already-exported environment values.

## 8. Build sequence

1. **Done:** define evaluation semantics and latent answer key before classifier work.
2. Render realistic enquiry descriptions from latent facts without exposing answer keys.
3. Review/freeze rendered cases; validate schemas and case counts.
4. Implement input models, semantic classifier, output invariants, and deterministic router.
5. Run the frozen benchmark and preserve raw results.
6. Inspect errors and make only evidence-driven classifier/prompt changes.
7. Add evaluator-facing result tables, error analysis, architecture/fallback notes, and reproducible run commands to README.
8. Optional only after the core deliverable is sound: tiny presentation/demo surface.

## 9. Explicit non-goals for v0

No agent framework, vector database, RAG system, workflow engine, live CRM write,
production queue, elaborate synthetic-data factory, or browser UI is on the critical
path. A small CLI is sufficient.

A later demo may expose the formal configuration visually — even via a tiny fictional
Meridian site — but presentation must remain downstream of the functioning,
reproducible classifier/evaluator.

## 10. Local inspection workbench

The Phase 3 demo is one localhost-only page backed by the existing triage and
scoring functions. It supports the four submitted fields, read-only frozen-case
browsing, explicit live triage, and a collapsed post-run benchmark comparison.
Editing a loaded case makes it ad-hoc and removes comparison eligibility. Expected
routes continue to be derived mechanically from frozen semantics and routing policy.

An independent ephemeral generator uses the configured synthetic-rendering model
and company-size / urgency choices to populate the form from a scenario idea. It
receives no benchmark data, taxonomy, routing leads, classifier output, or evaluation
results. Generation never creates an answer key or automatically runs triage.

The workbench has no persistence, authentication, or frontend build system. It does
not change classifier instructions, model settings, business configuration, frozen
cases, or evaluation evidence. Its optional frozen metric summary is read-only;
live results are distinguished from the initial untuned evaluation.
