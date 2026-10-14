"""Testes unitários das funções de cálculo e leitura."""

import pandas as pd
import pytest
from shapely.geometry import box

from src.process.indicadores import (
    COM_RESSALVA,
    COMPARAVEL,
    NAO_COMPARAVEL,
    classificar_comparabilidade,
    densidade,
    iou,
    variacao,
)
from src.process.leitura import para_decimal, para_inteiro


def test_iou():
    assert iou(box(0, 0, 2, 2), box(0, 0, 2, 2)) == 1.0
    assert iou(box(0, 0, 2, 2), box(1, 0, 3, 2)) == pytest.approx(1 / 3)
    assert iou(box(0, 0, 1, 1), box(5, 5, 6, 6)) == 0.0


def test_classificar_comparabilidade():
    s = pd.Series([0.99, 0.90, 0.80, 0.75, 0.5, None])
    assert classificar_comparabilidade(s).tolist() == [
        COMPARAVEL, COMPARAVEL, COM_RESSALVA, COM_RESSALVA, NAO_COMPARAVEL, NAO_COMPARAVEL,
    ]


def test_variacao_omite_nao_comparaveis():
    v = variacao(
        pd.Series([100, 100, 100], dtype="Int64"),
        pd.Series([150, 80, 300]),
        pd.Series([COMPARAVEL, COM_RESSALVA, NAO_COMPARAVEL]),
    )
    assert v.var_abs.tolist()[:2] == [50, -20]
    assert pd.isna(v.var_abs.iloc[2])
    assert v.var_pct.tolist()[:2] == [50.0, -20.0]
    assert pd.isna(v.var_pct.iloc[2])


def test_densidade():
    assert densidade(pd.Series([1000]), pd.Series([0.5])).iloc[0] == 2000.0


def test_para_inteiro_recusa_valor_sigiloso():
    with pytest.raises(ValueError, match="não numéricos"):
        para_inteiro(pd.Series(["10", "X"]), "teste")


def test_para_decimal_com_virgula():
    assert para_decimal(pd.Series(["1,5678752"])).iloc[0] == pytest.approx(1.5678752)
