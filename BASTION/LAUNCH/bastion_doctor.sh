#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OK=1
say(){ printf '%s\n' "$*"; }
check(){ if eval "$2"; then say "OK   $1"; else say "FAIL $1"; OK=0; fi; }

check "venv present" "test -x '$ROOT/RUNTIME/ENV/bin/python'"
check "lock versions" "test -f '$ROOT/CONFIG/LOCK_VERSIONS.txt'"
check "index sqlite path" "test -d '$ROOT/DATA/INDEX_ATLAS'"
check "required dirs" "test -d '$ROOT/DATA/DATASETS' && test -d '$ROOT/DATA/LORAS'"

if command -v nvidia-smi >/dev/null 2>&1; then
  say "OK   GPU detect:"
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true
else
  say "SKIP GPU detect (nvidia-smi absent)"
fi

CFG="$ROOT/STATE/locations.json"
if [[ -f "$CFG" ]]; then
  INBOX=$(python3 - <<PY
import json;print(json.load(open('$CFG')).get('inbox',''))
PY
)
  FRIGO=$(python3 - <<PY
import json;print(json.load(open('$CFG')).get('frigo',''))
PY
)
  [[ -n "$INBOX" ]] && check "INBOX read" "test -r '$INBOX'"
  [[ -n "$FRIGO" ]] && check "FRIGO read" "test -r '$FRIGO'"
else
  say "SKIP locations not configured"
fi

[[ $OK -eq 1 ]] && exit 0 || exit 1
