"""Penyimpanan riwayat proyek (disk server) + ekspor/impor JSON cadangan."""
import base64
import hashlib
import json
import re
import time
import uuid
from pathlib import Path

BASE = Path(__file__).parent / "history"
MAX_PROJECTS = 30                      # riwayat tertua dihapus otomatis bila lebih
_PID = re.compile(r"^[A-Za-z0-9\-]{6,40}$")


def _now_wib() -> str:
    return time.strftime("%d %b %Y %H:%M", time.gmtime(time.time() + 7 * 3600))


def _folder(code: str) -> Path:
    """Tiap 'kode riwayat' punya folder sendiri agar tidak tercampur dengan pengunjung lain."""
    h = hashlib.sha256((code or "umum").strip().encode("utf-8")).hexdigest()[:12]
    d = BASE / h
    d.mkdir(parents=True, exist_ok=True)
    return d


def _default(o):
    if isinstance(o, (bytes, bytearray)):
        return {"__b64__": base64.b64encode(bytes(o)).decode("ascii")}
    return str(o)


def _hook(d):
    if len(d) == 1 and "__b64__" in d:
        return base64.b64decode(d["__b64__"])
    return d


def dumps(data: dict) -> bytes:
    return json.dumps(data, default=_default, ensure_ascii=False).encode("utf-8")


def loads(raw) -> dict:
    return json.loads(raw, object_hook=_hook)


def _prune(d: Path):
    metas = sorted(d.glob("*.meta"), reverse=True)
    for m in metas[MAX_PROJECTS:]:
        pid = m.stem
        for ext in (".json", ".meta"):
            (d / f"{pid}{ext}").unlink(missing_ok=True)


def save_project(code: str, data: dict, pid: str | None = None) -> str:
    d = _folder(code)
    if not pid or not _PID.match(pid):
        pid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    meta = {"id": pid, "title": data.get("project_title") or "Proyek", "saved": _now_wib()}
    tmp = d / f"{pid}.json.tmp"
    tmp.write_bytes(dumps(data))
    tmp.replace(d / f"{pid}.json")     # tulis atomik: file tidak rusak bila terputus
    (d / f"{pid}.meta").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    _prune(d)
    return pid


def list_projects(code: str) -> list[dict]:
    d = _folder(code)
    out = []
    for m in sorted(d.glob("*.meta"), reverse=True):
        try:
            out.append(json.loads(m.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def load_project(code: str, pid: str) -> dict | None:
    if not pid or not _PID.match(pid):
        return None
    f = _folder(code) / f"{pid}.json"
    if not f.exists():
        return None
    return loads(f.read_bytes())


def delete_project(code: str, pid: str):
    if not pid or not _PID.match(pid):
        return
    d = _folder(code)
    for ext in (".json", ".meta"):
        (d / f"{pid}{ext}").unlink(missing_ok=True)
