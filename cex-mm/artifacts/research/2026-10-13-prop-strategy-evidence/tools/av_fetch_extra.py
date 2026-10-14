#!/usr/bin/env python3
"""Adversarial check: download daily klines + funding for the OTHER Binance USDT-M perps that existed by Feb 2020
(survivorship test of the 9-coin universe). Uses the repo loader read-only with tb.COINS patched; writes only to av_cache/."""
import sys, datetime as dt
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts")
import trend_backtest as tb
EXTRA = "EOS TRX ETC XLM XMR DASH ZEC XTZ ATOM ONT IOTA BAT VET NEO QTUM IOST".split()
tb.COINS = EXTRA
close, fund = tb.load_binance(sys.argv[1], dt.date(2026, 9, 30))
for c in EXTRA:
    ds = sorted(close.get(c, {}))
    print(c, len(ds), ds[0] if ds else None, ds[-1] if ds else None, "funding days", len(fund.get(c, {})))
