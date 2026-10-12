# DISM host on AWS (Tokyo)

Delta Exchange's servers are in AWS Tokyo, so the shadow test and the live pilot run on a Tokyo VM
instead of the home WSL machine (which loses its network and its clock drifts).

## Create or remove the host

```bash
aws cloudformation deploy --region ap-northeast-1 --stack-name dism-tokyo \
  --template-file infra/aws/dism-tokyo.yaml \
  --parameter-overrides SshCidr=<your-ip>/32 "PublicKey=$(cat ~/.ssh/dism-tokyo.pub)"
aws cloudformation describe-stacks --region ap-northeast-1 --stack-name dism-tokyo --query 'Stacks[0].Outputs'
aws cloudformation delete-stack --region ap-northeast-1 --stack-name dism-tokyo   # removes VM, disk and Elastic IP
```

- `t4g.small` (arm64, 2 vCPU, 2 GiB), Ubuntu 24.04, 30 GB encrypted gp3, Elastic IP (whitelist it on the
  Delta API key), IMDSv2 only, SSH only from `SshCidr`.
- About $22.6 a month in Tokyo (instance $16.06, public IPv4 $3.65, disk about $3).
- Home IP changed: re-run the deploy command with the new `SshCidr`.

## Set up the shadow test

On the VM, with a read-only deploy key for this repo:

```bash
git clone git@github.com:iprime2/crypto-strategy.git ~/crypto-strategy
~/crypto-strategy/cex-mm/infra/vm/setup.sh
```

`setup.sh` adds 2 GB swap, installs the toolchain and Rust, builds `mm-bot`, and installs the user services in
`infra/systemd/` (lingering, so they start at boot):

