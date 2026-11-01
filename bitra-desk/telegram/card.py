"""The bitra-desk digest as a Telegram card: a PNG drawn with Pillow in the look of the project's other Telegram
cards (a dark card 400 px wide: header and status pill, the leader's equity, BTCUSDT beside it, the desks' paper
equity since start, a table of the desks, a note), at 2.5x for a sharp photo. Drawn at twice that size and scaled
down, so lines and text are smooth. Input is a plain dict from notify.card_model(); output is PNG bytes.
Needs Pillow (apt python3-pil) and, for the intended look, the Inter font (apt fonts-inter); DejaVu otherwise.
"""
from __future__ import annotations

import io
import math
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, PAD = 400, 18           # card width and side padding, CSS px
OUT, SS = 2.5, 2           # output scale, and the supersampling on top of it
K = OUT * SS               # CSS px -> drawing px
IST = timezone(timedelta(hours=5, minutes=30))

BG, INK, SUB, MUT, DIM, NOTE = "#161b22", "#f0efec", "#c3c7ce", "#9aa1ab", "#8b919a", "#7d848e"
GRID, BASE, ROWLINE, DIVIDER = "#262c34", "#3d444e", "#232931", "#2a3038"
UP, DN, WARN, OK_TEXT = "#3ccf6a", "#ff7b72", "#fab219", "#5fe08a"
DESK = {1: "#3987e5", 2: "#d95926", 3: "#199e70"}  # the dashboard's dark-mode desk colors, in desk order

FONTS = {"regular": ("Inter-Regular.otf", "DejaVuSans.ttf"), "medium": ("Inter-Medium.otf", "DejaVuSans.ttf"),
         "semibold": ("Inter-SemiBold.otf", "DejaVuSans-Bold.ttf")}
FONT_DIRS = (Path("/usr/share/fonts/opentype/inter"), Path("/usr/share/fonts/truetype/dejavu"))


def blend(fg: str, alpha: float, bg: str = BG) -> tuple[int, int, int]:
    f, b = (int(fg[i:i + 2], 16) for i in (1, 3, 5)), [int(bg[i:i + 2], 16) for i in (1, 3, 5)]
    return tuple(round(c * alpha + b[j] * (1 - alpha)) for j, c in enumerate(f))


@lru_cache(maxsize=None)
def font(weight: str, size: float):
    for name in FONTS[weight]:
        for d in FONT_DIRS:
            if (d / name).exists():
                return ImageFont.truetype(str(d / name), round(size * K))
    return ImageFont.load_default(size=round(size * K))


def pct(v: float) -> str:
    s = f"{v:+.0f}%" if abs(v) >= 100 else f"{v:+.2f}%"
    return ("+" + s[1:] if float(s[:-1]) == 0 else s).replace("-", "−")


def tone(v: float | None) -> str:
    return MUT if v is None or round(v, 2) == 0 else (UP if v > 0 else DN)


class Card:
    def __init__(self, height: float):
        self.img = Image.new("RGB", (round(W * K), round(height * K)), BG)
        self.d = ImageDraw.Draw(self.img)

    def text(self, x, y, s, weight="regular", size=13.5, fill=INK, anchor="ls", spacing=0.0) -> float:
        """Draw at CSS (x, y), y the baseline by default; returns the width in CSS px."""
        f = font(weight, size)
        if not spacing:
            self.d.text((x * K, y * K), s, font=f, fill=fill, anchor=anchor)
            return f.getlength(s) / K
        width = sum(f.getlength(c) for c in s) / K + spacing * max(0, len(s) - 1)
        cx = x - (width if anchor[0] == "r" else 0)
        for c in s:  # letter-spaced, as the uppercase labels are
            self.d.text((cx * K, y * K), c, font=f, fill=fill, anchor="l" + anchor[1])
            cx += f.getlength(c) / K + spacing
        return width

    def width(self, s, weight="regular", size=13.5) -> float:
        return font(weight, size).getlength(s) / K

    def line(self, pts, fill, w=1.0):
        self.d.line([(x * K, y * K) for x, y in pts], fill=fill, width=max(1, round(w * K)), joint="curve")

    def dot(self, x, y, r, fill, ring=None, ring_w=2.0):
        rr = r + (ring_w if ring else 0)
        if ring:
            self.d.ellipse([(x - rr) * K, (y - rr) * K, (x + rr) * K, (y + rr) * K], fill=ring)
        self.d.ellipse([(x - r) * K, (y - r) * K, (x + r) * K, (y + r) * K], fill=fill)

    def pill(self, x_right, y_mid, s, ok: bool):
        size = 11.5
        tw = self.width(s, "semibold", size) + 13  # the dot and its gap
        h, x0 = 20, x_right - tw - 18
        self.d.rounded_rectangle([x0 * K, (y_mid - h / 2) * K, x_right * K, (y_mid + h / 2) * K], radius=h / 2 * K,
                                 fill=blend("#0ca30c", .2) if ok else blend(WARN, .18))
        col = OK_TEXT if ok else WARN
        self.dot(x0 + 13, y_mid, 3.2, col)
        self.text(x0 + 21, y_mid, s, "semibold", size, col, anchor="lm")

    def png(self) -> bytes:
        out = self.img.resize((round(self.img.width / SS), round(self.img.height / SS)), Image.LANCZOS)
        buf = io.BytesIO()
        out.save(buf, "PNG", optimize=True)
        return buf.getvalue()


