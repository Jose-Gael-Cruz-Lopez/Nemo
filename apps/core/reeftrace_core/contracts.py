"""Version 3 application contracts. Truth labels are deliberately absent."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Point = tuple[float, float]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Source(Contract):
    id: Literal["A", "B", "C"]
    polygon_cm: list[Point] = Field(min_length=3)
    prior: float = Field(default=1 / 3, gt=0, le=1)


class Trap(Contract):
    id: str
    polygon_cm: list[Point] = Field(min_length=3)
    retention_verified: bool = False


class Flow(Contract):
    nx: int = Field(ge=2, le=40)
    ny: int = Field(ge=2, le=40)
    velocity_cm_s: list[list[Point]]
    counts: list[list[int]]
    dispersion_cm_s: list[list[float]]
    min_samples: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def dimensions(self):
        for grid in (self.velocity_cm_s, self.counts, self.dispersion_cm_s):
            if len(grid) != self.ny or any(len(row) != self.nx for row in grid):
                raise ValueError("Flow arrays must have shape ny by nx")
        if any(n < 0 for row in self.counts for n in row):
            raise ValueError("Negative flow counts")
        if any(v < 0 for row in self.dispersion_cm_s for v in row):
            raise ValueError("Negative dispersion")
        return self


class Profile(Contract):
    id: str = Field(min_length=1, max_length=100)
    width_cm: float = Field(gt=0, le=300)
    height_cm: float = Field(gt=0, le=300)
    water_depth_cm: float = Field(gt=0)
    token_class: str
    pump_setting: str
    validity: Literal["development", "validated", "invalid"] = "development"
    synthetic: bool = False
    sources: list[Source] = Field(min_length=3, max_length=3)
    traps: list[Trap] = []
    surface_obstacles: list[list[Point]] = []
    observation_polygon_cm: list[Point] = Field(min_length=3)
    flow: Flow

    @model_validator(mode="after")
    def geometry(self):
        if {s.id for s in self.sources} != {"A", "B", "C"}:
            raise ValueError("Exactly one A, B and C source required")
        if abs(sum(s.prior for s in self.sources) - 1.0) > 1e-6:
            raise ValueError("Source priors must sum to one")
        polygons = [s.polygon_cm for s in self.sources] + [t.polygon_cm for t in self.traps]
        polygons += self.surface_obstacles + [self.observation_polygon_cm]
        for poly in polygons:
            if len(poly) < 3 or any(
                not (0 <= x <= self.width_cm and 0 <= y <= self.height_cm) for x, y in poly
            ):
                raise ValueError("Geometry must lie inside measured tank")
            area = abs(
                sum(
                    poly[i][0] * poly[(i + 1) % len(poly)][1]
                    - poly[(i + 1) % len(poly)][0] * poly[i][1]
                    for i in range(len(poly))
                )
            )
            if area < 1e-6:
                raise ValueError("Degenerate polygon")
        return self


class Observation(Contract):
    t: float = Field(ge=0)
    x: float
    y: float
    pixel_x: float | None = None
    pixel_y: float | None = None
    observed: bool = True
    quality: float = Field(default=1, ge=0, le=1)
    frame_id: str | None = None


class CaseInput(Contract):
    run_id: str
    calibration_id: str
    token_class: str
    mode: Literal["live", "recorded", "synthetic"]
    evidence_mode: Literal["trajectory", "retained_endpoint"]
    track: list[Observation] = Field(min_length=1, max_length=2000)
    retained_trap_id: str | None = None
    last_observed_at: float | None = Field(default=None, ge=0)
    observation_region_declared: bool = False

    @model_validator(mode="after")
    def history(self):
        if self.evidence_mode == "retained_endpoint" and len(self.track) != 1:
            raise ValueError(
                "Retained-endpoint cases accept exactly one endpoint, with no prior trajectory"
            )
        if self.mode == "live" and self.last_observed_at is None:
            raise ValueError("Live cases require actual observation wall-clock time")
        if any(b.t <= a.t for a, b in zip(self.track, self.track[1:])):
            raise ValueError("Timestamps must strictly increase")
        return self


class ModelConfig(Contract):
    particles_per_source: int = Field(default=500, ge=10, le=1000)
    dt_s: float = Field(default=0.1, ge=0.02, le=0.5)
    max_age_s: float = Field(default=60, ge=2, le=90)
    min_age_s: float = Field(default=0, ge=0)
    diffusion_cm2_s: float = Field(default=0.03, ge=0, le=1)
    drift_bound_cm_s: float = Field(default=0.1, ge=0, le=1)
    bandwidth_cm: float = Field(default=1, gt=0, le=5)
    min_fit: float = Field(default=0.02, gt=0, le=1)
    min_margin: float = Field(default=0.15, gt=0, le=1)
    min_coverage: float = Field(default=0.7, ge=0, le=1)
    max_gap_s: float = Field(default=0.6, gt=0)
    seed: int = 7

    @model_validator(mode="after")
    def age(self):
        if self.min_age_s >= self.max_age_s:
            raise ValueError("Invalid release age window")
        return self
