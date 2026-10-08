"use strict";
// Shared by shadow.html and trend.html (served by dashboard/shadow_server.py).
const SVGNS = "http://www.w3.org/2000/svg";

// ---------------------------------------------------------------- helpers
function el(tag, attrs = {}, text) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text !== undefined) n.textContent = text;
  return n;
}
function svg(tag, attrs = {}) {
  const n = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
}
function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function fmtNum(v, d = 2) { return v === null || v === undefined || Number.isNaN(v) ? "–" : Number(v).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d }); }
function fmtSigned(v, d = 2) { return v === null || v === undefined ? "–" : (v > 0 ? "+" : v < 0 ? "−" : "") + fmtNum(Math.abs(v), d); }
function fmtUsd(v) { return v === null || v === undefined ? "–" : (v < 0 ? "−$" : "$") + fmtNum(Math.abs(v), 2); }
function fmtCompact(v) { return v === null || v === undefined ? "–" : Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(v); }
function fmtTime(ms) { return new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }); }
function fmtHM(ms) { return new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
function fmtDateTime(ms) { return new Date(ms).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }); }
function priceDigits(v) { if (!v) return 2; const mag = Math.floor(Math.log10(Math.abs(v))); return Math.max(2, 4 - mag); }
function signClass(v) { return v > 0 ? "pos" : v < 0 ? "neg" : ""; }

function niceTicks(min, max, count = 5) {
  if (!(isFinite(min) && isFinite(max))) return [];
  if (min === max) { const pad = Math.abs(min) * 0.001 || 1; min -= pad; max += pad; }
  const span = max - min;
  const step0 = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const norm = step0 / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) ticks.push(+v.toPrecision(12));
  return ticks;
}
function timeTicks(t0, t1, count = 6) {
  const span = t1 - t0;
  const steps = [10e3, 30e3, 60e3, 120e3, 300e3, 600e3, 900e3, 1800e3, 3600e3, 7200e3, 21600e3, 43200e3, 86400e3];
  const step = steps.find(s => span / s <= count) || 86400e3;
  const out = [];
  for (let t = Math.ceil(t0 / step) * step; t <= t1; t += step) out.push(t);
  return out;
}

function tooltip(container) {
  let tip = container.querySelector(".tip");
  if (!tip) { tip = el("div", { class: "tip", role: "status" }); container.appendChild(tip); }
  return {
    show(x, y, title, rows) {
      tip.replaceChildren();
      tip.appendChild(el("div", { class: "t" }, title));
      for (const r of rows) {
        const row = el("div", { class: "r" });
        const k = el("span", { class: "k" });
        if (r.color) {
          const key = svg("svg", { width: 14, height: 8 });
          key.appendChild(svg("line", { x1: 1, x2: 13, y1: 4, y2: 4, stroke: r.color, "stroke-width": 2, "stroke-linecap": "round" }));
          k.appendChild(key);
        }
        k.appendChild(document.createTextNode(r.label));
        row.appendChild(k);
        row.appendChild(el("strong", {}, r.value));
        tip.appendChild(row);
      }
      tip.style.display = "block";
      const cw = container.clientWidth;
      const tw = tip.offsetWidth;
      const left = x + 14 + tw > cw ? x - 14 - tw : x + 14;
      tip.style.left = Math.max(0, left) + "px";
      tip.style.top = Math.max(0, y - 10) + "px";
    },
    hide() { tip.style.display = "none"; },
  };
}

function legend(container, items) {
  const lg = el("div", { class: "legend" });
  for (const it of items) {
    const s = el("span");
    const key = svg("svg", { width: 18, height: 12, "aria-hidden": "true" });
    if (it.kind === "band") key.appendChild(svg("rect", { x: 1, y: 2, width: 16, height: 8, rx: 2, fill: cssVar("--band"), stroke: cssVar("--axis") }));
    else if (it.kind === "up") key.appendChild(svg("path", { d: "M9 2 L13 10 L5 10 Z", fill: cssVar("--text-muted") }));
    else if (it.kind === "down") key.appendChild(svg("path", { d: "M9 10 L13 2 L5 2 Z", fill: cssVar("--text-muted") }));
    else if (it.kind === "diamond") key.appendChild(svg("path", { d: "M9 1 L14 6 L9 11 L4 6 Z", fill: cssVar("--text-primary") }));
    else key.appendChild(svg("line", { x1: 2, x2: 16, y1: 6, y2: 6, stroke: it.color, "stroke-width": 2, "stroke-linecap": "round" }));
    s.appendChild(key);
    s.appendChild(document.createTextNode(it.label));
    lg.appendChild(s);
  }
  container.appendChild(lg);
}

function frame(container, height, pad) {
  container.replaceChildren();
  const w = Math.max(280, container.clientWidth);
  const root = svg("svg", { viewBox: `0 0 ${w} ${height}`, height, role: "img" });
  container.appendChild(root);
  return { root, w, h: height, x0: pad.l, x1: w - pad.r, y0: pad.t, y1: height - pad.b };
}