def nice_step(lo: float, hi: float) -> float:
    """The smallest 1, 2, 2.5 or 5 times a power of ten that spans lo..hi in at most 4 steps."""
    mag = 10.0 ** math.floor(math.log10(max(hi - lo, 1e-6) / 4))
    for m in (1, 2, 2.5, 5, 10, 20):
        st = m * mag
        if math.ceil(hi / st - 1e-9) - math.floor(lo / st + 1e-9) <= 4:
            return st
    return 50 * mag


def chart(c: Card, series: list[dict], now_ms: int, top: float, left=PAD + 34, right=W - PAD - 66, height=112):
    """Each desk's paper equity as % since its start, as steps; labels at the line ends."""
    pts = [p for s in series for p in s["points"]]
    t0, t1 = min(p[0] for p in pts), max(now_ms, max(p[0] for p in pts))
    t1 += 1 if t1 == t0 else 0
    lo, hi = min(0.0, *(p[1] for p in pts)), max(0.0, *(p[1] for p in pts))
    st = nice_step(lo, hi)
    lo, hi = math.floor(lo / st - 1e-9) * st, math.ceil(hi / st + 1e-9) * st
    if hi == lo:
        hi = lo + st
    bottom = top + height - 20
    X = lambda t: left + (t - t0) / (t1 - t0) * (right - left)  # noqa: E731
    Y = lambda v: top + 4 + (hi - v) / (hi - lo) * (bottom - top - 4)  # noqa: E731
    for k in range(round(lo / st), round(hi / st) + 1):
        y, v = Y(k * st), k * st
        c.line([(left, y), (right + 4, y)], BASE if k == 0 else GRID, 1)
        lab = "0%" if k == 0 else f"{round(v, 2):+g}%".replace("-", "−")
        c.text(left - 6, y, lab, "regular", 11, DIM, anchor="rm")
    ends = []
    for s in series:
        col, p = DESK.get(s["slot"], INK), s["points"]
        path = [(X(p[0][0]), Y(p[0][1]))]
        for (ta, va), (tb, vb) in zip(p, p[1:]):
            path += [(X(tb), Y(va)), (X(tb), Y(vb))]
        if p[-1][0] < t1:
            path.append((X(t1), Y(p[-1][1])))
        c.line(path, col, 2.25)
        ends.append({"y": path[-1][1], "x": path[-1][0], "v": p[-1][1], "col": col, "name": s["name"]})
    for e in ends:
        c.dot(e["x"], e["y"], 3.6, e["col"], ring=BG)
    ends.sort(key=lambda e: e["y"])  # spread the end labels so they never overlap
    for i in range(1, len(ends)):
        ends[i]["ly"] = max(ends[i]["y"], ends[i - 1].get("ly", ends[i - 1]["y"]) + 14)
    ends[0]["ly"] = max(ends[0]["y"], top + 6)
    for i in range(1, len(ends)):
        ends[i]["ly"] = max(ends[i]["ly"], ends[i - 1]["ly"] + 14)
    shift = max(0.0, ends[-1]["ly"] - (bottom + 2))
    for e in ends:  # the desk's dot beside each label: two desks at the same value stay told apart
        c.dot(right + 14, e["ly"] - shift, 3, e["col"])
        c.text(right + 21, e["ly"] - shift, pct(e["v"]), "semibold", 12, INK, anchor="lm")
    day = lambda ms: f"{datetime.fromtimestamp(ms / 1000, IST).day} {datetime.fromtimestamp(ms / 1000, IST):%b}"  # noqa: E731
    c.text(left, top + height - 3, day(t0), "regular", 11, DIM)
    c.text(right, top + height - 3, day(t1), "regular", 11, DIM, anchor="rs")


