#!/usr/bin/env python3
"""bitra-desk Telegram updates: a digest of the desks every two hours, and an alert when a paper trade opens
or closes or a desk's service stops or comes back.

Reads what the dashboard reads, through ../dashboard/server.py, and keeps what it has already reported in
seen.json beside this file. Sends only to the one chat in TELEGRAM_CHAT_ID and takes no commands: outbound
only. The token comes from the environment (systemd EnvironmentFile=~/bitra/telegram/telegram.env, mode 600)
and never appears in output. Paper money only: nothing here can place an order.

    python3 notify.py digest --desk gemini=~/bitra/desk --desk groq=~/bitra/desk-groq --desk claude=~/bitra/desk-claude
    python3 notify.py alerts --desk ...      # every 15 minutes; the first run only records what exists
    python3 notify.py test                   # one hello, to check the token and chat

Until TELEGRAM_CHAT_ID is set, each run looks at the bot's messages: the first private chat to press Start
is written into the env file and gets a welcome, and from then on is the only chat it sends to.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))
import server  # noqa: E402  (the dashboard's reader: one definition of what a desk's state is)

API = "https://api.telegram.org"
DASHBOARD_URL = "https://bitra-desk.taildea8d9.ts.net/"
IST = server.IST
DIGEST_HOURS = 2
QUIET_FROM, QUIET_TO = 23, 7  # IST: messages still arrive, without a sound
WELCOME = ("👋 <b>Bitra Desk</b> is connected.\n\nEvery 2 hours: a digest of the three desks. As it happens: "
           "an alert when a paper trade opens or closes, or a desk stops. Silent from 23:00 to 07:00 IST.\n"
           "Paper money only; no orders are ever sent.")


class SendError(Exception):
    """A Telegram call failed; the message never carries the token."""


def redact(text: str, token: str) -> str:
    return text.replace(token, "***") if token else text


def api_get(token: str, method: str) -> dict:
    try:
        with urllib.request.urlopen(f"{API}/bot{token}/{method}", timeout=20) as r:
            return json.load(r)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise SendError(redact(f"{method}: {exc}", token)) from None


def send(token: str, chat_id: str, text: str, silent: bool = False) -> None:
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true",
                                   "disable_notification": "true" if silent else "false"}).encode()
    req = urllib.request.Request(f"{API}/bot{token}/sendMessage", data=data)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.load(r)
    except urllib.error.HTTPError as exc:
        try:
            desc = json.loads(exc.read() or b"{}").get("description", "")
        except ValueError:
            desc = ""
        raise SendError(redact(f"sendMessage {exc.code}: {desc}", token)) from None
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise SendError(redact(f"sendMessage: {exc}", token)) from None
    if not body.get("ok"):
        raise SendError(redact(f"sendMessage: {body.get('description', 'not ok')}", token))


def discover_chat(token: str, env_file: Path) -> str | None:
    """The one private chat that has messaged the bot, written into the env file; None if none or several."""
    chats = {}
    for u in api_get(token, "getUpdates").get("result") or []:
        chat = ((u.get("message") or u.get("my_chat_member") or {}).get("chat")) or {}
        if chat.get("id") is not None and chat.get("type") == "private":
            chats[str(chat["id"])] = True
    if len(chats) != 1:
        return None
    chat_id = next(iter(chats))
    lines = [ln for ln in env_file.read_text().splitlines() if not ln.startswith("TELEGRAM_CHAT_ID=")]
    env_file.write_text("\n".join(lines + [f"TELEGRAM_CHAT_ID={chat_id}"]) + "\n")
    return chat_id


def quiet(now: datetime) -> bool:
    h = now.astimezone(IST).hour
    return h >= QUIET_FROM or h < QUIET_TO


def e(v) -> str:
    return html.escape("" if v is None else str(v), quote=False)


def ranked(states: dict) -> list[dict]:
    rows = [server.comparison_row(n, s, slot=i + 1) for i, (n, s) in enumerate(states.items())]
    return sorted(rows, key=lambda r: -(server.num(r["equity"]) if r["equity"] is not None else -1e18))


def call_line(r: dict) -> str:
    st = r["stance"]
    if not st:
        return "not asked yet"
    conf = server.num(st.get("confidence"))
    return (f"{server.ARROW.get(st['target'], '')} {e(st['target'])} {e(st.get('setup') or '')}"
            + (f" {conf:.2f}" if conf is not None else "") + f" · {e(st['outcome'])} · {e(server.ago(st['at'], r['now']))}")


def activity(name: str, s: dict, since: datetime) -> str:
    cycles = [c for c in s.get("recent") or [] if c.get("at") and c["at"] >= since]
    asked = sum(c["outcome"] in ("refused", "would trade") for c in cycles)
    trades = sum(c["outcome"] == "would trade" for c in cycles)
    held = sum(c["outcome"] == "held" for c in cycles)
    errors = sum(c["outcome"] in ("error", "incomplete") for c in cycles)
    out = f"{e(name)} asked {asked}"
    if trades:
        out += f" ({trades} would-be trade{'s' if trades != 1 else ''})"
    out += f", held {held}"
    if errors:
        out += f", {errors} error{'s' if errors != 1 else ''}"
    return out


def digest_text(states: dict, candles: list[tuple[int, float]], now: datetime, since: datetime) -> str:
    lines = [f"<b>Bitra Desk</b> · {e(server.t(now))} IST"]
    if candles:
        last_ms, last = candles[-1]
        day_ago = next((c for a, c in reversed(candles) if a <= last_ms - 86_400_000), None)
        chg = f" ({server.signed((last / day_ago - 1) * 100, '{:.2f}')}% 24 h)" if day_ago else ""
        lines.append(f"BTCUSDT <b>{last:,.1f}</b>{chg}")
    lines.append("")
    for i, r in enumerate(ranked(states), 1):
        if r["equity"] is not None:
            trades = (f"{r['closed']} closed, {r['wins']}W {r['losses']}L" if r["closed"] else "no trades yet")
            money = f"{server.money(r['equity'])} ({float(r['return_pct']):+.2f}%) · {trades}"
        else:
            money = "no paper account yet"
        lines.append(f"<b>{i}. {e(r['name'])}</b> {money}")
        lines.append(f"    {call_line(r)}")
        o = r["open"]
        if o:
            lines.append(f"    open {e(o['side'])} from {o['entry']:,.1f} · {server.usd(o.get('unrealized_usd'))}")
    hours = max(1, round((now - since).total_seconds() / 3600))
    lines.append("")
    lines.append(f"Last {hours} h: " + " · ".join(activity(n, s, since) for n, s in states.items()))
    for n, s in states.items():
        cost = s.get("cost") or {}
        if cost.get("total_usd") is not None:
            lines.append(f"{e(n.capitalize())} API ≈ ${cost['total_usd']:,.2f} so far "
                         f"(${cost.get('today_usd') or 0:,.2f} today)")
    for n, s in states.items():
        if s.get("service") not in ("active", "unknown"):
            lines.append(f"⚠️ {e(n)}: service {e(s.get('service'))}")
    lines.append(f'<a href="{DASHBOARD_URL}">Dashboard</a> (with Tailscale on)')
    return "\n".join(lines)


def trade_key(t: dict) -> str:
    return f"{t['entry_ms']}:{t['side']}"


def events(states: dict, seen: dict) -> tuple[list[str], dict]:
    """Alerts for what changed since `seen`, and the new `seen`. A desk seen for the first time is only recorded."""
    alerts: list[str] = []
    new = {**seen, "desks": dict(seen.get("desks") or {})}
    for name, s in states.items():
        pa = s.get("paper") or {}
        trades = pa.get("trades") or []
        o = pa.get("open")
        now_rec = {"trades": [trade_key(t) for t in trades], "open": trade_key(o) if o else None,
                   "service": s.get("service")}
        before = (seen.get("desks") or {}).get(name)
        new["desks"][name] = now_rec
        if before is None:
            continue
        known = set(before.get("trades") or [])
        curve = {c[0]: c[1] for c in pa.get("equity_curve") or []}
        for t in trades:
            if trade_key(t) in known:
                continue
            eq = curve.get(t["exit_ms"], pa.get("equity"))
            alerts.append(f"🏁 <b>{e(name)}</b> closed {e(t['side'].upper())} at {t['exit']:,.1f} "
                          f"({e(t.get('exit_reason'))}): <b>{server.usd(t['net_usd'])}</b> "
                          f"({float(t.get('net_bps') or 0):+.0f} bps) · equity {server.money(eq)}")
        if o and now_rec["open"] != before.get("open"):
            alerts.append(f"🟢 <b>{e(name)}</b> opened {e(o['side'].upper())} {float(o['size']):g} BTC at "
                          f"{o['entry']:,.1f} · stop {o['stop']:,.1f} · take {o['take']:,.1f} · {e(o.get('setup'))}")
        was, is_ = before.get("service"), now_rec["service"]
        if "unknown" not in (was, is_) and was != is_:
            if is_ == "active":
                alerts.append(f"✅ {e(name)} desk is running again")
            elif was == "active":
                alerts.append(f"⚠️ {e(name)} desk is <b>{e(is_)}</b> (systemd); its cycles have stopped")
    return alerts, new


def read_env_file(path: Path) -> dict:
    try:
        return dict(ln.split("=", 1) for ln in path.read_text().splitlines() if "=" in ln and not ln.startswith("#"))
    except OSError:
        return {}


def main() -> int:
    here = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=["digest", "alerts", "test"])
    p.add_argument("--desk", action="append", default=[], help="NAME=PATH, as the dashboard takes them")
    p.add_argument("--state", type=Path, default=here / "seen.json")
    p.add_argument("--env-file", type=Path, default=Path(os.environ.get("TELEGRAM_ENV_FILE", here / "telegram.env")))
    args = p.parse_args()

    file_env = read_env_file(args.env_file)
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or file_env.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.environ.get("TELEGRAM_CHAT_ID") or file_env.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token:
        print(f"no TELEGRAM_BOT_TOKEN (in {args.env_file}); nothing sent")
        return 0
    try:
        if not chat:
            chat = discover_chat(token, args.env_file) or ""
            if not chat:
                print("no chat yet: waiting for one person to press Start in the bot")
                return 0
            send(token, chat, WELCOME)
            print("chat found and saved; welcome sent")
        if args.mode == "test":
            send(token, chat, "✅ Bitra Desk test message")
            print("test message sent")
            return 0

        now = datetime.now(timezone.utc)
        desks = [server.parse_desk(spec) for spec in args.desk]
        states = {d["name"]: server.build_state(d["path"], now=now, paper_dir=d["paper"], unit=d["unit"]) for d in desks}
        try:
            seen = json.loads(args.state.read_text())
        except (OSError, ValueError):
            seen = {}
        if args.mode == "digest":
            last = seen.get("last_digest_ms")
            since = server.ms_time(last) if last else now - timedelta(hours=DIGEST_HOURS)
            candles = server.load_candles([d["paper"] for d in desks], since_ms=server.ms(now) - 25 * 3_600_000)
            send(token, chat, digest_text(states, candles, now, since), silent=quiet(now))
            seen["last_digest_ms"] = server.ms(now)
            print("digest sent")
        else:
            alerts, seen = events(states, seen)
            for text in alerts:
                send(token, chat, text, silent=quiet(now))
            print(f"{len(alerts)} alert(s) sent")
        args.state.write_text(json.dumps(seen))  # only after every send went through: a failure retries
        return 0
    except SendError as exc:
        print(f"telegram: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
