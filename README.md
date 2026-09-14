# Meridian — Intake Triage Prototype

A small prototype for automating inbound-enquiry triage at **Meridian Advisory**, a
fictional professional-services firm.

The system makes one structured semantic assessment of an enquiry, then ordinary
code applies Meridian's routing policy. It can explicitly abstain for human review.
The implementation is intentionally small: this problem does not need an agentic
workflow.

```text
web form
   │
   ▼
validated intake
   │
   ▼
one structured LLM assessment
   │
   ▼
deterministic routing policy
   ├──────────────► practice lead
   └──────────────► human review
```

## Result

The first classifier implementation was evaluated **once, untuned**, against a
30-case synthetic benchmark that had been authored and frozen before classifier
work began.

| Metric | Untuned result |
| --- | ---: |
| Automation coverage | **27 / 30 (90.0%)** |
| Selective route accuracy | **24 / 27 (88.9%)** |
| Unsafe automation rate | **3 / 30 (10.0%)** |
| Review recall | **3 / 6 (50.0%)** |
| Unnecessary review rate | **0 / 24 (0.0%)** |
| Service-line accuracy¹ | **25 / 25 (100%)** |
| Complexity accuracy² | **26 / 28 (92.9%)** |

¹ Cases with an authored primary service line. Cases intentionally requiring no
primary owner are excluded from this denominator.

² Cases where complexity was inferable in the authored answer key.

The model was strong at understanding **what the client wanted**: it did not miss an
authored primary service line. Its weakness was deciding **when not to automate**.
It routed every safely routeable case automatically, but also auto-routed three of
six cases that were deliberately designed to require review.

That is the most important result of the exercise. On this evidence I would **not
yet turn on autonomous routing in production**. I would run the system in shadow
mode first, compare its decisions with analyst decisions and downstream
reassignments, and use those observations to calibrate the automation boundary.

The complete untouched first-run artifact is committed at
`eval/results/initial.json`, including per-case predictions, expected semantics,
routes, latency/token usage, configuration/code hashes, and scoring provenance.

## What failed

The five scored errors fall into two very different categories.

### Three automation-boundary misses

- **A01 — cross-practice claims transformation.** The model selected Strategy &
  Transformation for a program spanning claims workflow redesign, AI capability,
  and systems integration instead of sending it to review.
- **A02 — post-acquisition integration.** The model selected Finance & Transactions
  for a coordinated program spanning operating model, ERP consolidation, finance
  integration, and synergy capture instead of sending it to review.
- **I02 — contradictory company size.** The model correctly inferred Technology &
  Systems and moderate complexity, but ignored an explicit contradiction between
  the structured `small` company-size field and prose describing a 15,000-person
  enterprise. That contradiction changes default-versus-senior lead routing, so
  the safe action was review.

The first two are useful reminders that ambiguity is partly an **organizational
policy question**, not merely a model-quality question. In a real implementation I
would resolve with the client who owns integrated cross-practice programs rather
than silently encode my own preference. I02 is a clearer safety failure: routing-
relevant metadata conflicts should become first-class evidence for abstention.

### Two complexity mismatches with no routing impact

- **H02** was classified as complex rather than moderate. Because the client was an
  enterprise account, either label routes to the same senior Operations lead.
- **A03** was correctly identified as ambiguous and sent to review, but the model
  left complexity unset where the answer key marked the responsible-AI program
  complex.

Those matter for classification quality, but neither changed the operational
outcome in this routing policy.

## Economics: sensitivity, not ROI theater

The brief says roughly eight analyst-hours are spent on 40–60 enquiries each week.
At the midpoint of 50 enquiries, the manual baseline is **9.6 analyst-minutes per
enquiry**.

Because the benchmark deliberately oversamples difficult cases, its case mix is not
a production-frequency estimate. Instead, the evaluator asks how the observed
behavior performs under different assumed costs of an incorrect automatic route.
With human review conservatively costed at the full original triage effort:

| Misroute cost | Modeled system cost vs. manual | Modeled savings on 30-case stress set |
| --- | ---: | ---: |
| 1× manual triage | 20% | +230.4 analyst-minutes |
| 3× manual triage | 40% | +172.8 analyst-minutes |
| 10× manual triage | 110% | −28.8 analyst-minutes |

Under this deliberately simple model, the break-even misroute penalty is **9×** the
original manual-triage cost. These are sensitivity calculations, not production ROI
claims. Real economics require observed case mix, actual review time, downstream
misroute cost, and ideally lead-response/conversion outcomes.

## Design

The prototype separates concerns that change for different reasons:

1. **What is this enquiry?** The model interprets the submitted description and
   metadata against Meridian's configured service taxonomy, scope rules, and
   complexity guidance.
2. **What should Meridian do with it?** Deterministic code applies lead ownership,
   escalation, review, and urgency/SLA policy.
3. **What is that behavior worth?** The evaluator applies separately configurable
   economic assumptions.

The assumptions therefore live in separate files:

```text
config/firm.yaml       submitted fields and firm context
config/taxonomy.yaml   service ownership, scope, complexity guidance
config/routing.yaml    leads, escalation, review queue, urgency/SLA
config/economics.yaml  manual baseline and cost sensitivity
config/models.yaml     provider/model settings
```

