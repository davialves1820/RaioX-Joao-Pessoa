"""Coleta: INEP, microdados do Censo Escolar (matrículas por escola e etapa).

O Catálogo de Escolas (src/collect/inep_catalogo.py) não traz matrículas; os microdados trazem, por
escola, as matrículas de creche, pré-escola, fundamental e médio. O servidor do INEP não envia o
certificado intermediário da RNP, então a conexão é validada com o certificado público em certs/
somado aos certificados do sistema (a verificação TLS continua ligada).

Uso: python -m src.collect.inep_microdados [--force] [--ano AAAA]
"""

from __future__ import annotations

import argparse
import os
import shutil
import ssl
import urllib.request
from pathlib import Path

from src.collect.download import registrar
from src.config import DATA_RAW, ROOT

ANO = 2024
URL = "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_{ano}.zip"
FONTE = "INEP - Microdados do Censo Escolar da Educação Básica"
CERT = ROOT / "certs" / "rnp-icpedu-gr46-ov-tls-ca-2025.pem"


def destino(ano: int = ANO) -> Path:
    return DATA_RAW / "inep" / f"microdados_censo_escolar_{ano}.zip"


def _contexto() -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or None)
    ctx.load_verify_locations(cafile=str(CERT))
    return ctx


def main(force: bool = False, ano: int = ANO) -> None:
    dest = destino(ano)
    if dest.exists() and not force:
        print(f"[ok] já existe: {dest.relative_to(DATA_RAW)}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = URL.format(ano=ano)
    print(f"[baixando] {url}")
    tmp = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "raio-x-jp/0.1"})
    with urllib.request.urlopen(req, context=_contexto(), timeout=300) as r, tmp.open("wb") as out:
        shutil.copyfileobj(r, out)
    tmp.replace(dest)
    registrar(dest, url, FONTE)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--force", action="store_true")
    p.add_argument("--ano", type=int, default=ANO)
    a = p.parse_args()
    main(a.force, a.ano)
