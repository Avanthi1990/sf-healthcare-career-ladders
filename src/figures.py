"""Report figures.

Palette: reference categorical slots 1-3 (blue / orange / aqua), validated
all-pairs in light mode (worst CVD dE 9.2, worst normal-vision dE 24.0). Aqua
sits below 3:1 contrast on the light surface, so every segment is directly
labelled or listed in a table in the report. Light mode only, by design: the
deliverable is a printed PDF. Same palette and chrome as the WIOA figures.
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import common as c
from ladder import ENTRY, priced_destinations

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
INK_3 = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"

mpl.rcParams.update({
    "font.family": "Charter",
    "font.size": 9,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK_2,
    "text.color": INK,
    "xtick.color": INK_2,
    "ytick.color": INK_2,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "savefig.facecolor": SURFACE,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
})


def _recede(ax, xgrid=True):
    ax.grid(axis="x" if xgrid else "y", color=GRID, linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    ax.spines["bottom"].set_color(AXIS)


def _lw_line(ax, x, label, y=1.0, vertical=True):
    ax.axvline(x, color=INK_2, linewidth=1, linestyle=(0, (3, 2)), zorder=1)
    ax.text(x, y, f" {label}", transform=ax.get_xaxis_transform(), color=INK_2,
            fontsize=8, va="bottom", ha="left")


def fig_need() -> None:
    t = pd.read_csv(c.OUT / "need_below_lw.csv")
    rows = [("Bachelor's degree or higher", "All", "Bachelor's degree or higher"),
            ("No bachelor's degree", "All", "No bachelor's degree, all"),
            ("No bachelor's degree", "Latino", "   Latino"),
            ("No bachelor's degree", "Asian", "   Asian"),
            ("No bachelor's degree", "Black", "   Black"),
            ("No bachelor's degree", "White", "   White"),
            ("No bachelor's degree", "Women", "   Women"),
            ("No bachelor's degree", "Men", "   Men")]
    d = pd.DataFrame([dict(label=l, **t[(t.population == p) & (t.group == g)].iloc[0])
                      for p, g, l in rows])
    fig, ax = plt.subplots(figsize=(6.4, 3.1))
    y = np.arange(len(d))[::-1]
    colors = [INK_3 if i == 0 else BLUE for i in range(len(d))]
    ax.barh(y, d.share * 100, height=0.62, color=colors, zorder=2)
    ax.errorbar(d.share * 100, y, xerr=d.moe90 * 100, fmt="none", ecolor=INK,
                elinewidth=0.8, capsize=2, zorder=3)
    for yi, s, m in zip(y, d.share, d.moe90):
        ax.text(s * 100 + m * 100 + 1.2, yi, f"{s:.0%}", va="center", fontsize=8.5,
                color=INK)
    ax.set_yticks(y, d.label)
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(mpl.ticker.PercentFormatter())
    ax.set_xlabel("Share earning below the single-adult living wage "
                  "(bars show 90% margin of error)")
    _recede(ax)
    fig.savefig(c.FIG / "fig1_need.png")
    plt.close(fig)


def fig_screen() -> None:
    s = pd.read_csv(c.OUT / "wage_screen.csv")
    s = s[s.emp_2023 >= 400].sort_values("p50")
    b = c.benchmarks()
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    y = np.arange(len(s))
    clears = s.p50 >= b["Single adult"]
    ax.hlines(y, s.p25, s.p75, color=GRID, linewidth=3.5, zorder=2)
    ax.scatter(s.p50, y, s=34, color=np.where(clears, BLUE, ORANGE),
               edgecolor=SURFACE, linewidth=1.2, zorder=3)
    labels = [f"{t}  ({e:,.0f})" for t, e in zip(s.title.str.replace(
        " and Administrative Assistants", "").str.replace(
        "Licensed Practical and Licensed Vocational Nurses", "LVNs"), s.emp_2023)]
    ax.set_yticks(y, labels, fontsize=7.8)
    _lw_line(ax, b["Single adult"], f"Single adult ${b['Single adult']:.2f}")
    ax.axvline(b["Two earners, two children"], color=AXIS, linewidth=1,
               linestyle=(0, (3, 2)), zorder=1)
    ax.text(b["Two earners, two children"], 0.03,
            f" Two earners, two children:\n ${b['Two earners, two children']:.2f} per earner",
            transform=ax.get_xaxis_transform(), color=INK_3, fontsize=7.5, va="bottom")
    ax.set_xlim(10, 105)
    ax.xaxis.set_major_formatter(mpl.ticker.StrMethodFormatter("${x:,.0f}"))
    ax.set_xlabel("Hourly wage, SF-San Mateo (dot = median, bar = 25th-75th percentile)")
    _recede(ax)
    ax.legend(handles=[
        mpl.lines.Line2D([], [], marker="o", ls="", color=BLUE, label="Median at or above living wage"),
        mpl.lines.Line2D([], [], marker="o", ls="", color=ORANGE, label="Median below living wage")],
        loc="lower right", bbox_to_anchor=(1, 0.16), frameon=False, fontsize=8)
    fig.savefig(c.FIG / "fig2_screen.png")
    plt.close(fig)


def fig_ladder() -> None:
    s = pd.read_csv(c.OUT / "ladder_summary.csv")
    s = s[s.role != "Personal care aide"]  # same SF wage code as home health aide
    lw = c.lw_single()
    fig, ax = plt.subplots(figsize=(6.4, 3.9))
    size = np.sqrt(s.sf_emp.clip(lower=300)) * 2.2
    col = np.where(s.pattern == "Rung", BLUE, np.where(s.pattern == "Partial rung", AQUA, ORANGE))
    ax.scatter(s.sf_p50, s.share_to_lw_clinical * 100, s=size ** 1.25 / 2, c=col,
               alpha=0.9, edgecolor=SURFACE, linewidth=2, zorder=3)
    offsets = {"Licensed vocational nurse (LVN)": (-12, 6, "right"),
               "Home health aide": (0, -30, "center"),
               "Medical assistant": (-30, 6, "right"),
               "Nursing assistant": (-12, 2, "right"),
               "Dental assistant": (14, 22, "left"),
               "Phlebotomist": (-9, 5, "right"),
               "Medical secretary / admin": (14, -22, "left"),
               "Pharmacy technician": (-22, -24, "right"),
               "EMT / paramedic": (40, 44, "left"),
               "Medical records technician": (6, -12, "left"),
               "Sterile processing technician": (0, 14, "center")}
    for _, r in s.iterrows():
        dx, dy, ha = offsets.get(r.role, (6, 0, "left"))
        far = abs(dx) + abs(dy) > 24 and r.role != "Home health aide"
        ax.annotate(r.role.replace(" (LVN)", "").replace("Licensed vocational nurse", "LVN"),
                    (r.sf_p50, r.share_to_lw_clinical * 100), xytext=(dx, dy),
                    textcoords="offset points", ha=ha, va="center", fontsize=7.8, color=INK,
                    arrowprops=dict(arrowstyle="-", color=INK_3, lw=0.6, shrinkB=5) if far else None)
    _lw_line(ax, lw, f"Single-adult living wage ${lw:.2f}")
    ax.set_xlim(14, 52)
    ax.set_ylim(0, 42)
    ax.xaxis.set_major_formatter(mpl.ticker.StrMethodFormatter("${x:,.0f}"))
    ax.yaxis.set_major_formatter(mpl.ticker.PercentFormatter(decimals=0))
    ax.set_xlabel("San Francisco median hourly wage of the role")
    ax.set_ylabel("Of those who change occupation,\nshare moving to a clinical occupation\nwith an SF median at or above\nthe living wage")
    _recede(ax, xgrid=False)
    ax.legend(handles=[
        mpl.lines.Line2D([], [], marker="o", ls="", color=BLUE, label="Rung (30%+)"),
        mpl.lines.Line2D([], [], marker="o", ls="", color=AQUA, label="Partial (15-30%)"),
        mpl.lines.Line2D([], [], marker="o", ls="", color=ORANGE, label="Plateau (<15%)")],
        loc="upper left", frameon=False, fontsize=8, title="Bubble size = SF jobs",
        title_fontsize=7.5)
    fig.savefig(c.FIG / "fig3_ladder.png")
    plt.close(fig)


def fig_destinations() -> None:
    d = priced_destinations()
    lw = c.lw_single()
    roles = ["31-9092", "31-9091", "31-1014", "31-1011", "29-2061"]
    clinical = lambda p: p.dest_clinical
    rows = []
    for soc in roles:
        g = d[d.soc1 == soc]
        p = g[g.dest_p50.notna()]
        rows.append(dict(
            role=ENTRY[soc].replace("Licensed vocational nurse (LVN)", "LVN (second rung)"),
            # Clinical as defined by ladder.NON_CLINICAL, as in the ladder chart, so
            # the two figures agree.
            health_above=p.loc[clinical(p) & (p.dest_p50 >= lw), "share"].sum(),
            other_above=p.loc[~clinical(p) & (p.dest_p50 >= lw), "share"].sum(),
            below=p.loc[p.dest_p50 < lw, "share"].sum()))
    r = pd.DataFrame(rows)
    r.to_csv(c.OUT / "fig4_destination_mix.csv", index=False)
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    y = np.arange(len(r))[::-1]
    left = np.zeros(len(r))
    for col, color, name in [("health_above", BLUE, "Clinical occupation, median at or above living wage"),
                             ("other_above", ORANGE, "Other occupation at or above (incl. health admin and management)"),
                             ("below", AQUA, "Occupation with median below living wage")]:
        v = r[col].values * 100
        ax.barh(y, v - 0.4, left=left + 0.2, height=0.6, color=color, label=name, zorder=2)
        for yi, l, vi in zip(y, left, v):
            if vi >= 7:
                ax.text(l + vi / 2, yi, f"{vi:.0f}%", ha="center", va="center",
                        fontsize=8, color="white" if color == BLUE else INK)
        left += v
    ax.set_yticks(y, r.role)
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(mpl.ticker.PercentFormatter())
    ax.set_xlabel("Where people go when they leave the role (national, 2002-2015), "
                  "priced at SF wages. Remainder: no SF wage published.", fontsize=8)
    _recede(ax)
    ax.legend(loc="upper center", bbox_to_anchor=(0.42, -0.30), ncol=2, frameon=False,
              fontsize=7.8)
    fig.savefig(c.FIG / "fig4_destinations.png")
    plt.close(fig)


def main() -> None:
    fig_need()
    fig_screen()
    fig_ladder()
    fig_destinations()
    print(pd.read_csv(c.OUT / "fig4_destination_mix.csv").to_string(float_format=lambda v: f"{v:.3f}"))


if __name__ == "__main__":
    main()
