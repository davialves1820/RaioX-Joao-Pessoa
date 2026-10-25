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


# --- por órgão


def _orgaos():
    return pd.DataFrame({
        "ano": [2025] * 5,
        "cod_orgao": ["10", "10", "13", "06", "06"],
        "orgao": ["Secretaria Municipal de Educação e Cultura"] * 2 + ["Secretaria Municipal de Saúde"]
                 + ["Secretaria da Administração"] * 2,
        "orgao_sigla": ["SEDEC", "SEDEC", None, "SEAD", "SEAD"],
        "funcao": ["Educação", "Cultura", "Saúde", "Previdência Social", "Administração"],
        "v": [90.0, 10.0, 60.0, 30.0, 10.0],
    })


def test_resumo_orgaos_soma_100_e_mostra_a_area_principal():
    r = d.resumo_orgaos(_orgaos(), 2025, "v")
    assert list(r.cod_orgao) == ["10", "13", "06"]
    assert r.pct.sum() == pytest.approx(100)
    assert r.set_index("cod_orgao").loc["06", "area_principal"] == "Previdência Social"
    assert r.set_index("cod_orgao").loc["06", "pct_area_principal"] == pytest.approx(75)
    assert pd.isna(r.set_index("cod_orgao").loc["13", "sigla"])  # órgão sem sigla continua na lista


def test_orgaos_da_area():
    oa = d.orgaos_da_area(_orgaos(), 2025, "v", "Educação")
    assert list(oa.cod_orgao) == ["10"] and oa.pct.iloc[0] == pytest.approx(100)
    assert d.orgaos_da_area(_orgaos(), 2025, "v", "Urbanismo").empty


def test_nomes_de_unidades_e_orgaos():
    assert d.nome_unidade("SEDEC - AÇÕES DE GOVERNO") == "Ações de governo (SEDEC)"
    assert d.nome_unidade("CÂMARA MUNICIPAL - AÇÕES DE GOVERNO") == "Ações de governo (Câmara Municipal)"
    assert d.nome_unidade("INSTITUTO DE PREVIDÊNCIA DO MUNICIPIO - IPM") == "Instituto de Previdência do Municipio - IPM"
    assert d.nome_unidade("FUNDO DE APOIO AOS PEQUENOS NEGÓCIOS NO MUNICÍPIO") == \
        "Fundo de Apoio aos Pequenos Negócios no Município"
    assert d.nome_unidade("RECURSOS SOB A SUPERVISÃO DA SECRETARIA DA ADMINIS…").endswith("Adminis…")
    assert d.rotulo_orgao("Secretaria de Infraestrutura", "SEINFRA") == "Secretaria de Infraestrutura (SEINFRA)"
    assert d.rotulo_orgao("Câmara Municipal", None) == "Câmara Municipal"


def test_todo_orgao_dos_dados_tem_nome_oficial_com_fonte():
    from src.process.despesas_regras import NOMES_ORGAOS

    o = pd.read_parquet(d.PASTA / "orgaos.parquet")
    assert set(o.cod_orgao) <= set(NOMES_ORGAOS)
    assert all(nome and fonte for nome, _, fonte in NOMES_ORGAOS.values())
    assert (o.groupby("cod_orgao").orgao.first() == o.groupby("cod_orgao").cod_orgao.first().map(
        lambda c: NOMES_ORGAOS[c][0])).all()
