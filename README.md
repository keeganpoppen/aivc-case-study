# Meridian — Intake Triage Prototype

A small prototype for automating intake triage at **Meridian Advisory**, a
fictional professional-services firm. The system classifies an inbound enquiry,
estimates its complexity, and either routes it according to explicit business
policy or abstains for human review.

The implementation is intentionally small. This problem does not need an agentic
workflow: one structured semantic assessment followed by deterministic policy is
easier to reason about, cheaper to operate, and clearer to evaluate.

## Design

The prototype separates two concerns that change for different reasons:

1. **What is this enquiry?** A model interprets the submitted description and
   metadata against Meridian's configured service taxonomy and complexity rubric.
2. **What should the firm do with it?** Ordinary code applies configurable routing
   and escalation policy to the resulting assessment.

That separation lets Meridian change team ownership without reclassifying old
enquiries, or change the taxonomy without baking employee names into a prompt.
Ambiguous, insufficient, or unsupported requests are not forced into a category;
they are sent to human review.

## Evaluation approach

The benchmark is defined before classifier implementation. Each synthetic case
starts from authored latent facts and an independent answer key; realistic customer
wording can then be rendered from those facts without giving the renderer the
expected label. This keeps the evaluation from becoming a test written after the
model's behavior is known.

The evaluation will report more than raw accuracy. In particular, it measures the
tradeoff between **automation coverage** and **selective routing accuracy**: a system
that abstains on every hard case is safe but useless, while one that routes every
case may create expensive errors.

The brief implies roughly 8–12 analyst-minutes per enquiry, with 9.6 minutes at the
midpoint of 50 enquiries/week. The evaluator therefore also expresses performance
under a configurable cost of an incorrect automatic route rather than assuming that
all mistakes and all human reviews are equally expensive.

## Repository layout

The final repository will contain the runnable prototype, frozen synthetic cases,
configuration for Meridian's taxonomy and routing policy, reproducible evaluation
results, and brief production/fallback notes. `SPEC.md` records the detailed design
assumptions used to build the prototype.

## Running

```sh
uv sync --locked
```

Runnable classification and evaluation commands will be documented here alongside
the implementation that they exercise.
