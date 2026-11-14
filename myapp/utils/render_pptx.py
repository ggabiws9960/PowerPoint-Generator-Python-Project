"""명세(JSON) → PPTX. Node 렌더러(renderer/build.js)를 부른다."""
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent          # myapp/
ROOT = APP_DIR.parent                                      # 저장소 루트
RENDERER = ROOT / "renderer"
GENERATED = APP_DIR / "generated"


def node_bin() -> str:
    return os.getenv("NODE_BIN") or shutil.which("node") or "node"


def list_themes() -> list[dict]:
    """renderer/themes/*.json 의 {id, label, swatch} 목록. swatch 는 화면에 보일 대표색 4개(#hex)."""
    out = []
    for f in sorted((RENDERER / "themes").glob("*.json")):
        t = json.loads(f.read_text(encoding="utf-8"))
        c = t.get("colors", {})
        swatch = ["#" + c[k] for k in ("dk2", "accent1", "accent2", "accent3") if c.get(k)]
        out.append({"id": t["id"], "label": t.get("label", t["id"]), "swatch": swatch})
    return out


def render(spec: dict, theme: str, date: str = "") -> dict:
    """명세를 generated/<id>.json 으로 쓰고 build.js 로 <id>.pptx 를 만든다. {file, json, slides} 반환."""
    GENERATED.mkdir(parents=True, exist_ok=True)
    job = uuid.uuid4().hex[:10]
    spec = dict(spec)
    spec["theme"] = theme
    if date:
        spec["date"] = date
    spec_path = GENERATED / f"{job}.json"
    out_path = GENERATED / f"{job}.pptx"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    proc = subprocess.run(
        [node_bin(), str(RENDERER / "build.js"), str(spec_path), str(out_path), "--theme", theme],
        cwd=str(RENDERER), capture_output=True, text=True, encoding="utf-8", timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"렌더러 실패: {proc.stderr.strip()[-800:]}")
    info = json.loads(proc.stdout.strip().splitlines()[-1])
    return {"file": out_path.name, "json": spec_path.name, "slides": info.get("slides")}
