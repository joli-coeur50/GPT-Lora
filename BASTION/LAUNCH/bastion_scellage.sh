#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT="$ROOT/DATA/REPORTS/scellage_$(date +%Y%m%d_%H%M%S).txt"
mkdir -p "$(dirname "$REPORT")"
status=OK

echo "BASTION SCELLAGE" > "$REPORT"
echo "root=$ROOT" >> "$REPORT"

# 1) no-write-outside (journal interne prioritaire)
JOURNAL="$ROOT/STATE/write_journal.jsonl"
if [[ -f "$JOURNAL" ]]; then
  outside=$(python3 - <<PY
import json
root="$ROOT"
outs=[]
for line in open("$JOURNAL", encoding="utf-8"):
    try:
        p=json.loads(line).get("path","")
    except Exception:
        continue
    if p and not p.startswith(root):
        outs.append(p)
print("\n".join(outs[:50]))
PY
)
  if [[ -n "$outside" ]]; then
    echo "FAIL NO-WRITE-OUTSIDE (journal)" >> "$REPORT"
    echo "$outside" >> "$REPORT"
    status=FAIL
  else
    echo "OK NO-WRITE-OUTSIDE (journal)" >> "$REPORT"
  fi
else
  echo "SKIP NO-WRITE-OUTSIDE (journal absent)" >> "$REPORT"
fi

# 2) offline outbound check (snapshot sockets non-local)
if command -v ss >/dev/null 2>&1; then
  outbound=$(ss -tunp 2>/dev/null | rg ESTAB | rg -v '127\.0\.0\.1|::1' || true)
  if [[ -n "$outbound" ]]; then
    echo "FAIL OFFLINE no-outbound" >> "$REPORT"
    echo "$outbound" >> "$REPORT"
    status=FAIL
  else
    echo "OK OFFLINE no-outbound" >> "$REPORT"
  fi
else
  echo "SKIP OFFLINE no-outbound (ss absent)" >> "$REPORT"
fi

# 3) preuves ATLAS
latest_dataset=$(find "$ROOT/DATA/DATASETS" -maxdepth 1 -type d -name 'atlas_*' | sort | tail -n1 || true)
if [[ -n "$latest_dataset" ]]; then
  if [[ -f "$latest_dataset/dataset.json" && -f "$latest_dataset/report.txt" && -f "$latest_dataset/log.txt" ]]; then
    python3 - <<PY >> "$REPORT"
import json
p="$latest_dataset/dataset.json"
d=json.load(open(p))
print("OK ATLAS dataset parse", p, "items", len(d.get("items",[])))
PY
  else
    echo "FAIL ATLAS preuves manquantes" >> "$REPORT"; status=FAIL
  fi
else
  echo "SKIP ATLAS (aucun dataset)" >> "$REPORT"
fi

# 4) preuves ENCLUME
latest_lora=$(find "$ROOT/DATA/LORAS" -maxdepth 1 -type d -name '*_*_*' | sort | tail -n1 || true)
if [[ -n "$latest_lora" ]]; then
  if [[ -f "$latest_lora/run.json" && -f "$latest_lora/report.txt" && -f "$latest_lora/log.txt" ]]; then
    echo "OK ENCLUME run artefacts de base" >> "$REPORT"
  else
    echo "FAIL ENCLUME artefacts manquants" >> "$REPORT"; status=FAIL
  fi
else
  echo "SKIP ENCLUME (aucune run)" >> "$REPORT"
fi

# 5) bundle
BUNDLE="$ROOT/DATA/BUNDLES/bastion_bundle_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BUNDLE"
cp -a "$ROOT/bastion.sh" "$ROOT/LAUNCH" "$ROOT/CONFIG" "$ROOT/app.py" "$BUNDLE/"
echo "OK BUNDLE $BUNDLE" >> "$REPORT"

echo "FINAL=$status" >> "$REPORT"
echo "$REPORT"
[[ "$status" == "OK" ]] && exit 0 || exit 1
