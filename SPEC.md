# Meridian intake-triage system specification

This document defines the fictional business assumptions and the implemented system contract behind the prototype. It is the detailed companion to the [two-page case study](CASE_STUDY.pdf); evaluation methodology lives in [EVALUATION.md](EVALUATION.md).

## 1. Purpose

Meridian Advisory receives inbound enquiries containing four submitted fields:

- free-text description;
- industry;
- company size;
- urgency.

The existing manual step identifies the kind of work requested, estimates engagement complexity, and routes the enquiry to a team lead. The prototype automates that step where the submitted information supports a safe decision and otherwise routes the case to human review.

At the brief's midpoint volume, 50 enquiries/week and eight analyst-hours imply **9.6 analyst-minutes per enquiry**. That is an operating baseline, not an assumption that labor savings are the only source of value; response speed, routing quality, enrichment, and downstream conversion may matter more in production.

## 2. System boundary

The implemented flow is intentionally small:

```text
submitted enquiry
    │
    ▼
AI assessment
summary · service line · complexity · disposition · review evidence
    │
    ▼
validated assessment
    │
    ▼
Meridian routing policy
practice ownership · seniority · urgency / response target
    ├──────────────► practice lead
    └──────────────► Central Intake Review
```

The AI interprets the enquiry. Ordinary code applies organizational workflow rules.

That separation keeps business changes explicit:

- practice scope and complexity guidance live in the taxonomy configuration;
- lead ownership and escalation live in routing configuration;
- economic assumptions live in evaluation configuration;
- model selection lives in model configuration.

Changing a person's routing assignment does not require reinterpreting the enquiry. Changing economic assumptions does not change classification or routing.

## 3. Meridian Advisory

Meridian is a fictional generalist professional-services firm created to make the assignment's organizational decisions concrete.

### Practices

| Practice | Primary ownership boundary |
| --- | --- |
| **Strategy & Transformation** | Growth and market strategy, operating models, transformation roadmaps, organizational change; deciding what or how the organization should transform |
| **Operations & Process** | Workflow redesign, service operations, supply chain, operational efficiency; the business process is the primary object of change |
| **Data & AI** | Analytics, AI/ML systems, data strategy/governance/platforms; data or model capability is the primary deliverable |
| **Technology & Systems** | ERP/CRM, applications, cloud/infrastructure, integrations and migrations; software/system delivery is primary |
| **Risk & Compliance** | Cybersecurity, privacy, controls, regulatory readiness and risk governance; assurance/control outcome is primary |
| **Finance & Transactions** | FP&A, financial modeling, diligence, valuation and transaction support; finance/transaction outcome is primary |

The practices intentionally overlap. Ownership follows the client's requested outcome rather than keywords.

Examples:

- an AI extraction component inside a claims-process redesign can still be Operations & Process;
- a predictive-maintenance model can be Data & AI even though Operations later consumes its predictions;
- an ERP appearing in diligence does not make Finance & Transactions the implementation owner;
- AI governance can primarily be Risk & Compliance when the requested outcome is governance, controls and regulatory readiness.

### Practice leadership

Each practice has a default practice lead and a senior practice lead. The submitted `config/routing.yaml` is the source of truth for names and routing behavior.

## 4. Company size and urgency

Company size is submitted as a structured field and participates in routing policy. It is **evidence, not a complexity label**. A large firm can have a bounded simple engagement; a small firm can have a complex multi-system program.

Urgency affects priority and target response time. It does not change service ownership or engagement complexity.

Structured metadata is treated as submitted evidence rather than automatically trusted ground truth. If free text contradicts routing-relevant metadata, the semantic contract permits an `insufficient_information` disposition while retaining other conclusions that remain supported.

## 5. Complexity

The global complexity rubric is:

- **Simple** — bounded, well-defined work with roughly one deliverable/workstream and few dependencies.
- **Moderate** — meaningful discovery, customization, or coordination across stakeholders, workflows, data sources, or systems while remaining reasonably bounded.
- **Complex** — enterprise/multi-unit scope, multiple major systems/workstreams, substantial organizational change, material regulatory exposure, significant requirements ambiguity, transaction/integration programs, or dependencies across several functions.

Each practice also contributes domain-specific complexity evidence in `config/taxonomy.yaml`. For example, global multi-system migration is a Technology complexity signal; multi-jurisdiction remediation is a Risk complexity signal.

Cross-practice work has two distinct cases:

1. **One clear primary owner.** Other-practice dependencies can increase complexity without making ownership ambiguous.
2. **No defensible primary owner.** The assessment is `ambiguous` and the system sends the enquiry to review.

Eligibility is separate from complexity. Unsupported work is `out_of_scope`; it is not made artificially complex.

## 6. AI assessment contract

The classifier returns one structured `TriageAssessment` with:

- `summary` — concise description of the requested work grounded in the submission;
- `service_line` — configured practice identifier or null;
- `complexity` — `simple`, `moderate`, `complex`, or null;
- `disposition` — `clear`, `ambiguous`, `insufficient_information`, or `out_of_scope`;
- `alternative_service_lines` — plausible alternatives where useful;
- `review_reasons` — explicit reasons not to route automatically.

There is no model-generated numeric confidence score. The operational claim is discrete and testable: the model either says the case is clear enough to route or it does not. Evaluation then measures whether those automatic decisions are actually safe.

