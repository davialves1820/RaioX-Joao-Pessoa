"""Coleta: limites de bairros do Filipeia (Prefeitura de João Pessoa) via geodata-jp.

Não é a geometria usada no mapa (usamos a malha do IBGE 2022, que é o mesmo
território em que a população foi contada). Serve para a tabela de
correspondência de nomes e para as camadas municipais das próximas fases.
Fixamos o commit para que o arquivo seja sempre o mesmo.

Uso: python -m src.collect.geodata_jp [--force]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.collect.download import download

COMMIT = "76f128bbe0689de98c2a1d2f0bc1e897201d7941"
URL = f"https://raw.githubusercontent.com/paulovitorweb/geodata-jp/{COMMIT}/data/bairros.geojson"
FONTE = "paulovitorweb/geodata-jp (origem: Filipeia - Prefeitura de João Pessoa)"


def main(force: bool = False) -> None:
    download(URL, Path("geodata_jp/bairros.geojson"), fonte=FONTE, force=force)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--force", action="store_true", help="rebaixa mesmo se o arquivo já existir")
    main(p.parse_args().force)
