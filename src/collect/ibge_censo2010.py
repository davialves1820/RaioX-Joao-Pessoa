"""Coleta: IBGE, Censo Demográfico 2010, Resultados do Universo por setor censitário (PB).

O Censo 2010 não tem tabela agregada por bairro; cada setor traz o código do
bairro, então somamos os setores no processamento. Baixa também a malha de
setores de 2010, usada para medir quanto os limites dos bairros mudaram até 2022.

Uso: python -m src.collect.ibge_censo2010 [--force]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.collect.download import download

FTP = "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2010/Resultados_do_Universo/Agregados_por_Setores_Censitarios"
GEOFTP = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/"
    "malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2010/setores_censitarios_shp"
)

ARQUIVOS = {
    "ibge_censo2010/PB_20260615.zip": (
        f"{FTP}/PB_20260615.zip",
        "IBGE - Censo Demográfico 2010 - Resultados do Universo - Agregados por Setores Censitários",
    ),
    "ibge_censo2010/pb_setores_censitarios.zip": (
        f"{GEOFTP}/pb/pb_setores_censitarios.zip",
        "IBGE - Malha de Setores Censitários - Censo 2010",
    ),
}


def main(force: bool = False) -> None:
    for dest, (url, fonte) in ARQUIVOS.items():
        download(url, Path(dest), fonte=fonte, force=force)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--force", action="store_true", help="rebaixa mesmo se o arquivo já existir")
    main(p.parse_args().force)
