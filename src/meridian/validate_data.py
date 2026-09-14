"""Run with: uv run python -m meridian.validate_data [--root PATH]."""

import argparse
from pathlib import Path

from .data import load_config, load_latent, load_yaml, validate_rendered
from .models import RenderedBenchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate config and benchmark offline.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        config = load_config(args.root)
        latent = load_latent(args.root, config)
        print("Validated all five configuration files and 30 latent cases.")
        path = args.root / "eval/cases.yaml"
        if path.exists():
            rendered = load_yaml(path, RenderedBenchmark)
            validate_rendered(rendered, latent, config,
                              (args.root / "eval/latent_cases.yaml").read_bytes())
            print("Validated 30 rendered cases, frozen metadata, and latent provenance.")
        else:
            print("eval/cases.yaml is absent; rendered validation skipped.")
    except ValueError as exc:
        parser.exit(1, f"Validation failed: {exc}\n")


if __name__ == "__main__":
    main()
