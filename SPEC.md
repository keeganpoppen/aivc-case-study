# Meridian v0 specification and decision record

This is the portable record of the design accepted in **Case Study Strategy**
(ChatGPT conversation `6aa71e82-77d8-83ea-b9dd-c255cbfd691c`) and carried into the
current AIVC continuation task (`01a09d20-4b78-7c00-87c8-262d1bfc513e`) on
2026-09-13. That task is the canonical decision log. Later decisions there take
precedence; update this record to keep it aligned.

The original PDF and full retrieved discussion are in `.local/reference/`.
The PDF supplies requirements; the discussion supplies our fictional operating
assumptions. Neither constitutes evidence that the eventual prototype works.

## 1. Requirements from the brief

- 40-60 inbound web-form enquiries weekly; four inputs: short description,
  industry, company size, and urgency.
- Existing manual work: service-line tagging, simple/moderate/complex estimation,
  and routing to a team lead; approximately eight analyst-hours per week.
- Deliver a functioning prototype of the vital classification/routing logic,
  using synthetic data. Format is flexible.
- Architecture (1-2 pages or diagram with notes) and a half-page discussion of
  production failures, monitoring, and fallback are optional supplements.
- Spend 2-3 hours; prioritize depth over breadth. AI assistance is allowed.
- Submit no later than 24 hours before the panel interview. The subsequent
  technical conversation lasts 30-45 minutes. The interview date is not known here.

## 2. Accepted operating assumptions

Meridian Advisory is a fictional generalist consultancy serving operating
executives at mid-market and enterprise businesses. Small-company requests can
also appear and must be handled according to their actual scope.

| Service line | Primary problem and boundary |
| --- | --- |
| Strategy & Transformation | Growth, operating models, transformation roadmaps, organizational change; deciding what/how to transform. |
| Operations & Process | Workflow redesign, supply chain, service operations, process efficiency/automation; the business process is primary. |
| Data & AI | Analytics, AI/ML, BI, data platforms/strategy/governance; data or model capability is primary. |
| Technology & Systems | ERP/CRM, cloud, integration, migrations, application implementation; system delivery is primary. |
| Risk & Compliance | Cybersecurity, privacy, controls, regulatory readiness, operational risk; risk/control obligation is primary. |
| Finance & Transactions | FP&A, finance transformation, diligence, valuation, transaction support; finance/transaction problem is primary. |

These practices overlap. Each enquiry has a clear primary owner or should go to
human review. Mentioning several practices is not by itself a reason to abstain
when one is clearly dominant.

Useful boundaries from the agreed scenario include an AI-powered claims workflow
(Operations or Data & AI), finance ERP modernization (Technology or Finance),
bank AI governance (Data & AI or Risk), and post-acquisition systems consolidation
(Strategy, Finance, or Technology). The actual requested outcome determines
whether a primary practice is clear; keywords alone do not settle these cases.

### Complexity rubric

- **Simple:** bounded, well-defined work, approximately one deliverable/workstream,
  few dependencies. Examples: one-process assessment, bounded dashboard, focused
  compliance review, configuration of an existing platform.
- **Moderate:** discovery/customization or coordination across stakeholders,
  workflows, data sources, or systems, while remaining reasonably bounded.
- **Complex:** enterprise/multi-business-unit scope, multiple major systems or
  workstreams, substantial organizational change, material regulatory/risk exposure,
  significant requirements ambiguity, a transaction/integration program, or
  dependencies across several functions.

Company size is evidence, not a complexity label. Large companies can request
simple work; small companies can request complex work. Being in a regulated
industry alone does not establish material risk exposure.

### Routing and priority

Each practice has a default lead and a senior lead. Review takes precedence:

1. Ambiguous or insufficient assessments go to human review.
2. Otherwise, complex work or enterprise accounts go to the senior practice lead.
3. Other clear enquiries go to the default practice lead.

The complex/enterprise escalation rules are independent configuration switches.
Urgency changes priority/SLA, not semantic ownership. Industry supplies context.
Routing produces a local decision; live CRM writes are outside v0.

## 3. Accepted system contract

Input validation/normalization -> one structured LLM assessment -> output validation
-> deterministic routing policy -> team lead or human-review result.

Assessment fields agreed in the discussion:

- `summary`: concise enrichment grounded in submitted information.
- `service_line`: a configured service-line identifier or null.
- `complexity`: simple, moderate, complex, or null.
- `disposition`: clear, ambiguous, or insufficient_information.
- `alternative_service_lines`: plausible alternative practice identifiers.
- `review_reasons`: explicit reasons for abstention.

No model-generated numeric confidence. The system measures how often a claim of
clear ownership is correct. Model/schema failure falls back to human review.

Taxonomy definitions and complexity rubric are read from configuration and passed
to the classifier. Ownership and escalation policy are read separately by ordinary
code; the model does not choose a person's name. Saved assessments can be routed
again after a policy change, with no new model invocation.

Two distinct demonstrations must be possible:

- Change a taxonomy definition and rerun classification.
- Change lead ownership or escalation policy and reroute the same assessment;
  classification stays identical.

## 4. Evaluation commitments

Define the evaluation contract and latent cases **before implementing the
classifier**. Authors choose the underlying facts and expected labels first.
Optional generative wording introduces realistic language, not the answer key.
Review rendered wording to ensure it still supports the intended labels.

Target approximately 30 cases:

| Group | Count | Purpose |
| --- | ---: | --- |
| Straightforward, realistically messy | 18 | Three per practice. |
| Hard but routeable | 6 | Overlapping vocabulary with a dominant owner. |
| Genuinely ambiguous | 3 | Human review is expected. |
| Insufficient/contradictory | 3 | Human review is expected. |