def render(m: dict) -> bytes:
    """PNG bytes of the card for the model `m` (see notify.card_model)."""
    rows = m["rows"]
    height = 300 + 26 * len(rows) + 30
    c = Card(height)
    # header: the label and the status pill
    c.text(PAD, 27, f"BITRA DESK · {m['time']}".upper(), "semibold", 11.5, DIM, spacing=0.7)
    c.pill(W - PAD, 23, " + ".join(m["flags"]) if m["flags"] else "All running", not m["flags"])
    # hero: the leading desk's equity; BTCUSDT on the right
    lead = m["leader"]
    side_x = W - PAD - 108
    c.dot(PAD + 4, 54, 4, DESK.get(lead["slot"], INK))
    c.text(PAD + 13, 58, f"Leading · {lead['name']}", "regular", 12.5, MUT)
    big = 40 if len(lead["equity_txt"]) <= 9 else 32
    c.text(PAD, 100, lead["equity_txt"], "semibold", big, INK)
    w = c.text(PAD, 121, pct(lead["ret"]), "medium", 13.5, tone(lead["ret"]))
    c.text(PAD + w, 121, f" since start · {lead['record']}", "regular", 13.5, SUB)
    c.line([(side_x - 12, 48), (side_x - 12, 124)], DIVIDER, 1)
    btc = m.get("btc")
    c.text(W - PAD, 58, "BTCUSDT", "regular", 12.5, MUT, anchor="rs")
    if btc:
        c.text(W - PAD, 85, f"{btc['price']:,.1f}", "semibold", 21, INK, anchor="rs")
        if btc.get("chg") is not None:
            c.text(W - PAD, 105, pct(btc["chg"]), "medium", 13.5, tone(btc["chg"]), anchor="rs")
            c.text(W - PAD, 122, "last 24 h", "regular", 13.5, MUT, anchor="rs")
    else:
        c.text(W - PAD, 85, "–", "semibold", 21, MUT, anchor="rs")
    # chart header and legend
    c.text(PAD, 150, "Paper equity since start", "regular", 12.5, SUB)
    x = W - PAD
    for s in reversed(m["series"]):
        x -= c.width(s["name"], "regular", 11.5)
        c.text(x, 150, s["name"], "regular", 11.5, MUT)
        x -= 18
        c.line([(x, 146), (x + 12, 146)], DESK.get(s["slot"], INK), 3)
        x -= 8
    if any(len(s["points"]) for s in m["series"]):
        chart(c, [s for s in m["series"] if s["points"]], m["now_ms"], top=158)
    else:
        c.text(PAD, 200, "No paper account yet.", "regular", 13.5, MUT)
    # the desks, ranked
    eq_x, ret_x, wl_x = PAD + 142, PAD + 204, PAD + 250  # right edges; the call is right-aligned to the card
    cols = [(PAD, "DESK", "l"), (eq_x, "EQUITY", "r"), (ret_x, "RETURN", "r"), (wl_x, "W / L", "r"),
            (W - PAD, "LATEST CALL", "r")]
    y = 296
    for cx, label, al in cols:
        c.text(cx, y, label, "medium", 10.5, DIM, anchor=al + "s", spacing=0.5)
    for i, r in enumerate(rows):
        top = y + 7 + 26 * i
        c.line([(PAD, top), (W - PAD, top)], ROWLINE, 1)
        base = top + 18.5
        weight = "semibold" if i == 0 else "regular"
        c.dot(PAD + 4, base - 4.5, 4, DESK.get(r["slot"], INK))
        c.text(PAD + 13, base, r["name"], weight, 13.5, INK)
        c.text(eq_x, base, r["equity_txt"], weight, 13.5, INK, anchor="rs")
        c.text(ret_x, base, pct(r["ret"]) if r["ret"] is not None else "–", "regular", 13.5,
               tone(r["ret"]), anchor="rs")
        c.text(wl_x, base, r["record"], "regular", 13.5, SUB, anchor="rs")
        call = r["call"] or "–"
        c.text(W - PAD, base, call, "regular", 13.5, SUB if r["call"] else MUT, anchor="rs")
    c.text(PAD, y + 7 + 26 * len(rows) + 22, m["note"], "regular", 11.5, NOTE)
    return c.png()
