"""Coleta: CNES, base completa do mês (DATASUS), para as equipes de Saúde da Família.

A API de dados abertos do CNES (src/collect/cnes.py) não traz as equipes. Elas estão na base
completa que o DATASUS publica todo mês (https://cnes.datasus.gov.br/pages/downloads/arquivosBaseDados.jsp),
um ZIP de cerca de 750 MB com as tabelas do CNES do país inteiro em CSV. Baixamos a competência
mais recente e guardamos o ZIP sem alteração; o processamento lê só tbEquipe e tbTipoEquipe.

Uso: python -m src.collect.cnes_base [--force] [--competencia AAAAMM]
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

from src.collect.download import download
from src.config import DATA_RAW

LISTA = "https://cnes.datasus.gov.br/services/arquivos-download/base-dados/"
ARQUIVO = "https://cnes.datasus.gov.br/EstatisticasServlet?path={nome}"
FONTE = "Ministério da Saúde, DATASUS - CNES, base de dados completa (competência mensal)"


def competencias() -> list[str]:
    """Competências disponíveis (AAAAMM), da mais recente para a mais antiga."""
    req = urllib.request.Request(LISTA, headers={"User-Agent": "raio-x-jp/0.1",
                                                 "Referer": "https://cnes.datasus.gov.br/pages/downloads/arquivosBaseDados.jsp"})
    with urllib.request.urlopen(req, timeout=60) as r:
        nomes = [a["nomeArquivo"] for a in json.load(r)]
    return sorted((n.removeprefix("BASE_DE_DADOS_CNES_").removesuffix(".ZIP") for n in nomes), reverse=True)


def arquivo_local() -> Path | None:
    """ZIP mais recente já baixado (o processamento usa este)."""
    zips = sorted((DATA_RAW / "cnes").glob("BASE_DE_DADOS_CNES_*.ZIP"))
    return zips[-1] if zips else None


def main(force: bool = False, competencia: str | None = None) -> None:
    if arquivo_local() and not force and not competencia:
        print(f"[ok] já existe: cnes/{arquivo_local().name}")
        return
    comp = competencia or competencias()[0]
    nome = f"BASE_DE_DADOS_CNES_{comp}.ZIP"
    download(ARQUIVO.format(nome=nome), Path("cnes") / nome, fonte=FONTE, force=force)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--force", action="store_true")
    p.add_argument("--competencia", help="AAAAMM; padrão: a mais recente")
    a = p.parse_args()
    main(a.force, a.competencia)
