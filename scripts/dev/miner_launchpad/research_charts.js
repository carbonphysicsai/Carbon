"use strict";
// Carbon research charts (RSURF-D8): one SVG renderer, drawn by output kind.
//
// A chart is plain data from the campaign view: a kind (time_series, scalar,
// checkpoint_vector, field_2d or bars), its axes and units, and named series
// with a role (reference, current, previous, series). No chart library and
// nothing from the internet. Every label is text, never HTML.
//
// `layout(spec)` is pure: it returns a small tree of {tag, attrs, text,
// children} that a test can read without a browser. `render(spec)` mounts that
// tree with createElementNS and adds the legend, the data table and the hover
// readout.
(function (root) {
  const W = 480;
  const ROLE_ORDER = ["reference", "previous", "current", "series"];
  const KINDS = ["time_series", "scalar", "checkpoint_vector", "field_2d", "bars"];

  function node(tag, attrs, children, text) {
    return {tag, attrs: attrs || {}, children: children || [], text: text === undefined ? null : String(text)};
  }
  const finite = value => typeof value === "number" && Number.isFinite(value);
  function fmt(value) {
    if (!finite(value)) return "no value";
    const abs = Math.abs(value);
    if (abs !== 0 && (abs < 1e-3 || abs >= 1e5)) return value.toExponential(2);
    return String(Number(value.toPrecision(4)));
  }
  function unitText(unit) { return unit ? " " + unit : ""; }
  // Ticks a person can read: 1, 2 or 5 times a power of ten.
  function niceTicks(low, high, count) {
    if (!finite(low) || !finite(high)) return [];
    if (low === high) { const pad = Math.abs(low) * 0.1 || 1; low -= pad; high += pad; }
    const raw = (high - low) / Math.max(1, count);
    const power = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 5, 10].map(m => m * power).find(s => s >= raw) || 10 * power;
    const ticks = [];
    for (let v = Math.ceil(low / step) * step; v <= high + step * 1e-9; v += step) ticks.push(Number(v.toPrecision(12)));
    return ticks;
  }
  function logTicks(low, high) {
    const ticks = [];
    for (let e = Math.floor(Math.log10(low)); e <= Math.ceil(Math.log10(high)); e++) ticks.push(Math.pow(10, e));
    return ticks;
  }
  function allValues(spec) {
    const out = [];
    for (const series of spec.series) {
      const values = series.values;
      if (values === null || values === undefined) continue;
      if (spec.kind === "scalar") { if (finite(values)) out.push(values); continue; }
      for (const item of values) {
        if (Array.isArray(item)) { for (const v of item) if (finite(v)) out.push(v); }
        else if (finite(item)) out.push(item);
      }
    }
    return out;
  }
  // Role and position decide the style class, never the series' rank alone.
  function styleClass(series, index) {
    if (series.role === "series") return "ch-s" + (index % 4);
    return "ch-" + series.role;
  }
  function yScale(spec, values, top, bottom) {
    const log = spec.log === true && values.length && values.every(v => v > 0);
    let low = values.length ? Math.min(...values) : 0;
    let high = values.length ? Math.max(...values) : 1;
    if (log) {
      const ticks = logTicks(low, high);
      low = ticks[0]; high = ticks[ticks.length - 1];
      if (low === high) high = low * 10;
      const map = v => bottom - (Math.log10(v) - Math.log10(low)) / (Math.log10(high) - Math.log10(low)) * (bottom - top);
      return {map, ticks: ticks.filter(t => t >= low && t <= high), log: true};
    }
    if (spec.kind === "bars") low = Math.min(0, low);
    const ticks = niceTicks(low, high, 4);
    if (ticks.length) { low = Math.min(low, ticks[0]); high = Math.max(high, ticks[ticks.length - 1]); }
    if (low === high) high = low + 1;
    const map = v => bottom - (v - low) / (high - low) * (bottom - top);
    return {map, ticks, log: false};
  }
  function frame(spec, height, left, right) {
    return node("svg", {viewBox: "0 0 " + W + " " + height, class: "ch-svg ch-" + spec.kind, role: "img", "aria-label": spec.title + (spec.unit ? " (" + spec.unit + ")" : "")});
  }
  function yAxis(svg, y, left, right, unit) {
    for (const tick of y.ticks) {
      const at = y.map(tick);
      svg.children.push(node("line", {x1: left, x2: right, y1: at, y2: at, class: "ch-grid"}));
      svg.children.push(node("text", {x: left - 8, y: at + 4, "text-anchor": "end", class: "ch-tick"}, [], fmt(tick)));
    }
    if (unit) svg.children.push(node("text", {x: left - 8, y: 10, "text-anchor": "end", class: "ch-unit"}, [], unit));
  }

  // time_series and checkpoint_vector: lines over one axis (numbers or labels).
  function lines(spec) {
    const height = 260, left = 60, top = 18, bottom = height - 42;
    // Direct labels for several plain series (the legend names the roles).
    const multi = spec.series.length > 1 && spec.series.every(series => series.role === "series");
    const right = W - (multi ? 92 : 18);
    const labels = [];
    const axis = spec.axes[0];
    const coords = axis.values;
    const numeric = spec.kind === "time_series" && coords.every(finite);
    const n = coords.length;
    const xAt = numeric
      ? (() => { const lo = Math.min(...coords), hi = Math.max(...coords); return i => left + (hi === lo ? 0.5 : (coords[i] - lo) / (hi - lo)) * (right - left); })()
      : i => left + (n === 1 ? 0.5 : i / (n - 1)) * (right - left);
    const values = allValues(spec);
    const y = yScale(spec, values, top, bottom);
    const svg = frame(spec, height);
    yAxis(svg, y, left, right, spec.unit);
    const xticks = numeric ? niceTicks(Math.min(...coords), Math.max(...coords), 6) : coords.map((_, i) => i);
    for (const tick of xticks) {
      const at = numeric ? left + (tick - Math.min(...coords)) / ((Math.max(...coords) - Math.min(...coords)) || 1) * (right - left) : xAt(tick);
      svg.children.push(node("text", {x: at, y: bottom + 18, "text-anchor": "middle", class: "ch-tick"}, [], numeric ? fmt(tick) : String(coords[tick])));
    }
    svg.children.push(node("line", {x1: left, x2: right, y1: bottom, y2: bottom, class: "ch-axis"}));
    svg.children.push(node("text", {x: (left + right) / 2, y: height - 6, "text-anchor": "middle", class: "ch-axis-label"}, [], axis.name + (axis.unit ? " (" + axis.unit + ")" : "")));
    const markers = !numeric || n <= 40;
    const ordered = spec.series.map((series, index) => ({series, index})).sort((a, b) => ROLE_ORDER.indexOf(a.series.role) - ROLE_ORDER.indexOf(b.series.role));
    for (const {series, index} of ordered) {
      const cls = styleClass(series, index);
      if (!Array.isArray(series.values)) continue;
      let path = "", pen = false, last = null;
      series.values.forEach((value, i) => {
        if (!finite(value) || (y.log && value <= 0)) { pen = false; return; }
        path += (pen ? "L" : "M") + xAt(i).toFixed(2) + " " + y.map(value).toFixed(2) + " ";
        pen = true; last = i;
      });
      if (path) svg.children.push(node("path", {d: path.trim(), class: "ch-line " + cls}));
      if (markers) series.values.forEach((value, i) => {
        if (!finite(value) || (y.log && value <= 0)) return;
        svg.children.push(node("circle", {cx: xAt(i), cy: y.map(value), r: 4, class: "ch-dot " + cls}, [node("title", {}, [], series.label + ": " + fmt(value) + unitText(spec.unit) + " at " + axis.name + " " + coords[i])]));
      });
      // Direct labels at the line's end: identity is never colour alone.
      if (multi && last !== null) labels.push({x: xAt(last) + 8, y: y.map(series.values[last]) + 4, cls, text: series.label});
    }
    // Labels that would overlap are spread apart, 13 units at least.
    labels.sort((a, b) => a.y - b.y);
    for (let i = 1; i < labels.length; i++) labels[i].y = Math.max(labels[i].y, labels[i - 1].y + 13);
    for (const label of labels) svg.children.push(node("text", {x: label.x, y: Math.min(label.y, height - 4), class: "ch-direct " + label.cls}, [], label.text));
    // The hover readout's geometry, read by render().
    svg.attrs["data-plot"] = JSON.stringify({left, right, top, bottom, n, numeric});
    return {svg, xAt, height};
  }

  // scalar: one dot per series on a shared axis, its value beside it.
  function scalars(spec) {
    const rows = spec.series.length;
    const height = 36 + rows * 34, left = 150, right = W - 70;
    const values = allValues(spec);
    let low = values.length ? Math.min(...values) : 0, high = values.length ? Math.max(...values) : 1;
    const pad = (high - low) * 0.15 || Math.abs(high) * 0.15 || 1;
    low -= pad; high += pad;
    const ticks = niceTicks(low, high, 4);
    const x = v => left + (v - low) / (high - low) * (right - left);
    const svg = frame(spec, height);
    for (const tick of ticks) {
      if (tick < low || tick > high) continue;
      svg.children.push(node("line", {x1: x(tick), x2: x(tick), y1: 10, y2: height - 22, class: "ch-grid"}));
      svg.children.push(node("text", {x: x(tick), y: height - 6, "text-anchor": "middle", class: "ch-tick"}, [], fmt(tick)));
    }
    spec.series.forEach((series, index) => {
      const at = 24 + index * 34;
      const cls = styleClass(series, index);
      svg.children.push(node("text", {x: left - 12, y: at + 4, "text-anchor": "end", class: "ch-row-label"}, [], series.label));
      if (finite(series.values)) {
        svg.children.push(node("circle", {cx: x(series.values), cy: at, r: 6, class: "ch-dot " + cls}, [node("title", {}, [], series.label + ": " + fmt(series.values) + unitText(spec.unit))]));
        svg.children.push(node("text", {x: x(series.values) + 12, y: at + 4, class: "ch-value"}, [], fmt(series.values) + unitText(spec.unit)));
      } else svg.children.push(node("text", {x: left, y: at + 4, class: "ch-missing"}, [], "no value"));
    });
    return {svg, height};
  }

  // field_2d: one heatmap per series, small multiples on one shared scale.
  function fields(spec) {
    const [rows, columns] = spec.axes.map(axis => axis.values.length);
    const count = spec.series.length;
    const gap = 16, label = 22;
    const size = Math.min(220, (W - gap * (count - 1)) / count);
    const cell = Math.min(size / columns, size / rows);
    const height = label + cell * rows + 34;
    const values = allValues(spec);
    const low = values.length ? Math.min(...values) : 0, high = values.length ? Math.max(...values) : 1;
    const svg = frame(spec, height);
    spec.series.forEach((series, index) => {
      const x0 = index * (cell * columns + gap);
      svg.children.push(node("text", {x: x0, y: 14, class: "ch-row-label"}, [], series.label));
      if (!Array.isArray(series.values)) { svg.children.push(node("text", {x: x0, y: label + 20, class: "ch-missing"}, [], "no value")); return; }
      series.values.forEach((row, r) => row.forEach((value, c) => {
        const shade = finite(value) ? 0.06 + 0.94 * (high === low ? 0.5 : (value - low) / (high - low)) : 0;
        svg.children.push(node("rect", {x: x0 + c * cell, y: label + r * cell, width: cell, height: cell, class: finite(value) ? "ch-cell" : "ch-cell-missing", "fill-opacity": shade.toFixed(3)}, [node("title", {}, [], series.label + " [" + spec.axes[0].name + " " + spec.axes[0].values[r] + ", " + spec.axes[1].name + " " + spec.axes[1].values[c] + "]: " + fmt(value) + unitText(spec.unit))]));
      }));
    });
    // The shared scale, light to dark: one hue (sequential).
    const y = label + cell * rows + 14;
    for (let i = 0; i < 10; i++) svg.children.push(node("rect", {x: i * 14, y, width: 14, height: 8, class: "ch-cell", "fill-opacity": (0.06 + 0.94 * i / 9).toFixed(3)}));
    svg.children.push(node("text", {x: 146, y: y + 8, class: "ch-tick"}, [], fmt(low) + " to " + fmt(high) + unitText(spec.unit)));
    return {svg, height};
  }

  // bars: grouped bars, one group per category, one bar per series.
  function bars(spec) {
    const height = 240, left = 60, right = W - 18, top = 18, bottom = height - 40;
    const categories = spec.axes[0].values;
    const values = allValues(spec);
    const y = yScale(spec, values, top, bottom);
    const svg = frame(spec, height);
    yAxis(svg, y, left, right, spec.unit);
    const group = (right - left) / categories.length;
    const width = Math.min(36, (group - 16) / spec.series.length);
    const zero = y.map(Math.max(0, Math.min(...(y.ticks.length ? y.ticks : [0]))));
    categories.forEach((category, c) => {
      const start = left + c * group + (group - width * spec.series.length - 2 * (spec.series.length - 1)) / 2;
      spec.series.forEach((series, s) => {
        const value = Array.isArray(series.values) ? series.values[c] : null;
        if (!finite(value)) return;
        const top = Math.min(y.map(value), zero), h = Math.abs(zero - y.map(value));
        const cls = styleClass(series, s);
        svg.children.push(node("rect", {x: start + s * (width + 2), y: top, width, height: Math.max(1, h), class: "ch-bar " + cls}, [node("title", {}, [], series.label + " · " + category + ": " + fmt(value) + unitText(spec.unit))]));
        if (series.role === "current") svg.children.push(node("text", {x: start + s * (width + 2) + width / 2, y: top - 5, "text-anchor": "middle", class: "ch-value"}, [], fmt(value)));
      });
      svg.children.push(node("text", {x: left + c * group + group / 2, y: bottom + 18, "text-anchor": "middle", class: "ch-tick"}, [], String(category)));
    });
    svg.children.push(node("line", {x1: left, x2: right, y1: zero, y2: zero, class: "ch-axis"}));
    return {svg, height};
  }

  function layout(spec) {
    if (!spec || !KINDS.includes(spec.kind)) throw new Error("unknown chart kind");
    if (!Array.isArray(spec.series) || !spec.series.length) throw new Error("a chart needs a series");
    if (spec.kind === "scalar") return scalars(spec);
    if (spec.kind === "field_2d") return fields(spec);
    if (spec.kind === "bars") return bars(spec);
    return lines(spec);
  }

  // A table view of the same numbers, for reading and for screen readers.
  function table(spec) {
    const head = ["Series"];
    let rows = [];
    if (spec.kind === "scalar") {
      head.push("Value" + unitText(spec.unit));
      rows = spec.series.map(series => [series.label, fmt(series.values)]);
    } else if (spec.kind === "field_2d") {
      head.push("Min", "Max");
      rows = spec.series.map(series => {
        const flat = Array.isArray(series.values) ? series.values.flat().filter(finite) : [];
        return [series.label, flat.length ? fmt(Math.min(...flat)) : "no value", flat.length ? fmt(Math.max(...flat)) : "no value"];
      });
    } else {
      const coords = spec.axes[0].values;
      const step = Math.max(1, Math.ceil(coords.length / 13));
      const picked = coords.map((_, i) => i).filter(i => i % step === 0 || i === coords.length - 1);
      head.push(...picked.map(i => spec.axes[0].name + " " + coords[i]));
      rows = spec.series.map(series => [series.label, ...picked.map(i => fmt(Array.isArray(series.values) ? series.values[i] : null))]);
    }
    return {head, rows};
  }

  function mount(tree, doc) {
    const element = doc.createElementNS("http://www.w3.org/2000/svg", tree.tag);
    for (const [key, value] of Object.entries(tree.attrs)) element.setAttribute(key, String(value));
    if (tree.text !== null) element.textContent = tree.text;
    for (const child of tree.children) element.append(mount(child, doc));
    return element;
  }

  function render(spec, doc) {
    doc = doc || document;
    const figure = doc.createElement("figure");
    figure.className = "ch-figure";
    figure.dataset.chart = spec.id;
    figure.dataset.kind = spec.kind;
    const caption = doc.createElement("figcaption");
    caption.textContent = spec.title + (spec.unit && spec.kind !== "bars" ? " · " + spec.unit : "") + (spec.log ? " · log scale" : "");
    figure.append(caption);
    const built = layout(spec);
    const svg = mount(built.svg, doc);
    const plot = doc.createElement("div"); plot.className = "ch-plot";
    plot.append(svg);
    figure.append(plot);
    if (spec.series.length > 1) {
      const legend = doc.createElement("ul"); legend.className = "ch-legend";
      spec.series.forEach((series, index) => {
        const item = doc.createElement("li");
        const swatch = doc.createElement("span"); swatch.className = "ch-swatch " + styleClass(series, index);
        swatch.setAttribute("aria-hidden", "true");
        const text = doc.createElement("span"); text.textContent = series.label;
        item.append(swatch, text); legend.append(item);
      });
      figure.append(legend);
    }
    if (built.xAt) hover(figure, plot, svg, spec, built, doc);
    const data = table(spec);
    const box = doc.createElement("details"); box.className = "ch-data";
    const summary = doc.createElement("summary"); summary.textContent = "Data";
    const wrap = doc.createElement("div"); wrap.className = "table-wrap";
    const grid = doc.createElement("table"); grid.className = "metrics-table";
    const headRow = doc.createElement("tr");
    for (const cell of data.head) { const th = doc.createElement("th"); th.textContent = cell; headRow.append(th); }
    grid.append(headRow);
    for (const row of data.rows) { const tr = doc.createElement("tr"); for (const cell of row) { const td = doc.createElement("td"); td.textContent = cell; tr.append(td); } grid.append(tr); }
    wrap.append(grid); box.append(summary, wrap); figure.append(box);
    return figure;
  }

  // A crosshair and readout on a line chart: nearest point, every series.
  function hover(figure, plot, svg, spec, built, doc) {
    const geometry = JSON.parse(built.svg.attrs["data-plot"]);
    const readout = doc.createElement("p"); readout.className = "ch-readout"; readout.hidden = true;
    readout.setAttribute("aria-live", "polite");
    const cross = doc.createElementNS("http://www.w3.org/2000/svg", "line");
    cross.setAttribute("class", "ch-cross"); cross.setAttribute("y1", geometry.top); cross.setAttribute("y2", geometry.bottom);
    cross.setAttribute("visibility", "hidden");
    svg.append(cross);
    plot.append(readout);
    const coords = spec.axes[0].values;
    svg.addEventListener("pointermove", event => {
      const box = svg.getBoundingClientRect();
      if (!box.width) return;
      const x = (event.clientX - box.left) / box.width * W;
      let best = 0, distance = Infinity;
      for (let i = 0; i < geometry.n; i++) { const d = Math.abs(built.xAt(i) - x); if (d < distance) { distance = d; best = i; } }
      cross.setAttribute("x1", built.xAt(best)); cross.setAttribute("x2", built.xAt(best));
      cross.setAttribute("visibility", "visible");
      readout.textContent = spec.axes[0].name + " " + coords[best] + (spec.axes[0].unit ? " " + spec.axes[0].unit : "") + " · " + spec.series.map(series => series.label + " " + fmt(Array.isArray(series.values) ? series.values[best] : null)).join(" · ") + unitText(spec.unit);
      readout.hidden = false;
    });
    svg.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); readout.hidden = true; });
  }

  const api = {layout, render, table, fmt, niceTicks, KINDS};
  root.CarbonCharts = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
