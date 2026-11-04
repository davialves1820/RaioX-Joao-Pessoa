"""Testes das funções de apoio da página da Câmara."""

import pandas as pd
import pytest

from src.app import dados_camara as d
from src.process.camara import SITUACOES


@pytest.fixture(scope="module")
def dados():
    return d.carregar()


def test_vereadores_em_ordem_alfabetica_sem_repeticao(dados):
    for leg in d.LEGISLATURAS:
        v = d.vereadores_da_legislatura(dados["vereadores"], leg)
        assert v["id_parlamentar"].is_unique
        nomes = [d.normalizar(n) for n in v["nome"]]
        assert nomes == sorted(nomes)
        assert len(v) >= 29


def test_producao_da_legislatura_so_nos_anos_dela(dados):
    p = dados["producao"]
    t19 = d.producao_por_vereador(p, 19)
    assert t19.values.sum() == p.loc[p["ano"] >= 2025, "materias"].sum()
    assert list(t19.columns) == [c for c in d.ORDEM_GRUPOS if c in t19.columns]


def test_projetos_do_vereador_tem_o_vereador_como_autor(dados):
    proj = dados["projetos"]
    ver = d.vereadores_da_legislatura(dados["vereadores"], 19)
    pid = ver["id_parlamentar"].iloc[0]
    pj = d.projetos_do_vereador(proj, pid, 19)
    assert pj["autores_ids"].str.split(";").map(lambda ids: str(pid) in ids).all()
    assert pj["ano"].between(2025, 2028).all()
    assert sum(d.resumo_projetos(pj).values()) == len(pj)
    assert list(d.resumo_projetos(pj)) == SITUACOES


def test_situacao_por_ano_soma_os_projetos(dados):
    proj = dados["projetos"]
    s = d.situacao_por_ano(proj)
    assert s.values.sum() == len(proj)
    assert list(s.columns) == SITUACOES


def test_busca_sem_acento_e_por_autor(dados):
    proj = dados["projetos"]
    assert d.buscar_projetos(proj, "").empty
    r = d.buscar_projetos(proj, "saude")
    assert len(r) > 0 and r["ementa"].map(d.normalizar).str.contains("SAUDE").all()
    autor = proj["autores"].dropna().iloc[0].split(";")[0]
    assert len(d.buscar_projetos(proj, autor)) > 0


def test_sem_subsidio_desde():
    sub = pd.DataFrame({"id_parlamentar": [1, 1, 2, 2], "ano_mes": ["202412", "202501", "202501", "202609"],
                        "valor": [1, 1, 1, 1], "cargo": ["Vereador"] * 4})
    assert d.sem_subsidio_desde(sub, 1, 19, "202609") == "202502"
    assert d.sem_subsidio_desde(sub, 2, 19, "202609") is None
    assert d.sem_subsidio_desde(sub, 3, 19, "202609") is None
    assert d.sem_subsidio_desde(sub, 1, 18, "202609") is None  # recebeu até o fim da 18ª


def test_folha_mensal_e_formatos(dados):
    m = d.folha_mensal(dados["folha"])
    assert m.values.sum() == pytest.approx(dados["folha"]["total"].sum())
    assert d.fmt_mes("202609") == "09/2026"
    assert d.fmt_periodo("2025-01-01", "2028-12-31") == "01/01/2025 a 31/12/2028"
    assert d.fmt_periodo("2025-01-01", float("nan")) == "desde 01/01/2025"
