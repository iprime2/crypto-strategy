#!/usr/bin/env bash
# Bootstrap the bitra sandbox desks on an Ubuntu 24.04 host (bitra-desk, ap-south-1).
# Installs uv and bitra, lays down ~/bitra/desk from this folder's desk/ config and ~/bitra/desk-groq as
# the same desk on a different model, and installs the hourly user services, the read-only dashboard
# (published on the tailnet by `tailscale serve`) and the hindsight and paper timers. Never touches
# ~/bitra/desk/.env (beyond creating it empty), runs/ or the fetched series under sources/*/. Starts a
# desk only once its model's key (GEMINI_API_KEY, GROQ_API_KEY) is set.
# Run as the login user from a copy of this folder; uses sudo for apt and linger. Safe to re-run.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DESK="$HOME/bitra/desk"
GDESK="$HOME/bitra/desk-groq"
BITRA_VERSION="${BITRA_VERSION:-0.10.2}"

sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git tmux jq curl

if ! command -v uv >/dev/null && [[ ! -x "$HOME/.local/bin/uv" ]]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
# Groq goes through the openai client, so that extra is needed beside google's
if [[ "$(tra --version 2>/dev/null)" != "tra $BITRA_VERSION" ]] \
  || ! "$HOME/.local/share/uv/tools/bitra/bin/python" -c "import openai, google.genai" 2>/dev/null; then
  uv tool install --force "bitra[ccxt,google,openai,data]==$BITRA_VERSION"
fi

# The repo is the source of truth for the desk's config; the VM keeps its secrets and records.
mkdir -p "$DESK"
tar -C "$HERE/desk" --exclude=.env --exclude=runs --exclude='*.csv' -c . | tar -C "$DESK" -x
if [[ ! -f "$DESK/.env" ]]; then
  (umask 077 && cp "$HERE/desk/.env.example" "$DESK/.env")
fi
chmod 600 "$DESK/.env"

# The second desk is the first with only its model changed, so the comparison is the model alone.
mkdir -p "$GDESK"
tar -C "$HERE/desk" --exclude=.env --exclude=runs --exclude='*.csv' -c . | tar -C "$GDESK" -x
sed -i -e 's/^provider = "google"$/provider = "groq"/' \
  -e 's#^model = "gemini-3.1-flash-lite"$#model = "openai/gpt-oss-120b"#' \
  -e 's#^fallback = \["google:.*\]$#fallback = ["groq:openai/gpt-oss-20b"]#' "$GDESK/strategy.toml"
for want in '^provider = "groq"$' '^model = "openai/gpt-oss-120b"$' '^fallback = \["groq:openai/gpt-oss-20b"\]$'; do
  grep -q "$want" "$GDESK/strategy.toml" || { echo "desk-groq: could not set ${want} in strategy.toml" >&2; exit 1; }
done
ln -sfn ../desk/.env "$GDESK/.env"  # one key file for both desks

cp "$HERE/README.md" "$HOME/bitra/README.md"
mkdir -p "$HOME/bitra/dashboard" "$HOME/bitra/paper" "$HOME/bitra/paper-groq"
cp "$HERE/dashboard/server.py" "$HOME/bitra/dashboard/server.py"
cp "$HERE/paper/paper.py" "$HOME/bitra/paper/paper.py"

mkdir -p "$HOME/.config/systemd/user"
cp "$HERE"/systemd/*.service "$HERE"/systemd/*.timer "$HOME/.config/systemd/user/"
sudo loginctl enable-linger "$USER"
systemctl --user daemon-reload

# The dashboard and the hindsight and paper timers only read the records (and public candles), so they
# run whether or not a key is set.
systemctl --user enable bitra-dashboard bitra-hindsight.timer bitra-paper.timer
systemctl --user restart bitra-dashboard
systemctl --user start bitra-hindsight.timer bitra-paper.timer
systemctl --user start bitra-paper.service || echo "paper: first run failed; journalctl --user -u bitra-paper"
if command -v tailscale >/dev/null; then
  sudo tailscale serve --bg 8790 >/dev/null  # HTTPS on the tailnet only; nothing opens to the internet
  echo "dashboard: $(tailscale serve status 2>/dev/null | grep -oE 'https://[^ ]+' | head -1)"
fi

if grep -q '^GEMINI_API_KEY=.' "$DESK/.env"; then
  systemctl --user enable bitra-desk
  systemctl --user restart bitra-desk
  echo "bitra-desk: running ($(tra --version)); journalctl --user -u bitra-desk -n 50"
else
  echo "bitra-desk: installed, not started. Put GEMINI_API_KEY in $DESK/.env, then re-run this script."
fi

if grep -q '^GROQ_API_KEY=.' "$DESK/.env"; then
  # its own copies of the series the analysts read, before its first cycle
  [[ -f "$GDESK/sources/sentiment/fear_greed.csv" ]] || (cd "$GDESK" && tra --plain sources pull >/dev/null) || true
  sleep 20  # not on the same second as the first desk's start-up cycle: Bybit rate-limits bursts
  systemctl --user enable bitra-desk-groq
  systemctl --user restart bitra-desk-groq
  echo "bitra-desk-groq: running on $(grep '^model = ' "$GDESK/strategy.toml")"
else
  systemctl --user disable --now bitra-desk-groq 2>/dev/null || true
  echo "bitra-desk-groq: installed, not started. Put GROQ_API_KEY in $DESK/.env, then re-run this script."
fi
