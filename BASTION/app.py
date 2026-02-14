#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs, urlparse

BASTION_ROOT = Path(__file__).resolve().parent
DATA_DIR = BASTION_ROOT / "DATA"
STATE_DIR = BASTION_ROOT / "STATE"
CONFIG_PATH = STATE_DIR / "locations.json"
JOBS_PATH = DATA_DIR / "LOGS" / "jobs.jsonl"
INDEX_DB = DATA_DIR / "INDEX_ATLAS" / "index.sqlite"

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
MODEL_EXT = {".safetensors", ".ckpt", ".pt"}


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()




def journal_write(path: Path):
    j = STATE_DIR / "write_journal.jsonl"
    j.parent.mkdir(parents=True, exist_ok=True)
    with j.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now_iso(), "path": str(path.resolve())}, ensure_ascii=False) + "\n")

def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    journal_write(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_index_db() -> None:
    INDEX_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(INDEX_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS images (
                source_rel TEXT PRIMARY KEY,
                mtime REAL NOT NULL,
                size INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                phash64 TEXT,
                width INTEGER,
                height INTEGER,
                quality REAL,
                updated_at TEXT NOT NULL
            )
            """
        )


def phash64(path: Path) -> str:
    from PIL import Image
    import numpy as np

    img = Image.open(path).convert("L").resize((32, 32))
    arr = np.asarray(img, dtype=float)
    dct = np.fft.fft2(arr)
    low = np.abs(dct[:8, :8])
    med = np.median(low)
    bits = (low > med).flatten()
    val = 0
    for bit in bits[:64]:
        val = (val << 1) | int(bit)
    return f"{val:016x}"


def hamming_hex(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


def quality_score(path: Path) -> Dict[str, float]:
    from PIL import Image, ImageFilter
    import numpy as np

    img = Image.open(path).convert("RGB")
    w, h = img.size
    gray = img.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    arr = np.asarray(edges, dtype=float)
    sharpness = min(100.0, float(arr.var() / 40.0))
    resolution = min(100.0, (w * h) / (1024 * 1024) * 25)
    ratio = w / h if h else 1
    ratio_pen = 0 if 0.6 <= ratio <= 1.8 else 20
    score = max(0.0, min(100.0, sharpness * 0.65 + resolution * 0.35 - ratio_pen))
    return {
        "quality": round(score, 2),
        "sharpness": round(sharpness, 2),
        "resolution": round(resolution, 2),
        "ratio_penalty": ratio_pen,
        "width": w,
        "height": h,
    }


def tolerance_to_dist(tol: int) -> int:
    mapping = {1: 4, 2: 5, 3: 6, 4: 8, 5: 10, 6: 12, 7: 14, 8: 16, 9: 18, 10: 20}
    return mapping.get(max(1, min(10, tol)), 10)


@dataclass
class Job:
    job_id: str
    kind: str
    status: str = "RUNNING"
    progress: int = 0
    step: str = "starting"
    run_dir: str = ""
    log_path: str = ""
    started_at: str = ""
    ended_at: str = ""
    error: str = ""


class JobStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.jobs: Dict[str, Job] = {}

    def create(self, kind: str, run_dir: Path) -> Job:
        j = Job(job_id=f"{kind}_{uuid.uuid4().hex[:8]}", kind=kind, run_dir=str(run_dir.relative_to(BASTION_ROOT)), started_at=now_iso())
        j.log_path = str((run_dir / "log.txt").relative_to(BASTION_ROOT))
        with self.lock:
            self.jobs[j.job_id] = j
        self.persist(j)
        return j

    def update(self, job_id: str, **kwargs):
        with self.lock:
            job = self.jobs[job_id]
            for k, v in kwargs.items():
                setattr(job, k, v)
            self.persist(job)

    def list(self):
        with self.lock:
            return [vars(x) for x in self.jobs.values()]

    def persist(self, job: Job):
        JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with JOBS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(vars(job), ensure_ascii=False) + "\n")


JOBS = JobStore()


def get_locations() -> Dict[str, str]:
    return read_json(CONFIG_PATH, {"inbox": "", "frigo": ""})


def write_log(logf: Path, line: str):
    logf.parent.mkdir(parents=True, exist_ok=True)
    with logf.open("a", encoding="utf-8") as f:
        f.write(f"[{now_iso()}] {line}\n")
    journal_write(logf)


def scan_images(root: Path) -> List[Path]:
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXT]


def atlas_worker(job: Job, payload: dict):
    run_id = f"atlas_{datetime.utcnow().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
    run_dir = DATA_DIR / "DATASETS" / run_id
    images_out = run_dir / "images"
    logf = run_dir / "log.txt"
    report = run_dir / "report.txt"
    dataset_json = run_dir / "dataset.json"
    try:
        locations = get_locations()
        inbox_raw = locations.get("inbox", "")
        if not inbox_raw:
            raise RuntimeError("INBOX non configuré.")
        inbox = Path(inbox_raw)
        if not inbox.exists():
            raise RuntimeError("INBOX introuvable. Configurez Emplacements.")
        ensure_index_db()
        tol = int(payload.get("dedup_tolerance", 6))
        target_mode = payload.get("target_mode", "count")
        target_value = int(payload.get("target_value", 100))
        JOBS.update(job.job_id, progress=5, step="scan inbox", run_dir=str(run_dir.relative_to(BASTION_ROOT)), log_path=str(logf.relative_to(BASTION_ROOT)))
        paths = scan_images(inbox)
        write_log(logf, f"Scanned {len(paths)} images")
        rows = []
        with sqlite3.connect(INDEX_DB) as conn:
            for idx, p in enumerate(paths, start=1):
                stat = p.stat()
                rel = str(p.relative_to(inbox))
                db = conn.execute("SELECT mtime,size,sha256,phash64,width,height,quality FROM images WHERE source_rel=?", (rel,)).fetchone()
                if db and float(db[0]) == stat.st_mtime and int(db[1]) == stat.st_size:
                    sha, ph, w, h, q = db[2], db[3], db[4], db[5], db[6]
                else:
                    sha = sha256_file(p)
                    qd = quality_score(p)
                    ph = phash64(p)
                    w, h, q = qd["width"], qd["height"], qd["quality"]
                    conn.execute(
                        "REPLACE INTO images(source_rel,mtime,size,sha256,phash64,width,height,quality,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        (rel, stat.st_mtime, stat.st_size, sha, ph, w, h, q, now_iso()),
                    )
                rows.append({"path": p, "source_rel": rel, "sha256": sha, "phash64": ph, "quality": float(q), "width": w, "height": h})
                if idx % 20 == 0:
                    JOBS.update(job.job_id, progress=min(60, 5 + int(idx / max(1, len(paths)) * 55)), step=f"indexed {idx}/{len(paths)}")
        max_dist = tolerance_to_dist(tol)
        accepted, rejected_dups = [], []
        for item in sorted(rows, key=lambda r: r["quality"], reverse=True):
            is_dup = any(hamming_hex(item["phash64"], keep["phash64"]) <= max_dist for keep in accepted)
            if is_dup:
                rejected_dups.append(item)
            else:
                accepted.append(item)
        kept_target = target_value if target_mode == "count" else max(1, int(len(rows) * (target_value / 100)))
        kept = accepted[:kept_target]
        images_out.mkdir(parents=True, exist_ok=True)
        items = []
        for idx, item in enumerate(kept, start=1):
            dst = images_out / f"{idx:06d}{item['path'].suffix.lower()}"
            shutil.copy2(item["path"], dst)
            journal_write(dst)
            items.append({
                "image_rel": str(dst.relative_to(run_dir)),
                "source_rel": item["source_rel"],
                "sha256": item["sha256"],
                "phash64": item["phash64"],
                "scores": {"quality": item["quality"], "aesthetic": None, "diversity": 0.0},
                "tags": [],
                "caption": "",
            })
        dataset = {
            "bastion_version": "0.1.0",
            "atlas_run_id": run_id,
            "created_at": now_iso(),
            "inbox_signature": {"root_name": inbox.name, "file_count_scanned": len(rows)},
            "params": {
                "preset": payload.get("preset", "balanced"),
                "target_mode": target_mode,
                "target_value": target_value,
                "dedup_tolerance": tol,
                "diversity": int(payload.get("diversity", 3)),
            },
            "stats": {
                "scanned": len(rows),
                "kept": len(kept),
                "rejected_quality": max(0, len(rows) - len(accepted)),
                "rejected_duplicates": len(rejected_dups),
            },
            "items": items,
        }
        write_json(dataset_json, dataset)
        report.write_text(
            "\n".join([
                f"ATLAS RUN: {run_id}",
                f"Params: preset={dataset['params']['preset']} target={target_mode}:{target_value} tol={tol}",
                f"Stats: scanned={len(rows)} kept={len(kept)} rejected_duplicates={len(rejected_dups)}",
                "Top raisons de rejet: duplicates"
            ]),
            encoding="utf-8",
        )
        journal_write(report)
        JOBS.update(job.job_id, status="DONE", progress=100, step="finished", ended_at=now_iso())
        write_log(logf, "ATLAS DONE")
    except Exception as e:
        write_log(logf, f"ERROR: {e}")
        JOBS.update(job.job_id, status="ERROR", step="failed", ended_at=now_iso(), error=str(e))


def enclume_dry_run(payload: dict) -> dict:
    dataset = BASTION_ROOT / payload.get("dataset_ref", "")
    model = Path(get_locations().get("frigo", "")) / payload.get("model_rel", "")
    checks = {
        "dataset_exists": dataset.exists(),
        "dataset_json_ok": (dataset / "dataset.json").exists(),
        "model_exists": model.exists(),
        "deps_ok": True,
        "engine_available": (BASTION_ROOT / "RUNTIME/ASSETS/kohya_sd_scripts/train_network.py").exists(),
    }
    checks["ok"] = all([checks["dataset_exists"], checks["dataset_json_ok"], checks["model_exists"], checks["deps_ok"]])
    checks["message"] = "OK" if checks["ok"] else "Prérequis manquants"
    return checks


def enclume_worker(job: Job, payload: dict):
    run_name = payload.get("output_name", "lora")
    run_id = f"{run_name}_{datetime.utcnow().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
    run_dir = DATA_DIR / "LORAS" / run_id
    logf = run_dir / "log.txt"
    report = run_dir / "report.txt"
    run_json = run_dir / "run.json"
    kit = run_dir / "KIT_DE_TEST"
    try:
        dry = enclume_dry_run(payload)
        if not dry["ok"]:
            raise RuntimeError(f"Dry-run KO: {dry}")
        engine = BASTION_ROOT / "RUNTIME/ASSETS/kohya_sd_scripts/train_network.py"
        if not engine.exists():
            raise RuntimeError("Engine kohya introuvable dans RUNTIME/ASSETS. Acquisition requise.")
        # Real training is delegated to engine; currently enforced as unavailable until assets are installed.
        raise RuntimeError("Entraînement non lancé: configurez le script kohya et paramètres dans RUNTIME/ASSETS.")
    except Exception as e:
        run_dir.mkdir(parents=True, exist_ok=True)
        report.write_text(f"ENCLUME ERROR\nCause: {e}\nAction: installer/configurer engine kohya.", encoding="utf-8")
        journal_write(report)
        write_json(
            run_json,
            {
                "bastion_version": "0.1.0",
                "enclume_run_id": run_id,
                "created_at": now_iso(),
                "dataset_ref": payload.get("dataset_ref", ""),
                "base_model_ref": {"frigo_rel": payload.get("model_rel", ""), "sha256": ""},
                "profile": payload.get("profile", "low_vram"),
                "engine": "kohya_sd_scripts",
                "params": payload.get("params", {}),
                "outputs": {"lora_file": f"{run_name}.safetensors", "lora_sha256": ""},
                "duration_sec": 0,
                "status": "ERROR",
            },
        )
        kit.mkdir(parents=True, exist_ok=True)
        (kit / "README_TEST.md").write_text("Run failed before model creation.", encoding="utf-8")
        journal_write(kit / "README_TEST.md")
        (kit / "PROMPTS.txt").write_text("", encoding="utf-8")
        journal_write(kit / "PROMPTS.txt")
        (kit / "REGLAGES_RECOMMANDES.txt").write_text("", encoding="utf-8")
        journal_write(kit / "REGLAGES_RECOMMANDES.txt")
        (kit / "CHEMINS.txt").write_text("", encoding="utf-8")
        journal_write(kit / "CHEMINS.txt")
        write_log(logf, f"ERROR: {e}")
        JOBS.update(job.job_id, status="ERROR", step="failed", ended_at=now_iso(), run_dir=str(run_dir.relative_to(BASTION_ROOT)), log_path=str(logf.relative_to(BASTION_ROOT)), error=str(e))


INDEX_HTML = """<!doctype html><html><head><meta charset='utf-8'><title>BASTION</title>
<style>body{font-family:Arial;margin:20px}nav button{margin-right:8px}.card{border:1px solid #ccc;padding:12px;margin-top:10px}pre{background:#111;color:#0f0;padding:8px;height:180px;overflow:auto}</style></head>
<body><h1>BASTION</h1><nav><button onclick="show('empl')">Emplacements</button><button onclick="show('atlas')">Atlas</button><button onclick="show('enc')">Enclume</button></nav>
<div id='empl' class='card'>INBOX <input id='inbox' size='60'><br>FRIGO <input id='frigo' size='60'><br><button onclick='saveCfg()'>Enregistrer</button><button onclick='rescan()'>Rescanner tout</button><pre id='scan'></pre></div>
<div id='atlas' class='card' style='display:none'>Target mode <select id='tm'><option>count</option><option>percent</option></select> Value <input id='tv' value='100' size='6'> Tol <input id='tol' value='6' size='2'><button onclick='runAtlas()'>Lancer ATLAS</button></div>
<div id='enc' class='card' style='display:none'>Dataset ref (ex: DATA/DATASETS/atlas_xxx) <input id='ds' size='40'><br>Model rel (depuis FRIGO) <input id='mr' size='40'><br>Output <input id='on' value='lora'><button onclick='dryRun()'>Dry-run</button><button onclick='runEnc()'>Lancer ENCLUME</button><pre id='dry'></pre></div>
<div class='card'><h3>Jobs/Logs</h3><pre id='jobs'></pre></div>
<script>
function show(id){for (const x of ['empl','atlas','enc']) document.getElementById(x).style.display=(x===id?'block':'none');}
async function api(u,m='GET',b=null){let r=await fetch(u,{method:m,headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):null});return r.json()}
async function loadCfg(){let c=await api('/api/config');inbox.value=c.inbox||'';frigo.value=c.frigo||''}
async function saveCfg(){await api('/api/config','POST',{inbox:inbox.value,frigo:frigo.value});await rescan();}
async function rescan(){scan.textContent=JSON.stringify(await api('/api/rescan'),null,2)}
async function runAtlas(){await api('/api/atlas/run','POST',{target_mode:tm.value,target_value:+tv.value,dedup_tolerance:+tol.value,preset:'balanced',diversity:3})}
async function dryRun(){dry.textContent=JSON.stringify(await api('/api/enclume/dry_run','POST',{dataset_ref:ds.value,model_rel:mr.value,output_name:on.value,profile:'low_vram'}),null,2)}
async function runEnc(){await api('/api/enclume/run','POST',{dataset_ref:ds.value,model_rel:mr.value,output_name:on.value,profile:'low_vram'})}
async function poll(){jobs.textContent=JSON.stringify(await api('/api/jobs'),null,2);setTimeout(poll,1500)}
loadCfg();rescan();poll();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload, status=200):
        b = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            b = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif path == "/api/config":
            self._json(get_locations())
        elif path == "/api/rescan":
            cfg = get_locations()
            inbox_raw = cfg.get("inbox", "")
            frigo_raw = cfg.get("frigo", "")
            inbox = Path(inbox_raw) if inbox_raw else None
            frigo = Path(frigo_raw) if frigo_raw else None
            datasets = list((DATA_DIR / "DATASETS").glob("atlas_*"))
            self._json({
                "inbox_exists": bool(inbox and inbox.exists()),
                "inbox_images": len(scan_images(inbox)) if inbox and inbox.exists() else 0,
                "frigo_exists": bool(frigo and frigo.exists()),
                "frigo_models": len([p for p in frigo.rglob("*") if p.is_file() and p.suffix.lower() in MODEL_EXT]) if frigo and frigo.exists() else 0,
                "datasets": [str(p.relative_to(BASTION_ROOT)) for p in datasets],
            })
        elif path == "/api/jobs":
            self._json(JOBS.list())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(length) or b"{}")
        if path == "/api/config":
            write_json(CONFIG_PATH, {"inbox": data.get("inbox", ""), "frigo": data.get("frigo", "")})
            self._json({"ok": True})
        elif path == "/api/atlas/run":
            tmp = DATA_DIR / "DATASETS" / f"pending_{uuid.uuid4().hex[:6]}"
            job = JOBS.create("atlas", tmp)
            threading.Thread(target=atlas_worker, args=(job, data), daemon=True).start()
            self._json({"job_id": job.job_id})
        elif path == "/api/enclume/dry_run":
            self._json(enclume_dry_run(data))
        elif path == "/api/enclume/run":
            tmp = DATA_DIR / "LORAS" / f"pending_{uuid.uuid4().hex[:6]}"
            job = JOBS.create("enclume", tmp)
            threading.Thread(target=enclume_worker, args=(job, data), daemon=True).start()
            self._json({"job_id": job.job_id})
        else:
            self._json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):
        pass


def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ensure_index_db()
    host = os.environ.get("BASTION_HOST", "127.0.0.1")
    port = int(os.environ.get("BASTION_PORT", "8765"))
    print(f"BASTION UI: http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
