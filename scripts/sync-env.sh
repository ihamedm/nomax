#!/usr/bin/env bash
# Append keys that exist in a template but are missing from an existing env
# file, leaving every existing value alone. Commented keys count as present,
# so a variable disabled in the target is never silently re-enabled.
#   ./scripts/sync-env.sh .env.prod.example .env.prod
set -euo pipefail

template="${1:?usage: $0 <template.env> <target.env>}"
target="${2:?usage: $0 <template.env> <target.env>}"
[ -f "$template" ] || { echo "template not found: $template" >&2; exit 1; }
[ -f "$target" ] || { echo "target not found: $target" >&2; exit 1; }

added=0
while IFS= read -r line; do
  key=${line%%=*}
  if grep -qE "^[[:space:]]*#?[[:space:]]*${key}=" "$target"; then
    continue
  fi
  printf '%s\n' "$line" >> "$target"
  printf 'added: %s\n' "$key"
  added=$((added + 1))
done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$template")

echo "$added key(s) appended to $target"
