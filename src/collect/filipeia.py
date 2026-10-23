"""Coleta: Filipeia, Mapas da Cidade (Prefeitura de João Pessoa), exportação manual.

O portal (https://filipeia.joaopessoa.pb.gov.br/) fica atrás de um firewall anti-robô que bloqueia
acesso automatizado, então as camadas são exportadas à mão, pelo navegador, e salvas em
data/raw/filipeia/ com estes nomes:

- Parques_Municipais.zip   shapefile dos parques municipais (polígonos)
- Parques_Municipais.csv   tabela de atributos dos parques
- pracas.csv               tabela de atributos das praças (o portal não oferece o shapefile;
                           os contornos vêm do geodata-jp e são conferidos com esta tabela)
- quadras_gerais.zip       shapefile das quadras (usado para conferir a posição das praças)
- bairros.zip              shapefile dos bairros da Prefeitura (só para comparação; o mapa usa o IBGE)

Depois de salvar, rode `python -m src.collect.filipeia --registrar` para registrar os arquivos no
manifesto (data da exportação e SHA-256).

Uso: python -m src.collect.filipeia [--registrar]
"""

from __future__ import annotations

import argparse

from src.collect.download import load_manifest, registrar
from src.config import DATA_RAW

PORTAL = "https://filipeia.joaopessoa.pb.gov.br/"
FONTE = "Filipeia - Mapas da Cidade, Prefeitura de João Pessoa [exportação manual pelo navegador]"
PASTA = DATA_RAW / "filipeia"
ARQUIVOS = ["Parques_Municipais.zip", "Parques_Municipais.csv", "pracas.csv", "quadras_gerais.zip", "bairros.zip"]


def main(so_registrar: bool = False) -> None:
    faltam = [a for a in ARQUIVOS if not (PASTA / a).exists()]
    if faltam:
        print(f"[aviso] Filipeia: faltam em {PASTA.relative_to(DATA_RAW.parent.parent)}: {', '.join(faltam)}. "
              "Exporte-os à mão (ver src/collect/filipeia.py).")
    manifesto = load_manifest()
    for a in ARQUIVOS:
        caminho = PASTA / a
        if not caminho.exists():
            continue
        if so_registrar or f"filipeia/{a}" not in manifesto:
            registrar(caminho, PORTAL, FONTE)
            print(f"[ok] registrado: filipeia/{a}")
        else:
            print(f"[ok] já existe: filipeia/{a}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--registrar", action="store_true", help="registra de novo no manifesto (após nova exportação)")
    main(p.parse_args().registrar)
