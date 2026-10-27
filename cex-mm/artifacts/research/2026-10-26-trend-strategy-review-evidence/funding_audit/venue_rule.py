#!/usr/bin/env python3
"""Offline: which FUNDING candle does Delta's ledger charge at an exchange? For each funding entry of the live ADAUSD
market maker (venue_funding_ada.json: the wallet ledger's funding rows, and the bot's last logged inventory and mark
before the exchange), compare the booked amount with -inventory x mark x rate / 100 for the candle stamped at the
exchange (the block it starts) and for the candle just before it (the block it ends). ADAUSD contract = 1 ADA.
Run from this folder: python3 venue_rule.py"""
import datetime as dt
import json

UTC = dt.timezone.utc
dump = json.load(open("candles_2026-10-26T1835Z.json"))
ada = {int(t): v for t, v in dump["candles"]["ADA"].items()}
n = {"start": 0, "end": 0}
print(f"{'exchange':<13}{'inventory':>10}{'mark':>11}{'booked $':>11}{'starts $':>11}{'ends $':>11}  closer")
for x in json.load(open("venue_funding_ada.json")):
    E = x["exchange"]
    if x["inventory"] is None:
        print(f"{dt.datetime.fromtimestamp(E, UTC):%m-%d %H:%M}    no live-bot log at that time")
        continue
    a = -x["inventory"] * x["mark"] * ada[E] / 100
    b = -x["inventory"] * x["mark"] * ada[E - 3600] / 100
    k = "start" if abs(a - x["amount_usd"]) < abs(b - x["amount_usd"]) else "end"
    n[k] += 1
    print(f"{dt.datetime.fromtimestamp(E, UTC):%m-%d %H:%M}  {x['inventory']:>10.0f}{x['mark']:>11.6f}{x['amount_usd']:>11.6f}{a:>11.6f}{b:>11.6f}  "
          f"{k} (rel err starts {abs(a / x['amount_usd'] - 1):.1%}, ends {abs(b / x['amount_usd'] - 1):.1%})")
print(f"the candle stamped at the exchange is closer on {n['start']}, the one before it on {n['end']}")
