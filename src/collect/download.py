"""Download reexecutável com registro de origem em data/raw/manifest.json.

- Se o arquivo já existe, não baixa de novo (use force=True para rebaixar).
- O download vai para um arquivo .part e só é renomeado ao final, então uma
  interrupção nunca deixa um arquivo pela metade com o nome final.
- O manifesto guarda URL, data de download, tamanho e SHA-256 de cada arquivo.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from src.config import DATA_RAW, MANIFEST

TENTATIVAS = 4


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def _save_manifest(manifest: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(dict(sorted(manifest.items())), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def download(
    url: str, dest: Path, *, fonte: str, force: bool = False, tentativas: int = TENTATIVAS
) -> Path:
    """Baixa `url` para `dest` (relativo a data/raw ou absoluto)."""
    dest = dest if dest.is_absolute() else DATA_RAW / dest
    key = dest.relative_to(DATA_RAW).as_posix()
    manifest = load_manifest()

    if dest.exists() and not force:
        if key not in manifest:
            # Arquivo presente mas sem registro: registra sem data de download conhecida.
            manifest[key] = {
                "url": url,
                "fonte": fonte,
                "baixado_em": None,
                "bytes": dest.stat().st_size,
                "sha256": _sha256(dest),
            }
            _save_manifest(manifest)
        print(f"[ok] já existe: {key}")
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    print(f"[baixando] {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "raio-x-jp/0.1"})
    for tentativa in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp, tmp.open("wb") as out:
                shutil.copyfileobj(resp, out)
            break
        except OSError as e:  # URLError, reset de conexão, timeout
            if tentativa == tentativas:
                tmp.unlink(missing_ok=True)
                raise
            espera = min(2**tentativa, 30)
            print(f"[erro] {e}; nova tentativa em {espera}s ({tentativa}/{tentativas})")
            time.sleep(espera)
    tmp.replace(dest)

    manifest[key] = {
        "url": url,
        "fonte": fonte,
        "baixado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bytes": dest.stat().st_size,
        "sha256": _sha256(dest),
    }
    _save_manifest(manifest)
    print(f"[salvo] {key} ({dest.stat().st_size:,} bytes)")
    return dest


def registrar(dest: Path, url: str, fonte: str) -> None:
    """Registra no manifesto um arquivo obtido de outra forma (ex.: exportado por navegador)."""
    dest = dest if dest.is_absolute() else DATA_RAW / dest
    manifest = load_manifest()
    manifest[dest.relative_to(DATA_RAW).as_posix()] = {
        "url": url,
        "fonte": fonte,
        "baixado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bytes": dest.stat().st_size,
        "sha256": _sha256(dest),
    }
    _save_manifest(manifest)
    print(f"[salvo] {dest.relative_to(DATA_RAW).as_posix()} ({dest.stat().st_size:,} bytes)")
