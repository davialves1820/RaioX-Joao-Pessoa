"""Testes dos serviços públicos por bairro (gerados por src.process.servicos).

Os testes sobre data/processed/servicos/ rodam sempre. Os que recalculam a partir dos arquivos
brutos (data/raw, fora do git) só rodam se eles estiverem presentes.
"""

import json

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely

from src.config import CRS_METRICO, DATA_PROCESSED, DATA_RAW
from src.process import servicos as sv

SAIDA = DATA_PROCESSED / "servicos"
STATUS = {sv.STATUS_BAIRRO, sv.STATUS_FORA_BAIRRO, sv.STATUS_FORA_MUNICIPIO, sv.STATUS_SEM_COORD}
TEM_BRUTOS = (DATA_RAW / "inep" / "catalogo_escolas_PB.csv").exists() and (
    DATA_RAW / "cnes" / "estabelecimentos_250750.json"
).exists()
brutos = pytest.mark.skipif(not TEM_BRUTOS, reason="dados brutos ausentes (rode python -m src.collect)")


@pytest.fixture(scope="module")
def ind() -> pd.DataFrame:
    return pd.read_csv(SAIDA / "indicadores_servicos.csv", dtype={"cd_bairro": str})


@pytest.fixture(scope="module")
def pontos() -> gpd.GeoDataFrame:
    return gpd.read_file(SAIDA / "pontos_servicos.geojson")


@pytest.fixture(scope="module")
def nao_atrib() -> pd.DataFrame:
    return pd.read_csv(SAIDA / "pontos_nao_atribuidos.csv")