### Disposition semantics

| Disposition | Contract |
| --- | --- |
| `clear` | One primary `service_line` and a `complexity` are present; eligible for automatic routing |
| `ambiguous` | No primary service line; at least two plausible alternatives; review reason present |
| `insufficient_information` | Review reason present; supported partial semantics may remain |
| `out_of_scope` | No primary service line; explicit scope/review reason present |

The structured output is validated in ordinary code after the model call.

A review case may retain useful semantics. In benchmark case I02, for example, Technology & Systems and moderate complexity remain inferable while contradictory company-size evidence makes the final lead assignment unsafe.

## 7. Routing contract

Routing consumes the validated assessment plus submitted company size/urgency and `config/routing.yaml`.

Baseline policy:

1. Any semantic review disposition goes to `Central Intake Review`.
2. Otherwise, complex work goes to the practice's senior lead.
3. Otherwise, an enterprise account goes to the practice's senior lead.
4. Other clear work goes to the default practice lead.
5. Urgency changes priority and target response time, never semantic ownership.

The rule that fired is returned with the routing result for inspection.

Expected benchmark routes are derived from expected semantics plus the current routing configuration rather than duplicated as fixed answers. This keeps semantic evaluation stable when organizational ownership changes.

## 8. Operational failure behavior

Runtime/model failures are separate from semantic dispositions.

The following conditions fall back to human review rather than inventing a semantic answer:

- missing API configuration;
- timeout or connection error;
- API status error;
- refusal;
- incomplete response;
- missing structured output;
- structured output that violates semantic invariants;
- SDK/client failure.

The fallback destination is the existing human intake path. A failure therefore degrades to the workflow being automated rather than producing an unsupported route.

Client text is treated as data to classify. A client's request to be “routed directly to the managing partner,” for example, does not override Meridian's routing policy.

## 9. Runtime and model configuration

The classifier uses the OpenAI Responses API and Pydantic-validated structured output.

Submitted defaults in `config/models.yaml`:

```yaml
classification:
  model: gpt-5.6-terra
  reasoning_effort: low

synthetic_rendering:
  model: gpt-5.6-luna
  reasoning_effort: low
```

Requests are stateless for this workflow and response storage is disabled in configuration.

The synthetic renderer is intentionally separate from classification. Its task is only to turn already-authored fictional client scenarios into realistic enquiry wording; it does not receive benchmark answer keys, rationales, taxonomy, routing leads, or classifier output.

API credentials are supplied through the environment and are never committed. API-backed entry points load an ignored project-root `.env` when present while preserving already-exported environment values.

## 10. Configuration

The formal business/model configuration is split by reason for change:

```text
config/firm.yaml       firm identity, submitted fields, company-size bands, metadata semantics
config/taxonomy.yaml   practice ownership boundaries, eligibility, global/domain complexity guidance
config/routing.yaml    default/senior leads, escalation, review queue, urgency / SLA
config/economics.yaml  manual baseline and misroute-cost sensitivity assumptions
config/models.yaml     provider, model IDs, reasoning effort, response-storage setting
```

The website's firm/practice/people presentation is derived from this configuration rather than maintaining a second independent representation of Meridian.

## 11. Evaluation relationship

The classifier is evaluated against 30 synthetic enquiries whose underlying scenarios and intended answers were defined before classifier implementation.

The benchmark deliberately includes routine work, hard but routeable boundaries, genuine ambiguity, insufficient/contradictory information, and out-of-scope work. A separate renderer generated realistic free text without seeing the intended answers.

Headline metrics distinguish useful automation from unsafe over-automation:

- automation coverage;
- selective route accuracy;
- unsafe automation rate;
- review recall;
- unnecessary review rate;
- service-line accuracy;
- complexity accuracy.

`EVALUATION.md` is the source of truth for exact denominators, first-run interpretation, and economic sensitivity. `eval/results/initial.json` preserves the submitted historical run.

## 12. Inspection surfaces

### CLI

`python -m meridian.triage` runs one live enquiry and returns the assessment, route, and call metadata as JSON.

`python -m meridian.evaluate` runs the frozen benchmark and writes a new result artifact; it does not overwrite the preserved first run.

### Local site

`python -m meridian.workbench` serves the local Meridian site.

- `/` presents the fictional firm.
- practice and people pages are thin views over configuration.
- `/workbench` supports manual enquiries, generated fictional examples, and live reruns of benchmark cases.
- unchanged test cases can be compared with their authored expectation after a live call; editing a case makes it ad hoc and removes benchmark-comparison eligibility.
- `/evaluation` is a read-only explorer for `eval/results/initial.json`, showing the preserved first pass rather than making new model calls.
- links connect preserved evaluation cases to live workbench cases so stochastic reruns can be compared without rewriting history.

The local site has no persistence or authentication. Interactive enquiries/results are not saved, and the workbench does not modify configuration, frozen cases, or evaluation evidence.

## 13. Current system boundaries

This prototype does not write to a CRM, own a production queue, authenticate users, or make autonomous downstream changes outside its routing result. It does not use RAG, a vector database, multi-agent orchestration, self-critique/voting, or a generated confidence score.

Those are not prohibited future directions; they are simply not required by the observed problem. The production path is to learn first from real analyst decisions, overrides, reassignments, routing-relevant metadata conflicts, response times, and downstream outcomes, then add machinery only where those observations justify it.
