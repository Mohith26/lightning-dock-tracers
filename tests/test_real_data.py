"""Contract tests on the published tables. Skipped unless the CSVs are in ./data (run `python -m ldtracer.report` once)."""
from pathlib import Path

import pytest

from ldtracer import data
from ldtracer.report import PRODUCERS_2016, build

DATA = Path(__file__).resolve().parents[1] / "data"
pytestmark = pytest.mark.skipif(not (DATA / "tracer_concentrations.csv").exists(), reason="data not fetched")


def test_tables_load_with_expected_shape():
    tr = data.load_tracer(DATA)
    assert set(tr["campaign"]) >= {2016, 2019}
    assert set(tr["source"]) == {"consolidated", "lab_report"}
    inj = data.load_injections(DATA)
    assert (inj[inj["campaign"] == 2016]["amount_kg"] == 50.0).all()
    ops = data.load_daily_ops(DATA)
    assert ops.index.is_monotonic_increasing
    assert "geo_supply_temp_f" in ops.columns


def test_2016_recoveries_are_physical(tmp_path):
    res = build(DATA, tmp_path, figures=False)
    t = res["t2016"]
    assert set(t["producer"]) == set(PRODUCERS_2016)
    per_injector = t.groupby("injector")["recovery_fraction"].sum()
    assert ((per_injector > 0) & (per_injector < 1)).all()
    assert (t["first_detect_days"] <= t["peak_days"]).all()
