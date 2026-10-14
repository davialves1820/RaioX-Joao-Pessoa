"""Leitura dos arquivos brutos (data/raw) sem extraí-los no disco."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd


def ler_csv_do_zip(zip_path: Path, sufixo: str, **kwargs) -> pd.DataFrame:
    """Lê o único CSV do zip cujo nome termina com `sufixo`.

    Os CSVs do IBGE usam ';' como separador e codificação latin1.
    """
    with zipfile.ZipFile(zip_path) as z:
        nomes = [n for n in z.namelist() if n.lower().endswith(sufixo.lower())]
        if len(nomes) != 1:
            raise FileNotFoundError(f"esperava 1 arquivo '*{sufixo}' em {zip_path.name}, achei {nomes}")
        with z.open(nomes[0]) as f:
            return pd.read_csv(f, sep=";", encoding="latin1", dtype=str, **kwargs)


def para_inteiro(serie: pd.Series, nome: str) -> pd.Series:
    """Converte para inteiro e falha se houver valor não numérico.

    O IBGE marca valores sigilosos com 'X'. Nunca os trocamos por estimativas:
    se aparecerem, o pipeline para e o caso precisa ser tratado explicitamente.
    """
    s = serie.str.strip()
    invalidos = s[~s.str.fullmatch(r"\d+", na=False)]
    if len(invalidos):
        raise ValueError(f"{nome}: valores não numéricos {invalidos.unique()[:10].tolist()}")
    return s.astype("int64")


def para_decimal(serie: pd.Series) -> pd.Series:
    """Converte números com vírgula decimal ('1,5678') para float."""
    return pd.to_numeric(serie.str.strip().str.replace(",", ".", regex=False), errors="raise")
