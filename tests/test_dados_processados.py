"""Testes de sanidade sobre os arquivos em data/processed/ (gerados por src.process.build)."""

import json

import geopandas as gpd
import pandas as pd
import pytest

from src.config import DATA_PROCESSED, TOLERANCIA_TOTAL_MUNICIPIO
from src.process.indicadores import NAO_COMPARAVEL


@pytest.fixture(scope="module")
def ind() -> pd.DataFrame:
    return pd.read_csv(DATA_PROCESSED / "indicadores_bairros.csv", dtype={"cd_bairro": str})


@pytest.fixture(scope="module")
def geo() -> gpd.GeoDataFrame:
    return gpd.read_file(DATA_PROCESSED / "bairros_jp.geojson")


@pytest.fixture(scope="module")
def totais() -> pd.DataFrame:
    return pd.read_csv(DATA_PROCESSED / "totais_municipio.csv")


@pytest.mark.parametrize("ano", [2010, 2022])
def test_soma_dos_bairros_proxima_do_total_do_municipio(totais, ano):
    t = totais.set_index("ano").loc[ano]
    assert t.soma_bairros <= t.pop_municipio
    assert t.soma_bairros == pytest.approx(t.pop_municipio, rel=TOLERANCIA_TOTAL_MUNICIPIO)


def test_soma_dos_bairros_bate_com_indicadores(ind, totais):
    t = totais.set_index("ano")
    assert ind.pop_2022.sum() == t.loc[2022, "soma_bairros"]
    assert ind.pop_2010.sum() == t.loc[2010, "soma_bairros"]


def test_nenhum_bairro_sem_geometria(ind, geo):
    assert set(ind.cd_bairro) == set(geo.cd_bairro)
    assert geo.geometry.notna().all()
    assert not geo.geometry.is_empty.any()
    assert geo.geometry.is_valid.all()


def test_geometrias_nao_se_sobrepoem(geo):
    g = geo.to_crs("EPSG:31985")
    soma = g.area.sum()
    assert soma - g.geometry.union_all().area < 1e-6 * soma


def test_nenhuma_populacao_negativa(ind):
    assert (ind.pop_2022 >= 0).all()
    assert (ind.pop_2010.dropna() >= 0).all()
    assert (ind.domicilios_2022 >= 0).all()


def test_areas_positivas(ind):
    assert (ind.area_km2 > 0).all()


def test_codigos_unicos_e_do_municipio(ind):
    assert ind.cd_bairro.is_unique
    assert ind.cd_bairro.str.fullmatch(r"2507507\d{3}").all()


def test_variacao_consistente(ind):
    comp = ind[ind.comparabilidade != NAO_COMPARAVEL]
    assert (comp.var_abs == comp.pop_2022 - comp.pop_2010).all()
    nao = ind[ind.comparabilidade == NAO_COMPARAVEL]
    assert nao.var_abs.isna().all() and nao.var_pct.isna().all()


def test_densidade_consistente(ind):
    assert ((ind.pop_2022 / ind.area_km2).round(1) - ind.densidade_2022).abs().max() < 0.1


def test_metadados_rastreiam_arquivos_brutos():
    meta = json.loads((DATA_PROCESSED / "metadados.json").read_text(encoding="utf-8"))
    brutos = meta["arquivos_brutos"]
    assert brutos, "manifesto de arquivos brutos vazio"
    for nome, info in brutos.items():
        assert info["url"].startswith("https://"), nome
        assert len(info["sha256"]) == 64, nome
