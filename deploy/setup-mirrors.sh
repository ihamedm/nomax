#!/usr/bin/env bash
# Apply the host package mirrors from a Nomax .env file (default: .env):
#   APT_MIRROR_URL          -> Ubuntu apt archive mirror
#   APT_MIRROR_SECURITY_URL -> Ubuntu security mirror
#   DOCKER_MIRROR_URL       -> Docker daemon registry mirror (image pulls)
# Each one falls back to the Liara mirror when unset in the env file.
# Use it like:
#   sudo ./deploy/setup-mirrors.sh .env.prod
# Ubuntu sources are rewritten with sed; the Docker daemon config is merged
# with jq and the daemon restarted to pick up the mirror.
set -euo pipefail

env_file="${1:-.env}"
[ -f "$env_file" ] || { echo "env file not found: $env_file" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || { echo "run as root: sudo $0 $env_file" >&2; exit 1; }

set -a
# shellcheck disable=SC1090
. "$env_file"
set +a

: "${APT_MIRROR_URL:=http://linux-mirror.liara.ir/repository/ubuntu/}"
: "${APT_MIRROR_SECURITY_URL:=http://linux-mirror.liara.ir/repository/ubuntu-security/}"
: "${DOCKER_MIRROR_URL:=https://docker-mirror.liara.ir}"

# Normalize: the sed patterns leave the source line's trailing "/" in place.
apt_main="${APT_MIRROR_URL%/}"
apt_sec="${APT_MIRROR_SECURITY_URL%/}"

# --- Ubuntu apt mirrors (archive + security), both classic and deb822 formats
for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do
  [ -f "$f" ] || continue
  sed -i \
    -e "s|http://archive.ubuntu.com/ubuntu|$apt_main|g" \
    -e "s|http://security.ubuntu.com/ubuntu|$apt_sec|g" \
    -e "s|https://archive.ubuntu.com/ubuntu|$apt_main|g" \
    -e "s|https://security.ubuntu.com/ubuntu|$apt_sec|g" \
    "$f"
  echo "apt: rewrote $f -> $APT_MIRROR_URL / $APT_MIRROR_SECURITY_URL"
done
apt-get update

# --- Docker registry mirror. Merges into daemon.json so the log-driver setup
# from the bootstrap doc survives.
if ! command -v jq >/dev/null 2>&1; then
  echo "jq not found; skipping the Docker daemon mirror." >&2
else
  conf=/etc/docker/daemon.json
  [ -f "$conf" ] || echo '{}' > "$conf"
  jq --arg m "$DOCKER_MIRROR_URL" '.["registry-mirrors"] = [$m]' "$conf" > "$conf.new"
  mv "$conf.new" "$conf"
  systemctl restart docker
  echo "docker: registry-mirrors set to $DOCKER_MIRROR_URL"
fi
