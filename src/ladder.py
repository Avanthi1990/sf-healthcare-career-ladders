"""Section 3: which entry roles lead somewhere.

For each entry-level healthcare role, takes the national distribution of where
people go when they change occupation (Schubert, Stansbury & Taska) and prices
each destination at its San Francisco median wage (EDD OEWS).

The two sources are deliberately kept side by side, not merged into a single
"SF probability": the move pattern is national, 2002-2015; the wages are SF, 2026.

Writes data/processed/ladder_summary.csv and ladder_destinations.csv
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import common as c
from wage_screen import is_health

# Entry roles examined (SOC 2010 codes, as used by the transitions data).
# Chosen as the no-bachelor's healthcare roles with the most SF employment or
# openings in the wage screen, plus LVN as the comparison "second rung".
ENTRY = {
    "31-9092": "Medical assistant",
    "31-9091": "Dental assistant",
    "43-6013": "Medical secretary / admin",
    "31-1014": "Nursing assistant",
    "31-1011": "Home health aide",
    "39-9021": "Personal care aide",
    "31-9097": "Phlebotomist",
    "29-2052": "Pharmacy technician",
    "29-2041": "EMT / paramedic",
    "29-2071": "Medical records technician",
    "31-9093": "Sterile processing technician",
    "29-2061": "Licensed vocational nurse (LVN)",
}

# Destination counts as "healthcare" under the same definition as the screen,
# plus medical and health services managers (a common promotion path).
def dest_is_health(soc18: str) -> bool:
    return is_health(soc18) or soc18 == "11-9111"


# Healthcare occupations that are not clinical (patient care or clinical technical
# work): management, administration, records and health education. The "clinical
# rung" measure excludes them; "stay in healthcare" includes them.
NON_CLINICAL = {
    "11-9111": "Medical and health services managers",
    "43-6013": "Medical secretaries and administrative assistants",
    "29-2072": "Medical records specialists",
    "29-9021": "Health information technologists and medical registrars",
    "31-9094": "Medical transcriptionists",
    "21-1094": "Community health workers",
}


def is_clinical(soc18) -> bool:
    return isinstance(soc18, str) and dest_is_health(soc18) and soc18 not in NON_CLINICAL


def origin_stats(soc10: str) -> dict:
    """SF wage, employment and projected transfers for an entry role.

    Where the 2010 role became several 2018 occupations (EMT / paramedic; medical
    records), the successors are combined: employment and transfers are summed,
    and wages are the employment-weighted mean of the successors' percentiles. A
    weighted mean of medians is not the median of the combined group; it is
    labelled as an approximation wherever it is shown.
    """
    o, p = c.oews().set_index("soc"), c.projections().set_index("soc")
    x = c.soc2010_to_2018()
    codes = sorted({c.to_oews_code(s, set(o.index)) for s in x.loc[x.soc10 == soc10, "soc18"]} - {None})
    emp = o.emp.reindex(codes)
    w = emp / emp.sum()
    return dict(
        oews_code="+".join(codes), combined=len(codes) > 1,
        sf_emp=emp.sum(),
        sf_p25=float((o.p25.reindex(codes) * w).sum()),
        sf_p50=float((o.p50.reindex(codes) * w).sum()),
        sf_annual_transfer_rate=float(p.transfers.reindex(codes).sum() / 10
                                      / p.emp_2023.reindex(codes).sum()),
    )


def priced_destinations() -> pd.DataFrame:
    t, x, o = c.transitions(), c.soc2010_to_2018(), c.oews()
    avail = set(o.soc)
    wage = o.set_index("soc")

    d = t[t.soc1.isin(ENTRY)].merge(x, left_on="soc2", right_on="soc10", how="left")
    lost = d[d.soc18.isna()]
    if len(lost):
        print(f"note: {lost.soc2.nunique()} destination codes have no 2018 SOC mapping "
              f"({lost.transition_share.sum() / d.soc1.nunique():.1%} of share on average); "
              "counted as unpriced")
    d["share"] = d.transition_share * d.weight.fillna(1)
    d["oews_code"] = d.soc18.map(lambda s: c.to_oews_code(s, avail) if isinstance(s, str) else None)
    d["dest_p50"] = d.oews_code.map(lambda s: wage.p50.get(s, np.nan) if s else np.nan)
    d["dest_title"] = d.oews_code.map(lambda s: wage.title.get(s) if s else None)
    d["dest_health"] = d.soc18.map(lambda s: dest_is_health(s) if isinstance(s, str) else False)
    d["dest_clinical"] = d.soc18.map(is_clinical)
    return d


def summarise(d: pd.DataFrame) -> pd.DataFrame:
    lw = c.lw_single()
    rows = []
    for soc10, role in ENTRY.items():
        g = d[d.soc1 == soc10]
        st = origin_stats(soc10)
        priced = g[g.dest_p50.notna()]
        above = priced.dest_p50 >= lw
        rows.append(dict(
            soc2010=soc10, role=role, **st,
            clears_lw=st["sf_p50"] >= lw,
            switch_obs=g.total_obs.iloc[0],
            share_priced=priced.share.sum(),
            share_stay_health=g.loc[g.dest_health, "share"].sum(),
            share_to_lw_any=priced.loc[above, "share"].sum(),
            share_to_lw_health=priced.loc[above & priced.dest_health, "share"].sum(),
            share_to_lw_clinical=priced.loc[above & priced.dest_clinical, "share"].sum(),
            share_to_lw_nonclinical_health=priced.loc[above & priced.dest_health
                                                      & ~priced.dest_clinical, "share"].sum(),
            share_to_manager=g.loc[g.soc18 == "11-9111", "share"].sum(),
            share_to_higher_pay=priced.loc[priced.dest_p50 >= st["sf_p50"] * 1.15, "share"].sum(),
            top_destination=g.sort_values(["share", "soc2"], ascending=[False, True], kind="stable").iloc[0].soc2_name,
            top_share=g.share.max(),
        ))
    s = pd.DataFrame(rows)
    # Cut-offs on the clinical measure are analytical choices, shown in the report.
    s["pattern"] = np.select(
        [s.share_to_lw_clinical >= 0.30, s.share_to_lw_clinical >= 0.15],
        ["Rung", "Partial rung"], "Plateau")
    return s


def main() -> None:
    d = priced_destinations()
    s = summarise(d)
    s.to_csv(c.OUT / "ladder_summary.csv", index=False)

    top = (d.sort_values(["soc1", "share", "soc2", "soc18"], ascending=[True, False, True, True], kind="stable")
             .groupby("soc1").head(8))
    top = top.assign(role=top.soc1.map(ENTRY))[
        ["soc1", "role", "soc2", "soc2_name", "soc18", "dest_title", "share",
         "dest_p50", "dest_health", "dest_clinical"]]
    top.to_csv(c.OUT / "ladder_destinations.csv", index=False)

    with pd.option_context("display.width", 240):
        print(s[["role", "sf_emp", "sf_p50", "sf_annual_transfer_rate", "share_priced",
                 "share_stay_health", "share_to_lw_any", "share_to_lw_health", "share_to_lw_clinical", "share_to_lw_nonclinical_health",
                 "top_destination", "top_share", "pattern"]]
              .to_string(index=False, float_format=lambda v: f"{v:,.3f}"))
        for soc in ["31-9092", "31-9091", "43-6013", "29-2061"]:
            print(f"\n{ENTRY[soc]}")
            print(top[top.soc1 == soc][["soc2_name", "share", "dest_p50", "dest_health"]]
                  .to_string(index=False, float_format=lambda v: f"{v:,.3f}"))


if __name__ == "__main__":
    main()
