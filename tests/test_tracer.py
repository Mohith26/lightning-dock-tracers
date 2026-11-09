import numpy as np
import pandas as pd
import pytest

from ldtracer.tracer import Breakthrough, breakthrough, campaign_table, flow_at, gpm_to_liters_per_day


def gaussian_return(mass_kg, q_gpm, mu=40.0, sigma=8.0, days=None):
    """Concentration (ug/L) that carries exactly mass_kg past a producer at constant q_gpm."""
    days = np.linspace(0.5, 200, 4000) if days is None else days
    q = gpm_to_liters_per_day(q_gpm)
    rate = mass_kg * np.exp(-0.5 * ((days - mu) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi))  # kg/day
    return days, rate / q * 1e9


def test_recovers_known_mass_and_mean_residence():
    days, conc = gaussian_return(10.0, 1500.0)
    out = breakthrough(days, conc, np.full_like(days, 1500.0), injected_kg=50.0, injector_gpm=500.0)
    assert out.recovered_kg == pytest.approx(10.0, rel=1e-3)
    assert out.recovery_fraction == pytest.approx(0.2, rel=1e-3)
    assert out.mean_residence_days == pytest.approx(40.0, rel=1e-3)
    assert out.peak_days == pytest.approx(40.0, abs=0.1)
    # Shook (2005): recovery fraction * injection rate * mean residence time
    expected_m3 = 0.2 * gpm_to_liters_per_day(500.0) * 40.0 / 1000.0
    assert out.swept_volume_m3 == pytest.approx(expected_m3, rel=1e-3)


def test_variable_flow_weights_the_mass_rate():
    days = np.array([1.0, 2.0, 3.0])
    conc = np.array([10.0, 10.0, 10.0])
    a = breakthrough(days, conc, np.array([100.0, 100.0, 100.0]))
    b = breakthrough(days, conc, np.array([200.0, 200.0, 200.0]))
    assert b.recovered_kg == pytest.approx(2 * a.recovered_kg)


def test_unsorted_input_and_first_detect():
    days = np.array([5.0, 1.0, 3.0, 2.0])
    conc = np.array([4.0, 0.0, 2.0, 0.0])
    out = breakthrough(days, conc, np.full(4, 100.0))
    assert out.first_detect_days == 3.0
    assert out.peak_days == 5.0
    assert out.sampled_days == 5.0


def test_no_detection_gives_nan_moments():
    out = breakthrough(np.array([1.0, 2.0]), np.zeros(2), np.full(2, 100.0), injected_kg=50.0)
    assert out.recovered_kg == 0.0
    assert out.recovery_fraction == 0.0
    assert np.isnan(out.mean_residence_days)
    assert np.isnan(out.first_detect_days)
    assert np.isnan(out.peak_days)


def test_unknown_mass_leaves_fraction_and_volume_nan():
    days, conc = gaussian_return(1.0, 1000.0)
    out = breakthrough(days, conc, np.full_like(days, 1000.0))
    assert np.isnan(out.recovery_fraction)
    assert np.isnan(out.swept_volume_m3)
    assert out.recovered_kg == pytest.approx(1.0, rel=1e-3)


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        breakthrough(np.array([1.0, 2.0]), np.array([1.0]), np.array([1.0, 1.0]))
    with pytest.raises(ValueError):
        breakthrough(np.array([1.0]), np.array([-1.0]), np.array([1.0]))


def test_flow_at_interpolates_and_masks_outside_log():
    flows = pd.DataFrame({"well": ["P"] * 2, "flow_gpm": [100.0, 300.0],
                          "datetime": pd.to_datetime(["2020-01-01", "2020-01-03"])})
    q = flow_at(flows, "P", pd.Series(pd.to_datetime(["2020-01-02", "2019-12-31", "2020-01-05"])))
    assert q[0] == pytest.approx(200.0)
    assert np.isnan(q[1]) and np.isnan(q[2])
    assert np.isnan(flow_at(flows, "missing", pd.Series(pd.to_datetime(["2020-01-02"])))).all()


def test_campaign_table_end_to_end_on_synthetic_campaign():
    t0 = pd.Timestamp("2020-01-01")
    days, conc = gaussian_return(5.0, 1000.0, days=np.arange(1.0, 150.0, 0.5))
    tracer = pd.DataFrame({
        "campaign": 2020, "producer_well": "P", "tracer_compound": "X", "injector_well": "I",
        "sample_datetime": t0 + pd.to_timedelta(days, unit="D"), "concentration_ug_L": conc,
        "censored": False, "source": "consolidated"})
    # a censored row must count as zero, and lab-report rows must be ignored
    extra = tracer.iloc[[0]].assign(concentration_ug_L=999.0, censored=True)
    lab = tracer.iloc[[5]].assign(concentration_ug_L=999.0, source="lab_report")
    tracer = pd.concat([tracer, extra, lab], ignore_index=True)
    injections = pd.DataFrame({"campaign": [2020], "injector_well": ["I"], "tracer_compound": ["X"],
                               "injection_datetime": [t0], "amount_kg": [25.0]})
    flows = pd.DataFrame({"campaign": 2020, "well": ["P", "P", "I", "I"], "well_role": "x",
                          "flow_gpm": [1000.0, 1000.0, 400.0, 400.0],
                          "datetime": [t0, t0 + pd.Timedelta(days=200)] * 2})
    table = campaign_table(tracer, injections, flows, 2020, ["P"])
    assert len(table) == 1
    row = table.iloc[0]
    assert row["recovery_fraction"] == pytest.approx(0.2, rel=2e-3)
    assert row["injector_mean_gpm"] == pytest.approx(400.0)
    assert isinstance(breakthrough(days, conc, np.full_like(days, 1000.0)), Breakthrough)
