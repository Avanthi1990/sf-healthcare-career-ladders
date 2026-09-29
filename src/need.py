"""Section 1: who in San Francisco works full time and still earns below a
living wage, and who holds the entry healthcare jobs.

ACS PUMS 2020-2024 5-year, San Francisco County residents (PUMAs 07507-07514).
Wages are converted to 2024 dollars with ADJINC; the MIT threshold (December 2025 dollars) is
deflated to 2024 dollars with San Francisco CPI so both sides are in the same
year's money. Standard errors use the 80 successive-difference replicate weights,
as the Census Bureau specifies; estimates with a CV above 30% or fewer than 50
sample records are flagged as unreliable.

Writes data/processed/need_below_lw.csv and need_entry_role_composition.csv
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import common as c

REP = [f"PWGTP{i}" for i in range(1, 81)]
MIN_N, MAX_CV = 50, 0.30

ENTRY_OCCP = {  # Census occupation codes for the entry roles in the ladder
    "3645": "Medical assistants", "3640": "Dental assistants",
    "3603": "Nursing assistants", "3601": "Home health aides",
    "3602": "Personal care aides", "3649": "Phlebotomists",
    "5730": "Medical secretaries",
}
RUNG_OCCP = {"3500": "LVNs", "3255": "Registered nurses"}


def race(df: pd.DataFrame) -> pd.Series:
    r = np.select(
        [df.HISP != 1, df.RAC1P == 1, df.RAC1P == 2, df.RAC1P == 6],
        ["Latino", "White", "Black", "Asian"], "Other / multiracial")
    return pd.Series(r, index=df.index)


def weighted_share(df: pd.DataFrame, flag: pd.Series) -> dict:
    """Weighted share with replicate-weight standard error."""
    w = df.PWGTP
    est = (w * flag).sum() / w.sum()
    reps = np.array([(df[r] * flag).sum() / df[r].sum() for r in REP])
    se = np.sqrt(4 / 80 * ((reps - est) ** 2).sum())
    n = len(df)
    return dict(n=n, weighted=w.sum(), share=est, se=se, moe90=1.645 * se,
                reliable=(n >= MIN_N) and (se / est <= MAX_CV if est > 0 else False))


def full_time_workers(p: pd.DataFrame) -> pd.DataFrame:
    ft = p[(p.AGEP.between(18, 64)) & p.ESR.isin([1, 2]) & (p.WKHP >= 35)
           & (p.WKWN >= 50) & (p.WAGP > 0)].copy()
    ft["wage_2024"] = ft.WAGP * ft.ADJINC / 1e6
    ft["hourly_2024"] = ft.wage_2024 / (ft.WKHP * ft.WKWN)
    ft["no_ba"] = ft.SCHL < 21
    ft["race"] = race(ft)
    ft["sex"] = np.where(ft.SEX == 1, "Men", "Women")
    return ft


def below_lw_table(ft: pd.DataFrame, lw_2024: float) -> pd.DataFrame:
    below = ft.hourly_2024 < lw_2024
    rows = []

    def add(label, mask, group="All"):
        sub = ft[mask]
        r = weighted_share(sub, below[mask])
        r.update(population=label, group=group,
                 below_count=(sub.PWGTP * below[mask]).sum())
        rows.append(r)

    add("All full-time workers", ft.index == ft.index)
    add("Bachelor's degree or higher", ~ft.no_ba)
    add("No bachelor's degree", ft.no_ba)
    for g in ["Latino", "Black", "Asian", "White", "Other / multiracial"]:
        add("No bachelor's degree", ft.no_ba & (ft.race == g), g)
    for g in ["Women", "Men"]:
        add("No bachelor's degree", ft.no_ba & (ft.sex == g), g)
    return pd.DataFrame(rows)[["population", "group", "n", "weighted", "below_count",
                               "share", "se", "moe90", "reliable"]]


def composition(p: pd.DataFrame) -> pd.DataFrame:
    """Race and sex of SF residents working in entry roles vs. all SF workers."""
    emp = p[p.ESR.isin([1, 2]) & p.OCCP.notna()].copy()
    emp["OCCP"] = emp.OCCP.astype(str).str.zfill(4)
    emp["race"] = race(emp)
    emp["women"] = emp.SEX == 2
    groups = {
        "All employed SF residents": emp.index == emp.index,
        "Entry healthcare roles (pooled)": emp.OCCP.isin(ENTRY_OCCP),
        "Home health and personal care aides": emp.OCCP.isin({"3601", "3602"}),
        "Medical, dental and nursing assistants": emp.OCCP.isin({"3645", "3640", "3603"}),
        "LVNs and registered nurses": emp.OCCP.isin(RUNG_OCCP),
    }
    rows = []
    for label, m in groups.items():
        sub = emp[m]
        for g in ["Latino", "Black", "Asian", "White", "Other / multiracial"]:
            r = weighted_share(sub, sub.race == g)
            r.update(population=label, group=g)
            rows.append(r)
        r = weighted_share(sub, sub.women)
        r.update(population=label, group="Women")
        rows.append(r)
    return pd.DataFrame(rows)[["population", "group", "n", "weighted", "share",
                               "se", "moe90", "reliable"]]


def main() -> None:
    p = c.pums_sf()
    f = c.cpi_factor_2024_to_mit_basis()
    lw_2024 = c.lw_single() / f
    print(f"SF persons: {len(p):,}; MIT single-adult LW ${c.lw_single()} (Dec 2025 dollars) "
          f"= ${lw_2024:.2f} in 2024 dollars (SF CPI factor {f:.4f})")

    ft = full_time_workers(p)
    t = below_lw_table(ft, lw_2024)
    t.to_csv(c.OUT / "need_below_lw.csv", index=False)
    comp = composition(p)
    comp.to_csv(c.OUT / "need_entry_role_composition.csv", index=False)

    # The same table at every household tier, for the dashboard's benchmark selector.
    tiers = [below_lw_table(ft, v / f).assign(benchmark=k, benchmark_2026=v,
                                              benchmark_2024=v / f)
             for k, v in c.benchmarks().items()]
    pd.concat(tiers).to_csv(c.OUT / "need_below_lw_by_benchmark.csv", index=False)

    fmt = lambda v: f"{v:,.3f}"
    with pd.option_context("display.width", 200):
        print(t.to_string(index=False, float_format=fmt))
        print()
        print(comp.pivot(index="population", columns="group", values="share")
              .to_string(float_format=lambda v: f"{v:.0%}"))
        print(comp.groupby("population").n.first())
        print("unreliable:", comp[~comp.reliable][["population", "group", "n"]].values.tolist())


if __name__ == "__main__":
    main()
