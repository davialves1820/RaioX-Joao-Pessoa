"""Censo 2010: população por bairro a partir da soma dos setores censitários.

Variável: Domicilio02, V001 = "Moradores em domicílios particulares e
domicílios coletivos" (população residente total do setor). A soma de todos os
setores de João Pessoa é igual ao total oficial do município (723.515).
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from src.config import COD_MUNICIPIO, DATA_RAW
from src.process.leitura import ler_csv_do_zip, para_inteiro

RAW = DATA_RAW / "ibge_censo2010"
ZIP_SETORES = RAW / "PB_20260615.zip"
ZIP_MALHA = RAW / "pb_setores_censitarios.zip"

# Código usado pelo IBGE para setores que não pertencem a nenhum bairro
COD_SEM_BAIRRO = COD_MUNICIPIO + "000"


def setores_2010() -> pd.DataFrame:
    """Setores de João Pessoa: cod_setor, cd_bairro, nm_bairro_2010, pop."""
    basico = ler_csv_do_zip(ZIP_SETORES, "/Basico_PB.csv")
    basico = basico[basico["Cod_municipio"] == COD_MUNICIPIO]
    dom02 = ler_csv_do_zip(ZIP_SETORES, "/Domicilio02_PB.csv", usecols=["Cod_setor", "V001"])
    df = basico[["Cod_setor", "Cod_bairro", "Nome_do_bairro"]].merge(
        dom02, on="Cod_setor", how="left", validate="1:1"
    )
    if df["V001"].isna().any():
        raise ValueError("há setores de João Pessoa sem registro em Domicilio02")
    return pd.DataFrame(
        {
            "cod_setor": df["Cod_setor"],
            "cd_bairro": df["Cod_bairro"],
            "nm_bairro_2010": df["Nome_do_bairro"],
            "pop": para_inteiro(df["V001"], "Domicilio02 V001 (2010)"),
        }
    )


def populacao_bairros_2010(setores: pd.DataFrame | None = None) -> pd.DataFrame:
    """Uma linha por bairro de 2010 (sem os 'demais setores'): cd_bairro, nm_bairro_2010, pop_2010, setores_2010."""
    s = setores_2010() if setores is None else setores
    s = s[s["cd_bairro"] != COD_SEM_BAIRRO]
    return (
        s.groupby(["cd_bairro", "nm_bairro_2010"], as_index=False)
        .agg(pop_2010=("pop", "sum"), setores_2010=("cod_setor", "count"))
        .sort_values("cd_bairro")
        .reset_index(drop=True)
    )


def malha_bairros_2010(setores: pd.DataFrame | None = None) -> gpd.GeoDataFrame:
    """Polígonos dos bairros de 2010, dissolvendo os setores pela coluna de bairro do arquivo Básico."""
    s = setores_2010() if setores is None else setores
    malha = gpd.read_file(f"zip://{ZIP_MALHA}!25SEE250GC_SIR.shp")
    malha = malha[malha["CD_GEOCODM"] == COD_MUNICIPIO]
    malha = malha.merge(
        s[["cod_setor", "cd_bairro"]], left_on="CD_GEOCODI", right_on="cod_setor", how="inner"
    )
    return malha[["cd_bairro", "geometry"]].dissolve("cd_bairro").reset_index()