function yAxis(f, ticks, y, fmt) {
  const g = svg("g", { class: "axis" });
  for (const v of ticks) {
    const yy = y(v);
    g.appendChild(svg("line", { x1: f.x0, x2: f.x1, y1: yy, y2: yy, stroke: cssVar("--grid"), "stroke-width": 1 }));
    const t = svg("text", { x: f.x0 - 8, y: yy + 4, "text-anchor": "end" });
    t.textContent = fmt(v);
    g.appendChild(t);
  }
  f.root.appendChild(g);
}
function xTimeAxis(f, t0, t1, x) {
  const g = svg("g", { class: "axis" });
  g.appendChild(svg("line", { x1: f.x0, x2: f.x1, y1: f.y1, y2: f.y1, stroke: cssVar("--axis") }));
  const span = t1 - t0;
  for (const t of timeTicks(t0, t1, Math.max(3, Math.floor((f.x1 - f.x0) / 110)))) {
    const tx = svg("text", { x: x(t), y: f.y1 + 16, "text-anchor": "middle" });
    tx.textContent = span > 36 * 3600e3 ? fmtDateTime(t) : fmtHM(t);
    g.appendChild(tx);
  }
  f.root.appendChild(g);
}

function pathFrom(xs, ys, x, y, step = false) {
  let d = "", prevY = null, open = false;
  for (let i = 0; i < xs.length; i++) {
    const v = ys[i];
    if (v === null || v === undefined) { open = false; continue; }
    const px = x(xs[i]).toFixed(1), py = y(v).toFixed(1);
    if (!open) { d += `M${px},${py}`; open = true; }
    else if (step) d += `H${px}V${py}`;
    else d += `L${px},${py}`;
    prevY = py;
  }
  return d;
}

function nearestIndex(xs, target) {
  let lo = 0, hi = xs.length - 1;
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (xs[mid] < target) lo = mid; else hi = mid; }
  return Math.abs(xs[lo] - target) <= Math.abs(xs[hi] - target) ? lo : hi;
}

function crosshair(f, container, xs, x, onIndex) {
  const line = svg("line", { y1: f.y0, y2: f.y1, stroke: cssVar("--text-muted"), "stroke-width": 1, visibility: "hidden" });
  f.root.appendChild(line);
  const hit = svg("rect", { x: f.x0, y: f.y0, width: Math.max(0, f.x1 - f.x0), height: Math.max(0, f.y1 - f.y0), fill: "transparent", tabindex: 0 });
  f.root.appendChild(hit);
  const tip = tooltip(container);
  const scale = () => container.querySelector("svg").getBoundingClientRect().width / f.w;
  const move = (clientX) => {
    const r = container.querySelector("svg").getBoundingClientRect();
    const px = (clientX - r.left) / scale();
    const t = x.invert(Math.min(f.x1, Math.max(f.x0, px)));
    const i = nearestIndex(xs, t);
    const lx = x(xs[i]);
    line.setAttribute("x1", lx); line.setAttribute("x2", lx); line.setAttribute("visibility", "visible");
    const { title, rows } = onIndex(i);
    tip.show(lx * scale(), f.y0 * scale(), title, rows);
  };
  hit.addEventListener("pointermove", e => move(e.clientX));
  hit.addEventListener("pointerleave", () => { line.setAttribute("visibility", "hidden"); tip.hide(); });
  hit.addEventListener("focus", () => { const r = container.querySelector("svg").getBoundingClientRect(); move(r.right - 1); });
  hit.addEventListener("blur", () => { line.setAttribute("visibility", "hidden"); tip.hide(); });
}

function linear(d0, d1, r0, r1) {
  const f = v => r0 + (v - d0) / (d1 - d0 || 1) * (r1 - r0);
  f.invert = p => d0 + (p - r0) / (r1 - r0 || 1) * (d1 - d0);
  return f;
}

// ---------------------------------------------------------------- panels
function statusPill(ok, label, detail) {
  const p = el("span", { class: "pill" });
  p.appendChild(el("span", { class: "dot", style: `background: var(${ok ? "--good" : "--critical"})`, "aria-hidden": "true" }));
  p.appendChild(el("b", {}, ok ? "✓" : "✕"));
  p.appendChild(document.createTextNode(` ${label}${detail ? " · " + detail : ""}`));
  return p;
}

function infoPill(label, value, warn) {
  const p = el("span", { class: "pill" });
  if (warn) { p.appendChild(el("span", { class: "dot", style: "background: var(--warning)", "aria-hidden": "true" })); p.appendChild(el("b", {}, "!")); }
  p.appendChild(document.createTextNode(label + " "));
  p.appendChild(el("b", {}, value));
  return p;
}

function tile(label, value, note, cls = "") {
  const t = el("div", { class: `card tile ${cls}` });
  t.appendChild(el("div", { class: "label" }, label));
  t.appendChild(el("div", { class: "value" }, value));
  if (note) t.appendChild(el("div", { class: "note" }, note));
  return t;
}

function td(text, cls) { const c = el("td", cls ? { class: cls } : {}); c.textContent = text; return c; }
