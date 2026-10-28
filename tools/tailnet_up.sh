#!/usr/bin/env bash
# Join a Claude cloud session to the tailnet, so it can SSH to the VMs without opening port 22.
# Uses the environment's TS_AUTHKEY (the node comes up as tag:claude; the tailnet policy lets it
# SSH as ubuntu to tag:dism and tag:bitra only). Userspace networking: no TUN device, no root
# routes. Writes an ssh config, then: ssh -F "$TAILNET_DIR/ssh_config" bitra-desk
# Safe to re-run; never prints the key.
set -euo pipefail
TAILNET_DIR="${TAILNET_DIR:-/tmp/tailnet}"
HOSTNAME_TS="${TS_HOSTNAME:-claude-cloud}"
mkdir -p "$TAILNET_DIR/state"
SOCK="$TAILNET_DIR/tailscaled.sock"

if [[ -z "${TS_AUTHKEY:-}" ]]; then
  echo "TS_AUTHKEY is not set in this environment; add it in the environment settings" >&2
  exit 1
fi

case "$(uname -m)" in
  x86_64) ARCH=amd64 ;;
  aarch64 | arm64) ARCH=arm64 ;;
  *) echo "unsupported architecture $(uname -m)" >&2; exit 1 ;;
esac

BIN="$(ls -d "$TAILNET_DIR"/tailscale_*_"$ARCH" 2>/dev/null | tail -1 || true)"
if [[ -z "$BIN" ]]; then
  TGZ="$(curl -fsS https://pkgs.tailscale.com/stable/ | grep -oE "tailscale_[0-9.]+_${ARCH}\.tgz" | head -1)"
  curl -fsS -o "$TAILNET_DIR/$TGZ" "https://pkgs.tailscale.com/stable/$TGZ"
  echo "$(curl -fsS "https://pkgs.tailscale.com/stable/$TGZ.sha256")  $TAILNET_DIR/$TGZ" | sha256sum -c --quiet -
  tar -C "$TAILNET_DIR" -xzf "$TAILNET_DIR/$TGZ"
  BIN="$TAILNET_DIR/${TGZ%.tgz}"
fi
TS=("$BIN/tailscale" --socket="$SOCK")

if ! "${TS[@]}" status >/dev/null 2>&1; then
  nohup "$BIN/tailscaled" --tun=userspace-networking --port=0 \
    --state="$TAILNET_DIR/state/tailscaled.state" --socket="$SOCK" >"$TAILNET_DIR/tailscaled.log" 2>&1 &
  for _ in $(seq 20); do [[ -S "$SOCK" ]] && break; sleep 0.5; done
  "${TS[@]}" up --authkey="$TS_AUTHKEY" --hostname="$HOSTNAME_TS" --accept-routes=false >/dev/null
fi

command -v ssh >/dev/null || { apt-get install -y -qq openssh-client >/dev/null 2>&1 \
  || (apt-get update -qq >/dev/null && apt-get install -y -qq openssh-client >/dev/null); }

cat >"$TAILNET_DIR/ssh_config" <<EOF
Host bitra-desk dism-tokyo
  User ubuntu
  BatchMode yes
  StrictHostKeyChecking accept-new
  UserKnownHostsFile $TAILNET_DIR/known_hosts
  ProxyCommand ${TS[*]} nc %h %p
  ServerAliveInterval 30
EOF

"${TS[@]}" status
echo "ssh -F $TAILNET_DIR/ssh_config bitra-desk    (or dism-tokyo)"
