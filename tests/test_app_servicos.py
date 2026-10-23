"""Testes das funções de apoio da página de serviços."""

import pandas as pd

from src.app import dados_servicos as d
from src.process import servicos as sv


def _dados():
    return d.carregar()


def test_ranking_menos_servicos_ordem_e_filtros():
    ind = _dados()["ind"]
    r = d.ranking_menos_servicos(ind, n=10)
    assert len(r) == 10
    assert r.hab_por_equipamento.is_monotonic_decreasing
    assert (r.pop_2022 >= sv.POP_MIN_RANKING).all()
    assert (r.equipamentos > 0).all()


def test_sem_escola_nem_ubs_nao_aparece_no_ranking():
    ind = _dados()["ind"]
    sem = d.sem_escola_nem_ubs(ind)
    assert (sem.escolas == 0).all() and (sem.ubs_usf == 0).all()
    assert not set(sem.cd_bairro) & set(d.ranking_menos_servicos(ind, n=64).cd_bairro)


def test_componentes_refazem_o_indice():
    ind = _dados()["ind"]
    c = d.componentes_indice(ind)
    media = c[["p_escola", "p_ubs", "p_verde"]].mean(axis=1)
    assert (media - ind.indice_acesso).abs().max() <= 0.1
    assert c[["p_escola", "p_ubs", "p_verde"]].stack().between(0, 100).all()


def test_servicos_do_bairro_bate_com_as_contagens():
    dados = _dados()
    ind = dados["ind"].set_index("cd_bairro")
    for cd in ind.index:
        lista = d.servicos_do_bairro(dados["pontos"], cd)
        esperado = ind.loc[cd, ["escolas", "escolas_complementares", "ubs_usf", "policlinicas", "upas", "hospitais"]].sum()
        assert len(lista) == esperado


def test_toda_camada_do_mapa_tem_cor():
    from src.app.servicos import COR_CAMADA

    assert set(d.SUBTIPO_CAMADA.values()) == set(d.CAMADAS) == set(COR_CAMADA)
    assert _dados()["pontos"].camada_mapa.notna().all()


def test_comparar():
    assert d.comparar(150, 100) == 50
    assert d.comparar(pd.NA, 100) is None


def test_texto_comparacao_sem_sinal_e_com_cor_certa():
    assert d.texto_comparacao(-30, distancia=True) == ("30% mais perto", "green")
    assert d.texto_comparacao(40, distancia=True) == ("40% mais longe", "red")
    assert d.texto_comparacao(29, distancia=False) == ("29% acima", "green")
    assert d.texto_comparacao(-13, distancia=False) == ("13% abaixo", "red")
    assert d.texto_comparacao(0.2, distancia=False) == ("na média", "gray")
    assert d.texto_comparacao(None, distancia=True) is None
