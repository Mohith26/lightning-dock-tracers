"""Moment analysis of tracer breakthrough curves."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

LITERS_PER_GALLON = 3.785411784
MINUTES_PER_DAY = 1440.0


def gpm_to_liters_per_day(gpm):
    return np.asarray(gpm, dtype=float) * LITERS_PER_GALLON * MINUTES_PER_DAY


@dataclass
class Breakthrough:
    n_samples: int
    sampled_days: float
    first_detect_days: float
    peak_days: float
    peak_ug_L: float
    recovered_kg: float
    recovery_fraction: float
    mean_residence_days: float
    swept_volume_m3: float

    def as_dict(self):
        return asdict(self)


def breakthrough(days, conc_ug_L, producer_gpm, injected_kg=None, injector_gpm=None) -> Breakthrough:
    """Summarise one injector-to-producer tracer return.

    days: elapsed days since injection, conc_ug_L: concentration at the
    producer, producer_gpm: producer flow at each sample. The recovered mass is
    the trapezoidal integral of C(t) * Q(t), starting from zero concentration at
    t = 0. The mean residence time is the first moment of that mass rate.
    The swept volume follows Shook (2005): recovery fraction times injection
    rate times mean residence time; it needs both ``injected_kg`` and
    ``injector_gpm``. Values that cannot be computed are NaN.
    """
    days = np.asarray(days, dtype=float)
    conc = np.asarray(conc_ug_L, dtype=float)
    q = gpm_to_liters_per_day(producer_gpm)
    if not (days.shape == conc.shape == q.shape):
        raise ValueError("days, conc_ug_L and producer_gpm must have the same length")
    order = np.argsort(days)
    days, conc, q = days[order], conc[order], q[order]
    if np.any(conc < 0) or np.any(q < 0):
        raise ValueError("concentrations and flows must be non-negative")
    t = np.concatenate([[0.0], days])
    rate = np.concatenate([[0.0], conc * q * 1e-9])  # kg/day
    recovered = float(np.trapezoid(rate, t))
    detected = days[conc > 0]
    mean_residence = float(np.trapezoid(rate * t, t) / recovered) if recovered > 0 else np.nan
    fraction = recovered / injected_kg if injected_kg else np.nan
    swept = np.nan
    if injected_kg and injector_gpm and recovered > 0:
        swept = fraction * float(gpm_to_liters_per_day(injector_gpm)) * mean_residence / 1000.0
    peak = int(np.argmax(conc)) if len(conc) else 0
    return Breakthrough(
        n_samples=int(len(days)),
        sampled_days=float(days.max()) if len(days) else np.nan,
        first_detect_days=float(detected.min()) if len(detected) else np.nan,
        peak_days=float(days[peak]) if len(days) and conc[peak] > 0 else np.nan,
        peak_ug_L=float(conc[peak]) if len(conc) else np.nan,
        recovered_kg=recovered,
        recovery_fraction=fraction,
        mean_residence_days=mean_residence,
        swept_volume_m3=swept,
    )


def flow_at(flows: pd.DataFrame, well: str, when: pd.Series) -> np.ndarray:
    """Producer flow (gpm) linearly interpolated to sample times; NaN outside the logged range."""
    log = flows[flows["well"] == well].sort_values("datetime")
    if log.empty:
        return np.full(len(when), np.nan)
    # Compare on one time resolution: pandas may parse to [us] or [ns].
    x = log["datetime"].astype("datetime64[ns]").astype("int64").to_numpy()
    xi = pd.to_datetime(pd.Series(when)).astype("datetime64[ns]").astype("int64").to_numpy()
    out = np.interp(xi, x, log["flow_gpm"].to_numpy(dtype=float))
    out[(xi < x.min()) | (xi > x.max())] = np.nan
    return out


def campaign_table(tracer: pd.DataFrame, injections: pd.DataFrame, flows: pd.DataFrame,
                   campaign: int, producers, source: str = "consolidated") -> pd.DataFrame:
    """Breakthrough metrics for every injector/producer pair of one campaign."""
    rows = []
    inj = injections[injections["campaign"] == campaign]
    camp_flows = flows[flows["campaign"] == campaign]
    data = tracer[(tracer["campaign"] == campaign) & (tracer["source"] == source)]
    for _, injection in inj.dropna(subset=["injector_well"]).iterrows():
        injector = injection["injector_well"]
        mass = injection["amount_kg"] if pd.notna(injection["amount_kg"]) else None
        injector_log = camp_flows[camp_flows["well"] == injector]["flow_gpm"]
        injector_gpm = float(injector_log.mean()) if len(injector_log) else None
        for producer in producers:
            g = data[(data["producer_well"] == producer) & (data["tracer_compound"] == injection["tracer_compound"])]
            g = g.sort_values("sample_datetime")
            if g.empty:
                continue
            days = (g["sample_datetime"] - injection["injection_datetime"]).dt.total_seconds() / 86400.0
            q = flow_at(camp_flows, producer, g["sample_datetime"])
            keep = days.to_numpy() > 0
            keep &= ~np.isnan(q)
            conc = np.where(g["censored"].to_numpy(), 0.0, g["concentration_ug_L"].to_numpy(dtype=float))
            result = breakthrough(days.to_numpy()[keep], conc[keep], q[keep], mass, injector_gpm)
            rows.append({"campaign": campaign, "injector": injector, "tracer": injection["tracer_compound"],
                         "producer": producer, "injected_kg": mass, "injector_mean_gpm": injector_gpm,
                         **result.as_dict()})
    return pd.DataFrame(rows)
