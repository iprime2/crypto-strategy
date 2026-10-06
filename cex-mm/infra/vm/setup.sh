#!/usr/bin/env bash
# Bootstrap a DISM host (Ubuntu 24.04, e.g. the dism-tokyo stack): swap, toolchain, release build,
# and the shadow test as user services that survive reboots and restart when a process dies.
# Run as the login user from a checkout of this repo; uses sudo for apt, swap and linger.
# Safe to re-run.
set -euo pipefail
CEX_MM="$(cd "$(dirname "$0")/../.." && pwd)"

# The release build needs more than the 1.8 GiB a t4g.small has.
if ! swapon --show=NAME --noheadings | grep -qx /swapfile; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential pkg-config git python3 curl

if ! command -v cargo >/dev/null && [[ ! -x "$HOME/.cargo/bin/cargo" ]]; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
fi
export PATH="$HOME/.cargo/bin:$PATH"
(cd "$CEX_MM" && cargo build --release -p mm-bot)

mkdir -p "$HOME/.config/systemd/user"
for unit in "$CEX_MM"/infra/systemd/*.service "$CEX_MM"/infra/systemd/*.timer; do
  sed "s|@CEX_MM@|$CEX_MM|g" "$unit" >"$HOME/.config/systemd/user/$(basename "$unit")"
done
# User services keep running after logout and start at boot.
sudo loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable --now cex-mm-shadow.service cex-mm-shadow-dashboard.service cex-mm-shadow-watchdog.timer
"$CEX_MM/scripts/shadow.sh" status
