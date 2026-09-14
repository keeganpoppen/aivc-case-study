# Working agreement

This repository implements the AIVC intake triage case study. Read SPEC.md first.

- The user's "Case Study Strategy" ChatGPT thread is the design authority for
  product, evaluation, scope, and evaluator-facing decisions. Work/Codex/local
  sessions are execution environments, not independent product owners.
- SPEC.md is the portable record of accepted decisions, not a second authority.
  Later decisions in the strategy thread take precedence; reconcile the spec when
  decisions change.
- README.md is an evaluator-facing deliverable. Write it for an AIVC reviewer,
  not for a future coding agent. Never put chat/task IDs, local filesystem paths,
  connector mechanics, resumption bookkeeping, or internal project-management
  status in the README. Internal continuity belongs here, in SPEC.md, or under
  ignored local reference material.
- Finish the evaluation contract and approximately 30 latent cases before the
  classifier. Do not silently invent domain policy or claim synthetic reliability.
- Keep the implementation small: input validation, one structured model assessment,
  validated output, deterministic routing or human review. No agent framework.
- Taxonomy and complexity rubric must be configuration inputs. Organizational
  routing rules must be independently configurable and replayable without an LLM.
- No model-generated numeric confidence. Explicit abstention is measured by evals.
- Label latent facts first; render customer wording separately. The classifier
  sees only submitted fields and semantic config, never answer keys or lead names.
- Prioritize a functioning prototype and reproducible results. UI, live case
  generation, and interview presentation are optional after the deliverable works.
- Keep source PDF, raw conversations, credentials, and scratch runs out of Git.
  Preserve relevant curated evaluation evidence with the final deliverable.
- Do not broaden scope or introduce architectural machinery unless the strategy
  thread has decided it earns its place through evaluator-visible behavior.
- Inspect the diff and run the relevant checks before publishing implementation
  checkpoints. Do not change benchmark labels after seeing classifier results
  except to correct a demonstrable labeling error, and record any such correction.
- The GitHub repository is `keeganpoppen/aivc-case-study`. Keep local and remote
  history aligned when working locally.
- The local checkout is an independent repository nested inside ~/life. Never
  stage, commit, reset, or otherwise modify the parent repository while working
  on this case.

Current phase: evaluation contract and latent-case design. Classifier tuning must
not begin until the benchmark inputs and answer key are frozen.
