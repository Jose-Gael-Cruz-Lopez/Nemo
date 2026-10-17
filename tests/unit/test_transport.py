import numpy as np
import pytest

from apps.transport.reeftrace_transport import Bounds, FlowField, fit_flow, simulate
from apps.transport.reeftrace_transport.geometry import (
    advance_reflecting,
    polygon_array,
    sample_polygon,
)

BOUNDS = {"x_min_cm": 0, "x_max_cm": 40, "y_min_cm": 0, "y_max_cm": 30}


def constant_flow(vx=1.0, vy=0.0, radius=15.0):
    return fit_flow([
        {"x_cm": x, "y_cm": y, "vx_cm_s": vx, "vy_cm_s": vy}
        for x in (0, 10, 20, 30, 40) for y in (0, 10, 20, 30)
    ], BOUNDS, coverage_radius_cm=radius, data_origin="SYNTHETIC")


def test_measured_fit_preserves_constant_drift_and_reports_holdout_error():
    samples = [{"x_cm": x, "y_cm": y, "vx_cm_s": 2, "vy_cm_s": -0.5}
               for x, y in ((1, 1), (10, 10), (30, 20), (39, 29))]
    validation = [{"x_cm": 15, "y_cm": 15, "vx_cm_s": 3, "vy_cm_s": -0.5}]
    flow = fit_flow(samples, BOUNDS, coverage_radius_cm=30,
                    validation_samples=validation, data_origin="SYNTHETIC")
    predicted, supported = FlowField(flow).evaluate([[15, 15], [100, 100]])
    np.testing.assert_allclose(predicted[0], [2, -0.5])
    assert supported.tolist() == [True, False]
    assert flow["diagnostics"]["validation_rmse_cm_s"] == pytest.approx(1)
    assert flow["diagnostics"]["training_rmse_cm_s"] == pytest.approx(0)
    assert flow["data_origin"] == "SYNTHETIC"


def test_cell_median_resists_single_gross_marker_velocity_outlier():
    samples = [{"x_cm": 1 + i / 100, "y_cm": 1, "vx_cm_s": v, "vy_cm_s": 0}
               for i, v in enumerate((1, 1, 1, 1, 99))]
    flow = fit_flow(samples, BOUNDS)
    assert flow["nodes"][0]["vx_cm_s"] == 1
    assert flow["nodes"][0]["sample_count"] == 5
    assert flow["diagnostics"]["loo_rmse_cm_s"] is None


def test_constant_advection_matches_analytic_free_path():
    ensemble = simulate(constant_flow(2, -0.5), [[5, 10], [5.1, 10], [5.1, 10.1], [5, 10.1]],
                        bounds=BOUNDS, particles=40, dt_s=0.1, horizon_s=2,
                        diffusivity_cm2_s=0, seed=11)
    np.testing.assert_allclose(ensemble.positions_cm[-1] - ensemble.positions_cm[0],
                               np.tile([4, -1], (40, 1)), atol=1e-11)
    assert not ensemble.retained.any()


def test_diffusion_variance_matches_two_d_t_away_from_walls():
    ensemble = simulate(constant_flow(0, 0), [[19.999, 14.999], [20.001, 14.999],
                                           [20.001, 15.001], [19.999, 15.001]],
                        bounds=BOUNDS, particles=4000, dt_s=0.1, horizon_s=1,
                        diffusivity_cm2_s=0.2, seed=71)
    displacement = ensemble.positions_cm[-1] - ensemble.positions_cm[0]
    np.testing.assert_allclose(displacement.var(axis=0), [0.4, 0.4], rtol=0.07)
    np.testing.assert_allclose(displacement.mean(axis=0), [0, 0], atol=0.04)


def test_reflection_handles_corners_and_does_not_escape_tank():
    bounds = Bounds.from_dict({"x_min_cm": 0, "x_max_cm": 10, "y_min_cm": 0, "y_max_cm": 10})
    moved, retained = advance_reflecting(np.array([[9., 9.], [1., 1.]]),
                                        np.array([[4., 4.], [-4., -4.]]), bounds, [])
    np.testing.assert_allclose(moved, [[7, 7], [3, 3]])
    assert bounds.contains(moved).all()
    assert not retained.any()


