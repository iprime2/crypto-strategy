#!/usr/bin/env python3
"""bitra-desk consensus account and flat scores, computed from the desks' own records; no model is called.

Consensus: a paper account that takes a desk's intent only when at least two desks' technical answers for the
same UTC hour name the same direction (long or short) and one of those desks produced an intent, that is,
passed its own gates. Among several such intents in one hour the highest conviction wins (ties: the first
desk named). The intents are then replayed exactly as paper.py replays a desk's: one position at a time, the
intent's own levels, the account's own equity and risk rule, out at the stop, the take or the hold limit, net
of the priced round trip.

Flat score: for each desk, the hours in which it answered flat, and what the other desks' intents in those
hours returned when replayed on their own (entry at the next 5-minute bar, out at the stop, the take or the
hold limit, net of the round trip): how many, the mean net bps and the share that won. It answers "was the
silence right?", which `tra hindsight` cannot, since a flat answer has no side to replay.

    python3 consensus.py --desk gemini=~/bitra/desk --desk groq=~/bitra/desk-groq \
        --desk claude=~/bitra/desk-claude --out ~/bitra/paper-consensus

Writes state.json (the paper.py shape plus rule, desks, hours, taken and flat_scores) and candles.jsonl.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import paper

RULE = "at least two desks name the same direction in the same hour, and one of them passed its gates"
DIRECTIONS = ("long", "short")


def load_desk(desk: Path) -> dict:
    """The desk's technical answers by UTC hour and its intents by UTC hour."""
    cycles = desk / "runs" / "cycles"
    calls: dict[str, dict] = {}
    for c in sorted(cycles.glob("20*/")):
        try:
            cy = json.loads((c / "cycle.json").read_text())
        except (OSError, ValueError):
            continue
        a = cy.get("analyst") or {}
        if not a.get("target"):
            continue
        hour = c.name[:13]
        call = {"cycle": c.name, "target": a["target"], "confidence": a.get("confidence"), "intent": bool(cy.get("intent"))}
        held = calls.get(hour)
        if held is None or call["intent"] or not held["intent"]:  # a cycle that produced an intent speaks for the hour
            calls[hour] = call
    intents = {it["cycle"][:13]: it for it in paper.load_intents(cycles)}
    risk, step = paper.desk_sizing(desk)
    return {"calls": calls, "intents": intents, "risk_bps": risk, "size_step": step}


def consensus_intents(desks: list[tuple[str, dict]]) -> list[dict]:
    """The intents the rule admits, oldest first, each tagged with the desks that agreed."""
    hours = sorted({h for _, d in desks for h in d["calls"]})
    out = []
    for hour in hours:
        votes = {name: d["calls"][hour]["target"] for name, d in desks if hour in d["calls"]}
        for side in DIRECTIONS:
            agreed = [name for name, t in votes.items() if t == side]
            if len(agreed) < 2:
                continue
            candidates = [(name, d["intents"][hour]) for name, d in desks if name in agreed and hour in d["intents"]]
            if not candidates:
                continue
            name, it = max(candidates, key=lambda c: float(c[1].get("conviction") or 0))  # ties: the first desk
            out.append({**it, "cycle": f"{it['cycle']} via {name}", "desk": name, "hour": hour, "agreed": agreed})
    return out


def hours_summary(desks: list[tuple[str, dict]]) -> dict:
    hours = sorted({h for _, d in desks for h in d["calls"]})
    all_asked = [h for h in hours if all(h in d["calls"] for _, d in desks)]
    agreed = []
    for h in hours:
        votes = [d["calls"][h]["target"] for _, d in desks if h in d["calls"]]
        if any(votes.count(side) >= 2 for side in DIRECTIONS):
            agreed.append(h)
    return {"hours_any": len(hours), "hours_all": len(all_asked), "agreed_hours": len(agreed)}


def replay(it: dict, bars: dict, hold_ms: int) -> dict | None:
    """One intent on its own, by paper.py's rules; None while it is still open or has no bar yet."""
    s = paper.simulate([it], bars, hold_ms, 1_000.0)
    return s["trades"][0] if s["trades"] else None


