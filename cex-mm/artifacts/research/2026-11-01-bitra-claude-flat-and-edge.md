# bitra desks: why the Claude desk never trades, and what could make the desks money

Date: 1 Nov 2026, 17:30 UTC. Records copied from `bitra-desk` (`~/bitra/desk*/runs`, the paper accounts and
the candle cache); nothing on the VM was changed. Three sandbox desks on BTCUSDT 1h, identical but for the
model: Gemini flash-lite (since 28 Oct), Groq gpt-oss-120b and Claude Opus 5.5 (both since 31 Oct).

## 1. Why the Claude desk has not taken a trade

**It is not a fault.** Every one of Claude's 16 technical answers was `flat / no_setup` at confidence 0.60–0.62,
and bitra refuses a flat answer before pricing anything ("technical: flat, so there is nothing to price"). The
model answers; the desk works; the model declines. Four reasons, in order of weight:

1. **The prompt tells it to.** bitra's technical-analyst doctrine says: *"Flat with no_setup is the default,
   and it is the answer most of the time. You move off it only when the bars show the registered mechanism at
   work"*, and *"a trend setup needs a measured trend, so not in a ranging or mixed market"*. Claude follows
   this literally. Gemini does not (it named a trend setup in a mixed market 18 times and was refused by
   code each time); Groq mostly says flat at confidence 0.1–0.3.
2. **The market was "mixed" for most of its hours.** bitra's own regime detector labelled 12 of Claude's 17
   asked hours `mixed` and 5 `ranging` (Gemini's 71 hours: 34 mixed, 35 ranging, 2 trending). In a mixed
   regime bitra's `[regime]` gate refuses both trend setups and `range_reversion`, so the only admissible
   shapes are a breakout, an exhaustion or a volatility expansion, and Claude reported none on the screen
   (last-bar `volume_ratio` 0.09–0.37, no break). It was right about the gate: a short it declined would have
   been refused anyway.
3. **In the 5 `ranging` hours it weighed structure against the fade.** Each time (`variance_ratio` 0.78–0.96,
   z-score +0.93 to +1.19) Claude wrote that a `range_reversion` short "would run against the hourly uptrend
   of higher highs and higher lows" and that the stretch was "only modest". The doctrine invites exactly that
   weighing ("a short-timeframe setup against a higher timeframe's trend is yours to weigh"). Gemini named the
   same short at confidence 0.50–0.55 and was refused on confidence; Groq named it at 0.60–0.68 and got two
   intents (the open paper short from 17:35 IST, −$1.04 at the last look).
4. **It anchors on its own last answer.** The brief carries `previous` (the model's last target, setup,
   confidence and the move since). Claude's reasons end "with nothing changed materially since the last flat
   reading, flat stands"; Gemini, fed its previous short, repeated the same short with the same levels for ten
   hours. There is no switch for this in bitra 0.10.2 (`cycle.py` always attaches `previous` within the
   lookback window). Whatever a desk says first, it tends to keep saying.

Two side effects worth knowing:

- **Hindsight cannot score Claude.** `tra hindsight` replays directional calls against their reverse; flat
  answers carry no side, so Claude's "model side vs reverse" will stay "not computed" however long it runs.
  On 17 Nov it can only be judged on what it avoided: its equity against the trades the others took in the
  same hours.
- **Its macro analyst cites a null.** Three cycles show "macro_analyst: discarded a citation,
  series.us10y.correlation_measured.value was null". Harmless (the operator's declared state decides, not the
  model's sentence) but noise in the record.

Cost: 49 calls, 139k input / 33k output tokens, about **$1.22** at list price in 2.5 days (≈ $0.50/day).

## 2. What the records say about edge so far (5 days, one desk with trades)

Gemini is the only desk with a hindsight sample. `tra hindsight`, 5 days, 7 independent decisions:

| Group | Decisions | Mean net | Won |
|---|---|---|---|
| Admitted (would-be trades) | 10 | +93.9 bps | 80% |
| Refused by `regime` | 17 | +22.0 bps | 47% |
| Refused by `technical` (confidence < 0.6) | 14 | −64.0 bps | 14% |
| Refused by `exit` (reward/risk, break-even) | 12 | −77.8 bps | 33% |
| All refused | 43 | −33.9 bps | 33% |
| **Model's side vs exact reverse** | 50 | **−9.8 vs −11.1 bps** | "no clear difference yet" |

Read together: Gemini's directional calls, taken as a whole, have **no edge over their reverse** (both sides
lose about the round trip). What made the paper account +1.18% is the **gates**: the confidence and exit
gates threw out calls that would have lost 64–78 bps each, and every admitted trade was a short during a
fall from 81k to 76k. That is consistent with the outside evidence below, and it is the main lesson of the
experiment so far: the money is in the refusals, not in the calls.

## 3. The hurdle: cost against the size of the moves

From the 94 h of Bybit 5-minute closes in the paper cache (28 Oct–1 Nov):

| Horizon | Median \|move\| | Share > 30 bps (2× the round trip) |
|---|---|---|
| 1 h | 15.5 bps | 33% |
| 4 h | 29.0 bps | 47% |
| 12 h (the hold limit) | 59.9 bps | 82% |
| 24 h | 100.4 bps | 87% |

The desk pays a measured **15.02 bps** round trip (taker both ways) and bitra demands a claimed edge of 2×
that. On 1h bars the typical move inside the mechanism's "few hours" is about the cost itself; only a 12 h
hold clears it most of the time. Switching the channel to `bybit/maker-taker` (post-only entry, 2.0 + 5.5
bps fees) prices the round trip at about 12.5 bps estimated instead of 15.0 measured: worth having, but a
17% cut, not a different game, and a resting entry does not always fill.

