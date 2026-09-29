# SF Healthcare Career Ladders

Which entry-level healthcare jobs in San Francisco lead to a living wage, and which
tend to plateau.

**Dashboard:** https://avanthi1990.github.io/sf-healthcare-career-ladders/

Built by Avanthi Jandhyala from public data only. Every number traces to a source
file listed, with its checksum, in `data/raw/MANIFEST.csv`.

---

## What it shows

- **The need.** 60% of San Francisco full-time workers without a bachelor's degree
  earn below the MIT single-adult living wage ($32.44/hr). By group: Latino 69%, Asian
  62%, Black 60%, White 41%.
- **Which jobs clear the bar.** Among healthcare occupations below the bachelor's level,
  the most common first jobs sit just under
  that line: medical assistant $29.24, nursing assistant $28.75, dental assistant
  $31.86.
- **The ladder.** Nationally, 10-15% of medical, dental and nursing assistants who
  change occupation move into a clinical occupation whose SF median is at or above the
  living wage. For licensed vocational nurses it is 33%, and 30% become registered
  nurses.
- **Who holds the jobs.** By race, entry-level healthcare work is done
  disproportionately by Asian and Black workers. The LVN and RN rung looks much more
  like the city's workforce as a whole.
- **Measuring progress.** A living-wage progression metric for workforce training
  programs, with a logic model.

A household selector sets the living-wage benchmark for every page (single adult; two
earners with one or two children; single parent). The dashboard's **User manual**
tab explains each page, each measure, the caveats, and every source.

## How it stays current

`.github/workflows/refresh.yml` runs on the 1st of each month, or on demand from the
Actions tab. It:

1. re-downloads every source;
2. rebuilds each table from scratch;
3. regenerates `dashboard/data/dashboard.json`;
4. commits any changes;
5. republishes the site.

If a source site is unreachable, the previous copy is kept and the run continues.

## Data

| Source | Used for |
|---|---|
| EDD OEWS, San Francisco-San Mateo-Redwood City | Wages by occupation (25th, 50th, 75th percentile) |
| EDD occupational projections 2023-2033, same area | Openings, growth, occupational transfers, entry education |
| MIT Living Wage Calculator, San Francisco County | Living wage by household type |
| Schubert, Stansbury & Taska (2021) occupational transitions | Where people go when they change occupation (national, resumes 2002-2015) |
| O*NET taxonomy crosswalks | SOC 2010 to 2018 code mapping |
| ACS PUMS 2020-2024 5-year | Below-living-wage shares and workforce composition, SF residents |
| CA Department of Finance CPI (San Francisco) | Putting 2024 survey wages and the 2026 threshold in the same year's dollars |

## Running it locally

Requires Python 3.11+.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run_all.sh                          # fetch sources, rebuild every table
python3 -m http.server -d dashboard   # open http://localhost:8000
```

The ACS microdata file is 270 MB and takes a few minutes on first run. After that, a
San Francisco extract is cached in `data/interim/`.

## Layout

```
src/
  fetch.py             download sources; write MANIFEST.csv (URL, date, size, SHA-256)
  common.py            loaders, living-wage benchmarks, SOC 2010->2018 crosswalk, CPI
  need.py              below-living-wage shares (ACS PUMS, replicate-weight SEs)
  wage_screen.py       SF healthcare occupations vs. the living wage
  ladder.py            national transitions priced at SF wages
  export_dashboard.py  everything the dashboard shows -> dashboard/data/dashboard.json
  figures.py           static figures
dashboard/             static site: index.html, app.js, styles.css, data/
data/
  raw/                 every source file, unmodified, plus MANIFEST.csv
  processed/           every derived table
docs/
  data_dictionary.md   every field, its meaning, and its caveats
```

## Four things worth knowing about the code

**The occupation crosswalk is built, not hand-typed.** The transitions data uses
2010 occupation codes; SF wages use 2018 codes. `common.soc2010_to_2018()` chains
O*NET's two published crosswalks. Where a 2010 code was split, it maps through the
base occupation, so a small specialty such as "patient representatives" cannot take
half of all customer-service moves.

**National and local data are never merged into one number.** Transition shares are
national (2002-2015); wages are SF (2026) occupation medians, not movers' own earnings.
Every view shows them side by side.

**Split occupations are divided evenly.** Where one 2010 code became several 2018
codes, moves are split evenly across the successors, an assumption documented in
`common.soc2010_to_2018()`. "Clinical" excludes the administrative and
non-clinical healthcare occupations listed in `ladder.NON_CLINICAL`.

**Survey estimates carry their uncertainty.** `need.py` computes standard errors from
the 80 ACS replicate weights. It flags any estimate with fewer than 50 records or a
coefficient of variation above 30%, rather than dropping it.
