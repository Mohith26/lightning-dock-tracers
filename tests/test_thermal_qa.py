import numpy as np
import pandas as pd
import pytest

from ldtracer import qa, thermal


def test_decline_rate_recovers_linear_trend_despite_bad_cells():
    idx = pd.date_range("2020-01-01", "2024-12-31", freq="D")
    years = (idx - idx[0]).days / 365.25
    s = pd.Series(300.0 - 10.0 * years, index=idx)
    s.iloc[100] = 0.005   # transcription errors seen in the real reports
    s.iloc[900] = 4710.0
    out = thermal.decline_rate(s, "2020-01-01", "2024-12-31")
    assert out["slope_per_year"] == pytest.approx(-10.0, abs=0.05)
    assert out["n_months"] == 60


def test_decline_rate_needs_data():
    s = pd.Series([300.0, 299.0], index=pd.date_range("2020-01-01", periods=2, freq="D"))
    with pytest.raises(ValueError):
        thermal.decline_rate(s, "2020-01-01", "2020-12-31")


def test_annual_median_ignores_out_of_range():
    idx = pd.date_range("2021-01-01", periods=5, freq="D")
    s = pd.Series([300.0, 301.0, 0.0, 5000.0, 302.0], index=idx)
    assert thermal.annual_median(s).loc[2021] == 301.0


def test_compare_sources_flags_disagreements():
    t = pd.Timestamp("2016-08-10 09:30")
    base = dict(campaign=2016, producer_well="45-7", tracer_compound="2 NS", sample_datetime=t)
    tracer = pd.DataFrame([
        {**base, "concentration_ug_L": 1.0, "source": "consolidated", "lab_sample_no": np.nan},
        {**base, "concentration_ug_L": 1.1, "source": "lab_report", "lab_sample_no": "a"},
        {**base, "concentration_ug_L": 6.8, "source": "lab_report", "lab_sample_no": "a"},
    ])
    out = qa.compare_sources(tracer)
    assert len(out) == 2
    assert out["flagged"].tolist() == [False, True]
    assert (out["n_lab_values"] == 2).all()
