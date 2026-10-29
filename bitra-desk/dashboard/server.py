#!/usr/bin/env python3
"""bitra-desk dashboard: the sandbox desk's cycles, analysts, data series, model use and hindsight.

Reads only what `tra run` and `tra hindsight` write under <desk>/runs/cycles; never reads .env.
Read-only, stdlib only, binds 127.0.0.1. `tailscale serve` publishes it on the tailnet.

    python3 server.py --desk ~/bitra/desk --port 8790     # http://127.0.0.1:8790/
    curl -s 127.0.0.1:8790/api/state.json                 # the same state as JSON
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

IST = timezone(timedelta(hours=5, minutes=30))
RECENT_CYCLES = 48
REASON_CHARS = 280


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
        out["technical"] = f"{a['target']} {a.get('setup', '')} @ {conf}" if conf is not None else a["target"]
    ctx = cyc.get("context") or {}
    out["macro"] = (ctx.get("macro_analyst") or {}).get("regime", "")
    out["sentiment"] = (ctx.get("sentiment_analyst") or {}).get("state", "")
    return out


def usage_by_day(rows: list[dict]) -> list[dict]:
    days: dict[str, dict] = defaultdict(lambda: {"calls": 0, "ok": 0, "errors": 0, "tokens_in": 0,
                                                 "tokens_out": 0, "models": Counter(), "latency": []})
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
        if r.get("latency_ms"):
            d["latency"].append(float(r["latency_ms"]) / 1000)
    out = []
    for day in sorted(days, reverse=True):
        d = days[day]
        out.append({"day": day, "calls": d["calls"], "ok": d["ok"], "errors": d["errors"],
                    "tokens_in": d["tokens_in"], "tokens_out": d["tokens_out"],
                    "models": dict(d["models"].most_common()),
                    "median_latency_s": round(statistics.median(d["latency"]), 1) if d["latency"] else None})
    return out


def service_state(unit: str = "bitra-desk") -> str:
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", unit], capture_output=True, text=True, timeout=3)
        return r.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def build_state(desk: Path, now: datetime | None = None, service: str | None = None) -> dict:
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

    next_pass = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    return {
        "now": now,
        "service": service if service is not None else service_state(),
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
        "usage": usage_by_day(read_jsonl(cycles / "usage.jsonl")),
        "hindsight": hindsight,
    }


# ---- HTML -----------------------------------------------------------------------------------

def e(v) -> str:
    """Everything a model or a feed wrote is escaped: the records hold model text."""
    return html.escape("" if v is None else str(v))


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


PILL = {"would trade": "go", "refused": "warn", "held": "mute", "error": "bad", "incomplete": "bad",
        "active": "go", "bullish": "go", "risk-on": "go", "bearish": "bad", "risk-off": "bad",
        "neutral": "mute", "long": "go", "short": "bad"}


def pill(word: str) -> str:
    key = (word or "").split(" ")[0] if word not in PILL else word
    return f'<span class="pill {PILL.get(key, "mute")}">{e(word)}</span>'


CSS = """
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1b;--mute:#6b6b66;--line:#e4e3de;--go:#1f7a4d;--go-bg:#e3f3ea;
--warn:#8a5a00;--warn-bg:#fbf0d9;--bad:#a1321f;--bad-bg:#f8e2dc;--mute-bg:#eeede8}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--card:#1e1e1c;--ink:#ecebe6;--mute:#9b9a93;--line:#33322f;
--go:#7fd3a6;--go-bg:#183326;--warn:#f0c46b;--warn-bg:#3a2e14;--bad:#f2a08e;--bad-bg:#3d1f19;--mute-bg:#2a2a27}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 10px}
.sub{color:var(--mute);font-size:13px}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-top:16px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.tile b{display:block;font-size:22px;font-variant-numeric:tabular-nums}.tile span{color:var(--mute);font-size:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mute);font-weight:600;white-space:nowrap}tr:last-child td{border-bottom:0}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}td.nw{white-space:nowrap}td.why{min-width:260px}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;white-space:nowrap;
background:var(--mute-bg);color:var(--mute)}
.pill.go{background:var(--go-bg);color:var(--go)}.pill.warn{background:var(--warn-bg);color:var(--warn)}
.pill.bad{background:var(--bad-bg);color:var(--bad)}
.note{color:var(--mute);font-size:12px;margin:8px 2px}
"""


def render(s: dict) -> str:
    now = s["now"]
    last = s["last_cycle"]
    c, ct = s["counts"], s["counts_today"]
    u_today = s["usage"][0] if s["usage"] else {}
    parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60">
<title>bitra-desk</title><style>{CSS}</style></head><body><main>
<h1>bitra-desk {pill(s['service'])}</h1>
<div class="sub">Sandbox AI desk · BTCUSDT 1h · no orders · times IST · refreshes every minute ·
last cycle {e(t(last['at']) if last else '–')} ({e(ago(last['at'], now) if last else '')}) ·
next pass {e(t(s['next_pass'], with_date=False))} · BTC mid {e(last['mid'] if last else '–')}</div>
<div class="tiles">
<div class="tile"><b>{s['total_cycles']}</b><span>cycles recorded ({sum(ct.values())} today)</span></div>
<div class="tile"><b>{c.get('would trade', 0)}</b><span>would-be trades ({ct.get('would trade', 0)} today)</span></div>
<div class="tile"><b>{c.get('asked', 0)}</b><span>asked, then refused</span></div>
<div class="tile"><b>{c.get('held', 0)}</b><span>held (market too quiet)</span></div>
<div class="tile"><b>{c.get('error (recent)', 0)}</b><span>errors in last {RECENT_CYCLES}</span></div>
<div class="tile"><b>{u_today.get('calls', 0)}</b><span>model calls today ({u_today.get('errors', 0)} failed)</span></div>
</div>"""]

    parts.append("<h2>What the analysts say now</h2><div class='card'><table><tr><th>Analyst</th><th>Says</th>"
                 "<th>Why</th><th>Data as of</th></tr>")
    for a in s["analysts"]:
        parts.append(f"<tr><td class='nw'>{e(a['role'])}</td><td class='nw'>{pill(a['says'])}</td>"
                     f"<td class='why'>{e(clip(a['reason']))}</td><td class='nw'>{e((a['data_as_of'] or '')[:10])}</td></tr>")
    if not s["analysts"]:
        parts.append("<tr><td colspan=4>No analyst has answered yet.</td></tr>")
    parts.append("</table></div>")

    parts.append("<h2>Data series the analysts read</h2><div class='card'><table><tr><th>Series</th><th>Value</th>"
                 "<th>State</th><th>As of</th><th>Age</th><th>Source</th></tr>")
    for x in s["series"]:
        parts.append(f"<tr><td class='nw'>{e(x.get('series'))}</td><td class='num'>{e(x.get('value'))}</td>"
                     f"<td>{pill(x.get('state') or '')}</td><td class='nw'>{e((x.get('observed_at') or '')[:10])}</td>"
                     f"<td class='num'>{e(x.get('age_h'))} h</td><td>{e(x.get('source'))}</td></tr>")
    parts.append("</table></div>")

    parts.append("<h2>Would-be trades</h2><p class='note'>Sandbox intents: what the desk would have sent. "
                 "Nothing was sent.</p><div class='card'><table><tr><th>Time</th><th>Side</th><th>Setup</th>"
                 "<th>Mid</th><th>Stop</th><th>Take</th><th>Conviction</th><th>Round trip</th>"
                 "<th>Break-even win rate</th><th>Why</th></tr>")
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
    parts.append("</table></div>")

    h = s["hindsight"]
    parts.append("<h2>Hindsight</h2>")
    if h:
        side = h.get("side") or {}
        parts.append(f"<p class='note'>Every decision replayed on the candles that followed, net of costs. "
                     f"Updated {e(ago(h['_written'], now))}. {e(h.get('days'))} day(s), "
                     f"{e(h.get('independent'))} independent decision(s): the verdict needs at least 10 a side "
                     f"and 5 days.</p><div class='card'><table><tr><th>Group</th><th>Decisions</th>"
                     f"<th>Mean net</th><th>Won</th><th>Verdict</th></tr>")
        groups = [("admitted (would-be trades)", h.get("admitted") or {})]
        groups += [(f"refused by {g.get('gate')}", g) for g in (h.get("gates") or [])]
        groups.append(("all refused", h.get("all_refused") or {}))
        for name, g in groups:
            won = g.get("won")
            won_txt = f"{float(won) * 100:.0f}%" if won not in (None, "") else ""
            parts.append(f"<tr><td>{e(name)}</td><td class='num'>{e(g.get('decisions'))}</td>"
                         f"<td class='num'>{e(g.get('mean_net_bps'))} bps</td><td class='num'>{e(won_txt)}</td>"
                         f"<td>{e(g.get('verdict', ''))}</td></tr>")
        parts.append("</table></div>")
        if side:
            ms, os_ = side.get("model_side") or {}, side.get("opposite_side") or {}
            parts.append(f"<p class='note'><b>The question this experiment asks:</b> the model's side averaged "
                         f"{e(ms.get('mean_net_bps'))} bps a decision, the exact reverse "
                         f"{e(os_.get('mean_net_bps'))} bps, over {e(ms.get('decisions'))} decisions: "
                         f"<b>{e(side.get('verdict', ''))}</b>. Not replayed yet: "
                         f"{e((h.get('skipped') or {}).get('hold not over', 0))} still inside their "
                         f"{e(int(h.get('hold_s') or 0) // 3600)} h hold.</p>")
    else:
        parts.append("<p class='note'>Not computed yet (the hindsight timer runs at half past each hour).</p>")

    parts.append(f"<h2>Recent cycles</h2><div class='card'><table><tr><th>Time</th><th>Outcome</th>"
                 f"<th>Reason</th><th>Technical</th><th>Macro</th><th>Sentiment</th><th>Tokens</th></tr>")
    for x in s["recent"]:
        parts.append(f"<tr><td class='nw'>{e(t(x['at']))}</td><td>{pill(x['outcome'])}</td>"
                     f"<td class='why'>{e(clip(x['reason'], 220))}</td><td class='nw'>{e(x['technical'])}</td>"
                     f"<td class='nw'>{e(x['macro'])}</td><td class='nw'>{e(x['sentiment'])}</td>"
                     f"<td class='num'>{e(x['tokens'] or '')}</td></tr>")
    parts.append("</table></div>")

    parts.append("<h2>Model use (Gemini free tier)</h2><div class='card'><table><tr><th>Day</th><th>Calls</th>"
                 "<th>Failed</th><th>Tokens in / out</th><th>Answered by</th><th>Median latency</th></tr>")
    for d in s["usage"][:14]:
        models = ", ".join(f"{k} {v}" for k, v in d["models"].items())
        parts.append(f"<tr><td class='nw'>{e(d['day'])}</td><td class='num'>{d['calls']}</td>"
                     f"<td class='num'>{d['errors']}</td><td class='num'>{d['tokens_in']} / {d['tokens_out']}</td>"
                     f"<td>{e(models)}</td><td class='num'>{e(d['median_latency_s'])} s</td></tr>")
    parts.append("</table></div><p class='note'>Read-only view of ~/bitra/desk/runs/cycles. "
                 "JSON: <a href='api/state.json'>api/state.json</a>. Runbook: bitra-desk/README.md.</p>"
                 "</main></body></html>")
    return "".join(parts)


def to_json(s: dict) -> str:
    return json.dumps(s, default=lambda o: o.isoformat() if isinstance(o, datetime) else str(o), indent=1)


def make_handler(desk: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server's name)
            path = self.path.split("?", 1)[0]
            if path not in ("/", "/api/state.json"):
                self.send_error(404)
                return
            state = build_state(desk)
            if path == "/":
                body, ctype = render(state).encode(), "text/html; charset=utf-8"
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
    p.add_argument("--desk", type=Path, default=Path.home() / "bitra" / "desk")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8790)
    args = p.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.desk.expanduser()))
    print(f"bitra-desk dashboard on http://{args.host}:{args.port}/ reading {args.desk}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
