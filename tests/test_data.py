"""Contract mutations and rendering boundary checks; no network calls."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from meridian.data import load_config, load_latent, load_yaml, validate_benchmark, validate_rendered
from meridian.models import LatentBenchmark, RenderedBenchmark
from meridian.render_cases import RENDERER_INSTRUCTION, RenderingResult, render, render_description

ROOT = Path(__file__).resolve().parents[1]


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT)
        cls.latent = load_latent(ROOT, cls.config)

    def test_frozen_data_and_partial_semantics(self):
        case = next(c for c in self.latent.cases if c.id == "I02")
        self.assertEqual(case.expected.service_line, "technology_systems")
        self.assertEqual(case.expected.complexity, "moderate")

    def test_invalid_benchmark_mutations(self):
        mutations = {
            "count": lambda d: d["cases"].pop(),
            "duplicate ID": lambda d: d["cases"][1].update(id="S01"),
            "cohort": lambda d: d["cases"][0].update(cohort="hard_routeable"),
            "size": lambda d: d["cases"][0]["form"].update(company_size="tiny"),
            "urgency": lambda d: d["cases"][0]["form"].update(urgency="ASAP"),
            "primary": lambda d: d["cases"][0]["expected"].update(service_line="unknown"),
            "complexity": lambda d: d["cases"][0]["expected"].update(complexity="easy"),
            "alternative": lambda d: d["cases"][0]["expected"].update(alternative_service_lines=["unknown"]),
            "duplicate alternative": lambda d: d["cases"][0]["expected"].update(alternative_service_lines=["data_ai", "data_ai"]),
            "clear line": lambda d: d["cases"][0]["expected"].update(service_line=None),
            "clear complexity": lambda d: d["cases"][0]["expected"].update(complexity=None),
            "ambiguous primary": lambda d: d["cases"][24]["expected"].update(service_line="data_ai"),
            "ambiguous alternatives": lambda d: d["cases"][24]["expected"].update(alternative_service_lines=["data_ai"]),
            "out of scope primary": lambda d: d["cases"][-1]["expected"].update(service_line="data_ai"),
            "coverage": lambda d: d["cases"][0]["expected"].update(complexity="moderate"),
            "extra key": lambda d: d["cases"][0].update(unexpected=True),
            "type coercion": lambda d: d["cases"][0]["form"].update(industry=42),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                data = deepcopy(self.latent.model_dump())
                mutate(data)
                validate_benchmark(LatentBenchmark.model_validate(data), self.config)

    def test_yaml_duplicate_keys_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.yaml"
            path.write_text("version: 1\nversion: 1\nnotes: []\ncases: []\n")
            with self.assertRaisesRegex(ValueError, "duplicate YAML key"):
                load_yaml(path, LatentBenchmark)

    def test_config_references_rejected(self):
        from meridian.models import Configuration
        for section, mutation in [
            ("routing", lambda d: d["service_lines"].update(unknown=d["service_lines"]["data_ai"])),
            ("routing", lambda d: d["policy"].update(enterprise_company_size="unknown")),
            ("routing", lambda d: d["priority"].pop("urgent")),
            ("models", lambda d: d.update(store_responses=True)),
        ]:
            with self.subTest(section=section), self.assertRaises(ValueError):
                data = self.config.model_dump(by_alias=True)
                mutation(data[section])
                Configuration.model_validate(data)

    def test_request_contains_exactly_form_seed(self):
        client = SimpleNamespace(responses=SimpleNamespace(parse=Mock()))
        for case in self.latent.cases:
            render_description(client, self.config.models.synthetic_rendering, case.form, case.seed)
            request = client.responses.parse.call_args.kwargs
            self.assertEqual(json.loads(request["input"][0]["content"]),
                             {"form": case.form.model_dump(), "seed": case.seed.model_dump()})
            self.assertEqual(request["instructions"], RENDERER_INSTRUCTION)
            self.assertIs(request["store"], False)
            self.assertIs(request["text_format"], RenderingResult)
            self.assertEqual(set(request), {"model", "reasoning", "store", "instructions", "input", "text_format"})

    def test_rendered_metadata_and_provenance(self):
        raw = (ROOT / "eval/latent_cases.yaml").read_bytes()
        data = self.latent.model_dump()
        data["provenance"] = dict(latent_file="eval/latent_cases.yaml", latent_sha256=sha256(raw).hexdigest(),
                                  model="test", reasoning_effort="low", renderer_instruction=RENDERER_INSTRUCTION,
                                  generated_at="test", raw_responses="test")
        for case in data["cases"]:
            case["form"]["description"] = "Test fixture only."
            case["response_id"] = "test-" + case["id"]
        benchmark = RenderedBenchmark.model_validate(data)
        validate_rendered(benchmark, self.latent, self.config, raw)
        for field, value in [("rationale", "changed"), ("id", "changed")]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                changed = deepcopy(data)
                changed["cases"][0][field] = value
                validate_rendered(RenderedBenchmark.model_validate(changed), self.latent, self.config, raw)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            validate_rendered(benchmark, self.latent, self.config, raw + b"\n")

    def test_refusal_never_publishes(self):
        import shutil
        with TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "config", root / "config")
            (root / "eval").mkdir()
            shutil.copyfile(ROOT / "eval/latent_cases.yaml", root / "eval/latent_cases.yaml")
            response = SimpleNamespace(status="completed", output_parsed=None, id="test-refusal",
                                       model_dump_json=lambda **kw: '{"refusal": "test"}')
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test"}), patch("meridian.render_cases.OpenAI") as client:
                client.return_value.__enter__.return_value.responses.parse.return_value = response
                with self.assertRaisesRegex(ValueError, "refused"):
                    render(root)
            self.assertFalse((root / "eval/cases.yaml").exists())
            self.assertEqual(len(list((root / ".local/render-runs").glob("*/S01.json"))), 1)

    def test_missing_key_and_existing_output_make_no_calls(self):
        import shutil
        with TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "config", root / "config")
            (root / "eval").mkdir()
            shutil.copyfile(ROOT / "eval/latent_cases.yaml", root / "eval/latent_cases.yaml")
            with patch.dict("os.environ", {"OPENAI_API_KEY": ""}), patch("meridian.render_cases.OpenAI") as client:
                with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY is required"):
                    render(root)
                output = root / "eval/cases.yaml"
                output.write_text("existing frozen output")
                with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                    render(root)
                self.assertEqual(output.read_text(), "existing frozen output")
                client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
