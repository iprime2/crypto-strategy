#!/usr/bin/env bash
# Bootstrap the bitra sandbox desks on an Ubuntu 24.04 host (bitra-desk, ap-south-1).
# Installs uv and bitra, lays down ~/bitra/desk from this folder's desk/ config and ~/bitra/desk-groq and
# ~/bitra/desk-claude as the same desk on different models, and installs the hourly user services, the
# read-only dashboard (published on the tailnet by `tailscale serve`) and the hindsight and paper timers.
# Never touches ~/bitra/desk/.env (beyond creating it empty), runs/ or the fetched series under
# sources/*/. Starts a desk only once its model's key (GEMINI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY)
# is set.
# Run as the login user from a copy of this folder; uses sudo for apt, swap and linger. Safe to re-run.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DESK="$HOME/bitra/desk"
GDESK="$HOME/bitra/desk-groq"
CDESK="$HOME/bitra/desk-claude"
BITRA_VERSION="${BITRA_VERSION:-0.10.2}"

sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git tmux jq curl

# Each desk's process holds about 420 MB and the host has 2 GiB: swap keeps three of them and an hourly
# hindsight run from ending in the OOM killer. They sleep between cycles, so what is swapped is idle.
if [[ -z "$(swapon --show=NAME --noheadings)" ]]; then
  [[ -f /swapfile ]] || sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

if ! command -v uv >/dev/null && [[ ! -x "$HOME/.local/bin/uv" ]]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
# Groq goes through the openai client, and Claude through anthropic's, beside google's. Claude also needs
# claude-provider/ (bitra's anthropic adapter with schemas the Claude API accepts), installed beside bitra
# and reinstalled whenever its copy here differs from the installed one.
BPY="$HOME/.local/share/uv/tools/bitra/bin/python"
if [[ "$(tra --version 2>/dev/null)" != "tra $BITRA_VERSION" ]] \
  || ! "$BPY" -c "import openai, google.genai, anthropic" 2>/dev/null \
  || ! cmp -s "$HERE/claude-provider/bitra_claude.py" \
       "$("$BPY" -c "import bitra_claude; print(bitra_claude.__file__)" 2>/dev/null || echo /nonexistent)"; then
  uv tool install --force "bitra[ccxt,google,openai,anthropic,data]==$BITRA_VERSION" --with "$HERE/claude-provider"
fi

# The repo is the source of truth for the desk's config; the VM keeps its secrets and records.
mkdir -p "$DESK"
tar -C "$HERE/desk" --exclude=.env --exclude=runs --exclude='*.csv' -c . | tar -C "$DESK" -x
if [[ ! -f "$DESK/.env" ]]; then
  (umask 077 && cp "$HERE/desk/.env.example" "$DESK/.env")
fi
chmod 600 "$DESK/.env"

# Every other desk is the first with only its three [agents] model lines changed, so a comparison
# between them is the model alone.
model_desk() {  # DIR PROVIDER MODEL FALLBACK
  local dir=$1 provider=$2 model=$3 fallback=$4
  mkdir -p "$dir"
  tar -C "$HERE/desk" --exclude=.env --exclude=runs --exclude='*.csv' -c . | tar -C "$dir" -x
  sed -i -e "s#^provider = \"google\"\$#provider = \"$provider\"#" \
    -e "s#^model = \"gemini-3.1-flash-lite\"\$#model = \"$model\"#" \
    -e "s#^fallback = \\[\"google:.*\\]\$#fallback = [\"$fallback\"]#" "$dir/strategy.toml"
  for want in "provider = \"$provider\"" "model = \"$model\"" "fallback = [\"$fallback\"]"; do
    grep -qxF "$want" "$dir/strategy.toml" \
      || { echo "$(basename "$dir"): could not set ${want} in strategy.toml" >&2; exit 1; }
  done
  ln -sfn ../desk/.env "$dir/.env"  # one key file for every desk
}
model_desk "$GDESK" groq openai/gpt-oss-120b groq:openai/gpt-oss-20b
model_desk "$CDESK" claude claude-opus-5-5 claude:claude-sonnet-5-5  # the provider claude-provider/ adds

cp "$HERE/README.md" "$HOME/bitra/README.md"
mkdir -p "$HOME/bitra/dashboard" "$HOME/bitra/paper" "$HOME/bitra/paper-groq" "$HOME/bitra/paper-claude"
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

start_desk() {  # UNIT DIR KEY
  local unit=$1 dir=$2 key=$3
  if grep -q "^$key=." "$DESK/.env"; then
    # its own copies of the series the analysts read, before its first cycle
    [[ -f "$dir/sources/sentiment/fear_greed.csv" ]] || (cd "$dir" && tra --plain sources pull >/dev/null) || true
    sleep 20  # not on the same second as the previous desk's start-up cycle: Bybit rate-limits bursts
    systemctl --user enable "$unit"
    systemctl --user restart "$unit"
    echo "$unit: running on $(grep '^model = ' "$dir/strategy.toml")"
  else
    systemctl --user disable --now "$unit" 2>/dev/null || true
    echo "$unit: installed, not started. Put $key in $DESK/.env, then re-run this script."
  fi
}
start_desk bitra-desk-groq "$GDESK" GROQ_API_KEY
start_desk bitra-desk-claude "$CDESK" ANTHROPIC_API_KEY
