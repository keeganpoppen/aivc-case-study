"""Strict YAML loading and cross-file benchmark invariants (entirely offline)."""

from collections import Counter
from hashlib import sha256
from pathlib import Path

import yaml
from pydantic import BaseModel

from .models import (
    Configuration, EconomicsConfig, FirmConfig, LatentBenchmark, ModelsConfig,
    RenderedBenchmark, RoutingConfig, TaxonomyConfig,
)


class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader normally silently keeps the last duplicate mapping key."""


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            if key in result:
                raise ValueError(f"duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}")
            result[key] = loader.construct_object(value_node, deep=deep)
        except TypeError as exc:
            raise ValueError(f"invalid YAML mapping key at line {key_node.start_mark.line + 1}") from exc
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def load_yaml[T: BaseModel](path: Path, model: type[T]) -> T:
    try:
        return model.model_validate(yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ValueError(f"{path}: {exc}") from exc


def load_config(root: Path) -> Configuration:
    return Configuration(
        firm=load_yaml(root / "config/firm.yaml", FirmConfig),
        taxonomy=load_yaml(root / "config/taxonomy.yaml", TaxonomyConfig),
        routing=load_yaml(root / "config/routing.yaml", RoutingConfig),
        economics=load_yaml(root / "config/economics.yaml", EconomicsConfig),
        models=load_yaml(root / "config/models.yaml", ModelsConfig),
    )


def validate_benchmark(benchmark: LatentBenchmark | RenderedBenchmark, config: Configuration) -> None:
    cases = benchmark.cases
    if len(cases) != 30 or len({case.id for case in cases}) != 30:
        raise ValueError("benchmark requires exactly 30 unique case IDs")
    expected_counts = {"straightforward": 18, "hard_routeable": 6, "ambiguous": 3,
                       "insufficient": 2, "out_of_scope": 1}
    counts = Counter(case.cohort for case in cases)
    if counts != expected_counts:
        raise ValueError(f"cohort counts {dict(counts)} do not match {expected_counts}")
    lines = set(config.taxonomy.service_lines)
    fields = config.firm.intake.fields
    dispositions = {"straightforward": "clear", "hard_routeable": "clear",
                    "ambiguous": "ambiguous", "insufficient": "insufficient_information",
                    "out_of_scope": "out_of_scope"}
    for case in cases:
        expected = case.expected
        references = set(expected.alternative_service_lines)
        if expected.service_line is not None:
            references.add(expected.service_line)
        if unknown := references - lines:
            raise ValueError(f"{case.id}: unknown service-line IDs {sorted(unknown)}")
        if case.form.company_size not in fields.company_size.values:
            raise ValueError(f"{case.id}: invalid company_size {case.form.company_size!r}")
        if case.form.urgency not in fields.urgency.values:
            raise ValueError(f"{case.id}: invalid urgency {case.form.urgency!r}")
        if expected.disposition != dispositions[case.cohort]:
            raise ValueError(f"{case.id}: disposition disagrees with authored cohort")
    coverage = Counter((case.expected.service_line, case.expected.complexity)
                       for case in cases if case.cohort == "straightforward")
    required = Counter({(line, level): 1 for line in lines
                        for level in ("simple", "moderate", "complex")})
    if len(lines) != 6 or coverage != required:
        raise ValueError("straightforward cases require one simple, moderate, and complex case per each of six service lines")


def load_latent(root: Path, config: Configuration) -> LatentBenchmark:
    benchmark = load_yaml(root / "eval/latent_cases.yaml", LatentBenchmark)
    validate_benchmark(benchmark, config)
    return benchmark


def validate_rendered(benchmark: RenderedBenchmark, latent: LatentBenchmark,
                      config: Configuration, latent_bytes: bytes) -> None:
    validate_benchmark(benchmark, config)
    if benchmark.provenance.latent_sha256 != sha256(latent_bytes).hexdigest():
        raise ValueError("rendered provenance does not match latent file SHA-256")
    originals = {case.id: case for case in latent.cases}
    if set(originals) != {case.id for case in benchmark.cases}:
        raise ValueError("rendered case IDs do not match latent case IDs")
    for case in benchmark.cases:
        metadata = case.model_dump(exclude={"response_id"})
        del metadata["form"]["description"]
        if metadata != originals[case.id].model_dump():
            raise ValueError(f"{case.id}: rendered metadata differs from frozen latent case")
