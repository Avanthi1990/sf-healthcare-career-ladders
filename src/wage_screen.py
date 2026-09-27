"""Section 2: which San Francisco healthcare jobs clear the living wage.

Joins EDD projections (growth, openings, entry education) to EDD OEWS wages on
2018 SOC code, keeps healthcare occupations that do not require a bachelor's
degree, and places each one against the MIT living wage for several household
types.

Writes data/processed/wage_screen.csv
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import common as c

# Healthcare, as used here: SOC major groups 29 (practitioners and technical) and
# 31 (healthcare support), plus two health-specific roles outside them that are
# common entry points. An analytical choice, stated so it can be argued with.
EXTRA_HEALTH = {"43-6013": "Medical secretaries and administrative assistants",
                "21-1094": "Community health workers"}


def is_health(soc: str) -> bool:
    return soc[:2] in {"29", "31"} and soc != "31-9011" or soc in EXTRA_HEALTH


def build() -> pd.DataFrame:
    p, o = c.projections(), c.oews()
    df = p.merge(o[["soc", "emp", "p25", "p50", "p75", "flagged"]], on="soc",
                 how="left", validate="one_to_one")
    df = df[df.soc.map(is_health) & df.entry_ed.isin(c.NO_BA)].copy()

    unmatched = df[df.p50.isna()]
    if len(unmatched):
        print(f"note: {len(unmatched)} occupations have no OEWS wage for this area "
              f"and are listed without one: {', '.join(unmatched.title)}")

    b = c.benchmarks()
    df["annual_transfer_rate"] = df.transfers / 10 / df.emp_2023
    df["growth_2023_33"] = df["growth"]
    tiers = sorted(b.items(), key=lambda kv: kv[1])

    def tier(w):
        if pd.isna(w):
            return "No wage published"
        met = [name for name, v in tiers if w >= v]
        return met[-1] if met else "Below all living-wage levels"

    df["median_supports"] = df.p50.map(tier)
    df["entry_wage_supports"] = df.p25.map(tier)
    df["p50_vs_single_lw"] = df.p50 - c.lw_single()
    cols = ["soc", "title", "entry_ed", "emp_2023", "openings", "growth_2023_33",
            "annual_transfer_rate", "p25", "p50", "p75", "p50_vs_single_lw",
            "median_supports", "entry_wage_supports", "flagged"]
    return df[cols].sort_values("p50", ascending=False).reset_index(drop=True)


def main() -> None:
    df = build()
    df.to_csv(c.OUT / "wage_screen.csv", index=False)
    lw = c.lw_single()
    has = df[df.p50.notna()]
    print(f"{len(df)} non-BA healthcare occupations; {len(has)} with SF wages")
    print(f"median clears single-adult LW ${lw}: {(has.p50 >= lw).sum()}  "
          f"| 25th pct clears: {(has.p25 >= lw).sum()}")
    emp_below = has.loc[has.p50 < lw, "emp_2023"].sum()
    print(f"employment in occupations whose median is below LW: {emp_below:,.0f} "
          f"of {has.emp_2023.sum():,.0f} ({emp_below / has.emp_2023.sum():.0%})")
    op_below = has.loc[has.p50 < lw, "openings"].sum()
    print(f"openings 2023-33 in those occupations: {op_below:,.0f} "
          f"of {has.openings.sum():,.0f} ({op_below / has.openings.sum():.0%})")
    with pd.option_context("display.width", 220, "display.max_colwidth", 42):
        print(df[["soc", "title", "entry_ed", "emp_2023", "openings", "growth_2023_33",
                  "annual_transfer_rate", "p25", "p50", "median_supports"]]
              .to_string(index=False, float_format=lambda v: f"{v:,.2f}"))


if __name__ == "__main__":
    main()
