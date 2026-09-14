# Working agreement

This repository implements the AIVC intake triage case study. Read SPEC.md and
EVALUATION.md before making implementation decisions.

- The user's "Case Study Strategy" ChatGPT thread is the design authority for
  product, evaluation, scope, and evaluator-facing decisions. Work/Codex/local
  sessions are execution environments, not independent product owners.
- SPEC.md is the portable record of accepted decisions. Later decisions in the
  strategy thread take precedence; reconcile the spec when decisions change.
- README.md is an evaluator-facing deliverable. Write it for an AIVC reviewer,
  not for a future coding agent. Never put chat/task IDs, local filesystem paths,
  connector mechanics, resumption bookkeeping, or internal project-management
  status in the README.
- Keep the implementation small: input validation, one structured model assessment,
  validated output, deterministic routing or human review. No agent workflow.
- Runtime inference uses the ordinary OpenAI Responses API + typed Pydantic models,
  not Codex SDK. Model IDs are configurable in `config/models.yaml`.
- Taxonomy, global/practice-specific complexity guidance, eligibility, routing,
  and economics are explicit configuration. Do not move these assumptions into
  hidden prompt prose or source-code conditionals without a strong reason.
- No model-generated numeric confidence. Explicit abstention is measured by evals.
- `eval/latent_cases.yaml` and its semantic answer keys were authored before the
  classifier. Do not change benchmark labels after seeing classifier results except
  to correct a demonstrable labeling error, and record any such correction.
- Synthetic wording must be rendered from form + seed only. The rendering model
  must never receive expected labels or rationales. Review/freeze rendered wording
  before classifier implementation or tuning.
- The classifier sees only submitted fields and semantic config, never answer keys,
  rationales, or lead names. Routing sees the validated assessment + routing config.
- Preserve raw/reproducible evaluation evidence. Do not claim a stress-weighted
  synthetic benchmark estimates production reliability or production case mix.
- Prioritize a functioning prototype and reproducible results. UI, live scenario
  generation, and interview presentation are optional after the deliverable works.
- Keep source PDF, raw conversations, credentials, and scratch runs out of Git.
- Do not broaden scope or introduce architectural machinery unless the strategy
  thread has decided it earns its place through evaluator-visible behavior.
- Inspect the diff and run relevant checks before publishing implementation
  checkpoints. Do not commit credentials or modify the enclosing parent repository.
- The GitHub repository is `keeganpoppen/aivc-case-study`.

Current phase: the evaluation contract and 30 latent answer keys are frozen.
Next: implement offline schema/invariant validation plus the one-time synthetic
wording renderer; render and review enquiry descriptions; only then implement the
classifier/router/evaluator.
