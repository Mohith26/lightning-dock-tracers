"""Fetch and load the CSV tables of the Lightning Dock data package.

Only the members that are needed are pulled out of the GDR zip files, using
HTTP range requests, so the 7.4 GB package never has to be downloaded.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from .httpzip import open_remote_zip

GDR_BASE = "https://gdr.openei.org/files/1856/"
MEMBERS = {
    "tracer_concentrations.csv": "02_TRACER_TEST_CAMPAIGNS.zip",
    "tracer_injections.csv": "02_TRACER_TEST_CAMPAIGNS.zip",
    "well_flow_rates.csv": "02_TRACER_TEST_CAMPAIGNS.zip",
    "production_injection_generation_reports_daily.csv": "04_PRODUCTION_INJECTION_GENERATION.zip",
}
DEFAULT_DIR = Path(os.environ.get("LDTRACER_DATA", "data"))


def fetch(data_dir: Path = DEFAULT_DIR, members=None) -> Path:
    """Download the needed CSV members into ``data_dir`` (skips files already there)."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    by_zip: dict[str, list[str]] = {}
    for name in members or MEMBERS:
        if not (data_dir / name).exists():
            by_zip.setdefault(MEMBERS[name], []).append(name)
    for zip_name, names in by_zip.items():
        archive = open_remote_zip(GDR_BASE + zip_name)
        index = {Path(info.filename).name: info for info in archive.infolist()}
        for name in names:
            with archive.open(index[name]) as src, open(data_dir / name, "wb") as dst:
                dst.write(src.read())
    return data_dir


def load_tracer(data_dir: Path = DEFAULT_DIR) -> pd.DataFrame:
    """Tracer concentrations with a ``source`` column.

    The 2016 campaign carries two copies of many samples: the consolidated
    series (``days_since_injection`` filled, no lab sample number) and rows
    transcribed from the preliminary lab reports (lab sample number, no
    elapsed time). They are labelled ``consolidated`` and ``lab_report``.
    """
    df = pd.read_csv(Path(data_dir) / "tracer_concentrations.csv")
    df["sample_datetime"] = pd.to_datetime(df["sample_datetime"], format="mixed")
    df["source"] = "consolidated"
    df.loc[df["lab_sample_no"].notna() & df["days_since_injection"].isna(), "source"] = "lab_report"
    return df


def load_injections(data_dir: Path = DEFAULT_DIR) -> pd.DataFrame:
    df = pd.read_csv(Path(data_dir) / "tracer_injections.csv")
    df["injection_datetime"] = pd.to_datetime(df["injection_datetime"], format="mixed")
    return df


def load_flows(data_dir: Path = DEFAULT_DIR) -> pd.DataFrame:
    df = pd.read_csv(Path(data_dir) / "well_flow_rates.csv")
    df["datetime"] = pd.to_datetime(df["datetime"], format="mixed")
    return df


def load_daily_ops(data_dir: Path = DEFAULT_DIR) -> pd.DataFrame:
    """Daily plant reports, keeping only rows that are real daily reports, indexed by date."""
    df = pd.read_csv(Path(data_dir) / "production_injection_generation_reports_daily.csv")
    df = df[df["error"].isna()].copy()
    df["date"] = pd.to_datetime(df["date"])
    return df.drop(columns=["error"]).set_index("date").sort_index()


def well_series(ops: pd.DataFrame, well: str, field: str) -> pd.Series:
    """One per-well column of the daily reports, e.g. ``well_series(ops, "45-7", "temp")``."""
    return ops[f"well::{well}::{field}"].dropna()
