#!/usr/bin/env python3
"""Adversarial: Delta funding vs Binance funding as the cost input, design rule on Delta closes 2024-08-10..2026-10-12."""
import sys, datetime as dt
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts"); sys.path.insert(0, "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/tools")
import trend_backtest as tb
import av_universe as U   # reuses weekly() (its module-level run uses trend-cache: 9 coins)
