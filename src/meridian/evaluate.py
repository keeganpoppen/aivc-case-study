"""Predict first, then mechanically score the frozen benchmark. No tuning."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
from statistics import mean
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter

from openai import OpenAI
import yaml

from .data import UniqueKeyLoader, load_config
from .models import Expected
from .triage import CLASSIFIER_INSTRUCTION, SubmittedEnquiry, TriageAssessment, route, triage


def metric(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else "n/a"}


def score_case(result, expected, intake, routing):
    expected = Expected.model_validate(expected)
    # Only scoring creates an assessment from expected semantics. Prose is unscored.
    oracle = TriageAssessment(summary="Authored semantics for deterministic route derivation.",
                              **expected.model_dump(),
                              review_reasons=[] if expected.disposition == "clear" else ["Authored review."])
    expected_route = route(oracle, intake.company_size, intake.urgency, routing)
    automatic = result.routing.mode == "automatic"
    expected_review = expected.disposition in routing.policy.review_dispositions
    correct_route = (not expected_review and expected.disposition == "clear" and automatic
                     and result.routing.destination == expected_route.destination)
    predicted = result.assessment
    line_correct = (predicted is not None and predicted.service_line == expected.service_line
                    if expected.service_line is not None else None)
    complexity_correct = (predicted is not None and predicted.complexity == expected.complexity
                          if expected.complexity is not None else None)
    disposition_correct = predicted is not None and predicted.disposition == expected.disposition
    failures = []
    if result.metadata.failure_reason:
        failures.append(f"operational:{result.metadata.failure_reason}")
    if automatic and not correct_route:
        failures.append("unsafe_automatic_route")
    if not automatic and expected.disposition == "clear":
        failures.append("unnecessary_review")
    for label, correct in (("service_line", line_correct), ("complexity", complexity_correct),
                           ("disposition", disposition_correct)):
        if correct is False:
            failures.append(f"{label}_mismatch")
    return {"expected": expected.model_dump(), "expected_route": expected_route.model_dump(),
            "automatic": automatic, "expected_review": expected_review,
            "correct_automatic_route": correct_route, "service_line_correct": line_correct,
            "complexity_correct": complexity_correct, "disposition_correct": disposition_correct,
            "failure_reasons": failures}


def summarize(rows):
    n = len(rows)
    automatic = sum(row["automatic"] for row in rows)
    correct = sum(row["correct_automatic_route"] for row in rows)
    expected_review = sum(row["expected_review"] for row in rows)
    clear = [row for row in rows if row["expected"]["disposition"] == "clear"]
    metrics = {
        "automation_coverage": metric(automatic, n),
        "selective_route_accuracy": metric(correct, automatic),
        "unsafe_automation_rate": metric(automatic - correct, n),
        "review_recall": metric(sum(row["expected_review"] and not row["automatic"] for row in rows), expected_review),
        "unnecessary_review_rate": metric(sum(not row["automatic"] for row in clear), len(clear)),
    }
    for field in ("service_line", "complexity"):
        eligible = [row for row in rows if row[f"{field}_correct"] is not None]
        metrics[f"{field}_accuracy"] = metric(sum(row[f"{field}_correct"] for row in eligible), len(eligible))
    labels = ("clear", "ambiguous", "insufficient_information", "out_of_scope")
    confusion = {label: dict.fromkeys((*labels, "operational_fallback"), 0) for label in labels}
    for row in rows:
        predicted = row["prediction"]["assessment"]
        confusion[row["expected"]["disposition"]][predicted["disposition"] if predicted else "operational_fallback"] += 1
    diagnostics = {"exact_disposition_accuracy": metric(sum(row["disposition_correct"] for row in rows), n),
                   "disposition_confusion": {"rows": "expected", "columns": "predicted", "counts": confusion}}
    return metrics, diagnostics


def economics(n, reviews, wrong, config):
    m = config.manual_baseline.derived_minutes_per_enquiry_at_midpoint
    r = config.evaluation.human_review_cost_multiple
    manual = n * m
    scenarios = []
    for k in config.evaluation.misroute_cost_multiples:
        system = (reviews * r + wrong * k) * m
        scenarios.append({"misroute_cost_multiple": k, "manual_cost_minutes": manual,
                          "system_cost_minutes": system, "savings_minutes": manual - system,
                          "system_manual_ratio": system / manual if manual else "n/a"})
    return {"label": "Stress-weighted sensitivity calculations, not production ROI estimates",
            "cases": n, "reviews": reviews, "wrong_automatic_routes": wrong,
            "manual_minutes_per_enquiry": m, "human_review_cost_multiple": r,
            "scenarios": scenarios,
            "break_even_misroute_multiple": (n - reviews * r) / wrong if wrong else "n/a"}


def aggregate_calls(rows):
    calls = [row["prediction"]["metadata"] for row in rows]
    latencies = [call["elapsed_seconds"] for call in calls]
    usage = {}
    for field in ("input_tokens", "output_tokens", "reasoning_tokens"):
        known = [call[field] for call in calls if call[field] is not None]
        usage[field] = {"total_observed": sum(known) if known else "n/a",
                        "calls_with_usage": len(known)}
    return {"calls": len(calls), "states": dict(Counter(call["state"] for call in calls)),
            "usage": usage, "latency_seconds": {"sum": sum(latencies),
            "mean": mean(latencies) if latencies else "n/a", "max": max(latencies) if latencies else "n/a"}}


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def publish_json(output, data):
    # Publish atomically and never replace another run, including in a race.
    with TemporaryDirectory(dir=output.parent) as temp:
        staged = Path(temp) / "result.json"
        staged.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        os.link(staged, output)


def evaluate(root: Path, output: Path):
    if output.exists():
        raise ValueError("Result already exists; refusing to overwrite.")
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise ValueError("OPENAI_API_KEY is required; no evaluation was run.")
    config = load_config(root)
    benchmark_path = root / "eval/cases.yaml"
    benchmark_bytes = benchmark_path.read_bytes()
    # YAML is decoded as data, but answer fields are not accessed until all predictions exist.
    benchmark = yaml.load(benchmark_bytes, Loader=UniqueKeyLoader)
    intakes = [SubmittedEnquiry(**{key: case["form"][key] for key in
               ("description", "industry", "company_size", "urgency")}) for case in benchmark["cases"]]
    started = datetime.now(timezone.utc)
    watched = [*sorted((root / "config").glob("*.yaml")),
               *sorted((root / "src/meridian").glob("*.py")), root / "uv.lock",
               root / "SPEC.md", root / "EVALUATION.md"]
    hashes = {path.relative_to(root).as_posix(): file_hash(path) for path in watched}
    provenance = {"benchmark_file": "eval/cases.yaml", "benchmark_sha256": sha256(benchmark_bytes).hexdigest(),
                  "model": config.models.classification.model,
                  "reasoning_effort": config.models.classification.reasoning_effort,
                  "started_at": started.isoformat(), "file_hashes": hashes,
                  "classifier_instruction": CLASSIFIER_INSTRUCTION,
                  "assessment_schema": TriageAssessment.model_json_schema(),
                  "python": platform.python_version(),
                  "packages": {name: version(name) for name in ("openai", "pydantic", "pyyaml")},
                  "git_head_before_run": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
                  "run_kind": "untuned", "timeout_seconds": 120, "max_retries": 0}
    evidence = root / "eval/results/evidence" / started.strftime("%Y%m%dT%H%M%S%fZ")
    evidence.mkdir(parents=True, exist_ok=False)
    publish_json(evidence / "provenance.json", provenance)
    predictions = []
    clock = perf_counter()
    with OpenAI(timeout=120, max_retries=0) as client:
        for index, intake in enumerate(intakes, 1):
            def save(result, raw, index=index):
                publish_json(evidence / f"{index:03d}.json", {"prediction": result.model_dump(),
                                                            "raw_response": raw})
            result = triage(**intake.model_dump(), config=config, client=client, evidence_sink=save)
            predictions.append(result)
            print(f"Predicted {index}/{len(intakes)} ({result.metadata.state})", flush=True)
    # The first access to expected semantic fields occurs here, after prediction persistence.
    rows = []
    for case, intake, result in zip(benchmark["cases"], intakes, predictions, strict=True):
        scoring = score_case(result, case["expected"], intake, config.routing)
        rows.append({"id": case["id"], "intake": intake.model_dump(),
                     "prediction": result.model_dump(), **scoring})
    metrics, diagnostics = summarize(rows)
    auto = metrics["automation_coverage"]["numerator"]
    wrong = metrics["unsafe_automation_rate"]["numerator"]
    artifact = {"provenance": provenance, "completed_at": datetime.now(timezone.utc).isoformat(),
                "run_elapsed_seconds": perf_counter() - clock,
                "evidence_directory": evidence.relative_to(root).as_posix(),
                "metrics": metrics, "diagnostics": diagnostics,
                "economics": economics(len(rows), len(rows) - auto, wrong, config.economics),
                "observability": aggregate_calls(rows), "cases": rows}
    if benchmark_path.read_bytes() != benchmark_bytes or any(file_hash(root / path) != digest for path, digest in hashes.items()):
        raise ValueError("Benchmark or implementation/config changed during run; evidence preserved, result not published.")
    output.parent.mkdir(parents=True, exist_ok=True)
    publish_json(output, artifact)
    print(json.dumps({key: artifact[key] for key in ("metrics", "diagnostics", "economics", "observability")}, indent=2))
    print(f"Saved {output}")
    return artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("eval/results/initial.json"))
    args = parser.parse_args()
    try:
        evaluate(args.root.resolve(), args.root / args.output)
    except ValueError as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