@pytest.fixture(scope="module")
def meta() -> dict:
    return json.loads((SAIDA / "metadados.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def todos(pontos, nao_atrib) -> pd.DataFrame:
    """Todos os pontos da fonte filtrada: os do mapa mais os sem coordenada."""
    sem = nao_atrib[nao_atrib.status == sv.STATUS_SEM_COORD]
    return pd.concat([pontos.drop(columns="geometry"), sem], ignore_index=True)


# --- todo ponto atribuído a exatamente um bairro


def test_ids_unicos(todos):
    assert not todos["id"].duplicated().any()


def test_status_validos(todos):
    assert set(todos["status"]) <= STATUS


def test_ponto_em_bairro_tem_um_bairro_valido(pontos, ind):
    em_bairro = pontos[pontos.status == sv.STATUS_BAIRRO]
    assert em_bairro["cd_bairro"].notna().all()
    assert set(em_bairro["cd_bairro"]) <= set(ind["cd_bairro"])
    # um bairro por ponto: cd_bairro é um único código, não uma lista
    assert em_bairro["cd_bairro"].str.fullmatch(r"\d{10}").all()


def test_ponto_em_bairro_cai_dentro_do_seu_bairro(pontos):
    bairros = gpd.read_file(DATA_PROCESSED / "bairros_jp.geojson").to_crs(CRS_METRICO).set_index("cd_bairro")
    em_bairro = pontos[pontos.status == sv.STATUS_BAIRRO].to_crs(CRS_METRICO)
    # a malha do app é simplificada (5 m); a atribuição usa a malha original
    d = em_bairro.geometry.distance(bairros.geometry.reindex(em_bairro.cd_bairro), align=False)
    assert (d < 10).all()


def test_ponto_fora_de_bairro_nao_tem_bairro(todos):
    fora = todos[todos.status != sv.STATUS_BAIRRO]
    assert fora["cd_bairro"].isna().all()


def test_nao_atribuidos_listados_com_motivo(pontos, nao_atrib):
    """Pontos sem coordenada ou fora dos bairros são reportados, não descartados em silêncio."""
    fora_no_mapa = set(pontos.loc[pontos.status != sv.STATUS_BAIRRO, "id"])
    assert fora_no_mapa <= set(nao_atrib["id"])
    assert nao_atrib["status"].isin(STATUS - {sv.STATUS_BAIRRO}).all()
    sem = nao_atrib[nao_atrib.status == sv.STATUS_SEM_COORD]
    assert sem[["lat", "lon"]].isna().all().all()


# --- contagens batendo com o total da fonte filtrada por João Pessoa


def test_pontos_somam_o_total_da_fonte_filtrada(todos, meta):
    por_camada = todos.groupby("camada").size().to_dict()
    assert por_camada == meta["total_fonte_filtrada"]
    for chave, contagem in meta["pontos_por_status"].items():
        camada, subtipo = chave.split(" | ")
        sub = todos[(todos.camada == camada) & (todos.subtipo == subtipo)]
        assert sub.groupby("status").size().reindex(list(contagem), fill_value=0).to_dict() == contagem


def test_funil_fecha(meta):
    e, s = meta["funil"]["escolas"], meta["funil"]["saude"]
    assert e["publicas"] - e["paralisadas_ou_extintas"] == e["publicas_em_funcionamento"]
    assert e["publicas_em_funcionamento"] == meta["total_fonte_filtrada"]["escola"]
    assert s["sem_cadastros_de_regulacao"] == meta["total_fonte_filtrada"]["saude"]
    assert s["cnes_joao_pessoa"] >= s["tipos_pedidos"] >= s["ativos"] >= s["rede_sus_publicos_ou_atendem_sus"]


def test_contagens_por_bairro_batem_com_os_pontos(ind, pontos):
    em_bairro = pontos[pontos.status == sv.STATUS_BAIRRO]
    colunas = {sv.ESCOLA_REGULAR: "escolas", sv.ESCOLA_COMPLEMENTAR: "escolas_complementares",
               "UBS/USF": "ubs_usf", "Policlínica": "policlinicas", "UPA / pronto atendimento": "upas",
               "Hospital": "hospitais"}
    for subtipo, col in colunas.items():
        esperado = em_bairro[em_bairro.subtipo == subtipo].groupby("cd_bairro").size()
        obtido = ind.set_index("cd_bairro")[col]
        assert obtido.sum() == len(em_bairro[em_bairro.subtipo == subtipo])
        assert (obtido.reindex(esperado.index) == esperado).all(), col


@brutos
def test_total_recalculado_das_fontes_brutas(meta):
    cat = pd.read_csv(DATA_RAW / "inep" / "catalogo_escolas_PB.csv", dtype=str, encoding="utf-8-sig")
    jp = cat[(cat["Município"] == "João Pessoa") & (cat["Categoria Administrativa"] == "Pública")]
    ativas = ~jp["Restrição de Atendimento"].fillna("").str.contains("PARALISADA|EXTINTA")
    assert int(ativas.sum()) == meta["total_fonte_filtrada"]["escola"]

    e = pd.DataFrame(json.loads((DATA_RAW / "cnes" / "estabelecimentos_250750.json").read_text(encoding="utf-8")))
    e = e[e["codigo_tipo_unidade"].isin(sv.GRUPOS_SAUDE) & e["codigo_motivo_desabilitacao_estabelecimento"].isna()]
    publico = e["descricao_natureza_juridica_estabelecimento"].astype(str).str.startswith("1")
    e = e[publico | (e["estabelecimento_faz_atendimento_ambulatorial_sus"] == "SIM")]
    e = e[~e["nome_fantasia"].fillna("").str.contains("REGULACAO")]
    assert len(e) == meta["total_fonte_filtrada"]["saude"]


# --- distâncias, áreas e índice


DIST = ["dist_escola_centroide_m", "dist_escola_m", "dist_ubs_centroide_m", "dist_ubs_m"]


def test_nenhuma_distancia_negativa_ou_ausente(ind):
    assert ind[DIST].notna().all().all()
    assert (ind[DIST] >= 0).all().all()


def test_distancia_plausivel(ind):
    # João Pessoa mede uns 20 km de ponta a ponta: nenhuma distância à unidade mais próxima passa disso
    assert (ind[DIST] < 20000).all().all()


def test_distancia_mais_proxima_em_metros():
    o = gpd.GeoSeries([shapely.Point(0, 0), shapely.Point(10, 0)], crs=CRS_METRICO)
    d = gpd.GeoSeries([shapely.Point(3, 4), shapely.Point(100, 0)], crs=CRS_METRICO)
    np.testing.assert_allclose(sv.distancia_mais_proxima(o, d), [5.0, np.hypot(7, 4)])


def test_distancia_recusa_graus():
    o = gpd.GeoSeries([shapely.Point(-34.9, -7.1)], crs="EPSG:4326")
    with pytest.raises(ValueError):
        sv.distancia_mais_proxima(o, o)


def test_area_verde_nao_passa_da_area_do_bairro(ind):
    assert (ind["area_verde_m2"] >= 0).all()
    assert (ind["area_verde_m2"] <= ind["area_km2_calc"] * 1e6 * 1.001).all()


def test_area_verde_dos_bairros_nao_passa_da_uniao(ind, meta):
    assert ind["area_verde_m2"].sum() <= meta["areas_verdes"]["area_sem_sobreposicao_m2"] + 1


def test_indice_entre_0_e_100(ind):
    assert ind["indice_acesso"].between(0, 100).all()


def test_indice_premia_quem_esta_melhor_nos_tres():
    t = pd.DataFrame({"dist_escola_m": [100, 500, 900], "dist_ubs_m": [200, 600, 1000],
                      "area_verde_m2_hab": [10.0, 2.0, 0.0]})
    i = sv.indice_acesso(t)
    assert i.iloc[0] == 100.0
    assert i.is_monotonic_decreasing


def test_ranking_respeita_populacao_minima(ind, meta):
    assert (ind.loc[ind.entra_no_ranking, "pop_2022"] >= meta["pop_min_ranking"]).all()
    assert (ind.loc[~ind.entra_no_ranking, "pop_2022"] < meta["pop_min_ranking"]).all()
