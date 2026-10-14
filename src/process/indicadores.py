"""Cálculo dos indicadores por bairro (funções puras, testáveis isoladamente)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import IOU_COM_RESSALVA, IOU_COMPARAVEL

COMPARAVEL = "comparável"
COM_RESSALVA = "comparável com ressalva"
NAO_COMPARAVEL = "não comparável"


def iou(a, b) -> float:
    """Interseção sobre união de duas geometrias (no mesmo CRS métrico)."""
    uniao = a.union(b).area
    return float(a.intersection(b).area / uniao) if uniao else 0.0


def classificar_comparabilidade(iou_limites: pd.Series) -> pd.Series:
    """Classifica cada bairro pela sobreposição entre o limite de 2010 e o de 2022.

    Bairro sem limite em 2010 (IoU ausente) é não comparável.
    """
    return pd.Series(
        np.select(
            [iou_limites >= IOU_COMPARAVEL, iou_limites >= IOU_COM_RESSALVA],
            [COMPARAVEL, COM_RESSALVA],
            default=NAO_COMPARAVEL,
        ),
        index=iou_limites.index,
    )


def variacao(pop_2010: pd.Series, pop_2022: pd.Series, comparabilidade: pd.Series) -> pd.DataFrame:
    """Variação absoluta e percentual 2010→2022; vazia (NaN) quando não comparável."""
    ok = (comparabilidade != NAO_COMPARAVEL) & pop_2010.notna()
    var_abs = (pop_2022 - pop_2010).where(ok)
    var_pct = (100 * (pop_2022 - pop_2010) / pop_2010).where(ok & (pop_2010 > 0))
    return pd.DataFrame({"var_abs": var_abs.astype("Int64"), "var_pct": var_pct.round(2)})


def densidade(pop: pd.Series, area_km2: pd.Series) -> pd.Series:
    """Habitantes por km²."""
    return (pop / area_km2).round(1)
