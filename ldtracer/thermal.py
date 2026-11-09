"""Production temperature trends from the daily plant reports."""

from __future__ import annotations

import numpy as np
import pandas as pd


PLAUSIBLE_F = (150.0, 400.0)


def in_range(series: pd.Series, valid=PLAUSIBLE_F) -> pd.Series:
    """Drop missing values and values outside ``valid`` (transcription errors such as 0.005 or 4710 F)."""
    s = series.dropna()
    return s[(s >= valid[0]) & (s <= valid[1])]


def decline_rate(series: pd.Series, start: str, end: str, valid=PLAUSIBLE_F) -> dict:
    """Least-squares linear trend between two dates, in units per year.

    The daily values are first limited to ``valid`` and reduced to monthly
    medians, so a few bad spreadsheet cells cannot drive the slope. Returns the
    slope, its standard error, the number of months used and the fitted values
    at the window ends.
    """
    s = in_range(series.loc[start:end], valid).resample("MS").median().dropna()
    if len(s) < 3:
        raise ValueError("need at least 3 points in the window")
    t = (s.index - s.index[0]).days.to_numpy(dtype=float) / 365.25
    y = s.to_numpy(dtype=float)
    A = np.vstack([t, np.ones_like(t)]).T
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ coef
    dof = max(len(y) - 2, 1)
    se = float(np.sqrt(resid @ resid / dof / ((t - t.mean()) ** 2).sum()))
    return {"slope_per_year": float(coef[0]), "slope_se": se, "n_months": int(len(y)),
            "fit_start": float(coef[1]), "fit_end": float(coef[1] + coef[0] * t[-1])}


def annual_median(series: pd.Series, valid=PLAUSIBLE_F) -> pd.Series:
    out = in_range(series, valid).resample("YE").median()
    out.index = out.index.year
    return out
