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
- `eval/cases.yaml` is the frozen rendered benchmark from the pre-classifier Phase
  1.5 checkpoint. Do not rerender, rewrite, relabel, or otherwise tune benchmark
  inputs after classifier work begins except to correct a demonstrable benchmark
  defect, and record any such correction explicitly.
- Synthetic wording must be rendered from form + seed only. The rendering model
  must never receive expected labels or rationales.
- The classifier sees only submitted fields and semantic config, never answer keys,
  rationales, tags, cohort names, response IDs, or lead names. Routing sees the
  validated assessment + routing config.
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

Current phase: the evaluation contract, semantic answer keys, and 30 rendered
enquiry descriptions are frozen before classifier implementation. Phase 1.5 commit
`93ced9e13b5ebc521ba1ad6c52816d415d0a0b5a` is the benchmark checkpoint.
Next: implement the minimal structured classifier, deterministic router, and
reproducible evaluator against the frozen benchmark; inspect the first untuned
results before making any classifier/prompt/model changes.