Distribute small/complex and large/simple requests, urgency disagreements,
incidental technology mentions, regulated contexts, terse and rambling wording,
and references to practices that are not actually being requested.

Report service-line accuracy, complexity accuracy, review recall, selective
accuracy among automatic routes, automation coverage, and operational cost under
an explicit misroute penalty. Preserve failures and honest denominators. Synthetic
results are development evidence, not an estimate of production reliability.

The exact matching rules, handling of missing labels/zero denominators, and
definition of a correct final route are the next evaluation-contract work item.

### Cost assumptions

At the midpoint of the brief's volume range, `m = 480 / 50 = 9.6` analyst minutes
per enquiry. This is a **derived midpoint estimate**, not a separately measured
per-case cost. The implied range is 8-12 minutes at 60-40 enquiries per week.

For N cases, R sent for human review, and W incorrectly auto-routed:

```text
manual cost = N * m
system cost = R * m + W * lambda
estimated savings = manual cost - system cost
```

Lambda is an unknown business cost expressed in equivalent analyst-minutes;
show configurable sensitivity rather than inventing its true value. Changing
lambda changes the evaluation, not automatically the decision policy. Compare
policies only if actually implemented and measured. This simplified model omits
implementation, maintenance, API expense, and conversion effects; report model
usage separately where available. It does not establish investment ROI.

### What the artifact should demonstrate

Each design choice must earn its place through observable behavior:

| Choice | Evidence to produce |
| --- | --- |
| Configurable business assumptions | Edit a taxonomy/rubric definition and inspect the changed classification. |
| Separate organizational routing | Change a lead or escalation rule and reroute the identical saved assessment without a model call. |
| Explicit abstention | Show review recall and the coverage/error tradeoff, including unnecessary reviews and wrong automatic routes. |
| Latent facts before generated wording | Keep the authored labels independent from the model that renders customer language. |
| Operational cost assumptions | Recalculate estimated savings across misroute penalties; retain negative results when they occur. |
| Small implementation | One semantic assessment followed by ordinary validation and routing code. |

Do not manufacture mistakes or tune for a theatrical score. The point of difficult
cases is to expose real failure modes and report them honestly. Faster responses,
fewer dropped leads, conversion, and better qualification are potential business
benefits to investigate; none has been measured by this case study.

## 5. Scope and work sequence

1. Complete the evaluation contract and approximately 30 latent cases.
2. Review/freeze the dataset and answer key before classifier tuning.
3. Implement the smallest classifier/abstention/router satisfying that contract.
4. Run evaluations, inspect failures, and make evidence-driven changes.
5. Package the working prototype, data, and actual generated results.
6. Finish README architecture/production notes; prepare interview narrative after
   the deliverable is sound.

No agent framework, vector database, workflow platform, elaborate synthetic-data
factory, or browser UI on the critical path. A CLI is sufficient. A live scenario
generator and UI are optional additions only if time remains. Complexity errors
are reported separately without expanding the simple cost model unnecessarily.

## 6. Setup decisions — 2026-09-13

**Accepted design:** Sections 2-5 preserve the plan the user accepted in the source
discussion. The clarified midpoint estimate in section 4 corrects an overstatement
in that discussion without changing the formula or chosen baseline.

**User-selected location:** `/Users/elkeegano/life/aivc`.

**Implementation setup:** use Python 3.13 with uv, a project-local virtual
environment, and a lockfile. The original sketch already used Python; these
specific tooling choices are setup defaults, not requirements of the brief.
Add dependencies only when used. Work locally on main; checkpoint only when
the user asks. The parent `/Users/elkeegano/life` is already a Git repository;
this case study gets its own nested repository with a separate Git history.
An explicit empty uv workspace bounds discovery at this folder, avoiding the
invalid Python-version setting in the parent project. The parent was not edited.
`uv sync --locked`, `uv run python --version`, and `uv sync --locked --check`
passed with Python 3.13.2 and uv 0.6.11.

**GitHub:** created private
[`keeganpoppen/aivc-case-study`](https://github.com/keeganpoppen/aivc-case-study)
(repository ID `1369024539`). The user signed in through the in-app browser;
the form already held `aivc-case-study` and Private, so those selections were
preserved instead of the earlier proposed `meridian` repository name.
`origin` is `git@github.com:keeganpoppen/aivc-case-study.git`. The connected GitHub
tools confirm admin/push access. A read-only terminal `git ls-remote origin` check
failed with `Permission denied (publickey)`; browser sign-in does not configure
terminal Git authentication.

**Checkpoint workflow:** the user explicitly selected the connector and authorized
uploading the relevant work in this task. Use it to publish the specification,
working agreement, README, and locked environment setup. Synchronize the local
Git history to the published commits so the checkout and GitHub share the same
history. Further requested checkpoints use this workflow; terminal credential
setup is not a prerequisite. The source PDF, raw conversation, and environment
files stay local and ignored. Nothing is submitted to interviewers by this upload.

**Continuity:** this task owns decisions; this specification records them; code
and evaluation outputs record what actually exists. Keep the original brief and
source discussion in ignored `.local/reference/` so context survives without
publishing the interview discussion. GitHub is a checkpoint/submission surface.

**Still to settle during the next step:** precise input enums and enterprise
threshold; actual fictional lead identifiers; urgency normalization/conflict
handling; output invariants and treatment of out-of-scope requests without silently
adding a disposition; evaluation matching rules; model/provider and credential
source. These details were not frozen in the prior discussion.

**Current milestone:** publish the specification and environment checkpoint.
Dataset, classifier, router, evaluator, and results remain to be built in the order
above. The next work item is the evaluation contract and approximately 30 latent
cases, including resolution of the open domain-policy details.
