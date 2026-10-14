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