Changing a lead assignment can reroute a saved assessment without another model
call. Changing economic assumptions changes the value calculation without changing
classification or routing. Taxonomy changes remain explicit business-policy changes
rather than hidden prompt lore.

There is deliberately no model-generated numeric confidence score. Instead, the
system makes an observable claim that a case is safe to automate, and evaluation
measures whether that claim is actually reliable.

## Evaluation design

The benchmark was built before classifier implementation:

1. Author the underlying client situation and semantic answer key.
2. Render realistic client-written wording from **only the latent facts**, never the
   answer key.
3. Review the rendered wording for fidelity and freeze it.
4. Implement the classifier without using benchmark labels.
5. Persist all predictions before the evaluator first accesses expected semantics.
6. Score the untouched initial run and preserve it as evidence.

The 30 cases are intentionally stress-weighted: 18 straightforward cases, six hard
but routeable practice-boundary cases, three genuinely ambiguous enquiries, two
insufficient/contradictory enquiries, and one out-of-scope request.

This design is why the headline metrics emphasize **coverage and selective routing
accuracy**, not a single undifferentiated accuracy number. A classifier that sends
everything to review is safe but useless; one that routes everything can make
expensive mistakes.

`EVALUATION.md` contains the exact scoring contract and `SPEC.md` records the full
fictional operating assumptions.

## Production posture

I would initially deploy this in **shadow mode** rather than immediately replacing
the analyst step. From day one I would record:

- model, prompt/config versions and raw structured assessment;
- automatic route versus review decision;
- analyst override / final assigned practice and lead;
- downstream reassignment;
- review rate and automation coverage;
- latency, API/schema failures, and token usage;
- routing-relevant metadata conflicts;
- response-time and, if available, lead-conversion outcomes.

The most useful production evaluation set is not more synthetic prose: it is the
stream of real enquiries plus the human corrections they produce.

The fallback is intentionally boring. API failure, refusal, invalid structured
output, unsupported work, ambiguity, or insufficient information goes to the
existing human-review queue. The system degrades to the workflow it is replacing
rather than inventing an answer.

The first production improvements I would investigate are:

1. clarify ownership rules for integrated cross-practice programs with the actual
   practice leads;
2. make routing-relevant metadata conflicts first-class structured evidence;
3. evaluate whether additional model reasoning improves abstention enough to justify
   its marginal latency/cost;
4. calibrate the automation boundary using analyst overrides and downstream
   reassignments from shadow-mode traffic.

I would make those changes against observed failures rather than adding agent loops,
RAG, voting, or other machinery pre-emptively.

## Running

Python 3.13 and `uv` are used for the prototype.

```sh
uv sync --locked
uv run python -m meridian.validate_data
uv run python -m unittest discover -s tests -v
```

The offline tests cover benchmark/config invariants,
request isolation, structured-output invariants, routing/rerouting, operational
fallbacks, metric denominators, economic calculations, and workbench request isolation.

Put `OPENAI_API_KEY` in the project’s `.env` file or export it in your shell, then
triage one enquiry. The workbench and API-backed commands load that file
automatically; exported variables take precedence. Commands with `--root` load
`.env` from the selected project root. The file is ignored by Git.

Triage one enquiry:

```sh
uv run python -m meridian.triage \
  --industry retail \
  --company-size small \
  --urgency normal \
  --description "We need a dashboard showing agreed sales metrics from our existing reporting table."
```

The command returns the semantic assessment, deterministic routing decision, and
basic model-call metadata as JSON.

To run the frozen benchmark separately, choose a new result path; the preserved
initial run is never overwritten:

```sh
uv run python -m meridian.evaluate \
  --output eval/results/reproduction.json
```

The initial run used one `gpt-5.6-terra` call per case at low reasoning effort: 30/30
calls completed with no operational fallback, mean call latency was **1.74 s**, and
observed usage totaled **74,907 input tokens / 2,109 output tokens**.

## Local workbench

```sh
uv run python -m meridian.workbench
```

The server listens on all network interfaces (`0.0.0.0:8000`). Open
`http://127.0.0.1:8000` locally, or use the host machine’s network address from
another device, for the Meridian site, with practice and people pages
derived from configuration. At `/workbench`, enter an enquiry, browse test cases,
or generate an ephemeral fictional scenario. Run triage explicitly to inspect the semantic
assessment, deterministic route, and model-call metadata. An unchanged benchmark
case automatically shows a benchmark check after a run; edits make it an
ad-hoc enquiry. Live model answers may differ from the frozen untuned result.

Browsing and the frozen benchmark summary work offline. Live triage and generation
use `OPENAI_API_KEY` from the project’s `.env` or the server environment. Restart
the server after changing `.env`. Interactive enquiries and results
are not saved, and the workbench never changes the benchmark or evaluation evidence.

The `/evaluation` page shows the preserved first pass, including its cost-sensitivity
interpretation. Case links connect saved results and live intake; a live call can
produce a different answer. Contextual help explains the few specialized terms.
