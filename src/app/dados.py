"""Carga dos dados processados e funções de apoio do dashboard (sem dependência do Streamlit)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.config import DATA_PROCESSED
from src.process.indicadores import COM_RESSALVA, NAO_COMPARAVEL


def carregar_indicadores(pasta: Path = DATA_PROCESSED) -> pd.DataFrame:
    df = pd.read_csv(pasta / "indicadores_bairros.csv", dtype={"cd_bairro": str})
    for c in ["pop_2010", "setores_2010", "var_abs"]:
        df[c] = df[c].astype("Int64")
    return df


def carregar_geojson(pasta: Path = DATA_PROCESSED) -> dict:
    return json.loads((pasta / "bairros_jp.geojson").read_text(encoding="utf-8"))


def carregar_totais(pasta: Path = DATA_PROCESSED) -> pd.DataFrame:
    return pd.read_csv(pasta / "totais_municipio.csv").set_index("ano")


def carregar_metadados(pasta: Path = DATA_PROCESSED) -> dict:
    return json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))


def ranking(
    ind: pd.DataFrame,
    *,
    crescimento: bool,
    metrica: str = "var_pct",
    n: int = 10,
    pop_min_2010: int = 0,
) -> pd.DataFrame:
    """Bairros que mais cresceram (crescimento=True) ou mais perderam população.

    Exclui bairros não comparáveis e os com população de 2010 abaixo de `pop_min_2010`.
    Só entram valores com o sinal pedido (um bairro que cresceu nunca aparece em "perderam").
    """
    if metrica not in ("var_pct", "var_abs"):
        raise ValueError(metrica)
    base = ind[
        (ind.comparabilidade != NAO_COMPARAVEL)
        & ind[metrica].notna()
        & (ind.pop_2010.fillna(0) >= pop_min_2010)
    ]
    base = base[base[metrica] > 0] if crescimento else base[base[metrica] < 0]
    return base.sort_values(metrica, ascending=not crescimento).head(n).reset_index(drop=True)


def posicao(ind: pd.DataFrame, cd_bairro: str, coluna: str) -> tuple[int, int] | None:
    """Posição do bairro (1 = maior valor) entre os bairros com valor na coluna."""
    validos = ind[ind[coluna].notna()]
    if cd_bairro not in set(validos.cd_bairro):
        return None
    ordem = validos[coluna].rank(ascending=False, method="min")
    return int(ordem[validos.cd_bairro == cd_bairro].iloc[0]), len(validos)


# --- formatação pt-BR


def fmt_int(v) -> str:
    if pd.isna(v):
        return "—"
    return f"{int(v):,}".replace(",", ".")


def fmt_dec(v, casas: int = 1) -> str:
    if pd.isna(v):
        return "—"
    s = f"{float(v):,.{casas}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_var_int(v) -> str:
    if pd.isna(v):
        return "—"
    return ("+" if v > 0 else "−" if v < 0 else "") + fmt_int(abs(int(v)))


def fmt_var_pct(v) -> str:
    if pd.isna(v):
        return "—"
    return ("+" if v > 0 else "−" if v < 0 else "") + fmt_dec(abs(float(v))) + "%"


def fmt_pct(v, casas: int = 1, sinal: bool = False) -> str:
    if pd.isna(v):
        return "—"
    if sinal:
        return ("+" if v > 0 else "−" if v < 0 else "") + fmt_dec(abs(float(v)), casas) + "%"
    return fmt_dec(v, casas) + "%"


def fmt_reais(v) -> str:
    """R$ com centavos: 'R$ 1.234.567,89'."""
    if pd.isna(v):
        return "—"
    return ("−" if v < 0 else "") + "R$ " + fmt_dec(abs(float(v)), 2)


def tabela_br(df: pd.DataFrame, inteiros=(), decimais: dict | None = None, pct: dict | None = None,
              pct_sinal: dict | None = None, reais=(), variacao_int=()):
    """Mostra os números no padrão brasileiro (14.226; 12,8) sem transformá-los em texto.

    O formato "localized" do Streamlit segue o idioma do navegador; aqui o formato é fixo. Como só a
    exibição muda (pandas Styler), a ordenação das colunas continua numérica. Não use `format` no
    `column_config` dessas colunas: ele tem precedência sobre o Styler.
    """
    fmt = {c: (lambda v: fmt_int(v if pd.isna(v) else round(v))) for c in inteiros}
    fmt |= {c: (lambda v, k=k: fmt_dec(v, k)) for c, k in (decimais or {}).items()}
    fmt |= {c: (lambda v, k=k: fmt_pct(v, k)) for c, k in (pct or {}).items()}
    fmt |= {c: (lambda v, k=k: fmt_pct(v, k, sinal=True)) for c, k in (pct_sinal or {}).items()}
    fmt |= {c: fmt_reais for c in reais}
    fmt |= {c: fmt_var_int for c in variacao_int}
    return df.style.format(fmt, na_rep="—")


def rotulo(ind_row) -> str:
    """Nome do bairro com marca † quando a variação é comparável só com ressalva."""
    return ind_row.nm_bairro + (" †" if ind_row.comparabilidade == COM_RESSALVA else "")
