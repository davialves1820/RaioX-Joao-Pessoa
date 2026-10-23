"""Coleta: camadas do repositório geodata-jp (origem: Filipeia, Prefeitura de João Pessoa).

- bairros.geojson: só para a tabela de correspondência de nomes (o mapa usa a malha do IBGE).
- pracas.geojson: contornos das praças. O Filipeia só oferece a tabela das praças, sem os
  contornos; o processamento confere que as praças daqui são as mesmas da tabela oficial.
  (Os parques vêm do shapefile oficial do Filipeia, em src/collect/filipeia.py.)
- escolas_publicas.geojson: usado apenas para completar a coordenada de escolas que o
  Catálogo de Escolas do INEP (fonte principal) publica sem latitude/longitude.

Fixamos o commit para que os arquivos sejam sempre os mesmos.

Uso: python -m src.collect.geodata_jp [--force]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.collect.download import download

COMMIT = "76f128bbe0689de98c2a1d2f0bc1e897201d7941"
BASE = f"https://raw.githubusercontent.com/paulovitorweb/geodata-jp/{COMMIT}/data"
CAMADAS = ["bairros", "pracas", "escolas_publicas"]
FONTE = "paulovitorweb/geodata-jp (origem: Filipeia - Prefeitura de João Pessoa)"


def main(force: bool = False) -> None:
    for camada in CAMADAS:
        download(f"{BASE}/{camada}.geojson", Path(f"geodata_jp/{camada}.geojson"), fonte=FONTE, force=force)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--force", action="store_true", help="rebaixa mesmo se o arquivo já existir")
    main(p.parse_args().force)
