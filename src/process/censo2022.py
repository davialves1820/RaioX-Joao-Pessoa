"""Censo 2022: população por bairro (tabela oficial do IBGE) e malha de bairros."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from src.config import COD_MUNICIPIO, DATA_RAW
from src.process.leitura import ler_csv_do_zip, para_decimal, para_inteiro

RAW = DATA_RAW / "ibge_censo2022"
ZIP_BAIRROS = RAW / "Agregados_por_bairros_basico_BR_20260520.zip"
ZIP_MUNICIPIOS = RAW / "Agregados_por_municipios_basico_BR_20260520.zip"
GPKG_BAIRROS = RAW / "PB_bairros_CD2022.gpkg"


def populacao_bairros_2022() -> pd.DataFrame:
    """Uma linha por bairro de João Pessoa.

    Colunas: cd_bairro, nm_bairro, area_km2, pop_2022, domicilios_2022.
    Fonte: Agregados_por_bairros_basico_BR (v0001 = Total de pessoas;
    v0002 = Total de domicílios; AREA_KM2 = área do bairro na malha do Censo).
    """
    df = ler_csv_do_zip(ZIP_BAIRROS, "_basico_BR.csv")
    df = df[df["CD_MUN"] == COD_MUNICIPIO]
    out = pd.DataFrame(
        {
            "cd_bairro": df["CD_BAIRRO"],
            "nm_bairro": df["NM_BAIRRO"],
            "area_km2": para_decimal(df["AREA_KM2"]),
            "pop_2022": para_inteiro(df["v0001"], "v0001 (2022)"),
            "domicilios_2022": para_inteiro(df["v0002"], "v0002 (2022)"),
        }
    )
    return out.sort_values("cd_bairro").reset_index(drop=True)


def total_municipio_2022() -> int:
    """População total oficial de João Pessoa em 2022 (v0001 da tabela por município)."""
    df = ler_csv_do_zip(ZIP_MUNICIPIOS, "_basico_BR.csv")
    linha = df[df["CD_MUN"] == COD_MUNICIPIO]
    if len(linha) != 1:
        raise ValueError(f"esperava 1 linha para {COD_MUNICIPIO}, achei {len(linha)}")
    return int(para_inteiro(linha["v0001"], "v0001 município 2022").iloc[0])


def malha_bairros_2022() -> gpd.GeoDataFrame:
    """Polígonos dos bairros de João Pessoa na malha do Censo 2022 (CRS original: SIRGAS 2000)."""
    g = gpd.read_file(GPKG_BAIRROS)
    g = g[g["CD_MUN"] == COD_MUNICIPIO]
    return g[["CD_BAIRRO", "NM_BAIRRO", "geometry"]].rename(
        columns={"CD_BAIRRO": "cd_bairro", "NM_BAIRRO": "nm_bairro"}
    ).sort_values("cd_bairro").reset_index(drop=True)
