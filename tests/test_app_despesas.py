"""Testes das funções de apoio da página de despesas."""

import pandas as pd
import pytest

from src.app import dados_despesas as d


@pytest.fixture(scope="module")
def dados():
    return d.carregar()


def test_coluna():
    assert d.coluna("empenhado", True) == "empenhado_corrigido"
    assert d.coluna("pago", False) == "pago"
    with pytest.raises(ValueError):
        d.coluna("liquidado_x", False)


def test_filtrar_poder_e_transferencias(dados):
    c = dados["cubo"]
    assert set(d.filtrar(c, "Legislativo", False)["poder"]) == {"Legislativo"}
    assert not d.filtrar(c, "Todos", True)["intra"].any()
    assert len(d.filtrar(c, "Todos", False)) == len(c)


def test_status_e_variacao_so_entre_anos_completos(dados):
    meta = dados["meta"]
    tot = d.total_por_ano(dados["cubo"], "empenhado")
    assert d.status_ano(2016, meta) == "incompleto"
    assert d.status_ano(meta["ano_parcial"], meta) == "parcial"
    assert d.variacao_pct(tot, 2016, meta) is None
    assert d.variacao_pct(tot, 2017, meta) is None  # comparação com 2016
    assert d.variacao_pct(tot, meta["ano_parcial"], meta) is None
    assert d.variacao_pct(tot, 2024, meta) == pytest.approx(100 * (tot[2024] / tot[2023] - 1))


def test_por_habitante_sem_populacao_fica_vazio(dados):
    tot = d.total_por_ano(dados["cubo"], "empenhado")
    pc = d.por_habitante(tot, dados["populacao"])
    assert pd.isna(pc[2023])
    assert pc[2024] > 0


def test_participacao_licitacao_soma_100(dados):
    part = d.participacao_licitacao(dados["cubo"], "empenhado")
    assert list(part.columns) == d.ORDEM_LICITACAO
    assert (part.sum(axis=1).round(1) == 100).all()


def test_ranking_fornecedores(dados):
    cred = dados["credores"]
    rk = d.ranking_fornecedores(cred, (2024, 2025), "empenhado", n=10)
    assert len(rk) == 10 and rk["empenhado"].is_monotonic_decreasing
    publicos = set(cred.loc[cred.entidade_publica, "cnpj"])
    assert not set(rk["cnpj"]) & publicos


def test_buscar_credores_por_nome_e_cnpj(dados):
    cred = dados["credores"]
    por_nome = d.buscar_credores(cred, "energisa")
    assert len(por_nome) and por_nome["nome_credor"].str.contains("ENERGISA").all()
    assert "09095183000140" in set(d.buscar_credores(cred, "09.095.183")["cnpj"])
    assert d.buscar_credores(cred, "ab").empty


def test_fmt_reais():
    assert d.fmt_reais(4_856_505_655) == "R$ 4,86 bi"
    assert d.fmt_reais(123_456_789) == "R$ 123,5 mi"
    assert d.fmt_reais(950) == "R$ 950"
    assert d.fmt_reais_inteiro(1234567.891) == "R$ 1.234.567,89"


def test_frases_resumo(dados):
    c = dados["cubo"]
    frase = d.resumo_areas(c, 2025, "empenhado")
    assert frase.startswith("Saúde (") and "somaram" in frase
    assert d.lista_pt(["a", "b", "c"]) == "a, b e c"
    part = d.participacao_licitacao(c, "empenhado")
    assert d.resumo_licitacao(part, 2025).count("%") == 3
    rk = d.ranking_fornecedores(dados["credores"], (2025, 2025), "empenhado", n=10)
    assert 0 < d.fatia_do_ranking(dados["credores"], rk, (2025, 2025), "empenhado") < 100


def test_meses_de_pico_usa_so_anos_completos():
    dados = d.carregar()
    df = d.filtrar(dados["cubo"])
    pico, anos = d.meses_de_pico(df, "empenhado", dados["meta"])
    assert all(d.anos_comparaveis(a, dados["meta"]) for a in anos)
    assert pico.sum() == len(anos)


def test_gasto_por_funcao_bate_com_o_cubo():
    dados = d.carregar()
    g = d.gasto_por_funcao(dados["cubo"], dados["populacao"], dados["meta"])
    assert all(d.anos_comparaveis(int(a), dados["meta"]) for a in g.index)
    base = d.filtrar(dados["cubo"], "Todos", sem_intra=True)
    for funcao in ["Saúde", "Educação"]:
        esperado = base[base.funcao == funcao].groupby("ano")["empenhado_corrigido"].sum()
        assert (g[funcao] - esperado.reindex(g.index)).abs().max() < 0.01
    # sem população oficial em 2023: valor por habitante vazio
    if 2023 in g.index:
        assert pd.isna(g.loc[2023, "Saúde por habitante"])
