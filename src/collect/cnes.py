"""Coleta: CNES (Ministério da Saúde), estabelecimentos de saúde de João Pessoa.

API de dados abertos do Ministério da Saúde (apidadosabertos.saude.gov.br). A API devolve no
máximo 20 registros por página; percorremos todas as páginas do município 250750 (código
IBGE de 6 dígitos) e salvamos a resposta inteira em um JSON. Baixa também a tabela de tipos
de unidade.

Uso: python -m src.collect.cnes [--force] [--atualizar]
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

from src.collect.download import download, registrar
from src.config import COD_MUNICIPIO, DATA_RAW

API = "https://apidadosabertos.saude.gov.br/cnes"
FONTE = "Ministério da Saúde - CNES - API de dados abertos (estabelecimentos)"
DESTINO = DATA_RAW / "cnes" / f"estabelecimentos_{COD_MUNICIPIO[:6]}.json"
POR_PAGINA = 20


def _pagina(offset: int) -> list[dict]:
    url = f"{API}/estabelecimentos?codigo_municipio={COD_MUNICIPIO[:6]}&limit={POR_PAGINA}&offset={offset}"
    for tentativa in range(1, 7):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "raio-x-jp/0.1"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)["estabelecimentos"]
        except OSError as e:
            if tentativa == 6:
                raise
            print(f"[erro] offset {offset}: {e}; nova tentativa")
            time.sleep(2 * tentativa)
    return []


def baixar_estabelecimentos() -> Path:
    todos, offset = [], 0
    while True:
        lote = _pagina(offset)
        todos += lote
        if len(lote) < POR_PAGINA:
            break
        offset += POR_PAGINA
    if len({e["codigo_cnes"] for e in todos}) != len(todos):
        raise ValueError("a paginação do CNES devolveu estabelecimentos repetidos")
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    tmp = DESTINO.with_name(DESTINO.name + ".part")
    tmp.write_text(json.dumps(todos, ensure_ascii=False), encoding="utf-8")
    tmp.replace(DESTINO)
    print(f"[ok] {len(todos)} estabelecimentos")
    return DESTINO


def main(force: bool = False, atualizar: bool = False) -> None:
    download(f"{API}/tipounidades", Path("cnes/tipounidades.json"), fonte=FONTE + " - tipos de unidade", force=force)
    if DESTINO.exists() and not (force or atualizar):
        print(f"[ok] já existe: {DESTINO.relative_to(DATA_RAW)}")
        return
    registrar(baixar_estabelecimentos(), f"{API}/estabelecimentos?codigo_municipio={COD_MUNICIPIO[:6]}", FONTE)


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--force", action="store_true")
    a.add_argument("--atualizar", action="store_true", help="rebaixa os estabelecimentos (mudam com o tempo)")
    args = a.parse_args()
    main(args.force, args.atualizar)
