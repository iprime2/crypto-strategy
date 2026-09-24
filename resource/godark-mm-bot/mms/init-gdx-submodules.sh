#!/usr/bin/env bash
# Init gdx submodules over HTTPS (submodules default to git@ SSH).
set -euo pipefail

GDX_ROOT="${GDX_ROOT:-$HOME/gdx}"
export GIT_EXEC_PATH="${GIT_EXEC_PATH:-/usr/lib/git-core}"
CRED_HELPER='!gh auth git-credential'

if [[ ! -d "$GDX_ROOT/.git" ]]; then
  echo "Missing gdx repo at $GDX_ROOT" >&2
  exit 1
fi

cd "$GDX_ROOT"

rewrite_submodule_urls() {
  git config -f .gitmodules --get-regexp '^submodule\..*\.url$' | while read -r key url; do
    if [[ "$url" == git@github.com:* ]]; then
      https_url="https://github.com/${url#git@github.com:}"
      submodule_path="${key#submodule.}"
      submodule_path="${submodule_path%.url}"
      git config -f .gitmodules "$key" "$https_url"
      git config "submodule.${submodule_path}.url" "$https_url"
      echo "Rewrote ${submodule_path} -> $https_url"
    fi
  done
}

rewrite_submodule_urls

git -c "credential.helper=${CRED_HELPER}" submodule sync --recursive
git -c "credential.helper=${CRED_HELPER}" submodule update --init --recursive

echo "gdx submodules ready under $GDX_ROOT"