def flat_scores(desks: list[tuple[str, dict]], bars: dict, hold_ms: int) -> dict:
    out = {}
    for name, d in desks:
        flat_hours = [h for h, c in d["calls"].items() if c["target"] == "flat"]
        others = [(o, od["intents"][h]) for o, od in desks if o != name for h in flat_hours if h in od["intents"]]
        closed = [(o, replay(it, bars, hold_ms)) for o, it in others]
        closed = [(o, tr) for o, tr in closed if tr]
        nets = [tr["net_bps"] for _, tr in closed]
        by_desk: dict[str, int] = {}
        for o, _ in others:
            by_desk[o] = by_desk.get(o, 0) + 1
        out[name] = {"flat_hours": len(flat_hours), "others_intents": len(others), "closed": len(closed),
                     "mean_net_bps": round(statistics.mean(nets), 1) if nets else None,
                     "won": round(sum(n > 0 for n in nets) / len(nets), 3) if nets else None,
                     "sum_net_usd": round(sum(tr["net_usd"] for _, tr in closed), 2) if closed else None,
                     "by_desk": by_desk}
    return out


def build(desks: list[tuple[str, dict]], bars: dict, hold_ms: int, equity: float, risk_bps: float,
          size_step: float) -> dict:
    taken = consensus_intents(desks)
    state = paper.simulate(taken, bars, hold_ms, equity, risk_bps, size_step)
    for tr in state["trades"] + ([state["open"]] if state["open"] else []):
        src = next((t for t in taken if t["cycle"] == tr["cycle"]), {})
        tr["desk"], tr["agreed"] = src.get("desk"), src.get("agreed")
    state.update({"rule": RULE, "desks": [n for n, _ in desks], **hours_summary(desks),
                  "taken": [{"hour": t["hour"], "side": t["side"], "desk": t["desk"], "agreed": t["agreed"],
                             "conviction": t.get("conviction")} for t in taken],
                  "flat_scores": flat_scores(desks, bars, hold_ms)})
    return state


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--desk", action="append", default=[], help="NAME=PATH, in desk order; repeat for each desk")
    p.add_argument("--out", type=Path, default=Path.home() / "bitra" / "paper-consensus")
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--hold-hours", type=float, default=12.0)
    p.add_argument("--equity", type=float, default=1_000.0)
    args = p.parse_args()
    desks = []
    for spec in args.desk:
        name, _, path = spec.partition("=")
        desks.append((name, load_desk(Path(path).expanduser())))
    if not desks:
        raise SystemExit("name at least one --desk NAME=PATH")
    out = args.out.expanduser()
    out.mkdir(parents=True, exist_ok=True)
    now_ms = int(time.time() * 1000)
    first = [it["at_ms"] for _, d in desks for it in d["intents"].values()]
    bars, error = {}, None
    if first:
        bars, error = paper.update_cache(out / "candles.jsonl", args.symbol, (min(first) // paper.BAR_MS) * paper.BAR_MS, now_ms)
    risk, step = desks[0][1]["risk_bps"], desks[0][1]["size_step"]
    state = build(desks, bars, int(args.hold_hours * 3_600_000), args.equity, risk, step)
    state.update({"generated_ms": now_ms, "symbol": args.symbol, "hold_hours": args.hold_hours,
                  "fetch_error": error, "risk_bps": risk, "size_step": step})
    tmp = out / "state.json.tmp"
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(out / "state.json")
    print(f"consensus: equity {state['equity']:.2f} ({state['return_pct']:+.2f}%), {state['closed']} closed, "
          f"{len(state['taken'])} taken of {state['agreed_hours']} agreed hours ({state['hours_all']} with every desk asked); "
          "flat: " + ", ".join(f"{n} {s['others_intents']} trades → {s['mean_net_bps']} bps"
                               for n, s in state["flat_scores"].items())
          + (f"; fetch error: {error}" if error else ""))


if __name__ == "__main__":
    main()
