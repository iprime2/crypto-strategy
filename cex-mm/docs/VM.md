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

## Operate

```bash
ssh -i ~/.ssh/dism-tokyo ubuntu@<elastic-ip>
cd ~/crypto-strategy/cex-mm && scripts/shadow.sh status
systemctl --user stop cex-mm-shadow      # stop for good (the watchdog leaves a stopped test alone)
systemctl --user restart cex-mm-shadow   # new run, e.g. after `git pull` (it rebuilds first)
ssh -i ~/.ssh/dism-tokyo -N -L 8788:127.0.0.1:8788 ubuntu@<elastic-ip>   # dashboard at http://127.0.0.1:8788/
rsync -az -e 'ssh -i ~/.ssh/dism-tokyo' ubuntu@<elastic-ip>:crypto-strategy/cex-mm/artifacts/shadow/ artifacts/shadow-vm/
```

Four symbols write about 0.5 GB a day; the 30 GB disk holds about 50 days. Copy runs off and delete old
run directories before it fills.
