"""Shared paths, loaders and reference values.

Every loader reads a file in data/raw/ (see data/raw/MANIFEST.csv for its URL and
checksum). Nothing is typed in by hand except the occupation lists, which are
analytical choices and are labelled as such.
"""
from __future__ import annotations

import json
import re
import zipfile
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "data" / "processed"
FIG = ROOT / "report" / "figures"
for _p in (INTERIM, OUT, FIG):
    _p.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- living wage


@lru_cache
def living_wage() -> pd.DataFrame:
    """MIT Living Wage for San Francisco County, hourly, per working adult.

    Returns one row per household type with living, poverty and minimum wage.
    """
    t = pd.read_html(RAW / "mit_living_wage_sf_county.html")[0]
    t = t.set_index(t.columns[0])
    rows = []
    for (adults, kids), col in zip(t.columns, t.columns):
        adults = re.sub(r"\s+", " ", adults.replace("(", " (")).strip().title()
        kids = re.sub(r"\s+", " ", kids).strip().title()
        rows.append(dict(
            household=f"{adults}, {kids.lower()}",
            adults=adults, children=kids,
            living=_money(t.loc["Living Wage", col]),
            poverty=_money(t.loc["Poverty Wage", col]),
        ))
    return pd.DataFrame(rows)


def _money(s) -> float:
    return float(str(s).replace("$", "").replace(",", ""))


def lw(adults: str, children: str) -> float:
    d = living_wage()
    hit = d[d.adults.str.startswith(adults) & (d.children == children)]
    assert len(hit) == 1, (adults, children, hit)
    return float(hit.living.iloc[0])


def benchmarks() -> dict[str, float]:
    return {
        "Single adult": lw("1 Adult", "0 Children"),
        "Two earners, one child": lw("2 Adults (Both Working)", "1 Child"),
        "Two earners, two children": lw("2 Adults (Both Working)", "2 Children"),
        "Single parent, one child": lw("1 Adult", "1 Child"),
    }


def lw_single() -> float:
    """The benchmark used throughout: one adult, no children. It is the lowest
    MIT living wage for any household with a single earner, so a wage that
    misses it misses every such household."""
    return lw("1 Adult", "0 Children")


# ---------------------------------------------------------------- wages (EDD OEWS)