| Unit | What |
|---|---|
| `cex-mm-shadow.service` | `scripts/shadow.sh start $SHADOW_SYMBOLS` with `config/dism.env` |
| `cex-mm-shadow-dashboard.service` | dashboard on 127.0.0.1:8788 |
| `cex-mm-shadow-watchdog.timer` | every 2 min, restarts the test if the dry-run or recorder died |
| `cex-mm-trend-paper.timer` | hourly `scripts/trend_paper.py`: rebalances the trend paper book once per UTC day (00:05 UTC) |
| `cex-mm-shadow-housekeep.timer` | daily 03:30 UTC `scripts/shadow_housekeep.py --apply`: deletes shadow runs older than 14 days. Installed but **not enabled** by `setup.sh` (see [Housekeeping](#housekeeping)) |
| `cex-mm-oems.service` | the OEMS on 127.0.0.1:8791. Installed but **not enabled** by `setup.sh` (see [OEMS (optional)](#oems-optional)) |

## Operate

```bash
ssh -i ~/.ssh/dism-tokyo ubuntu@<elastic-ip>
cd ~/crypto-strategy/cex-mm && scripts/shadow.sh status
python3 scripts/delta_key_check.py       # read-only: mainnet key in quote-bot/.env works, ADAUSD leverage <= 5x
systemctl --user stop cex-mm-shadow      # stop for good (the watchdog leaves a stopped test alone)
systemctl --user restart cex-mm-shadow   # new run, e.g. after `git pull` (it rebuilds first)
ssh -i ~/.ssh/dism-tokyo -N -L 8788:127.0.0.1:8788 ubuntu@<elastic-ip>   # dashboard at http://127.0.0.1:8788/ (trend: /trend)
rsync -az -e 'ssh -i ~/.ssh/dism-tokyo' ubuntu@<elastic-ip>:crypto-strategy/cex-mm/artifacts/shadow/ artifacts/shadow-vm/
```

Four symbols write about 0.5 GB a day; the 30 GB disk holds about 50 days. Copy runs off with the `rsync` line
above (it has no `--delete`, so local copies survive), then let the housekeeping timer delete old run directories.

### Housekeeping

`scripts/shadow_housekeep.py` deletes run directories in `artifacts/shadow/` whose newest file is older than
`--days` (default 14). It never touches the run `current` points to, a run whose `*.pid` files name a live
process, symlinks, or anything not named like a run (`20261006T161427Z`). If `current` is missing, dangling, or
not a symlink to a run directory (as `shadow.sh` makes it) it deletes nothing and exits 2. Without `--apply` it
only reports. **Deletion is permanent: copy runs off first.**

```bash
cd ~/crypto-strategy/cex-mm && python3 scripts/shadow_housekeep.py   # dry run: keep/would-delete per run, sizes, disk free
systemctl --user enable --now cex-mm-shadow-housekeep.timer          # daily 03:30 UTC (+ up to 10 min), runs it with --apply
systemctl --user list-timers cex-mm-shadow-housekeep.timer
journalctl --user -u cex-mm-shadow-housekeep -n 30                   # what the last run kept and deleted
```

## Trend paper trader

`scripts/trend_paper.py` paper-trades the rule from `scripts/trend_backtest.py` on Delta mainnet public data:
daily target weights from Delta closes, whole contracts, fills walked through the live L2 book, Delta funding.
No keys, no orders. State and the daily journal live in `artifacts/trend/paper/` (`state.json`,
`journal.jsonl`); the dashboard shows them at `/trend`.

```bash
systemctl --user list-timers cex-mm-trend-paper.timer
journalctl --user -u cex-mm-trend-paper -n 20        # one line per rebalance, or the error that will be retried
systemctl --user start cex-mm-trend-paper            # run now (a no-op if today's rebalance is done)
```

Deleting `artifacts/trend/paper/` starts a new paper book at the next run.


## Real-money run (`scripts/live.sh`)

`scripts/live.sh` runs the DISM profile with **real money** on Delta mainnet next to the shadow test, so real fills
can be compared with the simulator over the same window. It is the shadow dry-run's exact command (same binary,
`config/dism.env`, `--loop-ms 400`) with `run` in place of `dry-run`, and the mainnet key from `quote-bot/.env`.
Starting it needs the user's explicit go-ahead.

```bash
scripts/live.sh start --confirm "START REAL"   # refuses unless the checks below pass
scripts/live.sh status                         # running / stopped / DOWN, last quote, venue position and orders
scripts/live.sh report                         # real fills vs the simulator, last 24 h (--hours N, --all)
scripts/live.sh stop                           # kill the bot, cancel its orders, check none are left open
```

- `start` refuses unless: the typed confirmation, no other `live.sh start`/`stop` in progress (a lock), no other
  `mm-bot run` process (the OEMS or a stray bot), the shadow dry-run is running the same binary, both mainnet keys
  are set without quotes or spaces, and `scripts/delta_key_check.py` passes (key works from this IP, order leverage
  at most 5x). If the bot dies during startup, `start` cancels its orders and says why.
- `stop` waits for an in-flight `start`, kills the bot, sends cancel-all for the stopped run's symbols, then reads
  the book and fails unless no order is left open.
- **No auto-restart.** mm-bot has no signal handler, so a crash or kill leaves its orders until Delta's dead man's
  switch (15 s) cancels them, and the position stays open. `status` and the dashboard's "Real-money bot" pill then
  say DOWN; the operator decides whether to restart, flatten or hold.
- The bot's working directory is `artifacts/live/`, so its economics file cannot reach the shadow dry-run (which
  reads `artifacts/economics/`). Its daily loss state ($15) is shared with the OEMS and any other mainnet run from
  `cex-mm/`: `artifacts/live/artifacts/risk` is a symlink to `artifacts/risk/`.
- Run data lives in `artifacts/live/<UTC start>/` (`config.txt` without secrets, `bot.log`, `bot.pid`, `fills.json`
  from the last report). A full-resolution report costs about 150 MB of RAM per day of window on a VM that also
  runs the bot; for a long run use `--compact` or copy the run off the VM.
- **While the live bot quotes, the shadow is no longer an independent prediction.** Our quotes are usually the
  Delta touch, so the shadow reads them as the book, and the trades that fill us print at our price, which the
  simulator's strict rule does not count. The shadow dashboard's simulated numbers for the live period are therefore
  not a counterfactual.
- `report` (`scripts/live_vs_shadow.py`) compares the real fills (from Delta) with the simulator on the shadow
  *before* the live start (the baseline: the window's length, 1-24 h). Per-fill edge is shown on the Delta mid (clean
  for the baseline, biased by our own quotes for the real row) and on the Binance mid shifted by the Delta-Binance
  basis (`b*` columns: compare real and sim on these). `PnLbp` is PnL per dollar traded, which needs no price
  reference; the live stop rule uses it: below 0 after 300 real fills means stop.
- Restarting the shadow test (`systemctl --user restart cex-mm-shadow`) does not touch the live bot.

## OEMS (optional)

The OEMS (`backend/mm-oems`, API on 127.0.0.1:8791) can run on the VM as the book of record and supervisor of
the `dism` strategy. `setup.sh` installs `cex-mm-oems.service` but does not enable it, and installs nothing it
needs. It was set up and verified on dism-tokyo on 2026-10-12, then switched off again.

**Never run the OEMS `dism` strategy and `scripts/live.sh` at the same time:** two bots on one account
fight over the same orders and position. `live.sh` refuses to start next to any `mm-bot run`, but the OEMS does not
check for a bot it did not start.

```bash
sudo apt-get install -y docker.io docker-compose-v2 postgresql-client
cd ~/crypto-strategy/cex-mm
cargo build --release -p mm-oems && cargo build -p mm-bot   # the supervisor starts target/debug/mm-bot
cd backend && sudo docker compose -f docker-compose.yml -f ../infra/vm/oems-compose.override.yml up -d && cd ..
systemctl --user enable --now cex-mm-oems
curl -s localhost:8791/api/strategies                       # mm (demo) and dism (mainnet), both stopped
journalctl --user -u cex-mm-oems -n 20                      # "real-money starts disabled" until you allow them
```

- TimescaleDB runs in Docker from the same `backend/docker-compose.yml` as on WSL. The override restarts it after
  a reboot and caps Postgres at 128 MB `shared_buffers`. The unit waits for Postgres before starting, because the
  OEMS reads its strategies only once.
- Real-money starts stay refused until `Environment=OEMS_ALLOW_MAINNET=1` is added with
  `systemctl --user edit cex-mm-oems`, and even then need the typed `START REAL`.
- `KillMode=process`: stopping or restarting the OEMS leaves a bot it started running; the next OEMS adopts it.
- The API is reachable only on the VM. From a laptop: `ssh -L 8791:127.0.0.1:8791 ubuntu@dism-tokyo`.
- Switch it off and free the disk (about 2 GB of image):
  `systemctl --user disable --now cex-mm-oems`, then
  `cd backend && sudo docker compose -f docker-compose.yml -f ../infra/vm/oems-compose.override.yml down -v --rmi all`
  (`-v` deletes the database).


## Phone access (Tailscale)

The dashboard is published on the operator's private tailnet, not the internet: no inbound ports are opened.

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --hostname=dism-tokyo          # prints a login link, approved once in the browser
sudo tailscale serve --bg 8788                   # https://dism-tokyo.<tailnet>.ts.net/ (tailnet only)
tailscale serve status
sudo tailscale serve --https=443 off             # unpublish
```

HTTPS needs MagicDNS and HTTPS certificates enabled for the tailnet (the first `serve` prints the link). Open the
dashboard by name, not by 100.x IP. Traffic inside the tailnet is WireGuard-encrypted. Disable key expiry for `dism-tokyo` in the Tailscale admin console,
or the VM drops off the tailnet when its node key expires (180 days).
