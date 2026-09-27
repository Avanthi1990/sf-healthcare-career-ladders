/* SF Healthcare Career Ladders dashboard.
   Reads data/dashboard.json (built by src/export_dashboard.py) and draws every
   page with D3. Every benchmark-dependent number is precomputed in the JSON;
   this file only looks values up and draws them. */
(function () {
  "use strict";

  const state = { bench: "Single adult", role: "Medical assistant", tab: "overview" };
  let DATA = null;

  const pct = (v, d = 0) => (v == null ? "n/a" : (v * 100).toFixed(d) + "%");
  const money = (v) => (v == null ? "n/a" : "$" + v.toFixed(2));
  const num = (v) => (v == null ? "n/a" : Math.round(v).toLocaleString("en-US"));
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
  };
  const benchValue = () => DATA.meta.benchmarks[state.bench];

  /* ---------------------------------------------------------------- tooltip */
  const tip = document.getElementById("tip");
  function showTip(evt, title, rows) {
    tip.innerHTML = `<b>${esc(title)}</b>` +
      rows.map(([k, v]) => `<div class="row"><span>${esc(k)}</span><span>${esc(v)}</span></div>`).join("");
    tip.hidden = false;
    const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
    let x = evt.clientX + pad, y = evt.clientY + pad;
    if (x + w > window.innerWidth - 8) x = evt.clientX - w - pad;
    if (y + h > window.innerHeight - 8) y = evt.clientY - h - pad;
    tip.style.left = Math.max(8, x) + "px";
    tip.style.top = Math.max(8, y) + "px";
  }
  const hideTip = () => { tip.hidden = true; };
  function bindTip(sel, fn) {
    sel.on("pointerenter pointermove", (e, d) => { const [t, r] = fn(d); showTip(e, t, r); })
       .on("pointerleave", hideTip);
  }

  const width = (id) => Math.max(300, document.getElementById(id).clientWidth);
  function table(id, head, rows, numeric) {
    const th = head.map((h, i) => `<th class="${numeric[i] ? "n" : ""}">${esc(h)}</th>`).join("");
    const tr = rows.map((r) => "<tr>" + r.map((c, i) => `<td class="${numeric[i] ? "n" : ""}">${esc(c)}</td>`).join("") + "</tr>").join("");
    document.getElementById(id).innerHTML = `<div class="table-wrap"><table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table></div>`;
  }
  function truncate(s, n) { return s.length > n ? s.slice(0, n - 1) + "…" : s; }

  /* ---------------------------------------------------------------- overview */
  function renderOverview() {
    const b = benchValue();
    const noBA = DATA.need.find((r) => r.benchmark === state.bench && r.population === "No bachelor's degree" && r.group === "All");
    const clears = DATA.screen.filter((r) => r.p50 != null && r.p50 >= b).length;
    const ma = DATA.ladder.roles.find((r) => r.role === "Medical assistant");
    const lvn = DATA.ladder.roles.find((r) => r.role.startsWith("Licensed vocational"));
    const rn = lvn.top_destinations.find((d) => d.name === "Registered nurses");
    const tiles = [
      [pct(noBA.share), `of SF full-time workers without a bachelor's degree earn below ${money(b)}/hr`],
      [`${clears} of ${DATA.screen.length}`, `healthcare occupations without a degree requirement have a median at or above ${money(b)}`],
      [pct(ma.mix[state.bench].clinical_above), "of medical assistants who change occupation move into a clinical job paying at least that"],
      [pct(rn ? rn.share : null), "of LVNs who change occupation become registered nurses (SF median $98.67)"],
    ];
    document.getElementById("tiles").innerHTML = tiles.map(([v, k]) => `<div class="tile"><div class="v">${v}</div><div class="k">${k}</div></div>`).join("");
  }

  /* ---------------------------------------------------------------- need */
  const NEED_ROWS = [
    ["Bachelor's degree or higher", "All", "Bachelor's degree or higher"],
    ["No bachelor's degree", "All", "No bachelor's degree, all"],
    ["No bachelor's degree", "Latino", "Latino"],
    ["No bachelor's degree", "Asian", "Asian"],
    ["No bachelor's degree", "Black", "Black"],
    ["No bachelor's degree", "White", "White"],
    ["No bachelor's degree", "Other / multiracial", "Other / multiracial"],
    ["No bachelor's degree", "Women", "Women"],
    ["No bachelor's degree", "Men", "Men"],
  ];
  function renderNeed() {
    const rows = NEED_ROWS.map(([p, g, label]) => ({ label, indent: g !== "All",
      ...DATA.need.find((r) => r.benchmark === state.bench && r.population === p && r.group === g) }));
    const all = rows[1];
    document.getElementById("need-lede").textContent =
      `Without a degree, ${pct(all.share)} of full-time workers (about ${num(Math.round(all.below_count / 100) * 100)} people) earn below the living wage for "${state.bench.toLowerCase()}". With a degree, ${pct(rows[0].share)}.`;

    const W = width("need-chart"), m = { t: 8, r: 56, b: 30, l: Math.min(190, W * 0.38) };
    const rowH = 30, H = m.t + m.b + rows.length * rowH;
    const x = d3.scaleLinear([0, 1], [m.l, W - m.r]);
    const y = d3.scaleBand(rows.map((r) => r.label), [m.t, H - m.b]).padding(0.28);
    const svg = d3.select("#need-chart").html("").append("svg").attr("viewBox", `0 0 ${W} ${H}`)
      .attr("role", "img").attr("aria-label", "Share earning below the living wage, by group");
    svg.append("g").attr("class", "grid").selectAll("line").data(x.ticks(5)).join("line")
      .attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", H - m.b);
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).ticks(5).tickFormat(d3.format(".0%")).tickSize(0).tickPadding(8)).select(".domain").remove();
    svg.append("g").selectAll("text").data(rows).join("text")
      .attr("x", m.l - 10).attr("y", (d) => y(d.label) + y.bandwidth() / 2)
      .attr("dy", "0.35em").attr("text-anchor", "end").text((d) => d.label)
      .style("font-weight", (d) => (d.indent ? 400 : 600));
    const g = svg.append("g").selectAll("g").data(rows).join("g");
    g.append("rect").attr("x", m.l).attr("y", (d) => y(d.label)).attr("height", y.bandwidth())
      .attr("width", (d) => Math.max(0, x(d.share) - m.l)).attr("rx", 4)
      .style("fill", (d, i) => (i === 0 ? "var(--muted-bar)" : "var(--s1)"));
    g.append("line").attr("x1", (d) => x(Math.max(0, d.share - d.moe90))).attr("x2", (d) => x(Math.min(1, d.share + d.moe90)))
      .attr("y1", (d) => y(d.label) + y.bandwidth() / 2).attr("y2", (d) => y(d.label) + y.bandwidth() / 2)
      .style("stroke", "var(--ink)").attr("stroke-width", 1.2);
    g.append("text").attr("class", "val").attr("x", (d) => x(Math.min(1, d.share + d.moe90)) + 6)
      .attr("y", (d) => y(d.label) + y.bandwidth() / 2).attr("dy", "0.35em")
      .text((d) => pct(d.share) + (d.reliable ? "" : " †"));
    const hit = g.append("rect").attr("class", "hit").attr("x", 0).attr("width", W)
      .attr("y", (d) => y(d.label) - (y.step() - y.bandwidth()) / 2).attr("height", y.step());
    bindTip(hit, (d) => [d.label, [
      ["Below living wage", pct(d.share, 1)], ["90% margin of error", "±" + pct(d.moe90, 1)],
      ["Workers below", num(d.below_count)], ["Full-time workers", num(d.weighted)],
      ["Survey records", num(d.n)], ["Reliable", d.reliable ? "Yes" : "No (†)"]]]);
    table("need-table", ["Group", "Below living wage", "±90% MOE", "Workers below", "Records"],
      rows.map((d) => [d.label, pct(d.share, 1), pct(d.moe90, 1), num(d.below_count), num(d.n)]), [0, 1, 1, 1, 1]);
  }

  /* ---------------------------------------------------------------- jobs */
  function renderJobs() {
    const b = benchValue();
    const all = DATA.screen.filter((r) => r.p50 != null);
    const below = all.filter((r) => r.p50 < b);
    const sum = (a, k) => d3.sum(a, (r) => r[k]);
    document.getElementById("jobs-tiles").innerHTML = [
      [`${all.length - below.length} of ${all.length}`, `occupations have a median at or above ${money(b)}`],
      [pct(sum(below, "emp_2023") / sum(all, "emp_2023")), "of these healthcare jobs are in occupations with a median below it"],
      [pct(sum(below, "openings") / sum(all, "openings")), "of projected openings to 2033 are in those occupations"],
      [`${all.filter((r) => r.p25 >= b).length} of ${all.length}`, "clear it at the 25th percentile, a rough proxy for entry pay"],
    ].map(([v, k]) => `<div class="tile"><div class="v">${v}</div><div class="k">${k}</div></div>`).join("");

    const small = document.getElementById("jobs-small").checked;
    const rows = all.filter((r) => small || r.emp_2023 >= 400).sort((a, c) => c.p50 - a.p50);
    const W = width("jobs-chart"), narrow = W < 560;
    const m = { t: 22, r: 18, b: 32, l: narrow ? Math.min(150, W * 0.42) : 290 };
    const rowH = 22, H = m.t + m.b + rows.length * rowH;
    const x = d3.scaleLinear([10, Math.max(105, b + 8)], [m.l, W - m.r]);
    const y = d3.scaleBand(rows.map((r) => r.soc), [m.t, H - m.b]).padding(0.2);
    document.getElementById("jobs-legend").innerHTML =
      `<span><i style="background:var(--s1)"></i>Median at or above ${money(b)}</span><span><i style="background:var(--s2)"></i>Median below</span>`;
    const svg = d3.select("#jobs-chart").html("").append("svg").attr("viewBox", `0 0 ${W} ${H}`)
      .attr("role", "img").attr("aria-label", "Hourly wage by occupation");
    svg.append("g").attr("class", "grid").selectAll("line").data(x.ticks(6)).join("line")
      .attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", H - m.b);
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).ticks(6).tickFormat((d) => "$" + d).tickSize(0).tickPadding(8)).select(".domain").remove();
    svg.append("line").attr("class", "ref").attr("x1", x(b)).attr("x2", x(b)).attr("y1", m.t - 4).attr("y2", H - m.b);
    svg.append("text").attr("class", "ref-label").attr("x", x(b) + 4).attr("y", m.t - 8).text(`${state.bench} ${money(b)}`);
    const label = (r) => (r.title.replace(" and Administrative Assistants", "").replace("Licensed Practical and Licensed Vocational Nurses", "LVNs"));
    svg.append("g").selectAll("text").data(rows).join("text")
      .attr("x", m.l - 10).attr("y", (d) => y(d.soc) + y.bandwidth() / 2).attr("dy", "0.35em")
      .attr("text-anchor", "end").text((d) => truncate(label(d), narrow ? 22 : 48));
    const g = svg.append("g").selectAll("g").data(rows).join("g");
    g.append("line").attr("x1", (d) => x(d.p25)).attr("x2", (d) => x(d.p75))
      .attr("y1", (d) => y(d.soc) + y.bandwidth() / 2).attr("y2", (d) => y(d.soc) + y.bandwidth() / 2)
      .style("stroke", "var(--range)").attr("stroke-width", 5).attr("stroke-linecap", "round");
    g.append("circle").attr("cx", (d) => x(d.p50)).attr("cy", (d) => y(d.soc) + y.bandwidth() / 2).attr("r", 5)
      .style("fill", (d) => (d.p50 >= b ? "var(--s1)" : "var(--s2)")).style("stroke", "var(--surface)").attr("stroke-width", 2);
    const hit = g.append("rect").attr("class", "hit").attr("x", 0).attr("width", W)
      .attr("y", (d) => y(d.soc) - (y.step() - y.bandwidth()) / 2).attr("height", y.step());
    bindTip(hit, (d) => [d.title, [
      ["Median", money(d.p50)], ["25th to 75th percentile", `${money(d.p25)} to ${money(d.p75)}`],
      ["Jobs (2023)", num(d.emp_2023)], ["Openings 2023-33", num(d.openings)],
      ["Growth 2023-33", pct(d.growth_2023_33, 1)], ["Leave occupation each year", pct(d.annual_transfer_rate, 1)],
      ["Entry education", d.entry_ed]]]);
    table("jobs-table", ["Occupation", "Entry education", "Jobs", "Openings", "25th", "Median", "75th"],
      rows.map((d) => [d.title, d.entry_ed, num(d.emp_2023), num(d.openings), money(d.p25), money(d.p50), money(d.p75)]),
      [0, 0, 1, 1, 1, 1, 1]);
  }

  /* ---------------------------------------------------------------- ladder */
  const shortRole = (r) => r.replace("Licensed vocational nurse (LVN)", "LVN");
  const klass = (v) => (v >= 0.30 ? "Rung" : v >= 0.15 ? "Partial rung" : "Plateau");
  const klassColor = { "Rung": "var(--s1)", "Partial rung": "var(--s3)", "Plateau": "var(--s2)" };

  function placeLabels(pts, W, H, m) {
    const boxes = pts.map((p) => ({ x0: p.cx - p.r, x1: p.cx + p.r, y0: p.cy - p.r, y1: p.cy + p.r }));
    const hits = (b) => boxes.some((o) => !(b.x1 < o.x0 || b.x0 > o.x1 || b.y1 < o.y0 || b.y0 > o.y1));
    pts.slice().sort((a, b) => b.r - a.r).forEach((p) => {
      const w = p.text.length * 6.3, h = 13;
      const cands = [
        [p.cx + p.r + 4, p.cy - h / 2, "start"], [p.cx - p.r - 4 - w, p.cy - h / 2, "end"],
        [p.cx - w / 2, p.cy - p.r - h - 2, "middle"], [p.cx - w / 2, p.cy + p.r + 2, "middle"],
        [p.cx + p.r * 0.7, p.cy - p.r - h, "start"], [p.cx - p.r * 0.7 - w, p.cy + p.r, "end"],
      ];
      for (const [x0, y0, anchor] of cands) {
        const b = { x0, x1: x0 + w, y0, y1: y0 + h };
        if (b.x0 < m.l || b.x1 > W - 4 || b.y0 < 0 || b.y1 > H - m.b || hits(b)) continue;
        boxes.push(b);
        p.lx = anchor === "start" ? x0 : anchor === "end" ? x0 + w : x0 + w / 2; p.ly = y0 + h / 2; p.anchor = anchor;
        return;
      }
      p.lx = null;
    });
    // Second pass for anything still unlabelled: allow overlapping bubbles (text sits
    // above them), but never another label.
    const labelBoxes = boxes.slice(pts.length);
    pts.filter((p) => p.lx == null).forEach((p) => {
      const w = p.text.length * 6.3, h = 13;
      const cands = [[p.cx - w / 2, p.cy + p.r + 2, "middle"], [p.cx - w / 2, p.cy - p.r - h - 2, "middle"],
        [p.cx + p.r + 4, p.cy - h / 2, "start"], [p.cx - p.r - 4 - w, p.cy - h / 2, "end"],
        [p.cx - w / 2, p.cy + p.r + h + 2, "middle"], [p.cx - w / 2, p.cy - p.r - 2 * h - 2, "middle"]];
      for (const [x0, y0, anchor] of cands) {
        const b = { x0, x1: x0 + w, y0, y1: y0 + h };
        if (b.x0 < m.l || b.x1 > W - 4 || b.y0 < 0 || b.y1 > H - m.b) continue;
        if (labelBoxes.some((o) => !(b.x1 < o.x0 || b.x0 > o.x1 || b.y1 < o.y0 || b.y0 > o.y1))) continue;
        labelBoxes.push(b);
        p.lx = anchor === "start" ? x0 : anchor === "end" ? x0 + w : x0 + w / 2; p.ly = y0 + h / 2; p.anchor = anchor;
        return;
      }
    });
  }

  function renderLadder() {
    const b = benchValue(), roles = DATA.ladder.roles;
    const pts = roles.map((r) => ({ ...r, v: r.mix[state.bench].clinical_above }));
    const W = width("ladder-chart"), H = Math.round(Math.min(560, Math.max(340, W * 0.9)));
    const m = { t: 18, r: 14, b: 40, l: 46 };
    const x = d3.scaleLinear([14, Math.max(52, b + 4)], [m.l, W - m.r]);
    const y = d3.scaleLinear([0, Math.max(0.42, d3.max(pts, (p) => p.v) + 0.05)], [H - m.b, m.t]);
    const r = d3.scaleSqrt([0, d3.max(pts, (p) => p.sf_emp)], [0, Math.min(34, W / 16)]);
    document.getElementById("ladder-legend").innerHTML = ["Rung", "Partial rung", "Plateau"].map((k) =>
      `<span><i style="background:${klassColor[k]}"></i>${k} (${k === "Rung" ? "30%+" : k === "Plateau" ? "under 15%" : "15-30%"})</span>`).join("") +
      "<span>Bubble size = SF jobs</span>";
    const svg = d3.select("#ladder-chart").html("").append("svg").attr("viewBox", `0 0 ${W} ${H}`)
      .attr("role", "img").attr("aria-label", "Entry roles by wage and upward mobility");
    svg.append("g").attr("class", "grid").selectAll("line").data(y.ticks(5)).join("line")
      .attr("x1", m.l).attr("x2", W - m.r).attr("y1", y).attr("y2", y);
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).ticks(6).tickFormat((d) => "$" + d).tickSize(0).tickPadding(8)).select(".domain").remove();
    svg.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`)
      .call(d3.axisLeft(y).ticks(5).tickFormat(d3.format(".0%")).tickSize(0).tickPadding(6)).select(".domain").remove();
    svg.append("text").attr("x", (m.l + W - m.r) / 2).attr("y", H - 4).attr("text-anchor", "middle").text("SF median hourly wage of the role");
    svg.append("line").attr("class", "ref").attr("x1", x(b)).attr("x2", x(b)).attr("y1", m.t).attr("y2", H - m.b);
    svg.append("text").attr("class", "ref-label").attr("x", x(b) + 4).attr("y", m.t + 2).text(money(b));
    pts.forEach((p) => { p.cx = x(p.sf_p50); p.cy = y(p.v); p.r = Math.max(5, r(p.sf_emp)); p.text = shortRole(p.role); });
    const sorted = pts.slice().sort((a, c) => c.r - a.r);
    const g = svg.append("g").selectAll("g").data(sorted).join("g").style("cursor", "pointer")
      .on("click", (e, d) => { state.role = d.role; document.getElementById("role").value = d.role; renderLadder(); });
    g.append("circle").attr("cx", (d) => d.cx).attr("cy", (d) => d.cy).attr("r", (d) => d.r)
      .style("fill", (d) => klassColor[klass(d.v)]).style("fill-opacity", 0.9)
      .style("stroke", (d) => (d.role === state.role ? "var(--ink)" : "var(--surface)"))
      .attr("stroke-width", (d) => (d.role === state.role ? 2.5 : 2));
    bindTip(g, (d) => [d.role, [
      ["SF median", money(d.sf_p50)], ["SF jobs", num(d.sf_emp)],
      ["Leavers to clinical job above " + money(b), pct(d.v)],
      ["Leavers staying in healthcare", pct(d.share_stay_health)],
      ["Leaves occupation each year (SF)", pct(d.annual_transfer_rate, 1)], ["Pattern", klass(d.v)]]]);
    placeLabels(pts, W, H, m);
    svg.append("g").selectAll("text").data(pts.filter((p) => p.lx != null)).join("text")
      .attr("x", (d) => d.lx).attr("y", (d) => d.ly).attr("dy", "0.35em").attr("text-anchor", (d) => d.anchor)
      .style("fill", "var(--ink)").style("font-weight", (d) => (d.role === state.role ? 700 : 400)).style("pointer-events", "none")
      .text((d) => d.text);
    renderRole();
  }

  function renderRole() {
    const b = benchValue(), r = DATA.ladder.roles.find((d) => d.role === state.role), mix = r.mix[state.bench];
    document.getElementById("role-title").textContent = `Where ${shortRole(r.role).toLowerCase()}s go next`;
    document.getElementById("role-facts").innerHTML = [
      [money(r.sf_p50), "SF median wage"], [num(r.sf_emp), "SF jobs"],
      [pct(r.annual_transfer_rate, 1), "leave the occupation each year"], [pct(r.share_stay_health), "of leavers stay in healthcare"],
    ].map(([v, k]) => `<div><b>${v}</b><span>${k}</span></div>`).join("");

    const segs = [
      ["Clinical job, at or above " + money(b), mix.clinical_above, "var(--s1)"],
      ["Other job at or above (incl. management)", mix.other_above, "var(--s2)"],
      ["Any job below", mix.below, "var(--s3)"],
      ["No SF wage published", mix.no_sf_wage, "var(--axis)"],
    ];
    const W = width("mix-chart"), H = 64, bar = 30;
    const x = d3.scaleLinear([0, 1], [0, W]);
    const svg = d3.select("#mix-chart").html("").append("svg").attr("viewBox", `0 0 ${W} ${H + 44}`)
      .attr("role", "img").attr("aria-label", "Where leavers go, by pay");
    let acc = 0;
    const data = segs.map(([k, v, c]) => { const o = { k, v, c, x0: acc }; acc += v; return o; });
    const g = svg.append("g").selectAll("g").data(data).join("g");
    g.append("rect").attr("x", (d) => x(d.x0) + (d.x0 > 0 ? 1 : 0)).attr("y", 4).attr("height", bar)
      .attr("width", (d) => Math.max(0, x(d.v) - 2)).attr("rx", 3).style("fill", (d) => d.c);
    g.append("text").attr("x", (d) => x(d.x0 + d.v / 2)).attr("y", 4 + bar / 2).attr("dy", "0.35em").attr("text-anchor", "middle")
      .style("fill", (d, i) => (i === 0 ? "#fff" : "var(--ink)")).style("font-size", "12px")
      .text((d) => (x(d.v) > 36 ? pct(d.v) : ""));
    bindTip(g, (d) => [d.k, [["Share of leavers", pct(d.v, 1)]]]);
    const leg = svg.append("g").attr("transform", `translate(0, ${bar + 20})`);
    let lx = 0, ly = 0;
    data.forEach((d) => {
      const w = d.k.length * 6.4 + 22;
      if (lx + w > W) { lx = 0; ly += 18; }
      leg.append("rect").attr("x", lx).attr("y", ly - 5).attr("width", 10).attr("height", 10).attr("rx", 2).style("fill", d.c);
      leg.append("text").attr("x", lx + 14).attr("y", ly).attr("dy", "0.35em").style("font-size", "11.5px").text(d.k);
      lx += w;
    });
    svg.attr("viewBox", `0 0 ${W} ${bar + 30 + ly + 10}`);

    const dest = r.top_destinations.map((d) => ({ ...d,
      cat: d.sf_p50 == null ? 3 : d.sf_p50 >= b ? (d.clinical ? 0 : 1) : 2 }));
    const catColor = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--axis)"];
    const DW = width("dest-chart"), narrow = DW < 480;
    const m = { t: 4, r: 44, b: 6, l: narrow ? Math.min(150, DW * 0.46) : 250 };
    const rowH = 22, DH = m.t + m.b + dest.length * rowH;
    const dx = d3.scaleLinear([0, d3.max(dest, (d) => d.share)], [m.l, DW - m.r]);
    const dy = d3.scaleBand(dest.map((d, i) => i), [m.t, DH - m.b]).padding(0.25);
    const dsvg = d3.select("#dest-chart").html("").append("svg").attr("viewBox", `0 0 ${DW} ${DH}`)
      .attr("role", "img").attr("aria-label", "Most common destinations");
    const dg = dsvg.append("g").selectAll("g").data(dest).join("g");
    dg.append("text").attr("x", m.l - 8).attr("y", (d, i) => dy(i) + dy.bandwidth() / 2).attr("dy", "0.35em")
      .attr("text-anchor", "end").text((d) => truncate(d.name, narrow ? 22 : 40));
    dg.append("rect").attr("x", m.l).attr("y", (d, i) => dy(i)).attr("height", dy.bandwidth())
      .attr("width", (d) => Math.max(1, dx(d.share) - m.l)).attr("rx", 3).style("fill", (d) => catColor[d.cat]);
    dg.append("text").attr("class", "val").attr("x", (d) => dx(d.share) + 5).attr("y", (d, i) => dy(i) + dy.bandwidth() / 2)
      .attr("dy", "0.35em").text((d) => pct(d.share, 1));
    const hit = dg.append("rect").attr("class", "hit").attr("x", 0).attr("width", DW)
      .attr("y", (d, i) => dy(i) - 2).attr("height", dy.step());
    bindTip(hit, (d) => [d.name, [["Share of leavers", pct(d.share, 1)], ["SF median", money(d.sf_p50)],
      ["Clinical healthcare", d.clinical ? "Yes" : "No"]]]);
  }

  /* ---------------------------------------------------------------- who */
  function renderWho() {
    const groups = ["Asian", "Black", "Latino", "White", "Other / multiracial", "Women"];
    const pops = [
      ["All employed SF residents", "All SF workers", "var(--muted-bar)"],
      ["Entry healthcare roles (pooled)", "Entry healthcare roles", "var(--s2)"],
      ["LVNs and registered nurses", "LVNs and RNs", "var(--s1)"],
    ];
    const get = (p, g) => DATA.composition.find((r) => r.population === p && r.group === g);
    const W = width("who-chart"), m = { t: 30, r: 60, b: 28, l: Math.min(150, W * 0.3) };
    const H = m.t + m.b + groups.length * 64;
    const x = d3.scaleLinear([0, 1], [m.l, W - m.r]);
    const y0 = d3.scaleBand(groups, [m.t, H - m.b]).padding(0.18);
    const y1 = d3.scaleBand(pops.map((p) => p[0]), [0, y0.bandwidth()]).padding(0.12);
    const svg = d3.select("#who-chart").html("").append("svg").attr("viewBox", `0 0 ${W} ${H}`)
      .attr("role", "img").attr("aria-label", "Workforce composition by rung");
    let lx = m.l;
    pops.forEach(([, label, c]) => {
      svg.append("rect").attr("x", lx).attr("y", 6).attr("width", 10).attr("height", 10).attr("rx", 2).style("fill", c);
      svg.append("text").attr("x", lx + 14).attr("y", 11).attr("dy", "0.35em").text(label);
      lx += label.length * 6.6 + 34;
    });
    svg.append("g").attr("class", "grid").selectAll("line").data(x.ticks(5)).join("line")
      .attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", H - m.b);
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).ticks(5).tickFormat(d3.format(".0%")).tickSize(0).tickPadding(8)).select(".domain").remove();
    const gg = svg.append("g").selectAll("g").data(groups).join("g").attr("transform", (g) => `translate(0,${y0(g)})`);
    gg.append("text").attr("x", m.l - 10).attr("y", y0.bandwidth() / 2).attr("dy", "0.35em").attr("text-anchor", "end")
      .style("font-weight", 600).text((g) => g);
    const bars = gg.selectAll("g").data((g) => pops.map(([p, label, c]) => ({ g, p, label, c, ...get(p, g) }))).join("g");
    bars.append("rect").attr("x", m.l).attr("y", (d) => y1(d.p)).attr("height", y1.bandwidth())
      .attr("width", (d) => Math.max(1, x(d.share) - m.l)).attr("rx", 3).style("fill", (d) => d.c);
    bars.append("text").attr("class", "val").attr("x", (d) => x(d.share) + 5).attr("y", (d) => y1(d.p) + y1.bandwidth() / 2)
      .attr("dy", "0.35em").style("font-size", "11px").text((d) => pct(d.share) + (d.reliable ? "" : " †"));
    const hit = bars.append("rect").attr("class", "hit").attr("x", 0).attr("width", W).attr("y", (d) => y1(d.p)).attr("height", y1.step());
    bindTip(hit, (d) => [`${d.g}: ${d.label}`, [["Share", pct(d.share, 1)], ["90% margin of error", "±" + pct(d.moe90, 1)],
      ["Survey records", num(d.n)], ["Reliable", d.reliable ? "Yes" : "No (†)"]]]);
    table("who-table", ["Group"].concat(pops.map((p) => p[1])),
      groups.map((g) => [g].concat(pops.map(([p]) => { const r = get(p, g); return `${pct(r.share)} ±${pct(r.moe90)}${r.reliable ? "" : " †"}`; }))),
      [0, 1, 1, 1]);
  }

  /* ---------------------------------------------------------------- manual */
  function renderSources() {
    table("sources", ["Source", "File", "Retrieved"],
      DATA.meta.sources.map((s) => [s.description, s.file, s.retrieved]), [0, 0, 0]);
    const rows = document.querySelectorAll("#sources tbody tr");
    DATA.meta.sources.forEach((s, i) => {
      const td = rows[i].children[0];
      td.innerHTML = `<a href="${esc(s.url)}" rel="noopener">${esc(s.description)}</a>`;
    });
    document.getElementById("built").textContent = "Data rebuilt " + DATA.meta.built;
  }

  /* ---------------------------------------------------------------- wiring */
  const renderers = { overview: renderOverview, need: renderNeed, jobs: renderJobs, ladder: renderLadder, who: renderWho };
  function renderTab() { (renderers[state.tab] || (() => {}))(); }

  function setTab(tab) {
    if (!document.getElementById(tab)) tab = "overview";
    state.tab = tab;
    document.querySelectorAll(".page").forEach((p) => { p.hidden = p.id !== tab; });
    document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
    hideTip();
    renderTab();
  }

  function applyTheme(t) {
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
    else document.documentElement.removeAttribute("data-theme");
  }

  function init(data) {
    DATA = data;
    const sel = document.getElementById("bench");
    sel.innerHTML = Object.keys(DATA.meta.benchmarks).map((k) => `<option>${esc(k)}</option>`).join("");
    const saved = store.get("bench");
    if (saved && DATA.meta.benchmarks[saved]) state.bench = saved;
    sel.value = state.bench;
    const note = () => { document.getElementById("bench-note").textContent = money(benchValue()) + "/hr per earner"; };
    note();
    sel.addEventListener("change", () => { state.bench = sel.value; store.set("bench", sel.value); note(); renderTab(); });

    const roleSel = document.getElementById("role");
    roleSel.innerHTML = DATA.ladder.roles.map((r) => `<option>${esc(r.role)}</option>`).join("");
    roleSel.value = state.role;
    roleSel.addEventListener("change", () => { state.role = roleSel.value; renderLadder(); });
    document.getElementById("jobs-small").addEventListener("change", renderJobs);

    document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => { location.hash = b.dataset.tab; }));
    window.addEventListener("hashchange", () => setTab(location.hash.slice(1)));
    applyTheme(store.get("theme"));
    document.getElementById("theme").addEventListener("click", () => {
      const dark = document.documentElement.getAttribute("data-theme") === "dark" ||
        (!document.documentElement.hasAttribute("data-theme") && matchMedia("(prefers-color-scheme: dark)").matches);
      const next = dark ? "light" : "dark";
      applyTheme(next); store.set("theme", next);
    });
    let t; window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(renderTab, 150); });
    document.addEventListener("scroll", hideTip, { passive: true });

    renderSources();
    setTab(location.hash.slice(1) || "overview");
  }

  fetch("data/dashboard.json").then((r) => r.json()).then(init).catch((e) => {
    document.querySelector("main").innerHTML = `<div class="card">Could not load data/dashboard.json (${esc(e.message)}). If you opened this file directly, serve the folder instead: <code>python3 -m http.server -d dashboard</code></div>`;
  });
})();
