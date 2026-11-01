# bitra-desk: a sandbox desk for learning AI trading agents

A learning experiment with [bitra](https://github.com/BijectiveLabs/bitra) (`pip install bitra`, CLI `tra`):
language-model analysts read live market figures and propose trades; code prices, sizes and refuses them.
It runs in **sandbox mode**: live public data, real model calls, every decision written down, **no
orders and no exchange keys**. Why it is not a trading engine for us:
`cex-mm/artifacts/research/2026-10-27-bitra-repo-review.md`.

The question it answers after 2–4 weeks: did the model's calls beat their exact reverse after costs
(`tra hindsight`)? Only if they did is anything further (a venue's demo, a prop firm) worth discussing.

## Rules

- Sandbox only. The service pins `--mode sandbox`; no exchange key goes in `.env`.
- No Delta keys, no live-bot code and no repo deploy key on this VM. It runs third-party packages.
- Tailscale tag `tag:bitra` is never a source in the tailnet policy, so the VM cannot reach
  `dism-tokyo` or the laptop. The policy's `tests` block enforces that on every save.
- Keys go into `~/bitra/desk/.env` on the VM by the owner, never through a chat.

## The VM

| | |
|---|---|
| Instance | `bitra-desk`, `i-08484437b21ad1b89`, `ap-south-1` (Mumbai), created by hand in the console |
| Type | `t4g.small` (arm64, 2 vCPU, 2 GiB, plus a 2 GiB swap file for three desks), Ubuntu 24.04, 20 GiB gp3, credit specification Standard |
| Address | Elastic IP `15.207.39.80`; security group `bitra-desk-sg`, SSH from the owner's home IP only |
| Tailnet | `bitra-desk`, `tag:bitra`, Tailscale SSH on (user `ubuntu`) |
| Cost | about $14/month (instance $8, disk $2, public IPv4 $3.65). Stop it in the console when paused. The Claude desk's model calls come out of the owner's Claude plan's monthly API credit |

Mumbai, not Tokyo: Bybit has been withdrawing from Japan since January 2026; from `ap-south-1` Bybit,
Binance, OKX, Delta India and Gemini all answered (28 Oct 2026).

## Access

```bash
ssh ubuntu@bitra-desk                       # laptop on the tailnet (check mode: approve in the browser once)
ssh -i ~/.ssh/bitra-desk-key.pem ubuntu@15.207.39.80   # laptop, direct, from the home IP
tools/tailnet_up.sh                         # a Claude cloud session: joins the tailnet as tag:claude
ssh -F /tmp/tailnet/ssh_config bitra-desk   # then this
```

## The desk (`desk/`)

| Setting | Value |
|---|---|
| Instrument, data | BTCUSDT on Bybit public endpoints (candles, book, funding, open interest) |
| Decision | one cycle per closed 1h bar; context from the 4h and 1d bars; a position closes after 12 bars |
| Trigger | the model is asked only after a 15 bps move since the last look, at most once an hour |
| Model | Gemini `gemini-3.1-flash-lite` for every role since 30 Oct 2026 (it already gave 74 of 78 answers as the fallback), falling back to `gemini-2.5-flash` and `gemini-flash-latest` |
| Analysts and weights | technical 2.0 (decides), sentiment 1.0, macro 1.0 (read only, move conviction) |
| Sentiment | Crypto Fear & Greed (alternative.me, daily, no key): bullish above 71, bearish below 50, the 25th/75th percentiles of its last 90 days, read as momentum |
| Macro | FRED (`FRED_API_KEY`): US 10-year yield `DGS10`, bearish above 4.65 and bullish below 4.18; broad dollar `DTWEXBGS`, bearish above 120.7 and bullish below 118.7 (each the 25th/75th percentiles of its last year). The dollar is released weekly, so its `max_age` is 12 days |
| Cost model | Bybit taker 5.5 bps a side, measured round trip 15.02 bps; refused unless the claimed edge is 2x the round trip |
| Risk | 50 bps of $1,000 equity at the stop ($5), size cut to fit; no new entry after a 3% day or a 10% drawdown. $1,000 since 31 Oct 2026 (was $10,000), the size of a first real account |

The desk was made with `tra init desk --profile autonomous --agent google`, then changed to 1h bars,
4h/1d context, a 12-bar hold, a 1h cooldown, the two series above and their conviction weights.
Changing a setting mid-experiment splits what `tra hindsight` measures into two populations: freeze
the config once the first days are in.

## Three desks: the model is the only difference

| Desk | Service | Model (fallback) | Since |
|---|---|---|---|
| `~/bitra/desk` | `bitra-desk` | Gemini `gemini-3.1-flash-lite` (`gemini-2.5-flash`, `gemini-flash-latest`), free tier | 28 Oct 2026 |
| `~/bitra/desk-groq` | `bitra-desk-groq` | Groq `openai/gpt-oss-120b` (`openai/gpt-oss-20b`), free tier | 31 Oct 2026 |
| `~/bitra/desk-claude` | `bitra-desk-claude` | Claude `claude-opus-5-5` (`claude-sonnet-5-5`), bitra's own default model, at its default effort (high), through the `claude` provider below | 31 Oct 2026 |

`setup.sh` builds the second and third from `desk/` and changes only the three `[agents]` lines
(`provider`, `model`, `fallback`), so market, data, series, rules and costs stay identical and any
difference in results is the model's. Their `.env` is a link to `~/bitra/desk/.env`, so every desk reads
one key file. Each desk has its own records, `tra hindsight` and paper account (`~/bitra/paper`,
`~/bitra/paper-groq`, `~/bitra/paper-claude`); the dashboard sets them side by side under **Model
comparison** and shows any one in full (`?desk=gemini`, `?desk=groq`, `?desk=claude`). On its first forced
cycle Groq answered all three roles in 4.9 s, against 40–180 s for Gemini's free tier.

bitra 0.10.2's bundled `anthropic` provider cannot run the technical analyst: that role's answer schema
puts `minimum`/`maximum` on numbers, which the Claude API refuses with a 400, so the desk's first cycle
(31 Oct 2026, 08:55 UTC) stopped there. `claude-provider/` is a bitra plugin, registered through
its provider entry point, that adds a provider named `claude`: the bundled adapter with each numeric bound
moved into its field's description (bitra still checks the bounds when it reads the answer). `setup.sh`
installs it beside bitra. Tests: `python3 -m venv /tmp/bv && /tmp/bv/bin/pip install ./bitra-desk/claude-provider
&& /tmp/bv/bin/python -m unittest discover -s bitra-desk/claude-provider -p 'test_*.py'`.

The Claude desk is the only one that costs money: Opus 5.5 is $4 / $20 per million input / output tokens,
and at high effort it also spends output tokens thinking. Its first cycle that asked all three
roles (31 Oct 2026) used about 8,400 input and 1,700 output tokens, about $0.07, so even a model call every
hour stays near $50 a month. Its key lives in its own Claude Console
workspace with a monthly spend limit, auto-reload is off and no credits are bought, so it draws only on
the plan's monthly API credit and stops, rather than charging anything, when that runs out. The dashboard's
**Model use** table shows its tokens by day.

## Set up or redeploy

From a checkout, copy this folder to the VM and run the script. It adds a 2 GiB swap file if the host
has none, installs uv and bitra (pinned, `BITRA_VERSION`, with the google, openai and anthropic clients),
writes `desk/` over `~/bitra/desk` and its Groq and Claude copies over `~/bitra/desk-groq` and
`~/bitra/desk-claude` (never `.env`, `runs/` or fetched series), and installs the user services. It starts
each desk only once its key is set (`GEMINI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`), and restarts
the running ones, each of which then runs a cycle at once.

```bash
tar -C bitra-desk -c . | ssh -F "${TAILNET_DIR:-/tmp/tailnet}/ssh_config" bitra-desk \
  'rm -rf ~/bitra/repo && mkdir -p ~/bitra/repo && tar -C ~/bitra/repo -x && bash ~/bitra/repo/setup.sh'
```

Keys (owner, on the VM): `nano ~/bitra/desk/.env`, see `desk/.env.example`. Then
`cd ~/bitra/desk && tra keys --probe` shows each key as a fingerprint, never its value.

## Dashboard

**https://bitra-desk.taildea8d9.ts.net/**: tailnet only (open it with Tailscale on), read-only. From the top:

- **Model comparison**: one card per desk, ranked by paper equity: return, closed trades won and lost,
  would-be trades, its latest call and how old it is, its side against the exact reverse (`tra hindsight`),
  and its model calls today with the estimated spend (Claude at list price; Gemini and Groq are free tiers).
- **Paper equity**: every desk's paper account on one chart, stepping at each closed trade.
- **BTCUSDT and the paper trades**: the last 96 h of Bybit 5-minute closes with each desk's paper trades on
  it (▲ long or ▼ short at the entry, ● at the exit, in the desk's color).
- **Hour by hour**: the last 48 hours as one row of squares per desk, so the same hour can be compared
  across models: a would-be trade, a call the desk's rules refused, flat, held (too quiet to ask) or an error.
  Hover or tap a square for what the model said and why.
- **The selected desk** (`?desk=gemini`, `groq`, `claude`, or its card or tab): the paper account with its open
  position and closed trades, what each analyst says now, hindsight, and folded sections for every
  would-be trade, the recent cycles, the data series and model use by day.

The charts are drawn in the browser from data embedded in the page (no library, nothing fetched from
elsewhere), with a tooltip on hover or tap. The page refreshes itself every minute while it is open, keeping
the scroll position and the open sections. The selected desk's state as JSON is at `/api/state.json`.

`dashboard/server.py` (stdlib only) runs as `bitra-dashboard.service` on 127.0.0.1:8790, and
`sudo tailscale serve --bg 8790` publishes it; both are set up by `setup.sh`. `bitra-hindsight.timer`
runs `tra hindsight` at half past each hour so the hindsight section stays current. Tests:
`python3 -m unittest discover -s bitra-desk/dashboard -p 'test_*.py'`.

## Paper account

The sandbox desk writes an intent whenever every gate passes, even while an earlier one would still be open,
so its record overstates how many trades a real account takes. `paper/paper.py` replays the intents the way
venue mode trades them: one position at a time (an intent while one is open is skipped), entry at the open of
the first 5-minute bar after the decision, the intent's own size, stop and take, out at either or after the
12 h hold limit (a bar that reaches both counts as the stop), net of the round trip the intent priced, on
$1,000 of practice equity, the size a first real account would be. Each trade's size is the smaller of the
intent's and what keeps the loss at the stop, round trip included, within the desk's
`max_risk_per_trade_bps` (50, so $5 on $1,000) of the account's equity at entry, rounded down to
`size_step` (0.001 BTC); a trade that rounds to nothing is skipped and says so. This also resizes the
intents recorded before the desk's equity went from $10,000 to $1,000. It replays from the desk's first
intent each run, so the result is deterministic.
The only network call is Bybit's public kline endpoint, cached in `~/bitra/paper/candles.jsonl`; the result is
`~/bitra/paper/state.json`, which the dashboard shows. `bitra-paper.timer` runs it every 15 minutes (:05, :20,
:35, :50). Tests: `python3 -m unittest discover -s bitra-desk/paper -p 'test_*.py'`.

Limits: 5-minute bars, so a stop and take touched inside one bar count as the stop; fills at the bar's open and
at the exact stop or take price, with slippage only as the intent's priced estimate; no funding.

## Operate

```bash
systemctl --user status bitra-desk bitra-desk-groq bitra-desk-claude bitra-dashboard bitra-hindsight.timer bitra-paper.timer
journalctl --user -u bitra-desk -n 80          # each hour's cycle; -f to follow
cd ~/bitra/desk && tra watch --every 5s        # read-only view of the records
tra sources show                               # every series, its age, stale or not
tra pause  /  tra pause --off                  # hold new decisions without stopping the service
systemctl --user disable --now bitra-desk     # stop for good
```

A cycle by hand (`tra run --now`) only while the service is stopped. A restart runs a cycle at once.

## Results

```bash
cd ~/bitra/desk
tra hindsight        # each gate's refusals vs admissions; the model's side vs its reverse, resampled by day
tra runs verify      # every cycle's files against their hashes
wc -l runs/cycles/usage.jsonl                  # model calls made
```

`tra hindsight` calls no winner with fewer than 10 decisions on a side or fewer than 5 days. Records:
`runs/cycles/<id>/` (snapshot, briefs, answers, intent, `cycle.json`), `runs/cycles/usage.jsonl`,
`runs/cycles/scheduler.jsonl`.
