"""Public, bounded Trace 3 evidence contract; trial truth is never source input.

``payload_canonical_json`` preserves exact hash bytes across JavaScript JSON
round trips (which otherwise change 1.0 to 1). This is a content digest, not a
signature or proof that an operator's report happened in the physical world.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, FiniteFloat, StrictBool, model_validator

from .contracts import StrictModel


def _public_identifier(value):
    if value.lower().startswith(("sk-", "sk_", "ck-", "xai-", "ghp_", "github_pat_", "ya29.", "aiza")):
        raise ValueError("Credentials cannot be exported as identifiers")
    return value


Identifier = Annotated[str, Field(min_length=1, max_length=128,
                                 pattern=r"^[A-Za-z][A-Za-z0-9_.:-]*$"),
                       AfterValidator(_public_identifier)]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Number = Annotated[FiniteFloat, Field(strict=True)]
Fraction = Annotated[FiniteFloat, Field(strict=True, ge=0, le=1)]
Count = Annotated[int, Field(strict=True, ge=0, le=10000)]
Origin = Literal["SYNTHETIC", "MEASURED_TANK"]
TrialOrigin = Literal["SYNTHETIC_DEMO", "OPERATOR_REPORTED_PHYSICAL"]
Layout = Literal["baseline", "intervention"]
Polygon = Annotated[list[tuple[Number, Number]], Field(min_length=3, max_length=65)]


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


class BoundsExport(StrictModel):
    x_min_cm: Number
    x_max_cm: Number
    y_min_cm: Number
    y_max_cm: Number


class SourceExport(StrictModel):
    id: Identifier
    polygon_cm: Polygon
    prior: Fraction | None = None


class TrapExport(StrictModel):
    id: Identifier
    polygon_cm: Polygon
    validated: Literal[True]
    retention: Literal["absorbing"]


class FlowDiagnosticsExport(StrictModel):
    sample_count: Count
    node_count: Count
    training_rmse_cm_s: Number
    loo_rmse_cm_s: Number | None
    loo_supported_nodes: Count
    grid_coverage_fraction: Fraction
    max_speed_cm_s: Number
    validation_rmse_cm_s: Number | None
    validation_coverage_fraction: Fraction | None


class FlowProvenanceExport(StrictModel):
    data_origin: Origin
    flow_id: Identifier | None
    flow_hash: Sha256
    training_recording_ids: list[Identifier] = Field(max_length=1000)
    validation_recording_ids: list[Identifier] = Field(max_length=1000)
    diagnostics: FlowDiagnosticsExport


class TransportExport(StrictModel):
    dt_s: Number
    max_age_s: Number
    diffusivity_cm2_s: Number
    drift_bias_cm_s: tuple[Number, Number]


class ScenarioExport(StrictModel):
    id: Identifier
    transport: TransportExport


class LayoutProvenanceExport(StrictModel):
    id: Identifier
    profile_hash: Sha256
    data_origin: Origin
    bounds: BoundsExport
    calibration_id: Identifier
    token_class: Identifier
    sources: list[SourceExport] = Field(min_length=2, max_length=5)
    traps: list[TrapExport] = Field(max_length=5)
    observation_polygon_cm: Polygon | None
    flow: FlowProvenanceExport
    transport: TransportExport
    scenarios: list[ScenarioExport] = Field(min_length=1, max_length=3)


class IndependenceExport(StrictModel):
    status: Literal["SYNTHETIC_NOT_PHYSICAL", "INDEPENDENT_MEASURED_RECORDING_SETS"]
    independently_measured: StrictBool
    distinct_flow_ids: StrictBool
    disjoint_layout_recording_sets: StrictBool
    outcome_validation: Literal["NOT_AUTOMATICALLY_VERIFIED"]


class ProvenanceExport(StrictModel):
    layouts: dict[Layout, LayoutProvenanceExport] = Field(min_length=2, max_length=2)
    independence: IndependenceExport


class NumericalIdentityExport(StrictModel):
    profile_id: Identifier
    profile_hash: Sha256
    flow_hash: Sha256


class SimulatedOutcomeExport(StrictModel):
    particles: Annotated[int, Field(strict=True, ge=20, le=200)]
    zone_entry_count: Count
    zone_entry_fraction: Fraction
    zone_entry_lower_fraction: Fraction
    zone_entry_upper_fraction: Fraction
    captured_before_zone_count: Count
    captured_before_zone_fraction: Fraction
    unresolved_count: Count
    unsupported_count: Count
    unsupported_fraction: Fraction
    supported_particle_fraction: Fraction
    path_coverage_fraction: Fraction


class NumericalRowExport(StrictModel):
    scenario_id: Identifier
    source_id: Identifier
    baseline: SimulatedOutcomeExport
    intervention: SimulatedOutcomeExport
    benefit_fraction: Number
    benefit_lower_fraction: Number
    benefit_upper_fraction: Number


class AssumptionsExport(StrictModel):
    outcomes: Literal["SIMULATED_FIRST_PASSAGE_NOT_PHYSICAL_TRIALS"]
    world_units: Literal["cm"]
    time_units: Literal["s"]
    boundary: Literal["reflecting_rectangle"]
    retention: Literal["perfect_absorbing_traps_no_escape_or_partial_capture"]
    flow: Literal["fixed_separate_layout_fields_no_predicted_hydrodynamic_change"]
    source_weighting: Literal["NONE_all_declared_sources_must_agree"]
    source_prior_and_release_age: Literal["NOT_USED_particles_released_at_t0"]
    support_rule: Literal["any_unsupported_time_node_until_first_event_or_horizon_is_unknown"]
    unsupported_denominator: Literal["all_particles_retained_unknown_outcomes_bound_benefit"]
    minimum_supported_particle_fraction: Literal[1.0]
    declared_profile_min_path_coverage: dict[Layout, Fraction] = Field(min_length=2, max_length=2)
    event_rule: Literal["competing_absorbing_zone_and_traps_segment_crossing_including_reflections"]
    touch_rule: Literal["boundary_contact_counts_as_entry_overlapping_geometries_rejected"]
    event_time_kind: Literal["time_node_upper_bound_resolution_dt_not_exact_exposure_time"]
    time_step_by_scenario_s: dict[Identifier, Number] = Field(min_length=1, max_length=3)
    recommendation_scope: Literal["declared_sources_and_scenarios_not_statistical_confidence"]
    monte_carlo: Literal["fixed_seed_common_random_numbers_no_sampling_confidence_claim"]
    display_paths: Literal["decimated_illustrations_not_used_for_metrics"]
    particle_time_states: Annotated[int, Field(strict=True, ge=0, le=6000000)]


class NumericalReportExport(StrictModel):
    schema_version: Literal[1]
    status: Literal["SIMULATED_COMPARISON", "WITHHELD_UNSUPPORTED_FLOW"]
    data_origin: Origin
    physical_validation: Literal[False]
    layouts: dict[Layout, NumericalIdentityExport] = Field(min_length=2, max_length=2)
    protected_zone_cm: Polygon
    horizon_s: Number
    particles_per_source: Annotated[int, Field(strict=True, ge=20, le=200)]
    seed: Annotated[int, Field(strict=True, ge=0, le=4294967295)]
    scenario_ids: list[Identifier] = Field(min_length=1, max_length=3)
    results: list[NumericalRowExport] = Field(min_length=2, max_length=15)
    robust_benefit_min: Number
    robust_benefit_max: Number
    recommendation: Literal["INTERVENTION", "BASELINE", "NO_ROBUST_RECOMMENDATION"]
    reason_codes: list[Literal["UNSUPPORTED_FLOW_PATHS", "MIXED_OR_ZERO_EFFECT"]] = Field(max_length=2)
    assumptions: AssumptionsExport


class ComparisonExport(StrictModel):
    id: Identifier
    case_id: Identifier
    case_revision: Annotated[int, Field(strict=True, ge=1)]
    source_evidence_id: Identifier
    source_evidence_status: Literal["ranked", "unknown"]
    baseline_profile_id: Identifier
    intervention_profile_id: Identifier
    protected_zone_cm: Polygon
    horizon_s: Annotated[FiniteFloat, Field(strict=True, ge=1, le=20)]
    particles: Annotated[int, Field(strict=True, ge=20, le=200)]
    trials_per_source: Annotated[int, Field(strict=True, ge=1, le=10)]
    data_origin: Origin
    physical_validation: Literal[False]
    numerical_report: NumericalReportExport


class PlanSlotExport(StrictModel):
    layout: Layout
    source_id: Identifier
    repeat: Annotated[int, Field(strict=True, ge=1, le=10)]


class PlanExport(StrictModel):
    id: Identifier
    source_ids: list[Identifier] = Field(min_length=2, max_length=5)
    layouts: list[Layout] = Field(min_length=2, max_length=2)
    trials_per_source: Annotated[int, Field(strict=True, ge=1, le=10)]
    horizon_s: Number
    expected_total: Annotated[int, Field(strict=True, ge=4, le=100)]
    sequence: list[PlanSlotExport] = Field(min_length=4, max_length=100)
    unit: Literal["one_token_release"]
    frozen_before_trials: Literal[True]
    order: Literal["predeclared_counterbalanced_alternation_not_randomized"]


class SourceEvidenceExport(StrictModel):
    id: Identifier
    case_id: Identifier
    status: Literal["ranked", "unknown"]
    data_origin: Origin


class TrialExport(StrictModel):
    id: Identifier
    comparison_id: Identifier
    ordinal: Annotated[int, Field(strict=True, ge=1, le=200)]
    layout: Layout
    source_id: Identifier
    data_origin: TrialOrigin
    outcome: Literal["zone_entry", "intercepted_before_entry", "no_entry", "unresolved"]
    entry_time_s: Number | None
    interception_time_s: Number | None
    token_accounted: StrictBool
    physical_confirmed: StrictBool
    horizon_completed: StrictBool
    recording_id: Identifier | None
    outcome_verification: Literal["operator_reported_not_automatically_camera_verified"]


class RateBoundsExport(StrictModel):
    lower: Fraction
    upper: Fraction
    denominator: Count
    kind: Literal["planned_slots_missing_and_unresolved_are_unknown",
                  "actual_releases_including_unresolved"]


class TrialStatsExport(StrictModel):
    planned: Count
    released: Count
    missing_planned: Count
    zone_entries: Count
    captured_before_entry: Count
    no_entry: Count
    unresolved: Count
    token_accounted: Count
    unaccounted: Count
    recording_linked: Count
    horizon_completed: Count
    outcome_resolved: Count
    tracking_verification: Literal["not_automatically_verified"]
    entry_rate_bounds: RateBoundsExport
    observed_entry_rate_bounds: RateBoundsExport


class SourceTrialStatsExport(StrictModel):
    source_id: Identifier
    baseline: TrialStatsExport
    intervention: TrialStatsExport


class PlanProgressExport(StrictModel):
    expected_total: Count
    recorded_total: Count
    complete: StrictBool
    balanced: StrictBool
    order_followed: StrictBool


class EffectBoundsExport(StrictModel):
    lower: Number
    upper: Number
    kind: Literal["baseline_minus_intervention_planned_entry_fraction",
                  "actual_releases_including_unresolved_not_causal_estimate"]


class OriginEvaluationExport(StrictModel):
    data_origin: TrialOrigin
    layouts: dict[Layout, TrialStatsExport] = Field(min_length=2, max_length=2)
    by_source: list[SourceTrialStatsExport] = Field(min_length=2, max_length=5)
    plan: PlanProgressExport
    effect_bounds: EffectBoundsExport
    observed_effect_bounds: EffectBoundsExport
    supports_causal_claim: Literal[False]
    physical_outcomes_automatically_verified: Literal[False]


class EvaluationExport(StrictModel):
    id: Identifier
    snapshot_hash: Sha256
    comparison_id: Identifier
    trial_ids: list[Identifier] = Field(max_length=200)
    physical_validation: Literal[False]
    by_origin: dict[TrialOrigin, OriginEvaluationExport] = Field(min_length=2, max_length=2)


class EvaluationTruthExport(StrictModel):
    purpose: Literal["EVALUATION_ONLY_NEVER_SOURCE_INFERENCE_INPUT"]
    trials: list[TrialExport] = Field(max_length=200)
    evaluation: EvaluationExport


LIMITATIONS = [
    "Content hashes verify bundle consistency, not physical truth or an authenticated signature.",
    "Trial source labels are evaluation truth and must never enter source inference input.",
    "Synthetic demonstrations and operator-reported physical trials remain separate.",
    "Neither simulated outcomes nor operator reports establish reef benefit or causal effects.",
    "The original evaluation snapshot hash includes private source records; the export payload hash binds this redacted bundle.",
]


class AnalysisPayload(StrictModel):
    comparison: ComparisonExport
    frozen_plan: PlanExport
    provenance: ProvenanceExport
    source_evidence: SourceEvidenceExport
    evaluation_truth: EvaluationTruthExport
    limitations: list[str] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def fixed_limitations(self):
        if self.limitations != LIMITATIONS:
            raise ValueError("Export limitations must be the fixed public contract")
        return self


class ExportMetadata(StrictModel):
    exported_at_utc: str = Field(max_length=40)
    is_current: StrictBool
    archive_reason: Literal["CASE_CHANGED_OR_STOPPED"] | None


class AnalysisBundle(StrictModel):
    schema_version: Literal["analysis_bundle_v1"]
    payload: AnalysisPayload
    payload_canonical_json: str = Field(min_length=1, max_length=400000)
    payload_sha256: Sha256
    metadata: ExportMetadata

    @model_validator(mode="after")
    def content_hash(self):
        raw = self.payload_canonical_json
        parsed = json.loads(raw)
        if canonical_json(parsed) != raw:
            raise ValueError("Payload bytes must use the declared canonical JSON format")
        if parsed != self.payload.model_dump(mode="json"):
            raise ValueError("Canonical payload and parsed payload disagree")
        if hashlib.sha256(raw.encode("utf-8")).hexdigest() != self.payload_sha256:
            raise ValueError("Export payload SHA256 does not match")
        return self
