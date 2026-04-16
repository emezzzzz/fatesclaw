#!/usr/bin/env bash
set -euo pipefail

root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
status=0

fail() {
  printf '[sanitize] %s\n' "$*" >&2
  status=1
}

scan_files() {
  find "$root" -type f \
    ! -path '*/.git/*' \
    ! -path '*/.venv/*' \
    ! -path '*/__pycache__/*' \
    ! -path '*/tmp/*' \
    ! -path '*/logs/*'
}

while IFS= read -r path; do
  case "$path" in
    *.pyc|*.pyo|*.dtbo|*.log|*.pem|*.key|*.p12|*.pfx)
      fail "forbidden generated or secret-like file: ${path#$root/}"
      ;;
  esac
done < <(find "$root" -type f ! -path '*/.git/*' ! -path '*/__pycache__/*' ! -path '*/logs/*' ! -path '*/tmp/*')

while IFS= read -r path; do
  case "$path" in
    */.openclaw/*|*/.codex/*|*/.ssh/*|*/.env.local|*/.npmrc)
      fail "forbidden local config path copied: ${path#$root/}"
      ;;
  esac
done < <(find "$root" -path '*/.git' -prune -o -print)

patterns=(
  'nvapi-[A-Za-z0-9_-]{20,}'
  'AKIA[0-9A-Z]{16}'
  '-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----'
  'xox[baprs]-[A-Za-z0-9-]{20,}'
  'gh[pousr]_[A-Za-z0-9_]{20,}'
  'sk-[A-Za-z0-9]{20,}'
  'api[_-]?key[[:space:]]*=[[:space:]]*["'\'']?[A-Za-z0-9_-]{16,}'
  'token[[:space:]]*=[[:space:]]*["'\'']?[A-Za-z0-9_-]{24,}'
  '/home/[A-Za-z0-9._-]+/'
  '/Users/[A-Za-z0-9._-]+/'
)

for pattern in "${patterns[@]}"; do
  if scan_files | xargs grep -nEI "$pattern" >/tmp/fatesclaw-sanitize-hit 2>/dev/null; then
    fail "suspicious content matched pattern: $pattern"
    sed 's/^/[sanitize]   /' /tmp/fatesclaw-sanitize-hit >&2
  fi
done

if scan_files | xargs grep -nE '(^|[^0-9])((10\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[0-1])|192\.168)\.[0-9]{1,3}\.[0-9]{1,3})([^0-9]|$)' >/tmp/fatesclaw-sanitize-ip 2>/dev/null; then
  fail "private LAN IP address found"
  sed 's/^/[sanitize]   /' /tmp/fatesclaw-sanitize-ip >&2
fi

current_user="${USER:-}"
if [ -n "$current_user" ] && [ ${#current_user} -ge 3 ]; then
  user_pattern="(^|[^A-Za-z0-9._-])${current_user}([^A-Za-z0-9._-]|$)"
  if scan_files | xargs grep -nE "$user_pattern" >/tmp/fatesclaw-sanitize-user 2>/dev/null; then
    fail "current local username appears in repository content"
    sed 's/^/[sanitize]   /' /tmp/fatesclaw-sanitize-user >&2
  fi
fi

rm -f /tmp/fatesclaw-sanitize-hit /tmp/fatesclaw-sanitize-ip /tmp/fatesclaw-sanitize-user

if [ "$status" -ne 0 ]; then
  fail "sanitization failed"
  exit "$status"
fi

printf '[sanitize] OK\n'
