"""Offline fixtures are constructed independently of the frozen benchmark."""

import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import httpx
from openai import OpenAI, APIConnectionError, APIStatusError, APITimeoutError
from pydantic import ValidationError

from meridian.data import load_config
from meridian.evaluate import aggregate_calls, economics, evaluate, publish_json, score_case, summarize
from meridian.triage import (
    CallMetadata, SubmittedEnquiry, TriageAssessment, TriageResult,
    build_request, route, triage, validate_assessment,
)

ROOT = Path(__file__).resolve().parents[1]


def assessment(**changes):
    data = dict(summary="A bounded analysis request.", service_line="data_ai", complexity="simple",
                disposition="clear", alternative_service_lines=[], review_reasons=[])
    return TriageAssessment(**(data | changes))


def intake(**changes):
    return SubmittedEnquiry(**(dict(description="Please analyze the supplied figures.", industry="retail",
                                   company_size="small", urgency="normal") | changes))


def fake_response(parsed=None, **changes):
    response = SimpleNamespace(id="resp_fixture", model="configured-model", status="completed",
                               usage=SimpleNamespace(input_tokens=100, output_tokens=25,
                                                     output_tokens_details=SimpleNamespace(reasoning_tokens=10)),
                               output=[], output_parsed=parsed or assessment())
    response.__dict__.update(changes)
    response.model_dump = lambda **kwargs: {"id": response.id, "status": response.status}
    return response


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT)

    def routed(self, value=None, size="small", urgency="normal"):
        return route(value or assessment(), size, urgency, self.config.routing)

    def test_default_complex_enterprise_and_policy_flags(self):
        leads = self.config.routing.service_lines["data_ai"]
        self.assertEqual(self.routed().destination, leads.default_lead)
        self.assertEqual(self.routed(assessment(complexity="complex")).rule, "complex_to_senior_lead")
        self.assertEqual(self.routed(size="enterprise").destination, leads.senior_lead)
        self.assertEqual(self.routed(size="enterprise").rule, "enterprise_to_senior_lead")
        self.config.routing.policy.complex_to_senior_lead = False
        self.config.routing.policy.enterprise_to_senior_lead = False
        self.assertEqual(self.routed(assessment(complexity="complex"), "enterprise").destination, leads.default_lead)

    def test_review_overrides_and_urgency(self):
        for disposition in ("ambiguous", "insufficient_information", "out_of_scope"):
            value = assessment(disposition=disposition, service_line=None, complexity="complex",
                               alternative_service_lines=["data_ai", "technology_systems"], review_reasons=["Needs review."])
            result = self.routed(value, "enterprise", "urgent")
            self.assertEqual(result.mode, "review")
            self.assertEqual(result.destination, self.config.routing.review.queue)
            self.assertEqual(result.priority, self.config.routing.review.priority)
        normal, urgent = self.routed(), self.routed(urgency="urgent")
        self.assertEqual(normal.destination, urgent.destination)
        self.assertEqual(normal.service_line, urgent.service_line)
        self.assertNotEqual(normal.target_response, urgent.target_response)
        self.assertNotEqual(normal.priority, urgent.priority)

    def test_saved_assessment_reroutes_without_client(self):
        saved = TriageAssessment.model_validate_json(assessment().model_dump_json())
        self.config.routing.service_lines["data_ai"].default_lead = "Replacement owner"
        with patch("meridian.triage.OpenAI") as client:
            self.assertEqual(self.routed(saved).destination, "Replacement owner")
            client.assert_not_called()

    def test_invariants_and_config_ids(self):
        invalid = [dict(service_line=None), dict(complexity=None), dict(review_reasons=["Review"]),
                   dict(alternative_service_lines=["data_ai"]),
                   dict(alternative_service_lines=["technology_systems", "technology_systems"]),
                   dict(summary=" "), dict(disposition="insufficient_information"),
                   dict(disposition="ambiguous", service_line=None, review_reasons=["Review"], alternative_service_lines=["data_ai"]),
                   dict(disposition="out_of_scope", review_reasons=["Unsupported"])]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                assessment(**changes)
        for changes in (dict(service_line="unknown"), dict(alternative_service_lines=["unknown"])):
            with self.assertRaises(ValueError):
                validate_assessment(assessment(**changes), self.config.taxonomy.service_lines)
            self.assertEqual(self.routed(assessment(**changes)).mode, "review")
        partial = assessment(disposition="insufficient_information", review_reasons=["Missing detail."])
        self.assertEqual(self.routed(partial).service_line, "data_ai")
        tampered = assessment().model_copy(update={"complexity": None})
        self.assertEqual(self.routed(tampered).mode, "review")

    def test_request_allowlist_even_with_extra_subclass_fields(self):
        class PoisonedIntake(SubmittedEnquiry):
            expected: str = "SECRET_EXPECTED"
            rationale: str = "SECRET_RATIONALE"
            cohort: str = "SECRET_COHORT"
            tags: str = "SECRET_TAGS"
            response_id: str = "SECRET_RESPONSE"
            id: str = "SECRET_ID"
        submitted = PoisonedIntake(**intake().model_dump())
        request = build_request(submitted, self.config.firm, self.config.taxonomy, self.config.models.classification)
        self.assertEqual(json.loads(request["input"][0]["content"]), intake().model_dump())
        self.assertEqual(set(request), {"model", "reasoning", "store", "instructions", "input", "text_format"})
        self.assertFalse(request["store"])
        self.assertEqual(request["model"], self.config.models.classification.model)
        self.assertEqual(request["reasoning"], {"effort": self.config.models.classification.reasoning_effort})
        self.assertIs(request["text_format"], TriageAssessment)
        text = request["instructions"] + request["input"][0]["content"]
        self.assertNotIn("SECRET_", text)
        self.assertNotIn("misroute_cost", text)
        for leads in self.config.routing.service_lines.values():
            self.assertNotIn(leads.default_lead, text)
            self.assertNotIn(leads.senior_lead, text)
        for changes in (dict(company_size="tiny"), dict(urgency="immediate")):
            with self.assertRaises(ValueError):
                build_request(intake(**changes), self.config.firm, self.config.taxonomy, self.config.models.classification)

    def test_success_metadata_and_single_call(self):
        client = Mock()
        client.responses.parse.return_value = fake_response()
        sink = Mock()
        result = triage(**intake().model_dump(), config=self.config, client=client, evidence_sink=sink)
        self.assertEqual(result.metadata.state, "completed")
        self.assertEqual(result.metadata.reasoning_tokens, 10)
        self.assertEqual(result.routing.mode, "automatic")
        self.assertEqual(client.responses.parse.call_count, 1)
        sink.assert_called_once()

    def test_operational_fallbacks(self):
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        failures = [
            (APITimeoutError(request), "timeout"),
            (APIConnectionError(request=request), "connection_error"),
            (APIStatusError("private body", response=httpx.Response(503, request=request), body={"secret": "private"}), "api_status_error"),
            (ValueError("private invalid value"), "invalid_structured_semantics"),
        ]
        responses = [(fake_response(status="incomplete"), "incomplete_response"),
                     (fake_response(output_parsed=None), "missing_structured_output"),
                     (fake_response(output=[SimpleNamespace(content=[SimpleNamespace(type="refusal")])]), "refusal"),
                     (fake_response(assessment(service_line="unknown")), "invalid_structured_semantics")]
        for failure, reason in failures + responses:
            with self.subTest(reason=reason):
                client = Mock()
                if isinstance(failure, Exception):
                    client.responses.parse.side_effect = failure
                else:
                    client.responses.parse.return_value = failure
                result = triage(**intake().model_dump(), config=self.config, client=client)
                self.assertIsNone(result.assessment)
                self.assertEqual(result.routing.mode, "review")
                self.assertEqual(result.metadata.failure_reason, reason)
                self.assertNotIn("private", result.model_dump_json())
                self.assertEqual(client.responses.parse.call_count, 1)

    def test_real_sdk_structured_parse_offline(self):
        captured = []
        def transport(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200, json={
                "id": "resp_mock", "object": "response", "created_at": 1, "model": "mock",
                "status": "completed", "parallel_tool_calls": False, "tool_choice": "auto", "tools": [],
                "output": [{"type": "message", "id": "msg_mock", "role": "assistant", "status": "completed",
                            "content": [{"type": "output_text", "text": assessment().model_dump_json(), "annotations": []}]}],
            })
        with OpenAI(api_key="offline-test", max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(transport))) as client:
            result = triage(**intake().model_dump(), config=self.config, client=client)
        self.assertEqual(result.metadata.state, "completed")
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["text"]["format"]["type"], "json_schema")
        self.assertTrue(captured[0]["text"]["format"]["strict"])
        self.assertFalse(captured[0]["store"])


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT)

    def row(self, expected, predicted, **changes):
        submitted = intake(**changes)
        result = TriageResult(assessment=predicted,
                              routing=route(predicted, submitted.company_size, submitted.urgency, self.config.routing),
                              metadata=CallMetadata(model="mock", state="completed" if predicted else "operational_fallback"))
        key = expected.model_dump(exclude={"summary", "review_reasons"})
        return {"prediction": result.model_dump(), **score_case(result, key, submitted, self.config.routing)}

    def test_metrics_mixed_fixture_and_confusion(self):
        clear = assessment()
        review = assessment(disposition="insufficient_information", review_reasons=["Missing context"])
        rows = [self.row(clear, clear), self.row(clear, assessment(service_line="technology_systems")),
                self.row(clear, None), self.row(review, review), self.row(review, clear)]
        metrics, diagnostics = summarize(rows)
        expected = {"automation_coverage": (3, 5), "selective_route_accuracy": (1, 3),
                    "unsafe_automation_rate": (2, 5), "review_recall": (1, 2),
                    "unnecessary_review_rate": (1, 3), "service_line_accuracy": (3, 5),
                    "complexity_accuracy": (4, 5)}
        for name, (num, den) in expected.items():
            self.assertEqual(metrics[name], {"numerator": num, "denominator": den, "value": num / den})
        self.assertEqual(diagnostics["exact_disposition_accuracy"]["value"], 3 / 5)
        self.assertEqual(diagnostics["disposition_confusion"]["counts"]["clear"]["operational_fallback"], 1)
        self.assertIn("unsafe_automatic_route", rows[-1]["failure_reasons"])
        self.assertEqual(aggregate_calls(rows)["usage"]["input_tokens"]["total_observed"], "n/a")

    def test_zero_denominators_and_partial_semantics(self):
        metrics, _ = summarize([])
        self.assertTrue(all(m["value"] == "n/a" for m in metrics.values()))
        partial = assessment(disposition="insufficient_information", review_reasons=["Context missing"], complexity=None)
        unknown = assessment(disposition="out_of_scope", service_line=None, complexity=None, review_reasons=["Unsupported"])
        metrics, _ = summarize([self.row(partial, partial), self.row(unknown, unknown)])
        self.assertEqual(metrics["service_line_accuracy"]["denominator"], 1)
        self.assertEqual(metrics["complexity_accuracy"]["value"], "n/a")
        self.assertEqual(metrics["selective_route_accuracy"]["value"], "n/a")
        self.assertEqual(metrics["unnecessary_review_rate"]["value"], "n/a")

    def test_final_lead_is_scored_independently_of_complexity(self):
        # Enterprise policy can make a wrong complexity label yield the correct lead.
        row = self.row(assessment(complexity="complex"), assessment(), company_size="enterprise")
        self.assertTrue(row["correct_automatic_route"])
        self.assertFalse(row["complexity_correct"])
        row = self.row(assessment(complexity="complex"), assessment())
        self.assertFalse(row["correct_automatic_route"])

    def test_economics_and_zero_wrong(self):
        result = economics(10, 2, 1, self.config.economics)
        self.assertEqual(result["break_even_misroute_multiple"], 8)
        first = result["scenarios"][0]
        self.assertEqual(first["manual_cost_minutes"], 96)
        self.assertAlmostEqual(first["system_cost_minutes"], 28.8)
        self.assertAlmostEqual(first["savings_minutes"], 67.2)
        self.assertAlmostEqual(first["system_manual_ratio"], .3)
        zero = economics(10, 2, 0, self.config.economics)
        self.assertEqual(zero["break_even_misroute_multiple"], "n/a")
        self.assertEqual(len({s["system_cost_minutes"] for s in zero["scenarios"]}), 1)
        self.assertEqual(economics(0, 0, 0, self.config.economics)["scenarios"][0]["system_manual_ratio"], "n/a")

    def test_evaluator_predicts_all_before_reading_keys(self):
        client = Mock()
        client.responses.parse.return_value = fake_response()
        expected = assessment().model_dump(exclude={"summary", "review_reasons"})
        class GuardedCase(dict):
            def __getitem__(case, key):
                if key == "expected":
                    self.assertEqual(client.responses.parse.call_count, 2)
                return super().__getitem__(key)
        cases = [GuardedCase(id=f"fixture-{i}", form=intake().model_dump(), expected=expected,
                             rationale="SECRET_KEY", tags=["SECRET_TAG"], cohort="SECRET_COHORT")
                 for i in range(2)]
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / "config", root / "config")
            for name in ("uv.lock", "SPEC.md", "EVALUATION.md"):
                shutil.copyfile(ROOT / name, root / name)
            (root / "eval").mkdir()
            (root / "eval/cases.yaml").write_text("offline placeholder")
            output = root / "eval/results/initial.json"
            with patch.dict("os.environ", {"OPENAI_API_KEY": "offline-test"}), \
                 patch("meridian.evaluate.load_config", return_value=self.config), \
                 patch("meridian.evaluate.yaml.load", return_value={"cases": cases}), \
                 patch("meridian.evaluate.subprocess.check_output", return_value="fixture-head"), \
                 patch("meridian.evaluate.OpenAI") as factory, patch("builtins.print"):
                factory.return_value.__enter__.return_value = client
                artifact = evaluate(root, output)
            self.assertEqual(artifact["metrics"]["selective_route_accuracy"]["value"], 1)
            self.assertEqual(artifact["observability"]["usage"]["input_tokens"]["total_observed"], 200)
            self.assertEqual(len(list((root / artifact["evidence_directory"]).glob("*.json"))), 3)
            self.assertEqual(json.loads(output.read_text()), artifact)
            factory.assert_called_once_with(timeout=120, max_retries=0)
            for call in client.responses.parse.call_args_list:
                self.assertNotIn("SECRET", str(call.kwargs))

    def test_exclusive_results_and_no_calls_when_unavailable(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "initial.json"
            publish_json(output, {"original": True})
            with self.assertRaises(FileExistsError):
                publish_json(output, {"replacement": True})
            self.assertEqual(json.loads(output.read_text()), {"original": True})
            with patch("meridian.evaluate.OpenAI") as client:
                with self.assertRaises(ValueError):
                    evaluate(ROOT, output)
                with patch.dict("os.environ", {"OPENAI_API_KEY": ""}), self.assertRaises(ValueError):
                    evaluate(ROOT, Path(temporary) / "missing.json")
                client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
