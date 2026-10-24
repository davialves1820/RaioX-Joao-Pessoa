"""Coleta: IBGE, Censo Demográfico 2022, Agregados por Setores Censitários.

Baixa:
- tabela básica agregada por bairro (Brasil inteiro; filtramos João Pessoa no processamento);
- tabela básica agregada por município (para o total oficial de João Pessoa);
- malha de bairros com atributos da Paraíba (geometria oficial dos bairros do Censo);
- dicionário de dados;
- tabelas por bairro de demografia (idade), características dos domicílios (partes 1 e 2) e rendimento
  do responsável pelo domicílio, com o dicionário do rendimento.

Uso: python -m src.collect.ibge_censo2022 [--force]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.collect.download import download

FTP = "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios"
FONTE = "IBGE - Censo Demográfico 2022 - Agregados por Setores Censitários"
FTP_RENDA = "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios_Rendimento_do_Responsavel"

# O IBGE coloca a data de revisão no nome de alguns arquivos. Se um arquivo
# for substituído no FTP, a URL antiga deixa de existir: atualize aqui.
ARQUIVOS = {
    "ibge_censo2022/Agregados_por_bairros_basico_BR_20260520.zip":
        f"{FTP}/Agregados_por_Bairro_csv/Agregados_por_bairros_basico_BR_20260520.zip",
    "ibge_censo2022/Agregados_por_municipios_basico_BR_20260520.zip":
        f"{FTP}/Agregados_por_Municipio_csv/Agregados_por_municipios_basico_BR_20260520.zip",
    "ibge_censo2022/PB_bairros_CD2022.gpkg":
        f"{FTP}/malha_com_atributos/bairros/gpkg/UF/PB/PB_bairros_CD2022.gpkg",
    # Setores censitários com população (v0001), usados na distância ponderada por população
    "ibge_censo2022/PB_setores_CD2022.gpkg":
        f"{FTP}/malha_com_atributos/setores/gpkg/UF/PB/PB_setores_CD2022.gpkg",
    "ibge_censo2022/dicionario_de_dados_agregados_por_setores_censitarios_20260520.xlsx":
        f"{FTP}/dicionario_de_dados_agregados_por_setores_censitarios_20260520.xlsx",
    # Por bairro (sem valores sigilosos em João Pessoa; por setor há "X" em setores pequenos):
    # idade (crianças por faixa) e domicílios (água, esgoto, lixo; o total de domicílios está na parte 1)
    "ibge_censo2022/Agregados_por_bairros_demografia_BR.zip":
        f"{FTP}/Agregados_por_Bairro_csv/Agregados_por_bairros_demografia_BR.zip",
    "ibge_censo2022/Agregados_por_bairros_caracteristicas_domicilio1_BR_20261021.zip":
        f"{FTP}/Agregados_por_Bairro_csv/Agregados_por_bairros_caracteristicas_domicilio1_BR_20261021.zip",
    "ibge_censo2022/Agregados_por_bairros_caracteristicas_domicilio2_BR_20250417.zip":
        f"{FTP}/Agregados_por_Bairro_csv/Agregados_por_bairros_caracteristicas_domicilio2_BR_20250417.zip",
    # Rendimento da pessoa responsável pelo domicílio (divulgação própria do IBGE, maio de 2026)
    "ibge_censo2022/Agregados_por_bairros_renda_responsavel_BR_20260508_csv.zip":
        f"{FTP_RENDA}/Agregados_por_bairros_renda_responsavel_BR_20260508_csv.zip",
    "ibge_censo2022/dicionario_de_dados_renda_responsavel_20260508.xlsx":
        f"{FTP_RENDA}/dicionario_de_dados_renda_responsavel_20260508.xlsx",
}


def main(force: bool = False) -> None:
    for dest, url in ARQUIVOS.items():
        download(url, Path(dest), fonte=FONTE, force=force)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--force", action="store_true", help="rebaixa mesmo se o arquivo já existir")
    main(p.parse_args().force)
