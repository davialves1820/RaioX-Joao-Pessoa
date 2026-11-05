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


def test_contagem_so_nos_anos_da_legislatura(dados):
    p = dados["producao"]
    pid = p["id_parlamentar"].iloc[0]
    c19 = d.contagem(p, pid, 19)
    esperado = p[(p["id_parlamentar"] == pid) & (p["ano"] >= 2025)].groupby("grupo")["materias"].sum().to_dict()
    assert c19 == esperado


def test_projetos_e_atuacao_do_vereador(dados):
    ver = d.vereadores_da_legislatura(dados["vereadores"], 19)
    pid = ver["id_parlamentar"].iloc[0]
    pj = d.projetos_do_vereador(dados["projetos"], pid, 19)
    assert pj["autores_ids"].str.split(";").map(lambda ids: str(pid) in ids).all()
    assert pj["ano"].between(2025, 2028).all()
    r = d.resumo_projetos(pj)
    assert sum(r.values()) == len(pj) and list(r) == SITUACOES
    at = d.atuacao_do_vereador(dados["materias"], pid, 19)
    assert at["grupo"].isin(d.ATUACAO).all()
    c = d.contagem(dados["producao"], pid, 19)
    assert len(at) == sum(c.get(g, 0) for g in d.ATUACAO)


def test_filtrar_por_texto_ano_autor_e_numero(dados):
    proj = dados["projetos"]
    assert len(d.filtrar(proj)) == len(proj)
    r = d.filtrar(proj, "saude")
    assert len(r) > 0 and r["busca"].str.contains("SAUDE").all()
    assert (d.filtrar(proj, ano=2025)["ano"] == 2025).all()
    p = proj.iloc[0]
    assert p["id_materia"] in set(d.filtrar(proj, str(p["numero"]), ano=p["ano"])["id_materia"])
    pid = int(proj["autores_ids"].dropna().iloc[0].split(";")[0])
    assert d.filtrar(proj, id_parlamentar=pid)["autores_ids"].str.split(";").map(lambda i: str(pid) in i).all()


def test_paginar():
    df = pd.DataFrame({"x": range(45)})
    pagina, paginas = d.paginar(df, 3)
    assert paginas == 3 and list(pagina["x"]) == list(range(40, 45))
    assert d.paginar(df, 99)[0]["x"].iloc[0] == 40
    assert d.paginar(df.iloc[0:0], 1)[1] == 1


def test_subsidio_do_vereador():
    sub = pd.DataFrame({"id_parlamentar": [1, 1, 2, 2], "ano_mes": ["202412", "202501", "202501", "202609"],
                        "valor": [10.0, 20.0, 30.0, 40.0], "cargo": ["Vereador"] * 4})
    assert d.sem_subsidio_desde(sub, 1, 19, "202609") == "202502"
    assert d.sem_subsidio_desde(sub, 2, 19, "202609") is None
    assert d.sem_subsidio_desde(sub, 3, 19, "202609") is None
    assert d.sem_subsidio_desde(sub, 1, 18, "202609") is None  # recebeu até o fim da 18ª
    assert d.subsidio_na_legislatura(sub, 2, 19) == (70.0, 2)
    assert d.ultimo_subsidio(sub, 2) == ("202609", 40.0, "Vereador")


def test_servidores_despesas_e_contas(dados):
    mes = dados["folha"]["ano_mes"].max()
    f = d.folha_do_mes(dados["folha"], mes)
    assert f["total"].is_monotonic_decreasing and "nome_servidor" not in f
    ano = int(dados["despesas"]["ano"].max())
    desp = d.despesas_do_ano(dados["despesas"], ano)
    assert desp["pct"].sum() == pytest.approx(100)
    hist = d.rgf_ultimo_por_ano(dados["rgf"])
    assert hist["ano"].is_unique
    assert d.situacao_rgf(2.4, 5.4, 5.7, 6) == "Dentro do limite"
    assert d.situacao_rgf(5.5, 5.4, 5.7, 6) == "Acima do limite de alerta"
    assert d.situacao_rgf(6.1, 5.4, 5.7, 6) == "Acima do limite máximo"


def test_formatos():
    assert d.fmt_mes("202609") == "09/2026"
    assert d.fmt_data("2026-11-03") == "03/11/2026"
    assert d.fmt_periodo("2025-01-01", "2028-12-31") == "01/01/2025 a 31/12/2028"
    assert d.fmt_periodo("2025-01-01", float("nan")) == "desde 01/01/2025"
