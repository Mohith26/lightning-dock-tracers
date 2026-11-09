"""Consistency checks on the tracer table."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compare_sources(tracer: pd.DataFrame, rel_tol: float = 0.5) -> pd.DataFrame:
    """Pair lab-report rows with consolidated rows for the same sample.

    A sample is identified by campaign, producer, tracer and timestamp. When the
    lab reports list several values for one sample, each is compared with the
    consolidated value. Rows are flagged when the relative difference exceeds
    ``rel_tol``.
    """
    key = ["campaign", "producer_well", "tracer_compound", "sample_datetime"]
    cons = tracer[tracer["source"] == "consolidated"][key + ["concentration_ug_L"]]
    lab = tracer[tracer["source"] == "lab_report"][key + ["concentration_ug_L", "lab_sample_no"]]
    merged = lab.merge(cons, on=key, suffixes=("_lab", "_consolidated"))
    a, b = merged["concentration_ug_L_lab"], merged["concentration_ug_L_consolidated"]
    denom = np.maximum(np.maximum(a.abs(), b.abs()), 1e-12)
    merged["rel_diff"] = (a - b).abs() / denom
    merged["flagged"] = merged["rel_diff"] > rel_tol
    merged["n_lab_values"] = merged.groupby(key)["concentration_ug_L_lab"].transform("size")
    return merged.sort_values(key).reset_index(drop=True)
