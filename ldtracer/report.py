"""Build the results tables and figures: ``python -m ldtracer.report``."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import data, qa, thermal, tracer

PRODUCERS_2016 = ["45-7", "55-7"]
PRODUCERS_2019 = ["45-7", "45A-7"]
PRODUCERS = ["45-7", "45A-7", "44-7"]  # production wells in the daily reports


def build(data_dir: Path, out_dir: Path, figures: bool = True) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    tr = data.load_tracer(data_dir)
    inj = data.load_injections(data_dir)
    flows = data.load_flows(data_dir)
    ops = data.load_daily_ops(data_dir)

    t2016 = tracer.campaign_table(tr, inj, flows, 2016, PRODUCERS_2016)
    t2019 = tracer.campaign_table(tr, inj, flows, 2019, PRODUCERS_2019)
    t2016.to_csv(out_dir / "tracer_2016.csv", index=False)
    t2019.to_csv(out_dir / "tracer_2019.csv", index=False)

    sources = qa.compare_sources(tr)
    sources.to_csv(out_dir / "qa_lab_vs_consolidated.csv", index=False)

    supply = ops["geo_supply_temp_f"]
    annual = pd.DataFrame({
        "supply_temp_f": thermal.annual_median(supply),
        "45-7_temp_f": thermal.annual_median(data.well_series(ops, "45-7", "temp")),
        "45A-7_temp_f": thermal.annual_median(data.well_series(ops, "45A-7", "temp")),
        "44-7_temp_f": thermal.annual_median(data.well_series(ops, "44-7", "temp")),
    })
    annual.to_csv(out_dir / "annual_medians.csv")
    trends = {
        "supply 2016-2019": thermal.decline_rate(supply, "2016-01-01", "2019-12-31"),
        "supply 2020-2024": thermal.decline_rate(supply, "2020-01-01", "2024-12-31"),
        "45-7 2020-2024": thermal.decline_rate(data.well_series(ops, "45-7", "temp"), "2020-01-01", "2024-12-31"),
        "45A-7 2020-2024": thermal.decline_rate(data.well_series(ops, "45A-7", "temp"), "2020-01-01", "2024-12-31"),
    }
    pd.DataFrame(trends).T.to_csv(out_dir / "temperature_trends.csv")
    temp_cols = ["geo_supply_temp_f"] + [f"well::{w}::temp" for w in PRODUCERS]
    out_of_range = pd.DataFrame({
        c: {"values": int(ops[c].notna().sum()),
            "outside_150_400F": int(ops[c].notna().sum() - len(thermal.in_range(ops[c])))}
        for c in temp_cols}).T
    out_of_range.to_csv(out_dir / "qa_temperature_out_of_range.csv")

    if figures:
        _figures(tr, inj, ops, out_dir)
    return {"t2016": t2016, "t2019": t2019, "sources": sources,
            "annual": annual, "trends": trends, "out_of_range": out_of_range}


def _figures(tr, inj, ops, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=False)
    for ax, (campaign, producers) in zip(axes, [(2016, PRODUCERS_2016), (2019, PRODUCERS_2019)]):
        sub = tr[(tr["campaign"] == campaign) & (tr["source"] == "consolidated")]
        for _, injection in inj[(inj["campaign"] == campaign)].dropna(subset=["injector_well"]).iterrows():
            for producer in producers:
                g = sub[(sub["producer_well"] == producer) & (sub["tracer_compound"] == injection["tracer_compound"])]
                g = g.sort_values("sample_datetime")
                if g.empty or g["concentration_ug_L"].max() <= 0:
                    continue
                days = (g["sample_datetime"] - injection["injection_datetime"]).dt.total_seconds() / 86400
                ax.plot(days, g["concentration_ug_L"], lw=1, label=f"{injection['injector_well']} -> {producer}")
        ax.set_title(f"{campaign} campaign")
        ax.set_xlabel("days since injection")
        ax.set_ylabel("concentration (ug/L)")
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "breakthrough_curves.png", dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 3.5))
    for well in ["45-7", "45A-7", "44-7"]:
        s = thermal.in_range(data.well_series(ops, well, "temp")).rolling("30D").median()
        ax.plot(s.index, s.values, lw=1, label=f"well {well}")
    ax.set_ylabel("production temperature (F)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "production_temperature.png", dpi=110)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=data.DEFAULT_DIR)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--no-fetch", action="store_true")
    args = parser.parse_args()
    if not args.no_fetch:
        data.fetch(args.data)
    res = build(args.data, args.out)
    pd.set_option("display.width", 200)
    cols = ["injector", "producer", "first_detect_days", "peak_days", "peak_ug_L",
            "recovery_fraction", "mean_residence_days", "swept_volume_m3", "sampled_days"]
    print("2016 campaign (50 kg per tracer)\n", res["t2016"][cols].round(3).to_string(index=False))
    print("\n2019 campaign (injected mass not in the package)\n",
          res["t2019"][["injector", "producer", "first_detect_days", "peak_days", "peak_ug_L", "sampled_days"]]
          .round(2).to_string(index=False))
    print("\nTemperature trends (F/yr)\n", pd.DataFrame(res["trends"]).T.round(2).to_string())
    print("\nAnnual medians\n", res["annual"].round(0).to_string())
    flagged = res["sources"][res["sources"]["flagged"]]
    print(f"\nLab-report vs consolidated rows compared: {len(res['sources'])}, differ by >50%: {len(flagged)}")
    print(flagged.groupby(["producer_well", "tracer_compound"]).size().to_string())
    oor = res["out_of_range"]
    print("Supply/producer daily temperatures outside 150-400 F:\n", oor.to_string())


if __name__ == "__main__":
    main()
