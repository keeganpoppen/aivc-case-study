# Evaluation contract

This benchmark is designed to answer a narrow deployment question:

> **When is automated routing safe enough to replace the manual triage step, and when should the system abstain?**

It is intentionally defined **before** classifier implementation. The cases are
stress-weighted to exercise service boundaries and abstention behavior; their
frequency is not intended to represent Meridian's production case mix.

## What is frozen before classifier work

Each case is authored in two layers:

1. **Latent facts** — the underlying client situation, metadata, requested outcome,
   and rendering style.
2. **Expected semantics** — disposition, primary service line when one exists, and
   complexity when it can reasonably be inferred.

Natural-language enquiry text is rendered from the latent facts only. The renderer
must not receive the expected labels or rationale. Rendered text is reviewed once
to ensure that it still supports the authored answer key, then frozen before the
classifier is tuned.

The classifier therefore does not get to define its own test.

## Dispositions

The model may return one of four semantic dispositions:

- **`clear`** — there is a defensible primary service line and enough information
  to estimate complexity.
- **`ambiguous`** — two or more service lines are genuinely plausible primary
  owners and the enquiry does not establish which outcome is primary.
- **`insufficient_information`** — important information is missing or internally
  contradictory, so automatic routing would be unsafe.
- **`out_of_scope`** — the request is understood, but Meridian does not offer the
  requested work under the configured taxonomy / eligibility policy.

The last three dispositions all go to human review in v0, but they are deliberately
kept distinct because they imply different real-world follow-up actions.

A review case may still contain inferable semantics. For example, contradictory
company-size metadata can make routing unsafe even when the requested service line
and engagement complexity are clear.

## Output invariants

These are validated in ordinary code rather than left solely to prompting:

| Disposition | Required semantic state |
| --- | --- |
| `clear` | `service_line` and `complexity` are present. |
| `ambiguous` | No primary `service_line`; at least two plausible alternatives; a review reason is present. |
| `insufficient_information` | A review reason is present; partial service-line or complexity conclusions are allowed when supported. |
| `out_of_scope` | No primary `service_line`; a review reason is present. |

Model/schema/API failures are operational fallbacks to human review; they are not
semantic dispositions that the model is asked to invent.

## Scored metrics

The headline metrics are deliberately about the automation boundary rather than a
single undifferentiated accuracy number.

### Automation coverage

`automatic routes / all cases`

How much of the manual step the system actually replaces.

### Selective route accuracy

`correct automatic routes / automatic routes`

A route is correct only when the case is safe to automate **and** the final lead
matches the route implied by the frozen semantic answer key plus the current routing
configuration. Automatically routing a case that should be reviewed is incorrect,
even if the selected service line happens to be plausible.

### Unsafe automation rate

`incorrect automatic routes / all cases`

This makes the cost of overconfidence visible without hiding it inside coverage.

### Review recall

`correctly reviewed cases / cases whose expected disposition requires review`

Measures whether the system catches cases where automation is unsafe.

### Unnecessary review rate

`clear cases sent to review / clear cases`

Measures whether safety comes from simply punting difficult-but-routeable work back
to humans.

### Service-line accuracy

`correct primary service line / cases with an authored primary service line`

This includes review cases where a primary line is still inferable. Cases whose
answer key intentionally has no primary line are excluded from the denominator.

### Complexity accuracy

`correct complexity / cases with an authored complexity label`

Cases where complexity cannot reasonably be inferred are excluded from the
denominator.

For any metric with a zero denominator, the evaluator reports `n/a` rather than
manufacturing a percentage.

## What is intentionally not auto-scored

`summary`, `review_reasons`, and `alternative_service_lines` are schema-validated
and inspected qualitatively, but v0 does not ask a second LLM to manufacture a
numeric quality score for them. The core decision can be evaluated directly.

## Economic sensitivity, not ROI theater

The brief gives a real manual baseline: 40–60 enquiries per week consume roughly
8 analyst-hours. At the midpoint of 50 enquiries/week:

`m = 8 * 60 / 50 = 9.6 analyst-minutes per enquiry`

Let:

- `N` = number of evaluated cases
- `R` = cases sent to human review
- `W` = incorrectly auto-routed cases
- `r` = review cost as a multiple of the original manual triage cost (default 1.0)
- `k` = cost of a misroute as a multiple of the original manual triage cost

Then the deliberately simple sensitivity model is:

```text
manual_cost = N * m
system_cost = (R * r * m) + (W * k * m)
estimated_savings = manual_cost - system_cost
```

Equivalently, normalized by the manual baseline:

```text
system_cost / manual_cost = (R*r + W*k) / N
```

When `W > 0`, the break-even misroute multiple is:

```text
k* = (N - R*r) / W
```

The evaluator reports several configurable `k` values rather than pretending the
business cost of a misroute is known. A default `r = 1.0` is conservative: it
assumes an abstained case still consumes the full original manual triage effort,
even though the model may already have produced useful enrichment.

**This is not a production ROI estimate.** The benchmark deliberately oversamples
hard and review-worthy cases. Production economics require observed case mix,
actual review time, model usage, downstream misroute cost, and ideally conversion /
response-time outcomes. The purpose here is to expose the operating trade-off and
show exactly which assumptions would need to be replaced with measured data.

## Benchmark composition

The frozen latent benchmark contains 30 cases:

| Cohort | Count | Purpose |
| --- | ---: | --- |
| Straightforward | 18 | One simple, moderate, and complex case for each of six service lines. |
| Hard but routeable | 6 | Overlapping vocabulary / adjacent practices with one defensible primary owner. |
| Ambiguous | 3 | Multiple plausible primary owners; human review expected. |
| Insufficient / contradictory | 2 | Missing or contradictory routing-relevant information. |
| Out of scope | 1 | Request is understood but not offered by Meridian. |

The set deliberately includes large-but-simple, small-but-complex, regulated-but-
simple, urgent-but-simple, AI-mentioned-but-not-Data-&-AI, and metadata-conflict
cases so that obvious shortcuts fail.

## How results should be shown to an evaluator

The README should lead with a compact result table containing:

1. automation coverage,
2. selective route accuracy,
3. unsafe automation rate,
4. review recall,
5. service-line and complexity accuracy.

Immediately below it, show a small misroute-cost sensitivity table and a short
error analysis with concrete failed cases. Do not bury errors, and do not imply that
a stress-weighted synthetic benchmark predicts production frequency.

The live demo should make the configuration boundaries visible: taxonomy changes
can change classification; routing changes can reroute an unchanged assessment;
economic assumptions can change the reported value without changing either.