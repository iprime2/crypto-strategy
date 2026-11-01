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
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))
import server  # noqa: E402  (the dashboard's reader: one definition of what a desk's state is)

API = "https://api.telegram.org"
DASHBOARD_URL = "https://bitra-desk.taildea8d9.ts.net/"
IST = server.IST
DIGEST_HOURS = 2
STRIP_HOURS = 24  # the card's hour-by-hour strip; the dashboard shows 48
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


def post(token: str, method: str, req: urllib.request.Request) -> None:
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            body = json.load(r)
    except urllib.error.HTTPError as exc:
        try:
            desc = json.loads(exc.read() or b"{}").get("description", "")
        except ValueError:
            desc = ""
        raise SendError(redact(f"{method} {exc.code}: {desc}", token)) from None
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise SendError(redact(f"{method}: {exc}", token)) from None
    if not body.get("ok"):
        raise SendError(redact(f"{method}: {body.get('description', 'not ok')}", token))


def send(token: str, chat_id: str, text: str, silent: bool = False) -> None:
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true",
                                   "disable_notification": "true" if silent else "false"}).encode()
    post(token, "sendMessage", urllib.request.Request(f"{API}/bot{token}/sendMessage", data=data))


def send_photo(token: str, chat_id: str, png: bytes, caption: str, silent: bool = False) -> None:
    """The card as a photo with its caption (multipart upload: the fields, then the PNG)."""
    b = uuid.uuid4().hex
    fields = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML",
              "disable_notification": "true" if silent else "false"}
    parts = [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="photo"; filename="card.png"\r\n'
                 f'Content-Type: image/png\r\n\r\n'.encode() + png + f"\r\n--{b}--\r\n".encode())
    req = urllib.request.Request(f"{API}/bot{token}/sendPhoto", data=b"".join(parts),
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    post(token, "sendPhoto", req)


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


def btc(candles: list[tuple[int, float]]) -> dict | None:
    """The last 5-minute close and its change over 24 h, in %."""
    if not candles:
        return None
    last_ms, last = candles[-1]
    day_ago = next((c for a, c in reversed(candles) if a <= last_ms - 86_400_000), None)
    return {"price": last, "chg": (last / day_ago - 1) * 100 if day_ago else None}


def digest_text(states: dict, candles: list[tuple[int, float]], now: datetime, since: datetime) -> str:
    lines = [f"<b>Bitra Desk</b> · {e(server.t(now))} IST"]
    b = btc(candles)
    if b:
        chg = f" ({server.signed(b['chg'], '{:.2f}')}% 24 h)" if b["chg"] is not None else ""
        lines.append(f"BTCUSDT <b>{b['price']:,.1f}</b>{chg}")
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


def flags(states: dict) -> list[str]:
    """Short problems for the card's pill and the caption's first line."""
    out = []
    for n, s in states.items():
        if s.get("service") not in ("active", "unknown"):
            out.append(f"{n} {s.get('service')}")
        elif (s.get("last_cycle") or {}).get("outcome") in ("error", "incomplete"):
            out.append(f"{n} error")
    return out


def card_model(states: dict, candles: list[tuple[int, float]], now: datetime) -> dict:
    """What card.render() draws: plain numbers and short texts, nothing computed there."""
    ranks = ranked(states)
    rows = []
    for r in ranks:
        st, call = r["stance"], None
        if st:
            conf = server.num(st.get("confidence"))
            call = f"{server.ARROW.get(st['target'], '')} {st['target']}" + (f" {conf:.2f}" if conf is not None else "")
        rows.append({"name": r["name"], "slot": r["slot"], "ret": server.num(r["return_pct"]), "call": call,
                     "equity_txt": server.money(r["equity"]),
                     "record": f"{r['wins']}W {r['losses']}L" if r["closed"] else "–",
                     "would_trade": r["would_trade"], "asked": r["refused"] + r["would_trade"], "held": r["held"]})
    lead = ranks[0]
    series = []
    for i, (n, s) in enumerate(states.items()):
        pa = s.get("paper") or {}
        start = float(pa.get("start_equity") or 0)
        if not start:
            continue
        first = s.get("first_cycle")
        pts = [[server.ms(first), 0.0]] if first else []
        pts += [[int(a), (float(v) / start - 1) * 100] for a, v in pa.get("equity_curve") or []]
        pts.append([server.ms(now), (float(pa.get("equity") or start) / start - 1) * 100])
        series.append({"name": n, "slot": i + 1, "points": pts})
    local = now.astimezone(IST)
    hours = server.hourly_decisions([], now, hours=STRIP_HOURS)
    labels = []
    for i, h in enumerate(hours):
        lh = h["hour"].astimezone(IST)
        if lh.hour == 0:
            labels.append([i, f"{lh.day} {lh:%b}"])
        elif lh.hour % 6 == 0:
            labels.append([i, f"{lh.hour:02d}"])
    strip = {"labels": labels, "rows": [
        {"name": n, "slot": i + 1,
         "cells": [list(server.cell_kind(h["cycle"])) for h in server.hourly_decisions(s.get("recent") or [], now,
                                                                                       hours=STRIP_HOURS)]}
        for i, (n, s) in enumerate(states.items())]}
    return {"time": f"{local.day} {local:%b %H:%M} IST", "flags": flags(states), "btc": btc(candles),
            "now_ms": server.ms(now), "series": series, "rows": rows, "strip": strip,
            "leader": {"name": lead["name"], "slot": lead["slot"], "equity_txt": rows[0]["equity_txt"],
                       "ret": server.num(lead["return_pct"]) or 0.0,
                       "record": (f"{lead['closed']} trades, {lead['wins']}W {lead['losses']}L" if lead["closed"]
                                  else "no trades yet")},
            "note": "Paper money, no real orders · details in the caption"}


def tglen(h: str) -> int:
    """Telegram's length of an HTML message: the text without tags, in UTF-16 code units."""
    return len(html.unescape(re.sub(r"<[^>]+>", "", h)).encode("utf-16-le")) // 2


def card_caption(states: dict, model: dict, now: datetime, since: datetime, limit: int = 1024) -> str:
    """The card's caption, readable on its own; detail lines drop from the end until it fits."""
    lead, fl = model["leader"], model["flags"]
    l1 = ((f"⚠️ {e(' + '.join(fl))} · " if fl else "") + f"<b>{e(lead['name'])}</b> leads at "
          f"<b>{e(lead['equity_txt'])}</b> ({server.signed(lead['ret'], '{:.2f}')}%)" + ("" if fl else " ✅"))
    l2 = f"<i>Bitra Desk · paper money, no real orders · {now.astimezone(IST):%H:%M} IST</i>"
    ranks = ranked(states)
    bullets = [f"• <b>{e(r['name'])}</b> {call_line(r)}" for r in ranks]
    hours = max(1, round((now - since).total_seconds() / 3600))
    bullets.append(f"• Last {hours} h: " + " · ".join(activity(n, s, since) for n, s in states.items()))
    for n, s in states.items():
        cost = s.get("cost") or {}
        if cost.get("total_usd") is not None:
            bullets.append(f"• {e(n.capitalize())} API ≈ ${cost['total_usd']:,.2f} so far "
                           f"(${cost.get('today_usd') or 0:,.2f} today)")
    details = []
    for r in ranks:
        o = r["open"]
        if o:
            details.append(f"{e(r['name'])} holds a paper {e(o['side'])} from {o['entry']:,.1f} "
                           f"({server.usd(o.get('unrealized_usd'))})")
    for r in ranks:
        side = (f"its side {server.signed(r['side_model'])} vs reverse {server.signed(r['side_reverse'])} bps over "
                f"{e(r['side_n'])} decisions: {e(r['verdict'])}" if r["side_model"] is not None else "hindsight not computed yet")
        details.append(f"{e(r['name'])} ({e(r['model'])}): {side}")
    details.append("Each desk started with $1,000 of paper money on BTCUSDT; only the model differs.")
    tail = [f'<a href="{DASHBOARD_URL}">Dashboard</a> (with Tailscale on)']
    while True:
        quote = [f"<blockquote expandable>{chr(10).join(details)}</blockquote>"] if details else []
        text = "\n".join([l1, l2, ""] + bullets + quote + tail)
        if tglen(text) <= limit or not (details or len(bullets) > len(ranks)):
            return text if tglen(text) <= limit else "\n".join([l1, l2] + tail)
        if details:
            details.pop()
        else:
            bullets.pop()


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
            try:  # the card, with the text digest as the fallback (no Pillow, a drawing error, a refused photo)
                import card
                model = card_model(states, candles, now)
                send_photo(token, chat, card.render(model), card_caption(states, model, now, since), silent=quiet(now))
                print("digest card sent")
            except Exception as exc:  # noqa: BLE001 - whatever stopped the card, the text digest still goes out
                print(f"card not sent ({redact(f'{type(exc).__name__}: {exc}', token)[:200]}); sending the text digest")
                send(token, chat, digest_text(states, candles, now, since), silent=quiet(now))
            seen["last_digest_ms"] = server.ms(now)
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
