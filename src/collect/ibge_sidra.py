"""Coleta: IBGE/SIDRA, IPCA mensal e estimativas anuais de população de João Pessoa.

- Tabela 1737, variável 2266: IPCA, número-índice (dez/1993 = 100), Brasil, todos os meses.
- Tabela 6579, variável 9324: população residente estimada, João Pessoa, todos os anos.

Uso: python -m src.collect.ibge_sidra [--force] [--atualizar]
  --atualizar  rebaixa as duas séries (ganham um mês/ano novo com o tempo)
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.collect.download import download
from src.config import COD_MUNICIPIO

SIDRA = "https://apisidra.ibge.gov.br/values"
ARQUIVOS = {
    "ibge_sidra/ipca_tabela1737.json": (
        f"{SIDRA}/t/1737/n1/all/v/2266/p/all",
        "IBGE - SIDRA tabela 1737 - IPCA número-índice",
    ),
    "ibge_sidra/populacao_estimada_tabela6579.json": (
        f"{SIDRA}/t/6579/n6/{COD_MUNICIPIO}/v/9324/p/all",
        "IBGE - SIDRA tabela 6579 - Estimativas de população",
    ),
}


def main(force: bool = False, atualizar: bool = False) -> None:
    for dest, (url, fonte) in ARQUIVOS.items():
        download(url, Path(dest), fonte=fonte, force=force or atualizar)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--force", action="store_true")
    p.add_argument("--atualizar", action="store_true")
    a = p.parse_args()
    main(a.force, a.atualizar)
