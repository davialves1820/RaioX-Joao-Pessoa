"""Coleta: TCE-PB, dados abertos do SAGRES, despesas (empenhos) de João Pessoa.

O portal dados-abertos.tce.pb.gov.br publica um .zip por município, conjunto e ano,
com um CSV de empenhos de todas as unidades gestoras do município (Prefeitura,
fundos, autarquias e Câmara). João Pessoa é o código 095.

Baixa também a listagem do repositório de arquivos (formato S3), que traz a data
em que o TCE-PB gerou cada arquivo.

Uso: python -m src.collect.tce_pb [--force] [--atualizar]
  --force      rebaixa todos os arquivos
  --atualizar  rebaixa só o que muda com o tempo: o ano corrente e a listagem
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from src.collect.download import download
from src.config import ANO_INICIAL_DESPESAS, COD_MUNICIPIO_TCE

BASE = "https://download.tce.pb.gov.br/dados-abertos"
FONTE = "TCE-PB - Dados Abertos do SAGRES - Despesas por município"
# O servidor do TCE-PB derruba conexões com frequência; insistimos mais.
TENTATIVAS = 8


def url_despesas(ano: int) -> str:
    return f"{BASE}/dados-por-municipio/{COD_MUNICIPIO_TCE}/despesas/despesas-{ano}.zip"


def main(force: bool = False, atualizar: bool = False) -> None:
    ano_corrente = date.today().year
    download(
        f"{BASE}/?prefix=dados-por-municipio/{COD_MUNICIPIO_TCE}/",
        Path("tce_pb/listagem.xml"),
        fonte="TCE-PB - listagem do repositório de dados abertos (datas de geração)",
        force=force or atualizar,
        tentativas=TENTATIVAS,
    )
    for ano in range(ANO_INICIAL_DESPESAS, ano_corrente + 1):
        download(
            url_despesas(ano),
            Path(f"tce_pb/despesas-{ano}.zip"),
            fonte=FONTE,
            force=force or (atualizar and ano == ano_corrente),
            tentativas=TENTATIVAS,
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--force", action="store_true")
    p.add_argument("--atualizar", action="store_true")
    a = p.parse_args()
    main(a.force, a.atualizar)
