"""Typed representations of the authored YAML, without classification or routing."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
Complexity = Literal["simple", "moderate", "complex"]
Disposition = Literal["clear", "ambiguous", "insufficient_information", "out_of_scope"]
ReviewDisposition = Literal["ambiguous", "insufficient_information", "out_of_scope"]
Cohort = Literal["straightforward", "hard_routeable", "ambiguous", "insufficient", "out_of_scope"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)


class Versioned(Model):
    version: Literal[1]


class Firm(Model):
    id: Text
    name: Text
    fictional: bool
    description: Text
    positioning: Text
    typical_buyers: list[Text]


class FreeTextField(Model):
    type: Literal["free_text"]
    required: bool
    description: Text


class EnumValue(Model):
    display: Text


class EnumField(Model):
    type: Literal["enum"]
    required: bool
    values: dict[Text, EnumValue] = Field(min_length=1)


class IntakeFields(Model):
    description: FreeTextField
    industry: FreeTextField
    company_size: EnumField
    urgency: EnumField


class Intake(Model):
    fields: IntakeFields


class FirmConfig(Versioned):
    firm: Firm
    intake: Intake
    interpretation: list[Text]


class ClassificationPolicy(Model):
    primary_owner: Text
    multiple_practices: Text
    out_of_scope: Text
    insufficient_information: Text


class Eligibility(Model):
    excluded_industries: list[Text]


class GlobalEligibility(Eligibility):
    notes: Text


class EligibilityConfig(Model):
    global_: GlobalEligibility = Field(alias="global")


class ComplexityGuidance(Model):
    simple: Text
    moderate: Text
    complex: Text
    principles: list[Text]


class ComplexityConfig(Model):
    global_: ComplexityGuidance = Field(alias="global")


class ComplexitySignals(Model):
    simple: list[Text]
    moderate: list[Text]
    complex: list[Text]


class ServiceLine(Model):
    name: Text
    owns: list[Text]
    boundary: Text
    eligibility: Eligibility
    complexity_signals: ComplexitySignals


class TaxonomyConfig(Versioned):
    classification_policy: ClassificationPolicy
    eligibility: EligibilityConfig
    complexity: ComplexityConfig
    service_lines: dict[Text, ServiceLine] = Field(min_length=1)


class ReviewQueue(Model):
    queue: Text
    priority: Text


class RoutingPolicy(Model):
    enterprise_company_size: Text
    complex_to_senior_lead: bool
    enterprise_to_senior_lead: bool
    review_dispositions: list[ReviewDisposition]


class Priority(Model):
    level: Text
    target_response: Text


class Leads(Model):
    default_lead: Text
    senior_lead: Text


class RoutingConfig(Versioned):
    review: ReviewQueue
    policy: RoutingPolicy
    priority: dict[Text, Priority]
    service_lines: dict[Text, Leads]
    notes: list[Text]


class WeeklyEnquiries(Model):
    low: int = Field(gt=0)
    midpoint: int = Field(gt=0)
    high: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self):
        if not self.low <= self.midpoint <= self.high:
            raise ValueError("weekly enquiries must satisfy low <= midpoint <= high")
        return self


class ManualBaseline(Model):
    weekly_enquiries: WeeklyEnquiries
    analyst_hours_per_week: float = Field(gt=0, allow_inf_nan=False)
    derived_minutes_per_enquiry_at_midpoint: float = Field(gt=0, allow_inf_nan=False)
    note: Text

    @model_validator(mode="after")
    def consistent_derivation(self):
        from math import isclose

        calculated = self.analyst_hours_per_week * 60 / self.weekly_enquiries.midpoint
        if not isclose(self.derived_minutes_per_enquiry_at_midpoint, calculated):
            raise ValueError("derived minutes disagree with hours and midpoint volume")
        return self


class EconomicEvaluation(Model):
    human_review_cost_multiple: float = Field(ge=0, allow_inf_nan=False)
    misroute_cost_multiples: list[Annotated[float, Field(ge=0, allow_inf_nan=False)]]
    interpretation: list[Text]


class EconomicsConfig(Versioned):
    manual_baseline: ManualBaseline
    evaluation: EconomicEvaluation


class ModelSettings(Model):
    model: Text
    reasoning_effort: Text
    rationale: Text


class ModelsConfig(Versioned):
    provider: Literal["openai"]
    api: Literal["responses"]
    store_responses: Literal[False]
    classification: ModelSettings
    synthetic_rendering: ModelSettings


class Configuration(Model):
    firm: FirmConfig
    taxonomy: TaxonomyConfig
    routing: RoutingConfig
    economics: EconomicsConfig
    models: ModelsConfig

    @model_validator(mode="after")
    def references(self):
        fields = self.firm.intake.fields
        if set(self.routing.service_lines) != set(self.taxonomy.service_lines):
            raise ValueError("routing service-line IDs must match taxonomy IDs")
        if self.routing.policy.enterprise_company_size not in fields.company_size.values:
            raise ValueError("routing enterprise_company_size is not configured in firm")
        if set(self.routing.priority) != set(fields.urgency.values):
            raise ValueError("routing priority keys must match firm urgency values")
        reviews = self.routing.policy.review_dispositions
        if len(reviews) != len(set(reviews)):
            raise ValueError("duplicate routing review dispositions")
        return self


class Form(Model):
    industry: Text
    company_size: Text
    urgency: Text


class Seed(Model):
    requested_outcome: Text
    facts: list[Text] = Field(min_length=1)
    rendering_style: Text


class Expected(Model):
    disposition: Disposition
    service_line: Text | None
    complexity: Complexity | None
    alternative_service_lines: list[Text]

    @model_validator(mode="after")
    def semantics(self):
        alternatives = self.alternative_service_lines
        if len(alternatives) != len(set(alternatives)):
            raise ValueError("alternative service-line IDs must be nonduplicated")
        if self.disposition == "clear" and (self.service_line is None or self.complexity is None):
            raise ValueError("clear requires a primary service line and complexity")
        if self.disposition == "ambiguous" and (self.service_line is not None or len(alternatives) < 2):
            raise ValueError("ambiguous requires no primary service line and at least two alternatives")
        if self.disposition == "out_of_scope" and self.service_line is not None:
            raise ValueError("out_of_scope requires no primary service line")
        return self


class LatentCase(Model):
    id: Text
    cohort: Cohort
    form: Form
    seed: Seed
    expected: Expected
    rationale: Text
    tags: list[Text]


class LatentBenchmark(Versioned):
    notes: list[Text]
    cases: list[LatentCase]


class RenderedForm(Form):
    description: Text


class RenderedCase(LatentCase):
    form: RenderedForm
    response_id: Text


class RenderProvenance(Model):
    latent_file: Literal["eval/latent_cases.yaml"]
    latent_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    model: Text
    reasoning_effort: Text
    renderer_instruction: Text
    generated_at: Text
    raw_responses: Text


class RenderedBenchmark(Versioned):
    notes: list[Text]
    provenance: RenderProvenance
    cases: list[RenderedCase]
