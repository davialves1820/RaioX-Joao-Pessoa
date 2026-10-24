"""Testes do Censo 2022 por bairro: rendimento, saneamento e crianças (src.process.censo_bairros)."""

import json

import pandas as pd
import pytest

from src.config import DATA_PROCESSED, DATA_RAW
from src.process import censo_bairros as cb


@pytest.fixture(scope="module")
def cen() -> pd.DataFrame:
    return pd.read_csv(DATA_PROCESSED / "censo_bairros.csv", dtype={"cd_bairro": str})


@pytest.fixture(scope="module")
def meta() -> dict:
    return json.loads((DATA_PROCESSED / "censo_bairros_meta.json").read_text(encoding="utf-8"))


def test_numero_do_ibge():
    assert cb.numero("4530,17") == pytest.approx(4530.17)
    assert cb.numero("6598.5") == pytest.approx(6598.5)
    assert cb.numero("3000") == 3000
    assert cb.numero("X") is None and cb.numero("") is None and cb.numero(None) is None
    with pytest.raises(ValueError):
        cb.numero("1.234,5")


def test_um_registro_por_bairro(cen):
    ind = pd.read_csv(DATA_PROCESSED / "indicadores_bairros.csv", dtype={"cd_bairro": str})
    assert set(cen.cd_bairro) == set(ind.cd_bairro) and cen.cd_bairro.is_unique


def test_percentuais_entre_0_e_100(cen):
    for c in ["pct_agua_rede", "pct_esgoto_rede", "pct_lixo_coletado"]:
        assert cen[c].dropna().between(0, 100).all()
        # vazio só onde não há domicílio particular (Mussuré: 3 moradores, 0 domicílios particulares)
        assert cen.loc[cen.domicilios > 0, c].notna().all()


def test_renda_coerente(cen, meta):
    r = cen.dropna(subset=["renda_mediana"])
    assert (r.renda_mediana > 0).all() and (r.renda_media > 0).all()
    # só pode faltar o que o IBGE não publicou, e isso fica registrado
    faltam = set(cen.loc[cen.renda_mediana.isna(), "cd_bairro"])
    assert faltam == set(meta["bairros_sem_linha"].get("renda_mediana", []))


def test_nenhum_valor_sigiloso_estimado(cen, meta):
    # se o IBGE tivesse "X", o valor ficaria vazio; aqui confirmamos a contagem
    for col, n in meta["valores_sigilosos_X"].items():
        assert cen[col].isna().sum() >= n


def test_criancas_batem_com_a_populacao_do_bairro(cen):
    ind = pd.read_csv(DATA_PROCESSED / "indicadores_bairros.csv", dtype={"cd_bairro": str}).set_index("cd_bairro")
    c = cen.set_index("cd_bairro")
    assert (c.pop_0a14 <= ind.pop_2022.reindex(c.index)).all()


@pytest.mark.skipif(not (DATA_RAW / "ibge_censo2022" / cb.ARQ["renda"]).exists(), reason="dados brutos ausentes")
def test_reprocessar_da_o_mesmo_resultado(cen):
    novo, _ = cb.montar()
    assert len(novo) == len(cen.dropna(subset=["domicilios"]))
    assert novo.renda_mediana.sum() == pytest.approx(cen.renda_mediana.sum())
