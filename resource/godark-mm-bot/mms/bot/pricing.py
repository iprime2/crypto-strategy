"""Vanilla quote math: reservation price, half-spread, tick rounding."""

from __future__ import annotations

import math


def round_to_tick(price: float, tick: float) -> float:
    if tick <= 0:
        return price
    steps = round(price / tick)
    return round(steps * tick, 10)


def half_spread_bps(configured_bps: float, maker_fee_bps: float) -> float:
    """Floor width at 2× maker fee + configured buffer."""
    floor = 2.0 * maker_fee_bps + max(configured_bps, 10.0)
    return floor


def reservation_price(fair: float, inventory: float, max_inventory: float, skew_bps: float) -> float:
    """Lean against inventory: long -> lower reservation, short -> higher."""
    if max_inventory <= 0:
        return fair
    ratio = max(-1.0, min(1.0, inventory / max_inventory))
    shift_bps = ratio * skew_bps
    return fair * (1.0 - shift_bps / 10_000.0)


def quote_prices(
    fair: float,
    inventory: float,
    *,
    max_inventory: float,
    half_spread_bps: float,
    inventory_skew_bps: float,
    tick_size: float,
) -> tuple[float, float, float]:
    """Return (reservation, bid, ask) post-only clamped below/above fair."""
    reservation = reservation_price(fair, inventory, max_inventory, inventory_skew_bps)
    half = reservation * (half_spread_bps / 10_000.0)
    bid = round_to_tick(reservation - half, tick_size)
    ask = round_to_tick(reservation + half, tick_size)

    # Post-only clamp: bid strictly below fair, ask strictly above fair.
    if bid >= fair:
        bid = round_to_tick(fair - tick_size, tick_size)
    if ask <= fair:
        ask = round_to_tick(fair + tick_size, tick_size)
    if bid <= 0 or ask <= bid:
        raise ValueError(f"invalid quotes fair={fair} bid={bid} ask={ask}")
    return reservation, bid, ask


def fair_jump_bps(old: float, new: float) -> float:
    if old <= 0 or new <= 0:
        return math.inf
    return abs(new - old) / old * 10_000.0
