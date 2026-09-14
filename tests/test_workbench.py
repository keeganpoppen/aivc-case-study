"""Local workbench boundaries; all provider calls are mocked."""

import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from openai import OpenAIError

from meridian.data import load_config, load_yaml
from meridian.evaluate import score_case
from meridian.models import RenderedBenchmark
from meridian.triage import CallMetadata, SubmittedEnquiry, TriageResult, route
from meridian.workbench import GeneratedEnquiry, create_app, generate_enquiry, site_data

ROOT = Path(__file__).resolve().parents[1]


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT)
        self.cases = load_yaml(ROOT / "eval/cases.yaml", RenderedBenchmark).cases
        self.client = TestClient(create_app(ROOT))
        self.addCleanup(self.client.close)
        self.intake = SubmittedEnquiry(**self.cases[0].form.model_dump())
        self.fallback = TriageResult(
            assessment=None, metadata=CallMetadata(model="mock", failure_reason="timeout"),
            routing=route(None, self.intake.company_size, self.intake.urgency,
                          self.config.routing, failure_reason="timeout"))

    def test_browser_projection_and_snapshot(self):
        rows = self.client.get("/api/cases").json()
        self.assertEqual(len(rows), 30)
        for row, original in zip(rows, self.cases, strict=True):
            self.assertEqual(set(row), {"id", "cohort", "form"})
            self.assertEqual(set(row["form"]), {"industry", "company_size", "urgency", "description"})
            self.assertEqual(row["form"], original.form.model_dump())
        public = self.client.get("/api/config").json()
        self.assertEqual(public["company_size"], self.config.firm.intake.fields.company_size.model_dump()["values"])
        self.assertEqual(public["snapshot"], json.loads((ROOT / "eval/results/initial.json").read_text())["metrics"])
        self.assertNotIn("cases", public)
        self.assertNotIn("expected", self.client.get("/").text)

    def test_triage_delegates_and_preserves_operational_review(self):
        with patch("meridian.workbench.pipeline.triage", return_value=self.fallback) as run:
            response = self.client.post("/api/triage", json=self.intake.model_dump())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), self.fallback.model_dump())
            run.assert_called_once_with(**self.intake.model_dump(), config=self.config)
            self.assertNotIn("evidence_sink", run.call_args.kwargs)
        with patch("meridian.workbench.pipeline.triage") as run:
            response = self.client.post("/api/triage", json=self.intake.model_dump() | {"expected": {}})
            self.assertEqual(response.status_code, 422)
            run.assert_not_called()

    def test_comparison_reuses_scorer_and_current_policy(self):
        case = next(c for c in self.cases if c.id == "I02")
        intake = SubmittedEnquiry(**case.form.model_dump())
        initial = json.loads((ROOT / "eval/results/initial.json").read_text())
        result = TriageResult.model_validate(next(c for c in initial["cases"] if c["id"] == case.id)["prediction"])
        changed = self.config.model_copy(deep=True)
        changed.routing.review.queue = "New review queue"
        with patch("meridian.workbench.load_config", return_value=changed):
            with TestClient(create_app(ROOT)) as client:
                response = client.post("/api/cases/I02/expected", json={"intake":intake.model_dump(), "result":result.model_dump()})
        self.assertEqual(response.json(), score_case(result, case.expected, intake, changed.routing))
        self.assertEqual(response.json()["expected_route"]["destination"], "New review queue")
        self.assertIn("unsafe_automatic_route", response.json()["failure_reasons"])
        # Automatic expected leads also come from current policy, never saved result leads.
        changed.routing.service_lines["strategy_transformation"].default_lead = "New owner"
        with patch("meridian.workbench.load_config", return_value=changed):
            with TestClient(create_app(ROOT)) as client:
                response = client.post("/api/cases/S01/expected", json={"intake":self.intake.model_dump(), "result":self.fallback.model_dump()})
        self.assertEqual(response.json()["expected_route"]["destination"], "New owner")

    def test_modified_input_rejected_and_artifacts_unchanged(self):
        paths = [*sorted((ROOT / "eval").rglob("*")), *sorted((ROOT / "config").glob("*.yaml"))]
        before = {p:p.read_bytes() for p in paths if p.is_file()}
        edited = self.intake.model_dump() | {"description":"An edited enquiry."}
        with patch("meridian.workbench.pipeline.triage", return_value=self.fallback), patch(
                "meridian.workbench.generate_enquiry", return_value=GeneratedEnquiry(**edited)):
            self.assertEqual(self.client.post("/api/triage", json=edited).status_code, 200)
            self.assertEqual(self.client.post("/api/generate", json={"prompt":"A fictional request"}).status_code, 200)
            self.assertEqual(self.client.post("/api/cases/S01/expected", json={"intake":edited, "result":self.fallback.model_dump()}).status_code, 409)
            self.assertEqual(self.client.post("/api/cases/missing/expected", json={"intake":edited, "result":self.fallback.model_dump()}).status_code, 404)
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                for url in ("/api/cases", "/api/config", "/eval/cases.yaml", "/eval/results/initial.json", "/static/../eval/cases.yaml"):
                    self.assertIn(self.client.request(method,url,json={}).status_code, (404,405))
        self.assertEqual(self.client.get("/api/cases").json()[0]["form"], self.intake.model_dump())
        self.assertEqual(before, {p:p.read_bytes() for p in before})
        self.assertEqual(set(paths), set([*sorted((ROOT / "eval").rglob("*")), *sorted((ROOT / "config").glob("*.yaml"))]))

    def test_generator_request_is_isolated_and_structured(self):
        generated = GeneratedEnquiry(**self.intake.model_dump())
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(status="completed", output_parsed=generated)
        with patch("meridian.workbench.OpenAI") as sdk:
            sdk.return_value.__enter__.return_value = client
            actual = generate_enquiry("A tiny manufacturer with a gnarly ERP migration", self.config.firm, self.config.models.synthetic_rendering)
        self.assertEqual(actual, generated)
        sdk.assert_called_once_with(timeout=120, max_retries=0)
        request = client.responses.parse.call_args.kwargs
        self.assertEqual(client.responses.parse.call_count, 1)
        self.assertEqual(request["model"], self.config.models.synthetic_rendering.model)
        self.assertEqual(request["reasoning"], {"effort":self.config.models.synthetic_rendering.reasoning_effort})
        self.assertFalse(request["store"])
        self.assertIs(request["text_format"], GeneratedEnquiry)
        payload = json.loads(request["input"][0]["content"])
        self.assertEqual(set(payload), {"scenario", "choices"})
        self.assertEqual(set(payload["choices"]), {"company_size", "urgency"})
        text = request["instructions"] + request["input"][0]["content"]
        for case in self.cases:
            for private in (case.form.description, case.rationale, case.seed.requested_outcome, case.response_id):
                self.assertNotIn(private,text)
        for key, leads in self.config.routing.service_lines.items():
            for private in (key, leads.default_lead, leads.senior_lead):
                self.assertNotIn(private,text)

    def test_generation_errors_leave_browser_data_available(self):
        for error in (OpenAIError("private credential details"), ValueError("private output")):
            with patch("meridian.workbench.generate_enquiry", side_effect=error):
                response = self.client.post("/api/generate",json={"prompt":"An enquiry"})
            self.assertEqual(response.status_code,503)
            self.assertNotIn("private",response.text)
            self.assertEqual(self.client.get("/api/cases").status_code,200)
        self.assertEqual(self.client.post("/api/generate",json={"prompt":" "}).status_code,422)

    def test_site_pages_and_public_projection(self):
        public = self.client.get("/api/site").json()
        self.assertEqual(set(public), {"firm", "practices", "people"})
        self.assertEqual(len(public["practices"]), 6)
        self.assertEqual(len(public["people"]), 12)
        self.assertIn('site-content', self.client.get("/").text)
        self.assertIn('id="intake"', self.client.get("/workbench").text)
        for key, practice in public["practices"].items():
            original = self.config.taxonomy.service_lines[key]
            self.assertEqual(practice["name"], original.name)
            self.assertEqual(practice["owns"], original.owns)
            self.assertEqual(practice["boundary"], original.boundary)
            self.assertEqual(practice["complexity_signals"], original.complexity_signals.model_dump())
            self.assertEqual(self.client.get(f"/practices/{key}").status_code, 200)
            for role in ("default_lead", "senior_lead"):
                person = public["people"][practice[role]]
                self.assertEqual(person["name"], getattr(self.config.routing.service_lines[key], role))
                self.assertEqual(self.client.get(f"/people/{person['slug']}").status_code, 200)
        for url in ("/people/missing", "/practices/missing"):
            self.assertEqual(self.client.get(url).status_code, 404)
        encoded = json.dumps(public)
        for case in self.cases:
            for private in (case.rationale, case.response_id, case.form.description):
                self.assertNotIn(private, encoded)
        for private in ('"expected"', '"seed"', '"snapshot"', 'OPENAI_API_KEY'):
            self.assertNotIn(private, encoded)

    def test_site_people_follow_config_and_router(self):
        changed = self.config.model_copy(deep=True)
        changed.routing.service_lines["data_ai"].default_lead = "New Person"
        changed.routing.policy.enterprise_to_senior_lead = False
        changed.routing.policy.complex_to_senior_lead = False
        changed.taxonomy.service_lines["data_ai"].name = "Renamed practice"
        public = site_data(changed)
        self.assertEqual(public["practices"]["data_ai"]["name"], "Renamed practice")
        self.assertEqual(public["practices"]["data_ai"]["default_lead"], "new-person")
        role = public["people"]["new-person"]["roles"][0]
        self.assertEqual(role["role"], "Practice Lead")
        self.assertEqual(len(role["routing_examples"]), 3)
        self.assertTrue(all(e["complexities"] == ["simple", "moderate", "complex"] for e in role["routing_examples"]))
        senior = public["people"][public["practices"]["data_ai"]["senior_lead"]]
        self.assertEqual(senior["roles"][0]["routing_examples"], [])

    def test_static_and_local_browser_boundary(self):
        for url in ("/", "/workbench", "/static/site.js", "/static/workbench.js", "/static/workbench.css"):
            response = self.client.get(url)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers["cache-control"],"no-store")
        self.assertEqual(self.client.post("/api/triage",json=self.intake.model_dump(),headers={"Origin":"https://unrelated.example"}).status_code,403)
        self.assertEqual(self.client.get("/",headers={"Host":"unrelated.example"}).status_code,400)
        self.assertEqual(self.client.post("/api/triage",content="{}").status_code,415)


if __name__ == "__main__":
    unittest.main()
