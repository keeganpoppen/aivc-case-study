# Meridian

AIVC intake triage case study for **Meridian Advisory**, a fictional professional
services firm. The target is a small classifier with explicit abstention and a
separate, configurable router.

**Status:** specification and environment checkpoint. The classifier, dataset, and
evaluation runner have not been implemented. There are no performance results yet.

The agreed design is recorded in [SPEC.md](SPEC.md), including:

- [Meridian's six practices, complexity rubric, and lead-routing policy](SPEC.md#2-accepted-operating-assumptions).
- [The structured assessment, abstention rules, and separation of classification from routing](SPEC.md#3-accepted-system-contract).
- [The synthetic evaluation plan, metrics, and cost assumptions](SPEC.md#4-evaluation-commitments).
- [Scope, build order, and decisions still to make](SPEC.md#5-scope-and-work-sequence).

## Work here

The current AIVC continuation task owns design decisions. [SPEC.md](SPEC.md)
records the accepted design and the next work items. [AGENTS.md](AGENTS.md) keeps
future coding sessions aligned with that agreement.

From a checkout of this repository:

```sh
uv sync --locked
uv run python --version
git status --short --branch
```

Python 3.13 and uv are the chosen local tools. The project currently needs no
third-party Python dependencies and makes no model API calls. We will add only
the dependencies the implementation uses and record them in `uv.lock`.

## Build order

1. Define the evaluation contract and author roughly 30 latent cases.
2. Review the submitted wording against those facts and freeze the answer key.
3. Build validation, structured classification, abstention, and deterministic routing.
4. Run evaluation, inspect errors, and change only what those errors justify.
5. Include reproducible results, run instructions, a small architecture diagram,
   and brief production/fallback notes in this README.

GitHub is for durable checkpoints and the eventual submission:
[keeganpoppen/aivc-case-study](https://github.com/keeganpoppen/aivc-case-study)
is private. We publish checkpoints through the GitHub connector and synchronize
the local Git history with the resulting commits. Terminal Git authentication is
not required for that workflow. The local checkout is `/Users/elkeegano/life/aivc`.

The original brief and discussion are retained locally under `.local/reference/`,
which Git ignores. They are not part of the submission.
