#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export BASTION_ROOT="$ROOT"

mkdir -p "$ROOT"/RUNTIME/{TMP,XDG/cache,XDG/config,XDG/data,PYCACHE,HOME,WHEELS,ASSETS}
mkdir -p "$ROOT"/RUNTIME/CACHES/{huggingface,transformers,torch,matplotlib,cuda,numba}

export TMPDIR="$ROOT/RUNTIME/TMP"
export XDG_CACHE_HOME="$ROOT/RUNTIME/XDG/cache"
export XDG_CONFIG_HOME="$ROOT/RUNTIME/XDG/config"
export XDG_DATA_HOME="$ROOT/RUNTIME/XDG/data"
export PYTHONPYCACHEPREFIX="$ROOT/RUNTIME/PYCACHE"
export HF_HOME="$ROOT/RUNTIME/CACHES/huggingface"
export TRANSFORMERS_CACHE="$ROOT/RUNTIME/CACHES/transformers"
export TORCH_HOME="$ROOT/RUNTIME/CACHES/torch"
export MPLCONFIGDIR="$ROOT/RUNTIME/CACHES/matplotlib"
export CUDA_CACHE_PATH="$ROOT/RUNTIME/CACHES/cuda"
export NUMBA_CACHE_DIR="$ROOT/RUNTIME/CACHES/numba"
export HOME="$ROOT/RUNTIME/HOME"

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
export no_proxy="127.0.0.1,localhost"
export NO_PROXY="127.0.0.1,localhost"

VENV="$ROOT/RUNTIME/ENV"
PY="$VENV/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "[BASTION] Création ENV interne..."
  python3 -m venv "$VENV"
  "$PY" -m pip install --upgrade pip
  if ! "$PY" -m pip install pillow safetensors numpy; then
    echo "ACQUISITION NÉCESSAIRE UNE FOIS: relancez avec internet pour installer pillow/safetensors/numpy." >&2
    exit 2
  fi
fi

exec "$PY" "$ROOT/app.py"