def test_segment_intersection_prevents_tunneling_through_thin_trap():
    trap = polygon_array([[8, 0], [8.2, 0], [8.2, 30], [8, 30]])
    moved, retained = advance_reflecting(np.array([[5., 15.]]), np.array([[10., 0.]]),
                                        Bounds.from_dict(BOUNDS), [trap])
    assert retained.tolist() == [True]
    np.testing.assert_allclose(moved, [[8, 15]])


def test_absorbed_particles_remain_retained_and_do_not_move():
    trap = {"id": "T", "polygon_cm": [[8, 0], [10, 0], [10, 30], [8, 30]],
                "retention": "absorbing", "validated": True}
    ensemble = simulate(constant_flow(2, 0), [[5, 10], [5.1, 10], [5.1, 10.1], [5, 10.1]],
                        bounds=BOUNDS, traps=[trap], particles=30, horizon_s=4,
                        dt_s=0.1, diffusivity_cm2_s=0)
    assert ensemble.retained[-1].all()
    np.testing.assert_allclose(ensemble.positions_cm[-1], ensemble.positions_cm[-2])
    np.testing.assert_allclose(ensemble.positions_cm[-1, :, 0], 8)


def test_step_is_reduced_for_small_retention_feature():
    trap = {"polygon_cm": [[8, 0], [8.2, 0], [8.2, 30], [8, 30]], "validated": True}
    ensemble = simulate(constant_flow(2), [[5, 10], [5.1, 10], [5.1, 10.1], [5, 10.1]],
                        bounds=BOUNDS, traps=[trap], particles=10, horizon_s=1,
                        dt_s=1, diffusivity_cm2_s=0)
    assert ensemble.dt_s <= 0.05


def test_invalid_geometry_and_unbounded_work_are_rejected():
    with pytest.raises(ValueError, match="polygon|Polygon"):
        polygon_array([[0, 0], [2, 2], [0, 2], [2, 0]])
    with pytest.raises(ValueError, match="outside"):
        fit_flow([{"x_cm": 500, "y_cm": 1, "vx_cm_s": 1, "vy_cm_s": 0}], BOUNDS)
    with pytest.raises(ValueError, match="budget"):
        simulate(constant_flow(), [[1, 1], [2, 1], [2, 2], [1, 2]],
                 bounds=BOUNDS, horizon_s=60, dt_s=0.0001, particles=100)


def test_polygon_sampling_and_seed_are_reproducible():
    polygon = polygon_array([[1, 1], [5, 1], [5, 2], [2, 2], [2, 5], [1, 5]])
    a = sample_polygon(polygon, 100, np.random.default_rng(5))
    b = sample_polygon(polygon, 100, np.random.default_rng(5))
    np.testing.assert_array_equal(a, b)
    assert not np.any((a[:, 0] > 2) & (a[:, 1] > 2))


def test_duplicate_polygon_edges_and_noninteger_neighbors_are_rejected():
    # A zero-length edge otherwise makes an on-edge test true for every point.
    with pytest.raises(ValueError, match="positive length"):
        polygon_array([[1, 1], [2, 1], [2, 1], [2, 2], [1, 2]])
    with pytest.raises(ValueError, match="integer"):
        fit_flow([{"x_cm": 1, "y_cm": 1, "vx_cm_s": 1, "vy_cm_s": 0}],
                 BOUNDS, neighbors=1.5)


def test_simulation_query_rejects_nonfinite_time():
    ensemble = simulate(constant_flow(), [[1, 1], [2, 1], [2, 2], [1, 2]],
                        bounds=BOUNDS, particles=2, horizon_s=1)
    with pytest.raises(ValueError, match="outside"):
        ensemble.at(np.array([float("nan")]))
