"""Export everything the dashboard shows into dashboard/data/dashboard.json.

The dashboard is a static page with no server: every number it displays is in
this one file, which the pipeline rebuilds. Figures that depend on the living-wage
benchmark are precomputed for each MIT household tier so the page never has to
recompute a statistic, only look one up.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math

import pandas as pd

import common as c
from ladder import ENTRY, priced_destinations, summarise

DASH = c.ROOT / "dashboard" / "data"
DASH.mkdir(parents=True, exist_ok=True)


def _clean(v):
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if hasattr(v, "item"):
        return _clean(v.item())
    return v


def records(df: pd.DataFrame) -> list[dict]:
    return [{k: _clean(v) for k, v in r.items()} for r in df.to_dict("records")]


def ladder_block() -> dict:
    d = priced_destinations()
    s = summarise(d)
    roles = []
    for soc10, role in ENTRY.items():
        if role == "Personal care aide":  # same SF wage code as home health aide
            continue
        g = d[d.soc1 == soc10]
        row = s[s.soc2010 == soc10].iloc[0]
        clinical = g.dest_clinical
        mix = {}
        for name, lw in c.benchmarks().items():
            priced = g.dest_p50.notna()
            above = priced & (g.dest_p50 >= lw)
            mix[name] = {
                "clinical_above": g.loc[above & clinical, "share"].sum(),
                "other_above": g.loc[above & ~clinical, "share"].sum(),
                "below": g.loc[priced & (g.dest_p50 < lw), "share"].sum(),
                "no_sf_wage": g.loc[~priced, "share"].sum(),
            }
        top = (g.groupby(["soc18", "dest_title", "dest_p50", "dest_clinical"], dropna=False)
                 .agg(share=("share", "sum")).reset_index()
                 .sort_values("share", ascending=False).head(12))
        top["dest_title"] = top.dest_title.fillna("(no SF wage published)")
        roles.append({
            "soc2010": soc10, "role": role,
            "sf_emp": row.sf_emp, "sf_p25": row.sf_p25, "sf_p50": row.sf_p50,
            "annual_transfer_rate": row.sf_annual_transfer_rate,
            "switch_obs": row.switch_obs,
            "share_stay_health": row.share_stay_health,
            "mix": {k: {kk: _clean(vv) for kk, vv in v.items()} for k, v in mix.items()},
            "combined": bool(row.combined),
            "top_destinations": records(top[["soc18", "dest_title", "share", "dest_p50", "dest_clinical"]]
                                        .rename(columns={"dest_title": "name", "dest_p50": "sf_p50",
                                                         "dest_clinical": "clinical"})),
        })
    return {"roles": [{k: _clean(v) for k, v in r.items()} for r in roles]}


def main() -> None:
    manifest = list(csv.DictReader((c.RAW / "MANIFEST.csv").open()))
    screen = pd.read_csv(c.OUT / "wage_screen.csv")
    need = pd.read_csv(c.OUT / "need_below_lw_by_benchmark.csv")
    comp = pd.read_csv(c.OUT / "need_entry_role_composition.csv")

    out = {
        "meta": {
            "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "benchmarks": c.benchmarks(),
            "cpi_factor_2024_to_mit_basis": c.cpi_factor_2024_to_mit_basis(),
            "mit_price_basis": c.MIT_PRICE_BASIS,
            "sources": [{k: r[k] for k in ("file", "url", "description", "retrieved")}
                        for r in manifest],
        },
        "need": records(need),
        "composition": records(comp),
        "screen": records(screen.drop(columns=["median_supports", "entry_wage_supports",
                                               "p50_vs_single_lw"])),
        "ladder": ladder_block(),
    }
    path = DASH / "dashboard.json"
    path.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {path.relative_to(c.ROOT)} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
