/* Timeline charts for MM dashboard — 1D / 1W / 1M / custom range */
(function () {
  const MS_DAY = 86400000;

  function parsePayload() {
    const el = document.getElementById("mm-timeseries");
    if (!el) return {};
    try {
      return JSON.parse(el.textContent || "{}");
    } catch {
      return {};
    }
  }

  function fmtTick(ms, spanMs) {
    const d = new Date(ms);
    if (spanMs <= MS_DAY * 2) {
      return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    }
    if (spanMs <= MS_DAY * 14) {
      return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit" });
    }
    return d.toLocaleString(undefined, { month: "short", day: "numeric" });
  }

  function filterRange(points, startMs, endMs) {
    if (!points || !points.length) return [];
    return points.filter((p) => p.t >= startMs && p.t <= endMs);
  }

  function drawChart(canvas, points, color, includeZero) {
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const w = Math.max(rect.width, 280);
    const h = Math.max(rect.height, 140);
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const pad = { l: 48, r: 12, t: 10, b: 28 };
    const innerW = w - pad.l - pad.r;
    const innerH = h - pad.t - pad.b;

    if (!points.length) {
      ctx.fillStyle = "#8b93a7";
      ctx.font = "12px system-ui,sans-serif";
      ctx.fillText("No data in range", pad.l, pad.t + 24);
      return;
    }

    const xs = points.map((p) => p.t);
    const ys = points.map((p) => p.v);
    let yMin = Math.min(...ys);
    let yMax = Math.max(...ys);
    if (includeZero) {
      yMin = Math.min(yMin, 0);
      yMax = Math.max(yMax, 0);
    }
    if (yMin === yMax) {
      yMin -= 1;
      yMax += 1;
    }
    const xMin = xs[0];
    const xMax = xs[xs.length - 1];
    const xSpan = xMax - xMin || 1;
    const ySpan = yMax - yMin || 1;

    const xMap = (t) => pad.l + ((t - xMin) / xSpan) * innerW;
    const yMap = (v) => pad.t + innerH - ((v - yMin) / ySpan) * innerH;

    ctx.strokeStyle = "#252b38";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad.l, pad.t);
    ctx.lineTo(pad.l, pad.t + innerH);
    ctx.lineTo(pad.l + innerW, pad.t + innerH);
    ctx.stroke();

    if (includeZero && yMin < 0 && yMax > 0) {
      const y0 = yMap(0);
      ctx.strokeStyle = "#4b5563";
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(pad.l, y0);
      ctx.lineTo(pad.l + innerW, y0);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    points.forEach((p, i) => {
      const x = xMap(p.t);
      const y = yMap(p.v);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    ctx.fillStyle = "#8b93a7";
    ctx.font = "10px system-ui,sans-serif";
    ctx.fillText(fmtTick(xMin, xSpan), pad.l, h - 8);
    const endLabel = fmtTick(xMax, xSpan);
    const tw = ctx.measureText(endLabel).width;
    ctx.fillText(endLabel, pad.l + innerW - tw, h - 8);

    ctx.textAlign = "right";
    ctx.fillText(yMax.toFixed(2), pad.l - 6, pad.t + 10);
    ctx.fillText(yMin.toFixed(2), pad.l - 6, pad.t + innerH);
    ctx.textAlign = "left";
  }

  function getRange(panel) {
    const preset = panel.dataset.rangePreset || "1d";
    const now = Date.now();
    if (preset === "1d") return [now - MS_DAY, now];
    if (preset === "1w") return [now - 7 * MS_DAY, now];
    if (preset === "1m") return [now - 30 * MS_DAY, now];
    if (preset === "custom") {
      const from = panel.querySelector(".range-from")?.value;
      const to = panel.querySelector(".range-to")?.value;
      const start = from ? new Date(from).getTime() : now - MS_DAY;
      const end = to ? new Date(to).getTime() : now;
      return [Math.min(start, end), Math.max(start, end)];
    }
    return [now - MS_DAY, now];
  }

  function redrawPanel(panel, payload) {
    const stack = panel.dataset.stack;
    const stackData = payload[stack];
    if (!stackData) return;
    const [startMs, endMs] = getRange(panel);
    panel.querySelectorAll("canvas.time-chart").forEach((canvas) => {
      const path = canvas.dataset.seriesPath;
      const color = canvas.dataset.color || "#60a5fa";
      const zero = canvas.dataset.zeroLine === "1";
      let points = [];
      if (path && stackData) {
        const parts = path.split(".");
        let cur = stackData;
        for (const p of parts) cur = cur?.[p];
        points = filterRange(cur || [], startMs, endMs);
      }
      drawChart(canvas, points, color, zero);
    });
  }

  function bindRangeBar(panel, payload) {
    panel.querySelectorAll(".range-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        panel.dataset.rangePreset = btn.dataset.range;
        panel.querySelectorAll(".range-btn").forEach((b) => b.classList.toggle("active", b === btn));
        const custom = panel.querySelector(".range-custom");
        if (custom) custom.hidden = btn.dataset.range !== "custom";
        redrawPanel(panel, payload);
      });
    });
    panel.querySelectorAll(".range-from, .range-to").forEach((inp) => {
      inp.addEventListener("change", () => {
        panel.dataset.rangePreset = "custom";
        panel.querySelectorAll(".range-btn").forEach((b) => b.classList.toggle("active", b.dataset.range === "custom"));
        const custom = panel.querySelector(".range-custom");
        if (custom) custom.hidden = false;
        redrawPanel(panel, payload);
      });
    });
  }

  function init() {
    const payload = parsePayload();
    document.querySelectorAll(".tab-panel").forEach((panel) => {
      if (!panel.dataset.stack) return;
      bindRangeBar(panel, payload);
      redrawPanel(panel, payload);
    });
    window.addEventListener("resize", () => {
      const payload = parsePayload();
      document.querySelectorAll(".tab-panel:not([hidden])").forEach((panel) => {
        if (panel.dataset.stack) redrawPanel(panel, payload);
      });
    });
    document.querySelectorAll(".tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        setTimeout(() => {
          const payload = parsePayload();
          document.querySelectorAll(".tab-panel:not([hidden])").forEach((panel) => {
            if (panel.dataset.stack) redrawPanel(panel, payload);
          });
        }, 50);
      });
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