## 4. What the outside evidence says (Nov 2026)

arxiv.org and protos.com do not resolve from the cloud session, so the figures below come from the papers'
abstracts and press summaries as returned by web search, not from the full texts: each is `[UNVERIFIED]`
until someone opens the source.

- **Production fleets:** a six-month record of two LLM trading fleets (DX Terminal, 3,505 vaults; a
  Hyperliquid fleet of 500–599 agents) found decision quality *statistically indistinguishable across model
  families* at that horizon, a 41% round-trip win rate against retail's 50%, volatility-blind sizing, and
  that 43% of positions saw +300 bps of favourable excursion yet half of those closed negative; a mechanical
  stop/take bracket recovered about +39 bps per position. The operating layer (constraints, order path)
  mattered more than the strategy text. `[UNVERIFIED]` ([arXiv 2609.05663](https://arxiv.org/abs/2609.05663), summary via
  [DXRG](https://www.dxrg.ai/blogs/continuous-record-paper))
- **Alpha Arena:** season 1 (crypto on Hyperliquid) four of six models lost; Qwen3 Max won at +22% with a 30%
  win rate over 43 trades `[UNVERIFIED]` ([Protos](https://protos.com/llm-crypto-trading-contest-finds-llms-cant-trade-crypto/),
  [Datawallet](https://www.datawallet.com/crypto/alpha-arena-nof1-ai-explained)); season 1.5 (US stocks) only
  Grok 4.2 stayed profitable ([Forklog](https://forklog.com/en/ai-model-grok-4-2-triumphs-in-trading-tournament/)).
  No season 2 results are published.
- **Cost viability:** LLM spend and trading friction have to be read together; most agents fail on
  over-trading and fees rather than on bad ideas `[UNVERIFIED]` ([arXiv 2607.10286](https://arxiv.org/html/2607.10286v1)).
- **Ensembles:** majority voting only helps when the members' errors are not strongly correlated
  ([arXiv 2602.08003](https://arxiv.org/pdf/2602.08003)); the one trading paper with direct evidence weights
  agents by agreement rather than a plain vote and reports lower drawdowns, self-reported
  ([TrustTrade, arXiv 2603.22567](https://arxiv.org/html/2603.22567v1)). Our three desks disagreed in 2 of the
  4 hours all three were asked (long / short / flat), so their errors look independent enough for this to be
  worth measuring.
- **Funding and open interest as signals:** industry reports only (K33's "negative 30-day funding precedes
  strong 90-day returns" `[UNVERIFIED]`, [The Block](https://www.theblock.co/post/315831/perp-signal-bitcoin-bottom-bullish-year-end-k33)),
  no out-of-sample study found; the technical brief already carries both figures.

Net: nothing published shows an LLM making directional hourly calls in crypto with an edge after fees. What
does show up, repeatedly, is that exits, sizing, cost and trade frequency decide the outcome, which is the
part of bitra that is code, not the model.

## 5. What would move the desks toward making money, ranked

Do not change the three running desks before the 17 Nov comparison: a changed setting splits what
`tra hindsight` measures into two populations (bitra-desk/README.md). Everything below is either a
measurement on the existing records or a new, separate desk.

1. **Measure a consensus account now, at zero model cost.** From the records, a fourth paper line that takes
   a trade only when at least two desks' latest calls agree on a direction and that desk's intent passed its
   gates. It uses data already on disk; it tests the one ensemble claim with evidence behind it.
2. **Score Claude's flats.** For every hour Claude said flat, what did the others' admitted trades return?
   If their trades lose, Claude's silence was the right call and the comparison should say so; if they win,
   Claude is leaving the gates' money on the table. Also from the records; goes on the dashboard beside
   hindsight.
3. **A v2 desk on the model that wins on 17 Nov, with three changes at once**, measured against v1 for two
   more weeks: (a) 4h decision bars, 1d and 1w context, 12-bar hold (48 h: median move 100 bps against a
   15 bps cost); (b) `venue_key = "bybit/maker-taker"` (post-only entries); (c) the model blind to its
   previous answer, which needs a small bitra patch or a strip in our provider plugin, since 0.10.2 has no
   switch. Fewer, larger, cheaper decisions is what every piece of evidence above points to.
4. **Keep the gates; tune them only on hindsight with ≥ 10 decisions a side.** On 5 days the confidence and
   exit gates are earning their keep (−64 and −78 bps per refused call) and the regime gate is costing a
   little (+22 bps per refusal); that is too few decisions to touch either. The one gate worth a look later is
   `min_reward_to_risk = 1.5`, which refused Groq's 1.19× and 1.01× targets: with bitra's `exit.mode =
   "volatility"` the stop and target are measured by code rather than named by the model.
5. **Not yet:** more instruments through the screener (alts cost more to trade than BTC), a derivatives
   analyst on funding/OI (no out-of-sample evidence), or paid frontier models on the same 1h setup (the
   production study found model families indistinguishable at this horizon).

## 6. The honest framing

The ADA market maker in this repo makes money by earning the spread, thousands of times, with the venue's
own fees as the hurdle. The bitra desks try to earn 30+ bps a call by being right about direction, against
15 bps of cost, with models the evidence rates as no better than a coin at this horizon. The desks are worth
running for what they teach about gating, costs and record-keeping; a prop-firm plan should rest on the
gates and the measurement, not on the model's calls.
