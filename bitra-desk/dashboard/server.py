#!/usr/bin/env python3
"""bitra-desk dashboard: the sandbox desks side by side, then one desk's cycles, analysts, data series,
model use and hindsight.

Reads only what `tra run` and `tra hindsight` write under <desk>/runs/cycles and the paper accounts'
state.json and candle cache (../paper/paper.py); never reads .env.
Read-only, stdlib only, binds 127.0.0.1. `tailscale serve` publishes it on the tailnet. The page draws its
two charts in the browser from data embedded in it (no library, nothing fetched from elsewhere) and
refreshes itself every minute.

    python3 server.py --desk gemini=~/bitra/desk --desk groq=~/bitra/desk-groq \
        --desk claude=~/bitra/desk-claude --port 8790
    curl -s '127.0.0.1:8790/api/state.json?desk=groq'      # one desk's state as JSON

Each desk is NAME=PATH; its paper account is the sibling paper<suffix> folder (desk -> paper, desk-groq ->
paper-groq) and its service bitra-<folder>. With more than one desk the page opens with a comparison.
"""
from __future__ import annotations

import argparse
import html
import json
import statistics
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

IST = timezone(timedelta(hours=5, minutes=30))
RECENT_CYCLES = 72
GRID_HOURS = 48          # the hour-by-hour strip
PRICE_HOURS = 96         # the price chart's window
REASON_CHARS = 280
# USD per million input / output tokens, Anthropic list prices on 31 Oct 2026. The Gemini and Groq desks
# run on free tiers, so their models are not priced. bitra counts cached prompt tokens as input, so the
# estimate errs high.
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}