def _num(x) -> float:
    s = str(x).replace("*", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return np.nan


@lru_cache
def oews() -> pd.DataFrame:
    """EDD OEWS, San Francisco-San Mateo-Redwood City MD. May 2025 employment,
    wages aged to 2026 Q1. An asterisk marks a top-coded or flagged value; the
    number is kept and the flag recorded."""
    o = pd.read_excel(RAW / "edd_oews_sf_md_2026.xlsx", "OEWS Data", header=2)
    o.columns = ["msa", "area", "soc", "title", "emp", "emp_rse", "mean_h",
                 "mean_a", "mean_rse", "p25", "p50", "p75"]
    o = o[o.soc.astype(str).str.match(r"^\d{2}-\d{4}$")].copy()
    o["flagged"] = o[["p25", "p50", "p75"]].astype(str).apply(
        lambda r: r.str.contains(r"\*").any(), axis=1)
    for c in ["emp", "emp_rse", "mean_h", "p25", "p50", "p75"]:
        o[c] = o[c].map(_num)
    return o.drop(columns=["msa", "area", "mean_a", "mean_rse"]).reset_index(drop=True)


@lru_cache
def projections() -> pd.DataFrame:
    """EDD 2023-2033 occupational projections, SF-San Mateo-Redwood City MD."""
    p = pd.read_excel(RAW / "edd_occproj_sf_2023_2033.xlsx", "Occupational", header=3)
    p.columns = ["level", "soc", "title", "emp_2023", "emp_2033", "change",
                 "growth", "exits", "transfers", "openings", "p50_2025",
                 "p50_annual_2025", "entry_ed", "experience", "ojt"]
    p = p[p.soc.astype(str).str.match(r"^\d{2}-\d{4}$")].copy()
    for c in ["emp_2023", "emp_2033", "change", "growth", "exits",
              "transfers", "openings"]:
        p[c] = p[c].map(_num)
    for c in ["entry_ed", "experience", "ojt"]:
        p[c] = p[c].astype(str).str.strip().replace({"nan": np.nan, "": np.nan})
    return p.reset_index(drop=True)


NO_BA = {
    "No formal educational credential", "High school diploma or equivalent",
    "Some college, no degree", "Postsecondary non-degree award",
    "Associate's degree",
}

# ---------------------------------------------------------------- SOC crosswalk


@lru_cache
def soc2010_to_2018() -> pd.DataFrame:
    """6-digit SOC 2010 -> 6-digit SOC 2018, built from O*NET's published
    taxonomy crosswalks (2010 O*NET-SOC -> 2019 O*NET-SOC -> 2018 SOC).

    A 2010 code can map to several 2018 codes; `weight` (summing to 1 per 2010
    code) splits it so a transition share is never double-counted.
    """
    a = pd.read_csv(RAW / "onet_2010_to_2019_crosswalk.csv", dtype=str)
    b = pd.read_csv(RAW / "onet_2019_to_soc2018_crosswalk.csv", dtype=str)
    a.columns = ["onet10", "t10", "onet19", "t19"]
    b.columns = ["onet19", "t19", "soc18", "soc18_title"]
    m = a.merge(b[["onet19", "soc18"]], on="onet19", how="inner")
    m["soc10"] = m.onet10.str[:7]
    # Where O*NET has the base occupation (xx-xxxx.00), map through it alone.
    # Otherwise a small specialty split out in 2019 (e.g. Patient Representatives,
    # once part of Customer Service Representatives) would take an equal share
    # of the whole occupation.
    base = m[m.onet10.str.endswith(".00")]
    m = pd.concat([base, m[~m.soc10.isin(base.soc10)]])
    m = m[["soc10", "soc18"]].drop_duplicates().reset_index(drop=True)
    # Where one 2010 code became several 2018 codes, the crosswalk does not say how
    # its workers divided. Allocate by each successor's SF employment (OEWS), and
    # evenly where no successor has published employment. An assumption, shown in
    # the report's appendix.
    o = oews().set_index("soc").emp
    avail = set(o.index)
    m["emp"] = m.soc18.map(lambda s: o.get(to_oews_code(s, avail) or "", np.nan))
    n = m.groupby("soc10").soc18.transform("nunique")
    tot = m.groupby("soc10").emp.transform("sum")
    m["weight"] = np.where(n == 1, 1.0, np.where(tot > 0, m.emp.fillna(0) / tot, 1 / n))
    # Successors sharing one broad OEWS code would double-count its employment.
    m["oews_code"] = m.soc18.map(lambda s: to_oews_code(s, avail))
    dup = m.duplicated(["soc10", "oews_code"], keep=False) & m.oews_code.notna() & (n > 1)
    if dup.any():
        k = m[dup].groupby(["soc10", "oews_code"]).soc18.transform("nunique")
        m.loc[dup, "weight"] = m.loc[dup, "weight"] / k
        m["weight"] = m.weight / m.groupby("soc10").weight.transform("sum")
    return m[["soc10", "soc18", "weight"]]


def to_oews_code(soc18: str, available: set[str]) -> str | None:
    """OEWS publishes some 2018 detailed codes only as a broad group (e.g. home
    health and personal care aides as 31-1120). Fall back to the broad code."""
    if soc18 in available:
        return soc18
    broad = soc18[:6] + "0"
    return broad if broad in available else None


# ---------------------------------------------------------------- transitions


@lru_cache
def transitions() -> pd.DataFrame:
    """Schubert, Stansbury & Taska (2021) national occupational transitions.

    transition_share = P(move from soc1 to soc2 | leave soc1), year to year,
    resumes 2002-2015, age-reweighted. SOC 2010 codes.
    """
    d = INTERIM / "Occ Transitions Public Data Set (Jan 2021)"
    f = d / "occupation_transitions_public_data_set.dta"
    subset = RAW / "occ_transitions_entry_roles.csv"
    archive = RAW / "occ_transitions_public_2021.7z"
    if not f.exists() and not archive.exists() and subset.exists():
        # Emailed copy: the 22 MB archive is replaced by the rows this analysis
        # uses (see MANIFEST.csv for the full file's URL and checksum).
        return pd.read_csv(subset, dtype={"soc1": str, "soc2": str})
    if not f.exists():
        import shutil
        import subprocess
        archive = str(RAW / "occ_transitions_public_2021.7z")
        if shutil.which("7z"):  # Linux runners: GNU tar cannot read .7z
            subprocess.run(["7z", "x", "-y", f"-o{INTERIM}", archive], check=True,
                           capture_output=True)
        else:  # macOS tar is bsdtar, which can
            subprocess.run(["tar", "-xf", archive, "-C", str(INTERIM)], check=True)
    return pd.read_stata(f)


# ---------------------------------------------------------------- CPI


@lru_cache
def cpi_sf() -> pd.Series:
    """San Francisco CPI-U (bimonthly), from the CA Department of Finance."""
    x = pd.read_excel(RAW / "cadof_cpi_all_items_monthly.xlsx", header=None)
    x[0] = x[0].astype(str).str.extract(r"(\d{4})")[0].ffill()
    x = x[x[1].isin(["January", "February", "March", "April", "May", "June", "July",
                     "August", "September", "October", "November", "December"])]
    s = pd.to_numeric(x[10], errors="coerce")
    s.index = pd.to_datetime(x[0] + "-" + x[1], format="%Y-%B")
    return s.dropna()


# MIT's 2026 estimates are "adjusted for inflation to December 2025 dollars"
# (livingwage.mit.edu/pages/methodology). SF CPI is published for that month.
MIT_PRICE_BASIS = "2025-12"


def cpi_factor_2024_to_mit_basis() -> float:
    """SF price level at MIT's price basis (Dec 2025) relative to the 2024 average,
    the dollar year of the ACS wages."""
    s = cpi_sf()
    return float(s[MIT_PRICE_BASIS].iloc[0] / s["2024"].mean())


# ---------------------------------------------------------------- ACS PUMS

SF_PUMAS = {"07507", "07508", "07509", "07510", "07511", "07512", "07513", "07514"}
PUMS_COLS = ["PUMA", "ADJINC", "PWGTP", "AGEP", "SCHL", "SEX", "WAGP", "WKHP",
             "WKWN", "HISP", "RAC1P", "OCCP", "ESR", "COW"] + [f"PWGTP{i}" for i in range(1, 81)]


def pums_sf() -> pd.DataFrame:
    """San Francisco County person records, ACS PUMS 2020-2024 5-year.

    Cached to data/interim after the first read of the 270 MB state file, and
    rebuilt whenever that file's size or modification time changes.
    """
    cache = INTERIM / "pums_sf_2020_2024.parquet"
    stamp = INTERIM / "pums_sf_2020_2024.source.json"
    src = RAW / "acs_pums_ca_person_2020_2024.zip"
    if cache.exists() and not src.exists():
        return pd.read_parquet(cache)  # offline copy: only the extract is shipped
    sig = {"bytes": src.stat().st_size, "mtime": int(src.stat().st_mtime)}
    if cache.exists() and stamp.exists() and json.loads(stamp.read_text()) == sig:
        return pd.read_parquet(cache)
    z = zipfile.ZipFile(src)
    name = next(n for n in z.namelist() if n.endswith(".csv"))
    parts = []
    with z.open(name) as f:
        for ch in pd.read_csv(f, usecols=PUMS_COLS, dtype={"PUMA": str, "OCCP": str},
                              chunksize=200_000):
            ch["PUMA"] = ch.PUMA.str.zfill(5)
            parts.append(ch[ch.PUMA.isin(SF_PUMAS)])
    df = pd.concat(parts, ignore_index=True)
    df.to_parquet(cache)
    stamp.write_text(json.dumps(sig))
    return df
