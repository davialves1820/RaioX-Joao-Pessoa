"""Coleta: Tesouro Nacional, SICONFI, DCA Anexo I-D (despesa por natureza) de João Pessoa.

É o total de despesa que o município declara ao Tesouro na Declaração de Contas
Anuais. Usado só para conferir os totais anuais calculados a partir do TCE-PB.

Uso: python -m src.collect.siconfi [--force]
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from src.collect.download import download
from src.config import ANO_INICIAL_DESPESAS, COD_MUNICIPIO

API = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca"
FONTE = "Tesouro Nacional - SICONFI - DCA Anexo I-D"


def main(force: bool = False) -> None:
    # A DCA de um ano é entregue no ano seguinte: baixamos até o ano anterior.
    for ano in range(ANO_INICIAL_DESPESAS, date.today().year):
        download(
            f"{API}?an_exercicio={ano}&no_anexo=DCA-Anexo%20I-D&id_ente={COD_MUNICIPIO}",
            Path(f"siconfi/dca-anexo-I-D-{ano}.json"),
            fonte=FONTE,
            force=force,
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--force", action="store_true")
    main(p.parse_args().force)