def cycle_time(cycle_id: str) -> datetime | None:
    """`2026-10-29T10-00-03Z-BTCUSDT` -> its UTC time."""
    try:
        return datetime.strptime(cycle_id[:20], "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a line being written as we read
    return rows


def load_index(cycles: Path) -> list[dict]:
    """One row per cycle from index/*.jsonl, the last record of a cycle winning, oldest first."""
    by_id: dict[str, dict] = {}
    for f in sorted((cycles / "index").glob("*.jsonl")):
        for row in read_jsonl(f):
            if "cycle_id" in row:
                by_id[row["cycle_id"]] = row
    return [by_id[k] for k in sorted(by_id)]


def load_cycle(cycles: Path, cycle_id: str) -> dict | None:
    try:
        return json.loads((cycles / cycle_id / "cycle.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None


def summarize(row: dict, cyc: dict | None) -> dict:
    """What one cycle decided, in the terms the page shows."""
    out = {
        "id": row["cycle_id"],
        "at": cycle_time(row["cycle_id"]),
        "mid": (row.get("seen") or {}).get("mid"),
        "intent": row.get("intent"),
        "tokens": None,
        "reason": "",
        "technical": "",
        "target": None,
        "setup": "",
        "confidence": None,
        "macro": "",
        "sentiment": "",
    }
    if row.get("intent"):
        out["outcome"] = "would trade"
    elif row.get("held"):
        out["outcome"] = "held"
    elif cyc is None:
        out["outcome"] = "incomplete"
    elif cyc.get("stopped_by"):
        out["outcome"] = "error"
    else:
        out["outcome"] = "refused"
    if cyc is None:
        out["reason"] = "no cycle.json (the cycle was cut short)"
        return out
    out["tokens"] = cyc.get("tokens")
    refusals = cyc.get("refusals") or []
    if cyc.get("stopped_by"):
        out["reason"] = f"stopped by: {cyc['stopped_by']}"
    elif refusals:
        out["reason"] = refusals[0]
    intent = row.get("intent")
    if intent:
        out["reason"] = intent.get("reason", "")
    a = cyc.get("analyst") or {}
    if a.get("target"):
        conf = a.get("confidence")
        out.update(target=a["target"], setup=a.get("setup", ""), confidence=conf)
        out["technical"] = f"{a['target']} {a.get('setup', '')} @ {conf}" if conf is not None else a["target"]
    ctx = cyc.get("context") or {}
    out["macro"] = (ctx.get("macro_analyst") or {}).get("regime", "")
    out["sentiment"] = (ctx.get("sentiment_analyst") or {}).get("state", "")
    return out


def token_usd(row: dict) -> float | None:
    """What one model call cost at list price, or None for a model this page does not price."""
    price = PRICES.get(row.get("model") or "")
    if not price:
        return None
    return (int(row.get("input_tokens") or 0) * price[0] + int(row.get("output_tokens") or 0) * price[1]) / 1e6


def usage_by_day(rows: list[dict]) -> list[dict]:
    days: dict[str, dict] = defaultdict(lambda: {"calls": 0, "ok": 0, "errors": 0, "tokens_in": 0, "tokens_out": 0,
                                                 "usd": None, "models": Counter(), "latency": []})
    for r in rows:
        try:
            day = datetime.fromtimestamp(float(r["at"]), tz=IST).strftime("%Y-%m-%d")
        except (KeyError, TypeError, ValueError):
            continue
        d = days[day]
        d["calls"] += 1
        if r.get("outcome") == "ok":
            d["ok"] += 1
            d["models"][r.get("model") or "?"] += 1
        else:
            d["errors"] += 1
        d["tokens_in"] += int(r.get("input_tokens") or 0)
        d["tokens_out"] += int(r.get("output_tokens") or 0)
        usd = token_usd(r)
        if usd is not None:
            d["usd"] = (d["usd"] or 0.0) + usd
        if r.get("latency_ms"):
            d["latency"].append(float(r["latency_ms"]) / 1000)
    out = []
    for day in sorted(days, reverse=True):
        d = days[day]
        out.append({"day": day, "calls": d["calls"], "ok": d["ok"], "errors": d["errors"],
                    "tokens_in": d["tokens_in"], "tokens_out": d["tokens_out"], "usd": d["usd"],
                    "models": dict(d["models"].most_common()),
                    "median_latency_s": round(statistics.median(d["latency"]), 1) if d["latency"] else None})
    return out


def api_cost(rows: list[dict], now: datetime) -> dict:
    """Estimated spend on priced models: in all and today (IST); None when no call used a priced model."""
    today = now.astimezone(IST).date()
    total = today_usd = 0.0
    priced = False
    for r in rows:
        usd = token_usd(r)
        if usd is None:
            continue
        priced = True
        total += usd
        try:
            if datetime.fromtimestamp(float(r["at"]), tz=IST).date() == today:
                today_usd += usd
        except (KeyError, TypeError, ValueError):
            pass
    return {"total_usd": total if priced else None, "today_usd": today_usd if priced else None}


def load_candles(paper_dirs: list[Path], since_ms: int = 0) -> list[tuple[int, float]]:
    """(open time ms, close) of the 5-minute bars the paper accounts cached, merged across desks (one market)."""
    bars: dict[int, float] = {}
    for d in paper_dirs:
        path = Path(d) / "candles.jsonl"
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            try:
                ms, _open, _high, _low, close = json.loads(line)[:5]
                bars[int(ms)] = float(close)
            except (ValueError, TypeError):
                continue  # json.JSONDecodeError is a ValueError
    return sorted((ms, c) for ms, c in bars.items() if ms >= since_ms)


OUTCOME_RANK = {"would trade": 4, "refused": 3, "error": 2, "incomplete": 2, "held": 1}


def hourly_decisions(recent: list[dict], now: datetime, hours: int = GRID_HOURS) -> list[dict]:
    """The last `hours` clock hours, oldest first, each with the cycle that says most about that hour."""
    end = now.replace(minute=0, second=0, microsecond=0)
    slots = [{"hour": end - timedelta(hours=hours - 1 - i), "cycle": None} for i in range(hours)]
    by_hour = {s["hour"]: s for s in slots}
    for c in reversed(recent):  # oldest first, so a later cycle of the same rank wins
        at = c.get("at")
        slot = by_hour.get(at.replace(minute=0, second=0, microsecond=0)) if at else None
        if slot is None:
            continue
        held = slot["cycle"]
        if held is None or OUTCOME_RANK.get(c["outcome"], 0) >= OUTCOME_RANK.get(held["outcome"], 0):
            slot["cycle"] = c
    return slots


def service_state(unit: str = "bitra-desk") -> str:
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", unit], capture_output=True, text=True, timeout=3)
        return r.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def desk_model(desk: Path) -> str:
    """provider:model from the desk's strategy.toml [agents] table (read by line: no tomllib on 3.10)."""
    try:
        lines = (desk / "strategy.toml").read_text().splitlines()
    except OSError:
        return ""
    found, section = {}, ""
    for line in lines:
        st = line.strip()
        if st.startswith("["):
            section = st
        elif section == "[agents]" and st.split("=")[0].strip() in ("provider", "model") and "=" in st:
            key, val = st.split("=", 1)
            found.setdefault(key.strip(), val.split("#")[0].strip().strip('"'))
    return f"{found.get('provider', '?')}:{found.get('model', '?')}"


def parse_desk(spec: str) -> dict:
    """`NAME=PATH` (or a bare PATH, named after its folder) -> the desk, its paper folder and its unit."""
    name, _, path = spec.partition("=") if "=" in spec else ("", "", spec)
    d = Path(path).expanduser()
    suffix = d.name[len("desk"):] if d.name.startswith("desk") else f"-{d.name}"
    return {"name": name or d.name, "path": d, "paper": d.parent / f"paper{suffix}", "unit": f"bitra-{d.name}"}


def build_state(desk: Path, now: datetime | None = None, service: str | None = None,
                paper_dir: Path | None = None, unit: str = "bitra-desk") -> dict:
    now = now or datetime.now(timezone.utc)
    cycles = desk / "runs" / "cycles"
    rows = load_index(cycles)
    recent_rows = rows[-RECENT_CYCLES:]
    loaded = {r["cycle_id"]: load_cycle(cycles, r["cycle_id"]) for r in recent_rows}
    recent = [summarize(r, loaded[r["cycle_id"]]) for r in recent_rows]

    counts = Counter()
    today = now.astimezone(IST).date()
    counts_today = Counter()
    for r in rows:
        kind = "would trade" if r.get("intent") else ("held" if r.get("held") else "asked")
        counts[kind] += 1
        at = cycle_time(r["cycle_id"])
        if at and at.astimezone(IST).date() == today:
            counts_today[kind] += 1
    for s in recent:
        if s["outcome"] in ("error", "incomplete"):
            counts["error (recent)"] += 1

    latest = next((loaded[r["cycle_id"]] for r in reversed(recent_rows)
                   if loaded[r["cycle_id"]] and loaded[r["cycle_id"]].get("series")), None)
    latest_ctx = next((loaded[r["cycle_id"]] for r in reversed(recent_rows)
                       if loaded[r["cycle_id"]] and loaded[r["cycle_id"]].get("context")), None)
    latest_tech = next((loaded[r["cycle_id"]] for r in reversed(recent_rows)
                        if loaded[r["cycle_id"]] and (loaded[r["cycle_id"]].get("analyst") or {}).get("target")), None)

    analysts = []
    if latest_ctx:
        for role, key in (("macro", "macro_analyst"), ("sentiment", "sentiment_analyst")):
            c = (latest_ctx.get("context") or {}).get(key)
            if c:
                analysts.append({"role": role, "says": c.get("regime") or c.get("state") or "",
                                 "reason": c.get("reason", ""), "data_as_of": c.get("data_as_of"),
                                 "cycle": latest_ctx.get("cycle_id")})
    if latest_tech:
        a = latest_tech["analyst"]
        analysts.append({"role": "technical",
                         "says": f"{a.get('target')} {a.get('setup', '')} at {a.get('confidence')}",
                         "reason": a.get("reason", ""), "data_as_of": None, "cycle": latest_tech.get("cycle_id")})

    # the intent carries its own "at" (the cycle id as text): ours goes last so the time wins
    trades = [{**r["intent"], "id": r["cycle_id"], "at": cycle_time(r["cycle_id"])} for r in rows if r.get("intent")]

    sched = read_jsonl(cycles / "scheduler.jsonl")
    hindsight_path = cycles / "hindsight.json"
    hindsight = None
    if hindsight_path.exists():
        try:
            hindsight = json.loads(hindsight_path.read_text())
            hindsight["_written"] = datetime.fromtimestamp(hindsight_path.stat().st_mtime, tz=timezone.utc)
        except (OSError, json.JSONDecodeError):
            hindsight = None

    paper = None
    paper_path = (paper_dir or desk.parent / "paper") / "state.json"
    if paper_path.exists():
        try:
            paper = json.loads(paper_path.read_text())
        except (OSError, json.JSONDecodeError):
            paper = None

    usage_rows = read_jsonl(cycles / "usage.jsonl")
    next_pass = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    return {
        "now": now,
        "desk": str(desk),
        "model": desk_model(desk),
        "service": service if service is not None else service_state(unit),
        "first_cycle": cycle_time(rows[0]["cycle_id"]) if rows else None,
        "last_cycle": recent[-1] if recent else None,
        "next_pass": next_pass,
        "scheduler_last": sched[-1] if sched else None,
        "counts": dict(counts),
        "counts_today": dict(counts_today),
        "total_cycles": len(rows),
        "recent": list(reversed(recent)),
        "series": (latest or {}).get("series") or [],
        "analysts": analysts,
        "trades": list(reversed(trades)),
        "usage": usage_by_day(usage_rows),
        "cost": api_cost(usage_rows, now),
        "hindsight": hindsight,
        "paper": paper,
    }


# ---- HTML -----------------------------------------------------------------------------------

def e(v) -> str:
    """Everything a model or a feed wrote is escaped: the records hold model text."""
    return html.escape("" if v is None else str(v))


def script_json(obj) -> str:
    """JSON safe to embed in <script type=application/json>: no <, > or & can end the element early."""
    text = json.dumps(obj, separators=(",", ":"), default=str)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def t(at: datetime | None, with_date: bool = True) -> str:
    if not at:
        return ""
    return at.astimezone(IST).strftime("%d %b %H:%M" if with_date else "%H:%M")


def clip(s: str, n: int = REASON_CHARS) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


def ago(at: datetime | None, now: datetime) -> str:
    if not at:
        return ""
    m = int((now - at).total_seconds() // 60)
    return f"{m} min ago" if m < 120 else f"{m // 60} h ago"


def ms_time(ms) -> datetime | None:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc) if ms else None


def ms(at: datetime) -> int:
    return int(at.timestamp() * 1000)


def num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def usd(v) -> str:
    x = num(v)
    if x is None:
        return ""
    return f"{'+' if x >= 0 else '−'}${abs(x):,.2f}"


def money(v) -> str:
    x = num(v)
    return "–" if x is None else f"${x:,.2f}"


def signed(v, fmt: str = "{:.1f}") -> str:
    x = num(v)
    if x is None:
        return "–"
    return ("+" if x > 0 else "−" if x < 0 else "") + fmt.format(abs(x))


def tone(v) -> str:
    x = num(v)
    return "" if not x else ("up" if x > 0 else "down")


ARROW = {"long": "▲", "short": "▼", "flat": "–"}
PILL = {"would trade": "go", "refused": "warn", "held": "mute", "error": "bad", "incomplete": "bad",
        "active": "go", "bullish": "go", "risk-on": "go", "bearish": "bad", "risk-off": "bad",
        "neutral": "mute", "long": "go", "short": "bad", "positive": "go", "negative": "bad"}


def pill(word: str) -> str:
    key = (word or "").split(" ")[0] if word not in PILL else word
    return f"<span class='pill {PILL.get(key, 'mute')}'>{e(word)}</span>"


def status(word: str) -> str:
    """A service state as dot and word: never color alone."""
    ok = word == "active"
    return f"<span class='status {'ok' if ok else 'down'}'><i></i>{e(word or 'unknown')}</span>"


def size_txt(tr: dict) -> str:
    """The paper size, with the desk's own when the account's risk rule cut it."""
    size, desk = tr.get("size"), tr.get("desk_size")
    cut = desk is not None and abs(float(desk) - float(size)) > 1e-12
    return f"{size:g} BTC" + (f" (desk {float(desk):g})" if cut else "")


CSS = """
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--surface-2:#f0efec;--ink:#0b0b0b;--ink-2:#52514e;
--muted:#6f6d68;--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;
--up:#006300;--down:#b42323;--good:#0ca30c;--bad:#d03b3b;--warn:#8a5a00;--warn-bg:#fbf0d9;--go-bg:#e3f3ea;
--bad-bg:#f8e2dc;--shadow:0 1px 2px rgba(11,11,11,.05)}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--surface-2:#252524;
--ink:#f0efec;--ink-2:#c3c2b7;--muted:#9a988f;--grid:#2c2c2a;--axis:#45453f;--ring:rgba(255,255,255,.10);
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--up:#3ec43e;--down:#f08a8a;--good:#0ca30c;--bad:#e66767;--warn:#f0c46b;
--warn-bg:#3a2e14;--go-bg:#183326;--bad-bg:#3d1f19;--shadow:none}}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
-webkit-text-size-adjust:100%}
a{color:inherit}
#app{max-width:1200px;margin:0 auto;padding:12px 16px 64px}
.top{display:flex;flex-wrap:wrap;gap:10px 24px;align-items:flex-end;justify-content:space-between;
padding:10px 0 16px;border-bottom:1px solid var(--grid)}
h1{font-size:20px;line-height:1.2;margin:0;letter-spacing:-.01em}
h2{font-size:15px;line-height:1.3;margin:0;font-weight:650}
.sub,.note{color:var(--muted);font-size:12.5px}
.note{margin:6px 2px 0}
.btc{text-align:right}.btc b{font-size:20px;font-weight:650}.btc .note{margin:0}
section{margin-top:28px}
.sec-head{display:flex;flex-wrap:wrap;gap:4px 16px;align-items:baseline;justify-content:space-between;margin-bottom:10px}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:12px;box-shadow:var(--shadow)}
.pad{padding:14px 16px}
.up{color:var(--up)}.down{color:var(--down)}
.board{display:grid;grid-template-columns:repeat(auto-fit,minmax(272px,1fr));gap:12px}
.desk{display:flex;flex-direction:column;gap:10px;padding:14px 16px 12px;text-decoration:none;position:relative;
overflow:hidden}
.desk::before{content:"";position:absolute;left:0;top:0;right:0;height:3px;background:var(--c)}
.desk:hover{border-color:var(--axis)}.desk.sel{box-shadow:0 0 0 2px var(--c)}
.desk:focus-visible,.tab:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.d-head{display:flex;align-items:center;gap:8px}.d-head b{font-size:16px}
.rank{color:var(--muted);font-size:12px;font-variant-numeric:tabular-nums}
.d-head .status{margin-left:auto}
.model{color:var(--muted);font-size:12px;margin-top:-6px;overflow-wrap:anywhere}
.eq{font-size:28px;font-weight:650;line-height:1.1;letter-spacing:-.01em}
.eq small{font-size:14px;font-weight:600;margin-left:6px}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:0}
.stats div{min-width:0}.stats dt{color:var(--muted);font-size:11.5px}.stats dd{margin:0;font-weight:600;
font-variant-numeric:tabular-nums}
.line2{font-size:12.5px;border-top:1px solid var(--grid);padding-top:8px;display:grid;gap:5px}
.line2>div{display:grid;grid-template-columns:104px minmax(0,1fr);gap:8px}
.line2 span.k{color:var(--muted)}
.sw{display:inline-block;width:10px;height:10px;border-radius:3px;background:var(--c);flex:none}
.status{display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--muted)}
.status i{width:7px;height:7px;border-radius:50%;background:var(--good)}.status.down i{background:var(--bad)}
.status.down{color:var(--bad)}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12.5px;color:var(--ink-2)}
.legend span{display:inline-flex;align-items:center;gap:6px}
.chart{position:relative;height:280px;touch-action:pan-y;margin-top:6px}
.chart svg{display:block;overflow:visible}
.chart .gridline{stroke:var(--grid);stroke-width:1}.chart .axisline{stroke:var(--axis);stroke-width:1}
.chart .baseline{stroke:var(--axis);stroke-width:1.5}
.chart text{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.chart text.endlabel{fill:var(--ink);font-size:12px;font-weight:600}
.chart .line{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.chart .price{fill:none;stroke:var(--ink-2);stroke-width:1.5;stroke-linejoin:round}
.chart .hold{stroke-width:2;opacity:.8;pointer-events:none}.chart .hold.open{opacity:.45}
.chart .ring{stroke:var(--surface);stroke-width:2}.chart .cross{stroke:var(--axis);stroke-width:1;pointer-events:none}
.chart .mark{cursor:pointer;outline:none}
.chart .line,.chart .ring,.chart text,.chart .baseline{pointer-events:none}.chart .mark:focus-visible path{stroke:var(--ink)}
.tip{position:absolute;z-index:3;pointer-events:none;background:var(--surface);border:1px solid var(--ring);
border-radius:8px;padding:6px 9px;font-size:12px;line-height:1.45;box-shadow:0 6px 20px rgba(0,0,0,.18);
white-space:nowrap;color:var(--ink)}
.tip div{display:flex;align-items:center;gap:6px}.tip .sw{width:8px;height:8px}
.empty{color:var(--muted);font-size:13px;padding:24px 4px}
.strip{overflow-x:auto;padding:12px 16px 10px 0;scrollbar-width:thin}
.srow{display:grid;grid-template-columns:92px repeat(var(--n),minmax(16px,1fr));gap:2px;align-items:center;
min-width:calc(92px + var(--n) * 18px)}
.srow+.srow{margin-top:3px}
.srow .lbl{display:flex;align-items:center;gap:6px;font-size:12.5px;font-weight:600;position:sticky;left:0;
background:var(--surface);padding:0 6px 0 16px;z-index:1;height:22px}
.cell{min-width:16px;height:22px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:9px;
line-height:1;color:var(--ink-2);box-shadow:inset 0 0 0 1px var(--grid);cursor:default}
.cell.none{box-shadow:none}
.cell.held::after{content:"";width:3px;height:3px;border-radius:50%;background:var(--axis)}
.cell.asked{background:color-mix(in oklab,var(--c) 24%,var(--surface));box-shadow:none;color:var(--ink)}
.cell.flat,.cell.refused{background:var(--surface-2);box-shadow:none;color:var(--ink-2)}
.cell.trade{background:var(--c);box-shadow:none;color:#fff}
.cell.err{box-shadow:inset 0 0 0 1.5px var(--bad);color:var(--bad);font-weight:700}
.cell:focus-visible{outline:2px solid var(--ink);outline-offset:1px}
.hours{color:var(--muted);font-size:10.5px;height:16px}.hours span{white-space:nowrap;overflow:visible}
.keys{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:var(--ink-2);padding:0 16px 12px}
.keys span{display:inline-flex;align-items:center;gap:5px}.keys .cell{width:16px;--c:var(--muted)}
#grid-tip{min-height:20px;padding:8px 16px 12px;margin:0;border-top:1px solid var(--grid);font-size:12.5px;color:var(--ink-2)}
.tabs{display:flex;flex-wrap:wrap;gap:6px}
.tab{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:99px;border:1px solid var(--ring);
background:var(--surface);text-decoration:none;font-size:13px;font-weight:600}
.tab[aria-current]{background:var(--ink);color:var(--surface);border-color:var(--ink)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.tile{padding:12px 14px}.tile b{display:block;font-size:20px;font-weight:650}
.tile span{color:var(--muted);font-size:12px}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}
.analyst h3{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin:0 0 6px;font-weight:600}
.analyst p{margin:8px 0 0;font-size:13px;color:var(--ink-2)}
.verdict{display:grid;gap:10px}.verdict p{margin:0}
.bars{display:grid;grid-template-columns:auto 1fr auto;gap:6px 10px;align-items:center;font-size:12.5px}
.bar{height:10px;position:relative;background:var(--surface-2);border-radius:5px}
.bar i{position:absolute;top:0;bottom:0;border-radius:5px;background:var(--ink-2)}
.bar::after{content:"";position:absolute;left:50%;top:-3px;bottom:-3px;width:1px;background:var(--axis)}
details.fold{margin-top:12px}
details.fold>summary{list-style:none;cursor:pointer;padding:12px 16px;display:flex;align-items:center;gap:10px}
details.fold>summary::-webkit-details-marker{display:none}
details.fold>summary::before{content:"▸";color:var(--muted);transition:transform .15s}
details.fold[open]>summary::before{transform:rotate(90deg)}
details.fold>summary .count{color:var(--muted);font-size:12.5px;margin-left:auto}
.tablewrap{overflow-x:auto;border-top:1px solid var(--grid)}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--grid);vertical-align:top}
th{color:var(--muted);font-weight:600;white-space:nowrap;font-size:12px}tr:last-child td{border-bottom:0}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap;text-align:right}th.num{text-align:right}
td.nw{white-space:nowrap}td.why{min-width:280px;color:var(--ink-2)}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;white-space:nowrap;background:var(--surface-2);
color:var(--ink-2)}
.pill.go{background:var(--go-bg);color:var(--up)}.pill.warn{background:var(--warn-bg);color:var(--warn)}
.pill.bad{background:var(--bad-bg);color:var(--down)}
.foot{margin-top:28px}
@media (max-width:560px){.eq{font-size:24px}.chart{height:240px}.btc{text-align:left}.line2>div{grid-template-columns:92px minmax(0,1fr)}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


def render_paper(pa: dict | None, now: datetime) -> str:
    """The would-be trades as one account: one position at a time, the desk's own size and levels."""
    if not pa:
        return ("<section><div class='sec-head'><h2>Paper account</h2></div><p class='note'>Not computed yet (the "
                "paper timer runs every 15 minutes, from the desk's first would-be trade).</p></section>")
    out = [f"""<section><div class='sec-head'><h2>Paper account</h2>
<span class='sub'>updated {e(ago(ms_time(pa.get('generated_ms')), now))}</span></div>
<div class="tiles">
<div class="card tile"><b>${float(pa['equity']):,.2f}</b><span>equity (from ${float(pa['start_equity']):,.0f})</span></div>
<div class="card tile"><b class="{tone(pa['return_pct'])}">{float(pa['return_pct']):+.2f}%</b><span>return</span></div>
<div class="card tile"><b>{e(usd(pa['realized_usd']))}</b><span>realized ({pa['closed']} closed: {pa['wins']} won, {pa['losses']} lost)</span></div>
<div class="card tile"><b>{e(usd(pa['unrealized_usd']))}</b><span>unrealized (open position)</span></div>
<div class="card tile"><b>{len(pa.get('skipped') or [])}</b><span>signals skipped (position already open)</span></div>
</div>
<p class='note'>The desk's would-be trades taken one at a time, as a real account would: entry at the next
5-minute bar, the desk's own size, stop and target, out at either or after
{e(f"{float(pa.get('hold_hours') or 0):g}")} h, net of the priced round trip; each size cut to keep the loss
at the stop within {e(f"{float(pa.get('risk_bps') or 0):g}")} bps of equity (the desk's size in brackets when cut).
Practice money only.{' Candle fetch failed: ' + e(pa['fetch_error']) if pa.get('fetch_error') else ''}</p>"""]
    o = pa.get("open")
    out.append("<div class='card tablewrap' style='margin-top:10px;border-top:1px solid var(--ring)'><table><tr>"
               "<th>Open position</th><th class='num'>Entry</th><th class='num'>Mark</th><th class='num'>Stop</th>"
               "<th class='num'>Take</th><th class='num'>Size</th><th class='num'>Unrealized</th><th>Closes by</th></tr>")
    if o:
        out.append(f"<tr><td class='nw'>{pill(o['side'])} {e(o.get('setup'))} · {e(t(ms_time(o['entry_ms'])))}</td>"
                   f"<td class='num'>{o['entry']:,.1f}</td><td class='num'>{o['mark']:,.1f}</td>"
                   f"<td class='num'>{o['stop']:,.1f}</td><td class='num'>{o['take']:,.1f}</td>"
                   f"<td class='num'>{e(size_txt(o))}</td><td class='num {tone(o['unrealized_usd'])}'>{e(usd(o['unrealized_usd']))}</td>"
                   f"<td class='nw'>{e(t(ms_time(o['deadline_ms'])))}</td></tr>")
    else:
        out.append("<tr><td colspan=8>Flat: no position open.</td></tr>")
    out.append("</table></div>")
    trades = pa.get("trades") or []
    out.append(f"<details class='card fold' id='d-closed' open><summary><h2>Closed trades</h2>"
               f"<span class='count'>{len(trades)}</span></summary><div class='tablewrap'><table><tr><th>When</th>"
               "<th>Side</th><th class='num'>Entry</th><th class='num'>Exit</th><th>Why</th><th class='num'>Size</th>"
               "<th class='num'>Net</th><th class='num'>Equity after</th></tr>")
    curve = {c[0]: c[1] for c in pa.get("equity_curve") or []}
    for tr in reversed(trades):
        out.append(f"<tr><td class='nw'>{e(t(ms_time(tr['entry_ms'])))} → {e(t(ms_time(tr['exit_ms']), with_date=False))}</td>"
                   f"<td>{pill(tr['side'])}</td><td class='num'>{tr['entry']:,.1f}</td><td class='num'>{tr['exit']:,.1f}</td>"
                   f"<td class='nw'>{e(tr['exit_reason'])}</td><td class='num'>{e(size_txt(tr))}</td>"
                   f"<td class='num {tone(tr['net_usd'])}'>{e(usd(tr['net_usd']))} ({tr['net_bps']:+.0f} bps)</td>"
                   f"<td class='num'>${curve.get(tr['exit_ms'], 0):,.2f}</td></tr>")
    if not trades:
        out.append("<tr><td colspan=8>No closed trades yet.</td></tr>")
    out.append("</table></div></details></section>")
    return "".join(out)


def stance(s: dict) -> dict | None:
    """The desk's latest answer from the technical analyst: the call it would act on."""
    return next((c for c in s.get("recent") or [] if c.get("target") and c["outcome"] in ("refused", "would trade")),
                None)


def comparison_row(name: str, s: dict, slot: int = 1) -> dict:
    """One desk's headline figures, for the cards that set the desks side by side."""
    pa = s.get("paper") or {}
    side = ((s.get("hindsight") or {}).get("side") or {})
    u_today = s["usage"][0] if s["usage"] else {}
    today = s["now"].astimezone(IST).strftime("%Y-%m-%d")
    if u_today.get("day") != today:
        u_today = {}
    return {"name": name, "slot": slot, "model": s.get("model", ""), "service": s.get("service", ""),
            "cycles": s["total_cycles"], "would_trade": s["counts"].get("would trade", 0),
            "refused": s["counts"].get("asked", 0), "held": s["counts"].get("held", 0),
            "errors": s["counts"].get("error (recent)", 0),
            "equity": pa.get("equity"), "start_equity": pa.get("start_equity"), "return_pct": pa.get("return_pct"),
            "closed": pa.get("closed"), "wins": pa.get("wins"), "losses": pa.get("losses"),
            "open": pa.get("open"),
            "side_model": (side.get("model_side") or {}).get("mean_net_bps"),
            "side_reverse": (side.get("opposite_side") or {}).get("mean_net_bps"),
            "side_n": (side.get("model_side") or {}).get("decisions"), "verdict": side.get("verdict", ""),
            "calls_today": u_today.get("calls", 0), "failed_today": u_today.get("errors", 0),
            "cost": s.get("cost") or {}, "stance": stance(s), "now": s["now"]}


def desk_card(r: dict, rank: int, selected: str) -> str:
    eq = (f"${float(r['equity']):,.2f}<small class='{tone(r['return_pct'])}'>{float(r['return_pct']):+.2f}%</small>"
          if r["equity"] is not None else "<span class='sub'>no paper account yet</span>")
    closed = f"{r['closed']} · {r['wins']}W {r['losses']}L" if r["closed"] is not None else "–"
    st = r["stance"]
    if st:
        conf = num(st.get("confidence"))
        call = (f"{ARROW.get(st['target'], '')} {e(st['target'])} · {e(st.get('setup') or '')}"
                + (f" · {conf:.2f}" if conf is not None else "")
                + f" <span class='sub'>· {e(ago(st['at'], r['now']))} · {e(st['outcome'])}</span>")
    else:
        call = "<span class='sub'>not asked yet</span>"
    if r["open"]:
        o = r["open"]
        call += (f"<br><span class='sub'>open {e(o['side'])} from {o['entry']:,.1f},</span> "
                 f"<span class='{tone(o.get('unrealized_usd'))}'>{e(usd(o.get('unrealized_usd')))}</span>")
    hs = (f"{e(signed(r['side_model']))} vs {e(signed(r['side_reverse']))} bps · {e(r['side_n'])} · {e(r['verdict'])}"
          if r["side_model"] is not None else "<span class='sub'>not computed yet</span>")
    cost = r["cost"].get("total_usd")
    spend = (f"≈ ${cost:,.2f} so far (${r['cost'].get('today_usd') or 0:,.2f} today)" if cost is not None
             else "free tier")
    sel = " sel" if r["name"] == selected else ""
    cur = " aria-current='true'" if r["name"] == selected else ""
    return f"""<a class='card desk{sel}' href='?desk={e(r['name'])}#detail' style='--c:var(--s{r['slot']})'{cur}>
<div class='d-head'><span class='sw'></span><b>{e(r['name'])}</b><span class='rank'>#{rank}</span>{status(r['service'])}</div>
<div class='model'>{e(r['model'])}</div>
<div class='eq'>{eq}</div>
<dl class='stats'><div><dt>Closed</dt><dd>{e(closed)}</dd></div><div><dt>Would-be trades</dt><dd>{r['would_trade']}</dd></div>
<div><dt>Asked / held</dt><dd>{r['refused'] + r['would_trade']} / {r['held']}</dd></div></dl>
<div class='line2'><div><span class='k'>Latest call</span><span>{call}</span></div>
<div><span class='k'>Side vs reverse</span><span>{hs}</span></div>
<div><span class='k'>Model calls</span><span>{r['calls_today']} today ({r['failed_today']} failed) · {e(spend)}</span></div></div>
</a>"""


def grid_cell(name: str, slot: dict) -> str:
    c = slot["cycle"]
    if c is None:
        return "<span class='cell none' aria-hidden='true'></span>"
    outcome, target = c["outcome"], c.get("target")
    if outcome == "would trade":
        cls, glyph = "trade", ARROW.get((c.get("intent") or {}).get("target") or target or "", "●")
    elif outcome == "held":
        cls, glyph = "held", ""
    elif outcome in ("error", "incomplete"):
        cls, glyph = "err", "!"
    elif target == "flat":
        cls, glyph = "flat", "–"
    elif target:
        cls, glyph = "asked", ARROW.get(target, "?")
    else:
        cls, glyph = "refused", "·"
    conf = num(c.get("confidence"))
    said = (f" · said {target} {c.get('setup') or ''}" + (f" at {conf:.2f}" if conf is not None else "")) if target else ""
    tip = f"{name} · {t(c['at'])} IST · {outcome}{said} · {clip(c.get('reason') or '', 200)}"
    if cls == "held":  # most hours: hover shows them, the keyboard skips them
        return f"<span class='cell {cls}' data-tip='{e(tip)}'></span>"
    return f"<span class='cell {cls}' role='button' tabindex='0' data-tip='{e(tip)}' aria-label='{e(tip)}'>{glyph}</span>"


def render_grid(rows: list[dict], states: dict, now: datetime) -> str:
    out = [f"<section><div class='sec-head'><h2>Hour by hour</h2><span class='sub'>last {GRID_HOURS} h, IST; "
           "what each model did with the same hour</span></div><div class='card'><div class='strip'>"]
    hours = hourly_decisions([], now)  # the axis
    labels = []
    for h in hours:
        local = h["hour"].astimezone(IST)
        txt = local.strftime("%d %b") if local.hour == 0 else (local.strftime("%H") if local.hour % 6 == 0 else "")
        labels.append(f"<span>{e(txt)}</span>")
    for r in rows:
        slots = hourly_decisions(states[r["name"]]["recent"], now)
        cells = "".join(grid_cell(r["name"], s) for s in slots)
        out.append(f"<div class='srow' style='--n:{GRID_HOURS};--c:var(--s{r['slot']})'>"
                   f"<span class='lbl'><span class='sw'></span>{e(r['name'])}</span>{cells}</div>")
    out.append(f"<div class='srow hours' style='--n:{GRID_HOURS}'><span class='lbl'></span>{''.join(labels)}</div>")
    out.append("</div><div class='keys'>"
               "<span><span class='key cell trade'>▼</span>would-be trade</span>"
               "<span><span class='key cell asked'>▲</span>asked, refused (▲ long ▼ short)</span>"
               "<span><span class='key cell flat'>–</span>said flat</span>"
               "<span><span class='key cell held'></span>held: market too quiet to ask</span>"
               "<span><span class='key cell err'>!</span>error</span></div>"
               "<p id='grid-tip'>Hover or tap a square to see what the model said.</p></div></section>")
    return "".join(out)


def chart_payload(rows: list[dict], states: dict, candles: list[tuple[int, float]], now: datetime) -> dict:
    desks = []
    for r in rows:
        s = states[r["name"]]
        pa = s.get("paper") or {}
        curve, trades = [], []
        if pa and s.get("first_cycle"):
            start = float(pa.get("start_equity") or 0)
            curve = [[ms(s["first_cycle"]), start]] + [[int(a), float(b)] for a, b in pa.get("equity_curve") or []]
            curve.append([ms(now), float(pa.get("equity") or start)])
            for tr in pa.get("trades") or []:
                trades.append({"side": tr["side"], "setup": tr.get("setup"), "entry_ms": tr["entry_ms"],
                               "entry": tr["entry"], "exit_ms": tr["exit_ms"], "exit": tr["exit"],
                               "exit_reason": tr.get("exit_reason"), "net_usd": tr.get("net_usd")})
            o = pa.get("open")
            if o:
                trades.append({"side": o["side"], "setup": o.get("setup"), "entry_ms": o["entry_ms"],
                               "entry": o["entry"], "mark": o.get("mark"), "net_usd": o.get("unrealized_usd"),
                               "open": True})
        desks.append({"name": r["name"], "slot": r["slot"], "start": float(pa.get("start_equity") or 0),
                      "curve": curve, "trades": trades})
    since = ms(now) - PRICE_HOURS * 3_600_000
    price = [[a, b] for a, b in candles if a >= since and (a % 900_000 == 0 or (a, b) == candles[-1])]
    return {"now": ms(now), "desks": desks, "price": price}


def render_overview(states: dict, selected: str, candles: list[tuple[int, float]], now: datetime) -> str:
    """The desks side by side (when there are several), the two charts and the hour-by-hour strip."""
    rows = [comparison_row(n, st, slot=i + 1) for i, (n, st) in enumerate(states.items())]
    out = []
    if len(rows) > 1:
        ranked = sorted(rows, key=lambda r: -(num(r["equity"]) if r["equity"] is not None else -1e18))
        out.append("<section><div class='sec-head'><h2>Model comparison</h2><span class='sub'>Same market, data, "
                   "rules and costs; only the model differs. Paper money, $1,000 each.</span></div><div class='board'>")
        out += [desk_card(r, i + 1, selected) for i, r in enumerate(ranked)]
        out.append("</div></section>")
    legend = "".join(f"<span><i class='sw' style='--c:var(--s{r['slot']})'></i>{e(r['name'])}</span>" for r in rows)
    out.append(f"""<section><div class='sec-head'><h2>Paper equity</h2><span class='legend'>{legend}</span></div>
<div class='card pad'><div class='chart' id='eq-chart' role='img' aria-label='Paper account equity of each desk over
time; the values are in the cards above and the closed trades below'><div class='tip' hidden></div></div>
<p class='note'>Steps at each closed trade; the line ends at today's equity, open position included.</p></div></section>
<section><div class='sec-head'><h2>BTCUSDT and the paper trades</h2><span class='legend'>{legend}
<span>▲ long / ▼ short entry · ● exit</span></span></div>
<div class='card pad'><div class='chart' id='price-chart' role='img' aria-label='BTCUSDT price over the last
{PRICE_HOURS} hours with each desk's paper trades marked'><div class='tip' hidden></div></div>
<p class='note'>Bybit 5-minute closes from the paper accounts' candle cache, last {PRICE_HOURS} h. Hover a marker
for the trade.</p></div></section>""")
    if len(rows) > 1:
        out.append(render_grid(rows, states, now))
    out.append(f"<script type='application/json' id='chart-data'>{script_json(chart_payload(rows, states, candles, now))}"
               "</script>")
    return "".join(out)


def btc_header(candles: list[tuple[int, float]], s: dict, now: datetime) -> str:
    if candles:
        last_ms, last = candles[-1]
        day_ago = next((c for a, c in reversed(candles) if a <= last_ms - 86_400_000), None)
        pct = (last / day_ago - 1) * 100 if day_ago else None
        chg = f"{e(signed(pct, '{:.2f}'))}% 24 h" if pct is not None else ""
        return (f"<div class='btc'><b>{last:,.1f}</b> <span class='{tone(pct)}'>{chg}</span>"
                f"<div class='note'>BTCUSDT · {e(t(ms_time(last_ms + 300_000), with_date=False))} IST</div></div>")
    mid = (s.get("last_cycle") or {}).get("mid")
    return f"<div class='btc'><b>{e(mid or '–')}</b><div class='note'>BTCUSDT mid</div></div>" if mid else ""


def render(s: dict, name: str = "", overview: str = "", candles: list[tuple[int, float]] | None = None,
           desks: list[str] | None = None) -> str:
    now = s["now"]
    last = s["last_cycle"]
    c, ct = s["counts"], s["counts_today"]
    u_today = s["usage"][0] if s["usage"] else {}
    title = f"bitra-desk · {name}" if name else "bitra-desk"
    parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark">
<noscript><meta http-equiv="refresh" content="60"></noscript>
<title>{e(title)}</title><style>{CSS}</style></head><body><div id="app">
<header class="top"><div><h1>bitra-desk</h1>
<div class="sub">AI trading sandbox · BTCUSDT on Bybit · one decision an hour · paper money, no orders ·
updated {e(t(now, with_date=False))} IST · next pass {e(t(s['next_pass'], with_date=False))}</div></div>
{btc_header(candles or [], s, now)}</header>
{overview}
<section id="detail"><div class="sec-head"><h2>{e(title)}</h2>"""]
    if desks and len(desks) > 1:
        tabs = "".join(f"<a class='tab' href='?desk={e(d)}#detail' style='--c:var(--s{i + 1})'"
                       f"{' aria-current=page' if d == name else ''}><span class='sw'></span>{e(d)}</a>"
                       for i, d in enumerate(desks))
        parts.append(f"<nav class='tabs' aria-label='Desk'>{tabs}</nav>")
    parts.append(f"""</div>
<p class="sub" style="margin:0 0 12px">{e(s.get('model', ''))} · {status(s['service'])} · last cycle
{e(t(last['at']) if last else '–')} ({e(ago(last['at'], now) if last else '')}) · BTC mid {e(last['mid'] if last else '–')}</p>
<div class="tiles">
<div class="card tile"><b>{s['total_cycles']}</b><span>cycles recorded ({sum(ct.values())} today)</span></div>
<div class="card tile"><b>{c.get('would trade', 0)}</b><span>would-be trades ({ct.get('would trade', 0)} today)</span></div>
<div class="card tile"><b>{c.get('asked', 0)}</b><span>asked, then refused</span></div>
<div class="card tile"><b>{c.get('held', 0)}</b><span>held (market too quiet)</span></div>
<div class="card tile"><b>{c.get('error (recent)', 0)}</b><span>errors in last {RECENT_CYCLES}</span></div>
<div class="card tile"><b>{u_today.get('calls', 0)}</b><span>model calls today ({u_today.get('errors', 0)} failed)</span></div>
</div></section>""")

    parts.append(render_paper(s.get("paper"), now))

    parts.append("<section><div class='sec-head'><h2>What the analysts say now</h2><span class='sub'>technical "
                 "decides; macro and sentiment move its conviction</span></div><div class='grid3'>")
    for a in s["analysts"]:
        parts.append(f"<div class='card pad analyst'><h3>{e(a['role'])}</h3>{pill(a['says'])}"
                     f"<p>{e(clip(a['reason']))}</p>"
                     + (f"<p class='note'>data as of {e((a['data_as_of'] or '')[:10])}</p>" if a["data_as_of"] else "")
                     + "</div>")
    if not s["analysts"]:
        parts.append("<div class='card pad'>No analyst has answered yet.</div>")
    parts.append("</div></section>")

    h = s["hindsight"]
    parts.append("<section><div class='sec-head'><h2>Hindsight</h2>")
    if h:
        side = h.get("side") or {}
        parts.append(f"<span class='sub'>updated {e(ago(h['_written'], now))} · {e(h.get('days'))} day(s), "
                     f"{e(h.get('independent'))} independent decision(s)</span></div>")
        if side:
            ms_, os_ = side.get("model_side") or {}, side.get("opposite_side") or {}
            a, b = num(ms_.get("mean_net_bps")), num(os_.get("mean_net_bps"))
            scale = max(abs(a or 0), abs(b or 0)) or 1

            def bar(v):
                if v is None:
                    return "<span class='bar'></span>"
                w = abs(v) / scale * 50
                pos = f"left:50%;width:{w:.1f}%" if v >= 0 else f"left:{50 - w:.1f}%;width:{w:.1f}%"
                return f"<span class='bar'><i style='{pos}'></i></span>"

            parts.append(f"""<div class='card pad verdict'><p><b>The question this experiment asks:</b> do the model's
calls beat their exact reverse after costs? Over {e(ms_.get('decisions'))} decisions the model's side averaged
{e(ms_.get('mean_net_bps'))} bps a decision, the reverse {e(os_.get('mean_net_bps'))} bps:
<b>{e(side.get('verdict', ''))}</b>.</p>
<div class='bars'><span>Model's side</span>{bar(a)}<span class='num {tone(a)}'>{e(signed(a))} bps</span>
<span>Exact reverse</span>{bar(b)}<span class='num {tone(b)}'>{e(signed(b))} bps</span></div>
<p class='note'>A verdict needs at least 10 decisions a side and 5 days. Not replayed yet:
{e((h.get('skipped') or {}).get('hold not over', 0))} still inside their {e(int(h.get('hold_s') or 0) // 3600)} h hold.</p></div>""")
        parts.append("<details class='card fold' id='d-gates'><summary><h2>By gate</h2><span class='count'>what "
                     "each refusal would have made</span></summary><div class='tablewrap'><table><tr><th>Group</th>"
                     "<th class='num'>Decisions</th><th class='num'>Mean net</th><th class='num'>Won</th>"
                     "<th>Verdict</th></tr>")
        groups = [("admitted (would-be trades)", h.get("admitted") or {})]
        groups += [(f"refused by {g.get('gate')}", g) for g in (h.get("gates") or [])]
        groups.append(("all refused", h.get("all_refused") or {}))
        for gname, g in groups:
            won = g.get("won")
            won_txt = f"{float(won) * 100:.0f}%" if won not in (None, "") else ""
            parts.append(f"<tr><td>{e(gname)}</td><td class='num'>{e(g.get('decisions'))}</td>"
                         f"<td class='num'>{e(g.get('mean_net_bps'))} bps</td><td class='num'>{e(won_txt)}</td>"
                         f"<td>{e(g.get('verdict', ''))}</td></tr>")
        parts.append("</table></div></details>")
    else:
        parts.append("</div><p class='note'>Not computed yet (the hindsight timer runs at half past each hour).</p>")
    parts.append("</section>")

    parts.append(f"<details class='card fold' id='d-trades'><summary><h2>Would-be trades</h2><span class='count'>"
                 f"{len(s['trades'])} · sandbox intents, nothing sent</span></summary><div class='tablewrap'><table>"
                 "<tr><th>Time</th><th>Side</th><th>Setup</th><th class='num'>Mid</th><th class='num'>Stop</th>"
                 "<th class='num'>Take</th><th class='num'>Conviction</th><th class='num'>Round trip</th>"
                 "<th class='num'>Break-even win rate</th><th>Why</th></tr>")
    for x in s["trades"]:
        be = x.get("break_even_win_rate")
        be_txt = f"{float(be) * 100:.0f}%" if be else ""
        parts.append(f"<tr><td class='nw'>{e(t(x['at']))}</td><td>{pill(x.get('target') or '')}</td>"
                     f"<td class='nw'>{e(x.get('setup'))}</td><td class='num'>{e(x.get('mid'))}</td>"
                     f"<td class='num'>{e(x.get('stop_price'))}</td><td class='num'>{e(x.get('take_price'))}</td>"
                     f"<td class='num'>{e(x.get('conviction'))}</td>"
                     f"<td class='num'>{e(x.get('priced_round_trip_bps'))} bps</td><td class='num'>{e(be_txt)}</td>"
                     f"<td class='why'>{e(clip(x.get('reason', ''), 200))}</td></tr>")
    if not s["trades"]:
        parts.append("<tr><td colspan=10>None yet.</td></tr>")
    parts.append("</table></div></details>")

    parts.append(f"<details class='card fold' id='d-cycles'><summary><h2>Recent cycles</h2><span class='count'>"
                 f"last {len(s['recent'])}</span></summary><div class='tablewrap'><table><tr><th>Time</th>"
                 "<th>Outcome</th><th>Reason</th><th>Technical</th><th>Macro</th><th>Sentiment</th>"
                 "<th class='num'>Tokens</th></tr>")
    for x in s["recent"]:
        parts.append(f"<tr><td class='nw'>{e(t(x['at']))}</td><td>{pill(x['outcome'])}</td>"
                     f"<td class='why'>{e(clip(x['reason'], 220))}</td><td class='nw'>{e(x['technical'])}</td>"
                     f"<td class='nw'>{e(x['macro'])}</td><td class='nw'>{e(x['sentiment'])}</td>"
                     f"<td class='num'>{e(x['tokens'] or '')}</td></tr>")
    parts.append("</table></div></details>")

    parts.append(f"<details class='card fold' id='d-series'><summary><h2>Data series the analysts read</h2>"
                 f"<span class='count'>{len(s['series'])}</span></summary><div class='tablewrap'><table><tr>"
                 "<th>Series</th><th class='num'>Value</th><th>State</th><th>As of</th><th class='num'>Age</th>"
                 "<th>Source</th></tr>")
    for x in s["series"]:
        parts.append(f"<tr><td class='nw'>{e(x.get('series'))}</td><td class='num'>{e(x.get('value'))}</td>"
                     f"<td>{pill(x.get('state') or '')}</td><td class='nw'>{e((x.get('observed_at') or '')[:10])}</td>"
                     f"<td class='num'>{e(x.get('age_h'))} h</td><td>{e(x.get('source'))}</td></tr>")
    parts.append("</table></div></details>")

    total = (s.get("cost") or {}).get("total_usd")
    spend = f"≈ ${total:,.2f} at list price" if total is not None else "free tier"
    parts.append(f"<details class='card fold' id='d-usage'><summary><h2>Model use</h2><span class='count'>"
                 f"{e(spend)}</span></summary><div class='tablewrap'><table><tr><th>Day</th><th class='num'>Calls</th>"
                 "<th class='num'>Failed</th><th class='num'>Tokens in / out</th><th class='num'>Est. cost</th>"
                 "<th>Answered by</th><th class='num'>Median latency</th></tr>")
    for d in s["usage"][:14]:
        models = ", ".join(f"{k} {v}" for k, v in d["models"].items())
        cost = f"${d['usd']:,.2f}" if d.get("usd") is not None else "–"
        parts.append(f"<tr><td class='nw'>{e(d['day'])}</td><td class='num'>{d['calls']}</td>"
                     f"<td class='num'>{d['errors']}</td><td class='num'>{d['tokens_in']:,} / {d['tokens_out']:,}</td>"
                     f"<td class='num'>{e(cost)}</td><td>{e(models)}</td><td class='num'>{e(d['median_latency_s'])} s</td></tr>")
    q = f"?desk={e(name)}" if name else ""
    parts.append(f"</table></div></details><p class='note foot'>Read-only view of {e(s.get('desk', ''))}/runs/cycles. "
                 f"JSON: <a href='api/state.json{q}'>api/state.json{q}</a>. Runbook: bitra-desk/README.md.</p>"
                 f"</div><script>{JS}</script></body></html>")
    return "".join(parts)


# The page's own script: draws the two charts at the container's real width from #chart-data, shows the
# hour strip's detail on hover or tap, and swaps in a fresh page every minute while the tab is visible,
# keeping the scroll position and which sections are open. Model text only ever reaches the DOM as text.
JS = r"""
(() => {
const NS = "http://www.w3.org/2000/svg", IST = 19800000, H = 3600000;
const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const ist = v => new Date(v + IST);
const two = n => String(n).padStart(2, "0");
const hhmm = v => { const d = ist(v); return two(d.getUTCHours()) + ":" + two(d.getUTCMinutes()); };
const day = v => { const d = ist(v); return d.getUTCDate() + " " + MON[d.getUTCMonth()]; };
const when = v => day(v) + " " + hhmm(v);
const usd = v => (v < 0 ? "−$" : "$") + Math.abs(v).toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
const px = v => Number(v).toLocaleString("en-US", {minimumFractionDigits: 1, maximumFractionDigits: 1});
function svg(tag, attrs, parent) {
  const n = document.createElementNS(NS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}
function niceTicks(lo, hi, count) {
  const raw = (hi - lo || 1) / count, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw);
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-6; v += step) out.push(Math.round(v / step) * step);
  return out;
}
function timeTicks(t0, t1, width) {
  const most = Math.max(2, Math.floor(width / 70));
  const step = [3, 6, 12, 24, 48, 96].map(h => h * H).find(s => (t1 - t0) / s <= most) || 192 * H;
  const out = [];
  for (let v = Math.ceil((t0 + IST) / step) * step - IST; v <= t1; v += step) out.push(v);
  return out;
}
function tipShow(box, lines, x, y) {
  const tip = box.querySelector(".tip");
  tip.replaceChildren(...lines.map(([text, color, strong]) => {
    const row = document.createElement("div");
    if (color) { const s = document.createElement("i"); s.className = "sw"; s.style.background = color; row.appendChild(s); }
    const span = document.createElement(strong ? "b" : "span");
    span.textContent = text;
    row.appendChild(span);
    return row;
  }));
  tip.hidden = false;
  const w = tip.offsetWidth, h = tip.offsetHeight, W = box.clientWidth;
  let left = x + 14;
  if (left + w > W) left = x - w - 14;
  tip.style.left = Math.max(0, left) + "px";
  tip.style.top = Math.max(0, y - h - 10) + "px";
}
const tipHide = box => { box.querySelector(".tip").hidden = true; };
function empty(box, text) {
  box.querySelectorAll("svg,.empty").forEach(n => n.remove());
  const p = document.createElement("p");
  p.className = "empty";
  p.textContent = text;
  box.appendChild(p);
}
function frame(box, lo, hi, t0, t1, opt) {
  box.querySelectorAll("svg,.empty").forEach(n => n.remove());
  const W = box.clientWidth, Hh = box.clientHeight, m = {l: opt.left, r: opt.right, t: 10, b: 26};
  const root = svg("svg", {width: W, height: Hh, viewBox: `0 0 ${W} ${Hh}`, "aria-hidden": "true"});
  box.prepend(root);
  const pw = W - m.l - m.r, ph = Hh - m.t - m.b;
  const x = v => m.l + (v - t0) / (t1 - t0 || 1) * pw;
  const y = v => m.t + (1 - (v - lo) / (hi - lo || 1)) * ph;
  for (const v of niceTicks(lo, hi, Math.max(3, Math.floor(ph / 46)))) {
    if (v < lo || v > hi) continue;
    svg("line", {x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), class: "gridline"}, root);
    svg("text", {x: m.l - 8, y: y(v), "text-anchor": "end", "dominant-baseline": "middle"}, root).textContent = opt.yFmt(v);
  }
  svg("line", {x1: m.l, x2: W - m.r, y1: m.t + ph, y2: m.t + ph, class: "axisline"}, root);
  for (const v of timeTicks(t0, t1, pw)) {
    const lbl = hhmm(v) === "00:00" ? day(v) : hhmm(v);
    svg("text", {x: x(v), y: Hh - 8, "text-anchor": "middle"}, root).textContent = lbl;
  }
  return {root, x, y, m, W, Hh, t0, t1, pw};
}
function hover(box, f, linesAt) {
  const cross = svg("line", {y1: f.m.t, y2: f.Hh - f.m.b, class: "cross", visibility: "hidden"}, f.root);
  const area = svg("rect", {x: f.m.l, y: 0, width: f.pw, height: f.Hh, fill: "transparent"}, f.root);
  const move = ev => {
    const r = box.getBoundingClientRect();
    const X = Math.min(Math.max(ev.clientX - r.left, f.m.l), f.m.l + f.pw);
    const at = f.t0 + (X - f.m.l) / f.pw * (f.t1 - f.t0);
    cross.setAttribute("x1", X); cross.setAttribute("x2", X); cross.setAttribute("visibility", "visible");
    tipShow(box, linesAt(at), X, ev.clientY - r.top);
  };
  area.addEventListener("pointermove", move);
  area.addEventListener("pointerdown", move);
  area.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); tipHide(box); });
}
const valueAt = (pts, at) => { let v = pts[0][1]; for (const p of pts) { if (p[0] <= at) v = p[1]; else break; } return v; };
function drawEquity(box, data) {
  const desks = data.desks.filter(d => d.curve.length);
  if (!desks.length) return empty(box, "No paper account yet.");
  const t0 = Math.min(...desks.map(d => d.curve[0][0])), t1 = data.now;
  const vals = desks.flatMap(d => d.curve.map(p => p[1]));
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = Math.max((hi - lo) * 0.18, hi * 0.002);
  lo -= pad; hi += pad;
  const narrow = box.clientWidth < 560;
  const f = frame(box, lo, hi, t0, t1, {left: 58, right: narrow ? 70 : 128,
    yFmt: v => "$" + v.toLocaleString("en-US", {maximumFractionDigits: 0})});
  const base = desks[0].start;
  if (base >= lo && base <= hi) svg("line", {x1: f.m.l, x2: f.m.l + f.pw, y1: f.y(base), y2: f.y(base), class: "baseline"}, f.root);
  hover(box, f, at => [[when(at) + " IST", null, true]].concat(desks.filter(d => at >= d.curve[0][0])
    .map(d => [`${d.name}  ${usd(valueAt(d.curve, at))}`, `var(--s${d.slot})`])));
  const ends = [];
  for (const d of desks) {
    let path = "";
    d.curve.forEach((p, i) => { path += i ? `H${f.x(p[0])}V${f.y(p[1])}` : `M${f.x(p[0])},${f.y(p[1])}`; });
    svg("path", {d: path, class: "line", stroke: `var(--s${d.slot})`}, f.root);
    const last = d.curve[d.curve.length - 1];
    svg("circle", {cx: f.x(last[0]), cy: f.y(last[1]), r: 4, fill: `var(--s${d.slot})`, class: "ring"}, f.root);
    ends.push({d, y: f.y(last[1]), v: last[1]});
  }
  ends.sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 15) ends[i].y = ends[i - 1].y + 15;
  for (const e of ends) {
    svg("text", {x: f.m.l + f.pw + 10, y: e.y, "dominant-baseline": "middle", class: "endlabel"}, f.root)
      .textContent = narrow ? e.d.name : `${e.d.name} ${usd(e.v)}`;
  }
}
function drawPrice(box, data) {
  const pr = data.price;
  if (pr.length < 2) return empty(box, "No price data yet: the paper account caches candles from a desk's first would-be trade.");
  const t0 = pr[0][0], t1 = Math.max(data.now, pr[pr.length - 1][0]);
  const trades = data.desks.flatMap(d => d.trades.map(tr => Object.assign({d}, tr)))
    .filter(tr => (tr.open ? data.now : tr.exit_ms) >= t0);
  const vals = pr.map(p => p[1]).concat(trades.flatMap(tr => [tr.entry, tr.open ? tr.mark : tr.exit]).filter(v => v != null));
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.08 || 50;
  lo -= pad; hi += pad;
  const f = frame(box, lo, hi, t0, t1, {left: 58, right: 14,
    yFmt: v => v.toLocaleString("en-US", {maximumFractionDigits: 0})});
  let path = "";
  pr.forEach((p, i) => { path += (i ? "L" : "M") + f.x(p[0]).toFixed(1) + "," + f.y(p[1]).toFixed(1); });
  svg("path", {d: path, class: "price"}, f.root);
  hover(box, f, at => [[when(at) + " IST", null, true], ["BTCUSDT " + px(valueAt(pr, at))]]);
  for (const tr of trades) {
    const c = `var(--s${tr.d.slot})`, endT = tr.open ? data.now : tr.exit_ms, endV = tr.open ? tr.mark : tr.exit;
    const xe = f.x(Math.max(tr.entry_ms, t0)), ye = f.y(tr.entry), xx = f.x(endT), yx = f.y(endV);
    svg("line", {x1: xe, y1: ye, x2: xx, y2: yx, class: "hold" + (tr.open ? " open" : ""), stroke: c}, f.root);
    const g = svg("g", {class: "mark", tabindex: 0, role: "img",
      "aria-label": `${tr.d.name} ${tr.side} from ${px(tr.entry)}`}, f.root);
    const s = 7, up = tr.side === "long";
    const tri = up ? `M${xe},${ye - s}L${xe + s},${ye + s * .8}L${xe - s},${ye + s * .8}Z`
                   : `M${xe},${ye + s}L${xe + s},${ye - s * .8}L${xe - s},${ye - s * .8}Z`;
    svg("circle", {cx: xe, cy: ye, r: 14, fill: "transparent"}, g);
    if (!tr.open) svg("circle", {cx: xx, cy: yx, r: 4.5, fill: c, class: "ring"}, g);
    svg("path", {d: tri, fill: c, class: "ring"}, g);
    const lines = [[`${tr.d.name} · ${tr.side} ${tr.setup || ""}`, c, true], [`in  ${when(tr.entry_ms)} at ${px(tr.entry)}`],
      tr.open ? [`open, mark ${px(tr.mark)}`] : [`out ${when(tr.exit_ms)} at ${px(tr.exit)} · ${tr.exit_reason || ""}`],
      [`${tr.open ? "unrealized" : "net"} ${usd(tr.net_usd || 0)}`]];
    const show = ev => { if (ev) ev.stopPropagation(); tipShow(box, lines, xe, ye); };
    g.addEventListener("pointerenter", show); g.addEventListener("pointerdown", show); g.addEventListener("focus", () => show());
    g.addEventListener("pointerleave", () => tipHide(box)); g.addEventListener("blur", () => tipHide(box));
  }
}
function draw() {
  const el = document.getElementById("chart-data");
  if (!el) return;
  const data = JSON.parse(el.textContent);
  const eq = document.getElementById("eq-chart"), pc = document.getElementById("price-chart");
  if (eq) drawEquity(eq, data);
  if (pc) drawPrice(pc, data);
}
function initGrid() {
  const cap = document.getElementById("grid-tip");
  if (!cap) return;
  for (const c of document.querySelectorAll(".strip .cell[data-tip]")) {
    const show = () => { cap.textContent = c.dataset.tip; };
    c.addEventListener("pointerenter", show); c.addEventListener("focus", show); c.addEventListener("click", show);
  }
  for (const s of document.querySelectorAll(".strip")) s.scrollLeft = s.scrollWidth;
}
function init() { draw(); initGrid(); }
let resizeTimer;
window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(draw, 120); });
async function refresh() {
  if (document.hidden) return;
  try {
    const r = await fetch(location.href, {cache: "no-store"});
    if (!r.ok) return;
    const next = new DOMParser().parseFromString(await r.text(), "text/html").getElementById("app");
    if (!next) return;
    const open = {};
    for (const d of document.querySelectorAll("details[id]")) open[d.id] = d.open;
    const strips = [...document.querySelectorAll(".strip")].map(s => s.scrollLeft);
    next.querySelectorAll("script:not([type])").forEach(n => n.remove());
    document.getElementById("app").replaceWith(next);
    for (const id in open) { const d = document.getElementById(id); if (d) d.open = open[id]; }
    init();
    document.querySelectorAll(".strip").forEach((s, i) => { if (strips[i] != null && strips[i] < s.scrollWidth - s.clientWidth - 4) s.scrollLeft = strips[i]; });
  } catch (err) { /* offline for a moment: the next minute tries again */ }
}
setInterval(refresh, 60000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
init();
})();
"""


def to_json(s: dict) -> str:
    return json.dumps(s, default=lambda o: o.isoformat() if isinstance(o, datetime) else str(o), indent=1)


def make_handler(desks: list[dict] | Path, paper_dir: Path | None = None):
    if isinstance(desks, Path):  # one desk, as before
        desks = [{"name": "", "path": desks, "paper": paper_dir or desks.parent / "paper", "unit": "bitra-desk"}]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server's name)
            path, _, query = self.path.partition("?")
            if path not in ("/", "/api/state.json"):
                self.send_error(404)
                return
            want = parse_qs(query).get("desk", [desks[0]["name"]])[0]
            chosen = next((d for d in desks if d["name"] == want), None)
            if chosen is None:
                self.send_error(404)
                return
            now = datetime.now(timezone.utc)
            states = {d["name"]: build_state(d["path"], now=now, paper_dir=d["paper"], unit=d["unit"]) for d in desks}
            state = states[chosen["name"]]
            if path == "/":
                since = int(now.timestamp() * 1000) - max(PRICE_HOURS, 25) * 3_600_000
                candles = load_candles([d["paper"] for d in desks], since_ms=since)
                overview = render_overview(states, chosen["name"], candles, now)
                body = render(state, chosen["name"], overview, candles, [d["name"] for d in desks]).encode()
                ctype = "text/html; charset=utf-8"
            else:
                body, ctype = to_json(state).encode(), "application/json"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # quiet: one line per request is noise in the journal
            pass

    return Handler


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--desk", action="append", default=[],
                   help="NAME=PATH, repeat for each desk; default ~/bitra/desk")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8790)
    args = p.parse_args()
    desks = [parse_desk(spec) for spec in (args.desk or [str(Path.home() / "bitra" / "desk")])]
    server = ThreadingHTTPServer((args.host, args.port), make_handler(desks))
    print(f"bitra-desk dashboard on http://{args.host}:{args.port}/ reading "
          + ", ".join(f"{d['name']}={d['path']}" for d in desks), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
