"""Download every public source used in the report into data/raw/ and write a
manifest (URL, retrieval date, size, SHA-256) so each figure traces to a file.

Files already present are not re-downloaded unless --refresh is passed; either way
they are checksummed and recorded.
bls.gov and dol.gov refuse scripted requests, so nothing here depends on them.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import sys
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko)"

SOURCES = [
    # (local file, url, what it is)
    ("edd_oews_sf_md_2026.xlsx",
     "https://labormarketinfo.edd.ca.gov/file/occup$/oeswages/"
     "CA-OEWS-San%20Francisco-San%20Mateo-Redwood%20City%20MD-2026.xlsx",
     "EDD OEWS wages, San Francisco-San Mateo-Redwood City MD (May 2025 estimates aged to 2026Q1)"),
    ("edd_occproj_sf_2023_2033.xlsx",
     "https://labormarketinfo.edd.ca.gov/file/occproj/sanf$OccProj.xlsx",
     "EDD long-term occupational projections 2023-2033, San Francisco-San Mateo-Redwood City MD"),
    ("mit_living_wage_sf_county.html",
     "https://livingwage.mit.edu/counties/06075",
     "MIT Living Wage Calculator, San Francisco County"),
    ("occ_transitions_public_2021.7z",
     "https://annastansbury.github.io/website/"
     "Occ%20Transitions%20Public%20Data%20Set%20%28Jan%202021%29.7z",
     "Schubert, Stansbury & Taska occupational transitions public data set (Jan 2021)"),
    ("acs_pums_ca_person_2020_2024.zip",
     "https://www2.census.gov/programs-surveys/acs/data/pums/2024/5-Year/csv_pca.zip",
     "ACS PUMS 2020-2024 5-year, California person records"),
    ("cadof_cpi_all_items_monthly.xlsx",
     "https://dof.ca.gov/media/docs/forecasting/economics/economic-indicators/inflation/CPI-All-Item-Monthly-6.xlsx",
     "CA Dept of Finance CPI-U by MSA incl. San Francisco (from BLS/DIR), for wage-year alignment"),
    ("onet_2010_to_2019_crosswalk.csv",
     "https://www.onetcenter.org/taxonomy/2019/walk/2010_to_2019_Crosswalk.csv?fmt=csv",
     "O*NET-SOC 2010 to O*NET-SOC 2019 taxonomy crosswalk"),
    ("onet_2019_to_soc2018_crosswalk.csv",
     "https://www.onetcenter.org/taxonomy/2019/soc/2019_to_SOC_Crosswalk.csv?fmt=csv",
     "O*NET-SOC 2019 to 2018 SOC crosswalk"),
    ("pums_data_dictionary_2020_2024.csv",
     "https://www2.census.gov/programs-surveys/acs/tech_docs/pums/data_dict/PUMS_Data_Dictionary_2020-2024.csv",
     "ACS PUMS 2020-2024 data dictionary (variable and occupation code definitions)"),
]


def report_sources() -> list:
    """Report-only sources live in src/report_sources.py, which ships with the
    written report but not with the public repository."""
    try:
        from report_sources import REPORT_SOURCES
    except ImportError:
        return []
    return REPORT_SOURCES


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as r, dest.open("wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)


def main() -> int:
    refresh = "--refresh" in sys.argv
    report = "--report" in sys.argv
    status = run(SOURCES, RAW / "MANIFEST.csv", refresh)
    if report and report_sources():
        status |= run(report_sources(), RAW / "report" / "MANIFEST.csv", refresh)
    return status


def run(sources, manifest_path: Path, refresh: bool) -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    prior = {}
    if manifest_path.exists():
        prior = {r["file"]: r for r in csv.DictReader(manifest_path.open())}

    rows, failed = [], []
    for name, url, desc in sources:
        dest = RAW / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if refresh or not dest.exists():
            print(f"fetching {name} ...", flush=True)
            part = dest.with_name(dest.name + ".part")
            try:
                fetch(url, part)
                part.replace(dest)
            except Exception as e:
                part.unlink(missing_ok=True)
                if dest.exists():  # a refresh failed: keep the copy we already have
                    print(f"  kept existing {name}: {e}", file=sys.stderr)
                else:
                    failed.append((name, str(e)))
                    continue
            else:
                prior.pop(name, None)  # new download: record today's date
        retrieved = prior.get(name, {}).get("retrieved", today)
        rows.append(dict(file=name, url=url, description=desc, retrieved=retrieved,
                         bytes=dest.stat().st_size, sha256=sha256(dest)))

    with manifest_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} sources recorded in {manifest_path.relative_to(RAW.parents[1])}")
    for name, err in failed:
        print(f"FAILED {name}: {err}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
