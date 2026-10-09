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

## Operate

```bash
ssh -i ~/.ssh/dism-tokyo ubuntu@<elastic-ip>
cd ~/crypto-strategy/cex-mm && scripts/shadow.sh status
systemctl --user stop cex-mm-shadow      # stop for good (the watchdog leaves a stopped test alone)
systemctl --user restart cex-mm-shadow   # new run, e.g. after `git pull` (it rebuilds first)
ssh -i ~/.ssh/dism-tokyo -N -L 8788:127.0.0.1:8788 ubuntu@<elastic-ip>   # dashboard at http://127.0.0.1:8788/ (trend: /trend)
rsync -az -e 'ssh -i ~/.ssh/dism-tokyo' ubuntu@<elastic-ip>:crypto-strategy/cex-mm/artifacts/shadow/ artifacts/shadow-vm/
```

Four symbols write about 0.5 GB a day; the 30 GB disk holds about 50 days. Copy runs off and delete old
run directories before it fills.

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
