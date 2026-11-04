# bitra desks, one-week review: keep running or shut down

Date: 4 Nov 2026, 09:00 IST. Records copied from `bitra-desk` (three desks' `runs/`, the four paper accounts,
the consensus file); nothing on the VM was changed. Baseline and method: `2026-11-01-bitra-claude-flat-and-edge.md`.

## Verdict

The one-hour desks have answered the question they were built to answer, and the answer is no: none of the
three models' directional calls on BTCUSDT 1h beat their exact reverse after costs, and the only money on the
board came from the code gates during a week in which BTC fell 5.5%. Running the same three desks to 17 Nov
will add sample, not change the conclusion. The experiment is worth ending as it stands; what is worth keeping
is the machinery (gates, replay, records, dashboard, Telegram) and, if the owner wants to keep learning, one
redesigned desk on the terms the evidence points to.

## The numbers (28 Oct 11:38 UTC to 4 Nov 03:30 UTC)

BTCUSDT went from 80,980 to 76,487 (−5.55%), low 75,673, high 81,967. A market that paid shorts.

| | Gemini flash-lite | Groq gpt-oss-120b | Claude Opus 5.5 | Consensus (2 of 3) |
|---|---|---|---|---|
| Running since | 28 Oct (7 d) | 31 Oct (4 d) | 31 Oct (4 d) | derived, 1 Nov |
| Paper equity (from $1,000) | **$1,014.59 (+1.46%)** | $991.89 (−0.81%) | $1,000.00 | $998.46 (−0.15%) |
| Closed trades | 6: 4 W, 2 L | 3: 0 W, 3 L | 0 | 4: 1 W, 3 L |
| Cycles: held / asked | 56 / 118 | 36 / 66 | 42 / 53 | 132 hours, 20 with all three |
| Would-be trades (passed gates) | 16 | 5 | 0 | 7 taken of 24 agreed hours |
| Technical answers | 105: 80 short, 19 long, 6 flat | 66: 21 short, 23 long, 22 flat | 52: 4 short, 8 long, 40 flat | |
| Every directional call replayed (12 h hold, 15 bps cost) | 97: **−13.8 bps** mean, 36% won | 43: **−16.5 bps**, 26% won | 10: **−51.2 bps**, 20% won | |
| `tra hindsight`: model side vs reverse | −11.3 vs −12.1 bps over 90 (7 d, 12 independent): **no clear difference** | −3.3 vs −21.2 over 38: too few | −27.6 vs +23.0 over 10: too few | |
| Errors (model did not answer) | 15 of 176 cycles (Google 503) | 0 | 1 | |
| Model cost | free tier | free tier | $3.88 (≈ $0.90/day) | none |

Every directional call, taken before any gate: all three models lose on average. The "replayed" row is the
model alone; the paper row is the model after the gates.

## Where Gemini's +1.46% came from

- **The market.** 80 of its 105 answers were short, in a week BTC fell 5.5%. A static short of its own
  usual size (0.005 BTC, about $400 notional) held for the whole week would have made about **+$22**, before
  funding; the desk made +$14.59 with six trades. The market, not the calls, made the money.
- **The gates.** Hindsight by gate (Gemini, 7 days): the confidence gate refused 23 calls that averaged
  −61 bps; the exit gate refused 19 at −41 bps; the regime gate refused 32 at +19.6 bps (it is the one gate
  that costs a little). The 14 admitted decisions averaged +46.5 bps and won 57%. The refusals are the edge.
- **Against its reverse.** Over 90 decisions the model's side lost 11.3 bps per decision and the exact
  reverse lost 12.1: a coin, with fees on both faces. This is the test the experiment was built around, and
  it has its answer with the minimum sample bitra asks for (10 a side, 5 days) already passed.

## Groq and Claude

- **Groq** names a direction two hours in three and has the lowest confidence of the three. Its five
  admitted trades all stopped out (−46 bps a decision); the calls its gates refused did better than the ones
  they let through. No edge, and no reason to expect one from more days.
- **Claude** stayed flat for 40 of 52 answers. Since 1 Nov it has started naming directions, at confidence
  0.33–0.46, below the 0.6 floor, so still no trade. Its ten directional calls, replayed, would have lost
  51 bps each: its silence was the better half of its output. The flat score says the other desks' five trades
  in its flat hours made +6.9 bps on average (+$5.39 in all): Claude's caution cost about five dollars of
  paper money in four days, which is nothing either way. It has cost $3.88 of the API credit.

## Consensus

Twenty hours had all three desks asked; in 24 hours at least two agreed on a direction; the account took 7
of them and closed 4: one win, three stops, −0.15%. Agreement between models that are each no better than a
coin is not a signal, and the first week says so.

## Reliability

The VM has run without a restart since 31 Oct: 623 MB free, swap in light use, 13 GB of disk free. The
Telegram bot sent 36 digest cards in three days (one fell back to text on a Telegram timeout) and ten alerts.
Gemini's free tier failed 15 cycles in 176 (8.5%) with Google's 503 "high demand"; Groq failed none.

## Keep running or shut down

Keeping the three desks to 17 Nov costs about $6 of VM and $12 of API credit: cost is not the issue. The
issue is that the 1h design has been measured and found wanting on every line above, and 13 more days of it
teach nothing new. Two honest paths:

1. **Shut the experiment down now.** Stop the three desks, the timers and the dashboard, copy the records off
   the VM, and stop the instance (the VM costs $14/month running, about $2/month stopped). The Telegram
   digests stop with it. Cancel the 17 Nov check-in. Everything is in the repo to bring it back in an hour.
2. **Replace it with one v2 desk** on the terms the memo of 1 Nov set out: Groq (free, no failures in four
   days), 4h decision bars with a 48 h hold (median move 100 bps against a 15 bps cost), `bybit/maker-taker`
   entries, and the model blind to its previous answer. Fewer, larger, cheaper decisions, and two to three
   weeks to a hindsight verdict. Same VM, no API cost.

Recommendation: **1 if the aim was to learn what an LLM desk does, which is now known; 2 if the aim is to keep
learning on the one design that has not yet been tried.** Running the current three desks any longer is the
one option with nothing to recommend it. Claude should stop in either case: it decides flat, its directional
calls are the worst of the three, and it is the only desk that costs anything.
