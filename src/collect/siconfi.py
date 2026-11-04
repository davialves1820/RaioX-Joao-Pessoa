"""Coleta: Tesouro Nacional, SICONFI, de João Pessoa.

- DCA Anexo I-D (despesa por natureza): o total de despesa que o município declara ao Tesouro na
  Declaração de Contas Anuais. Usado só para conferir os totais anuais calculados a partir do TCE-PB.
- RGF Anexo 01 do Poder Legislativo (Câmara Municipal): despesa com pessoal frente à Receita
  Corrente Líquida e aos limites da Lei de Responsabilidade Fiscal, por quadrimestre, de
  ANO_INICIAL_CAMARA em diante. Só quadrimestres encerrados há mais de 30 dias (prazo de publicação).

Uso: python -m src.collect.siconfi [--force]
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

from src.collect.download import download
from src.config import ANO_INICIAL_CAMARA, ANO_INICIAL_DESPESAS, COD_MUNICIPIO

API = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca"
FONTE = "Tesouro Nacional - SICONFI - DCA Anexo I-D"
API_RGF = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rgf"
FONTE_RGF = "Tesouro Nacional - SICONFI - RGF Anexo 01 (despesa com pessoal), Poder Legislativo"
# Último mês de cada quadrimestre
FIM_QUADRIMESTRE = {1: 4, 2: 8, 3: 12}


def quadrimestre_publicado(ano: int, q: int, hoje: date) -> bool:
    fim = date(ano + (FIM_QUADRIMESTRE[q] == 12), FIM_QUADRIMESTRE[q] % 12 + 1, 1)
    return hoje >= fim + timedelta(days=30)


def main(force: bool = False) -> None:
    # A DCA de um ano é entregue no ano seguinte: baixamos até o ano anterior.
    for ano in range(ANO_INICIAL_DESPESAS, date.today().year):
        download(
            f"{API}?an_exercicio={ano}&no_anexo=DCA-Anexo%20I-D&id_ente={COD_MUNICIPIO}",
            Path(f"siconfi/dca-anexo-I-D-{ano}.json"),
            fonte=FONTE,
            force=force,
        )
    hoje = date.today()
    for ano in range(ANO_INICIAL_CAMARA, hoje.year + 1):
        for q in FIM_QUADRIMESTRE:
            if not quadrimestre_publicado(ano, q, hoje):
                continue
            download(
                f"{API_RGF}?an_exercicio={ano}&in_periodicidade=Q&nr_periodo={q}&co_tipo_demonstrativo=RGF"
                f"&no_anexo=RGF-Anexo%2001&co_esfera=M&co_poder=L&id_ente={COD_MUNICIPIO}",
                Path(f"siconfi/rgf-legislativo-{ano}-q{q}.json"),
                fonte=FONTE_RGF,
                force=force,
            )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--force", action="store_true")
    main(p.parse_args().force)
