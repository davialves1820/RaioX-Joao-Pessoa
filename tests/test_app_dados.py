"""Testes das funções de apoio do dashboard (ranking, posição, formatação)."""

import pandas as pd

from src.app import dados as d
from src.process.indicadores import NAO_COMPARAVEL


def _ind():
    return d.carregar_indicadores()


def test_ranking_respeita_sinal_filtros_e_ordem():
    ind = _ind()
    cresc = d.ranking(ind, crescimento=True, n=10, pop_min_2010=1000)
    perd = d.ranking(ind, crescimento=False, n=10, pop_min_2010=1000)
    assert (cresc.var_pct > 0).all() and cresc.var_pct.is_monotonic_decreasing
    assert (perd.var_pct < 0).all() and perd.var_pct.is_monotonic_increasing
    for r in (cresc, perd):
        assert (r.comparabilidade != NAO_COMPARAVEL).all()
        assert (r.pop_2010 >= 1000).all()
        assert len(r) <= 10


def test_ranking_populacao_minima_exclui_bairro_pequeno():
    ind = _ind()
    sem_filtro = d.ranking(ind, crescimento=True, n=64, pop_min_2010=0)
    com_filtro = d.ranking(ind, crescimento=True, n=64, pop_min_2010=1000)
    assert "Barra de Gramame" in set(sem_filtro.nm_bairro)
    assert "Barra de Gramame" not in set(com_filtro.nm_bairro)


def test_posicao():
    ind = _ind()
    assert d.posicao(ind, "2507507039", "pop_2022") == (1, 64)  # Mangabeira
    assert d.posicao(ind, "2507507064", "var_pct") is None  # Mussuré: sem variação


def test_formatacao_pt_br():
    assert d.fmt_int(833932) == "833.932"
    assert d.fmt_dec(1234.56, 1) == "1.234,6"
    assert d.fmt_var_pct(-6.69) == "−6,7%"
    assert d.fmt_var_int(110417) == "+110.417"
    assert d.fmt_int(pd.NA) == "—"


def test_tabela_br_formata_sem_virar_texto():
    df = pd.DataFrame({"pop": [14226, 9], "verde": [12.84, None], "var": [-6.7, 2.0], "rs": [1234567.891, None]})
    s = d.tabela_br(df, inteiros=["pop"], decimais={"verde": 1}, pct_sinal={"var": 1}, reais=["rs"])
    html = s.to_html()
    for esperado in ["14.226", "12,8", "−6,7%", "+2,0%", "R$ 1.234.567,89", "—"]:
        assert esperado in html
    # os dados continuam numéricos: a ordenação no app é numérica
    assert "None" not in html and "nan" not in html
    assert s.data["pop"].dtype.kind in "iu" and s.data["verde"].dtype.kind == "f"
