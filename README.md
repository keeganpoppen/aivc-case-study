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
uv run python -m meridian.validate_data
uv run python -m unittest discover -s tests -v
```

Validation runs offline and checks all configuration files, the 30 latent cases,
and `eval/cases.yaml` when present. Rendered cases must retain the original IDs,
metadata, and answer keys, with a matching source-file hash.

To generate enquiry wording once, set `OPENAI_API_KEY` in the environment and run:

```sh
uv run python -m meridian.render_cases
uv run python -m meridian.validate_data
```

The renderer uses `synthetic_rendering` in `config/models.yaml` and sends only each
case's form and seed through the Responses API with response storage disabled.
It preserves raw responses locally in a Git-ignored run directory and records
provenance in the generated file. An existing `eval/cases.yaml` is never overwritten;
a failed run does not publish a partial benchmark. Generated wording requires a
fidelity review before classifier implementation or tuning.

Classifier, routing, and evaluation commands are not implemented yet.
