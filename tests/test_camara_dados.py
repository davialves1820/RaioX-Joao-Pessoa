"""Testes sobre os arquivos em data/processed/camara (gerados por src.process.camara)."""

import json
import re

import pandas as pd
import pytest

from src.config import DATA_PROCESSED, DATA_RAW, LEGISLATURAS_CAMARA
from src.process import camara

P = DATA_PROCESSED / "camara"
RAW = DATA_RAW / "camara_sapl"
sem_brutos = pytest.mark.skipif(not RAW.exists(), reason="dados brutos (data/raw) ausentes")


@pytest.fixture(scope="module")
def ver():
    return pd.read_csv(P / "vereadores.csv")


@pytest.fixture(scope="module")
def prod():
    return pd.read_csv(P / "producao.csv")


@pytest.fixture(scope="module")
def proj():
    return pd.read_parquet(P / "projetos.parquet")


@pytest.fixture(scope="module")
def folha():
    return pd.read_csv(P / "folha.csv")


@pytest.fixture(scope="module")
def sub():
    return pd.read_csv(P / "subsidio.csv")


@pytest.fixture(scope="module")
def meta():
    return json.loads((P / "metadados.json").read_text(encoding="utf-8"))


def test_vereadores_das_legislaturas(ver):
    assert set(ver["legislatura"]) == set(LEGISLATURAS_CAMARA)
    # 29 cadeiras com titulares do início ao fim em cada legislatura, mais suplentes
    for leg, g in ver.groupby("legislatura"):
        assert g["id_parlamentar"].nunique() >= 29, leg


def test_producao_so_de_vereadores_com_mandato(prod, ver):
    assert set(prod["id_parlamentar"]) <= set(ver["id_parlamentar"])
    assert (prod["materias"] > 0).all()


def test_situacao_dos_projetos(proj):
    assert proj["situacao"].isin(camara.SITUACOES).all()
    lei = proj["situacao"] == "Virou lei"
    assert proj.loc[lei, "norma"].notna().all() and proj.loc[~lei, "norma"].isna().all()
    assert proj["id_materia"].is_unique


def test_folha_sem_nomes_nem_cpf(folha):
    assert list(folha.columns) == ["ano_mes", "vinculo", "grupo_cargo", "pessoas", "total"]
    texto = folha.astype(str).to_string()
    assert not re.search(r"\d{3}\.\d{3}\.\d{3}|\*\*\*", texto)


def test_subsidio_bate_com_a_lei(sub, meta):
    """Na 19ª legislatura (2025–2028), mês cheio de vereador = R$ 26.000 e de presidente = R$ 32.000
    (Lei 14.702/2022). Meses com 13º ou exercício parcial ficam de fora."""
    lei = meta["regras"]["subsidio_legal"]
    s = sub[sub["ano_mes"].astype(str) >= "202501"]
    assert len(s) > 0
    moda = s.groupby("cargo")["valor"].agg(lambda v: v.mode().iloc[0])
    assert moda["Vereador"] == lei["vereador"]
    assert moda["Presidente"] == lei["presidente"]


def test_eletivos_da_folha_ligados_ao_sapl(meta):
    assert meta["eletivos_sem_correspondencia_no_sapl"] == []


def test_subsidio_so_dentro_do_mandato(sub, ver):
    """Confere a ligação folha -> SAPL: cada mês pago cai dentro de um mandato do parlamentar."""
    mandatos = ver.assign(ini=ver["inicio_mandato"].str[:7].str.replace("-", ""),
                          fim=ver["fim_mandato"].fillna("2100-12-31").str[:7].str.replace("-", ""))
    for _, s in sub.iterrows():
        m = mandatos[mandatos["id_parlamentar"] == s["id_parlamentar"]]
        mes = str(s["ano_mes"])
        assert ((m["ini"] <= mes) & (mes <= m["fim"])).any(), (s["id_parlamentar"], mes)


@sem_brutos
def test_producao_bate_com_o_sapl(prod, meta):
    """Total da produção = soma, matéria a matéria, dos autores vereadores nos arquivos brutos."""
    autores = {a["id"]: a for a in json.loads((RAW / "autores.json").read_text(encoding="utf-8"))}
    total = 0
    for ano in meta["anos"]:
        for m in json.loads((RAW / f"materias-{ano}.json").read_text(encoding="utf-8")):
            total += sum(autores[a]["tipo"] == 1 for a in m["autores"])
    assert prod["materias"].sum() == total


def test_grupos():
    assert camara.grupo("PLO") == "Projetos de lei"
    assert camara.grupo("R-OSM") == "Requerimentos de obras e serviços"
    assert camara.grupo("R-JFA") == camara.GRUPO_REQUERIMENTO
    assert camara.grupo("E-ADI") == camara.GRUPO_EMENDA
    assert camara.grupo("VETO") == camara.GRUPO_OUTROS


def test_situacao_pela_ultima_tramitacao():
    status = {5: {"descricao": "Arquivado"}, 22: {"descricao": "Rejeitado em Votação Plenária"},
              17: {"descricao": "Arquivado a Pedido do Autor"}, 3: {"descricao": "Enviado para a Ordem do Dia"}}
    t = lambda s, texto="": {"status": s, "texto": texto}  # noqa: E731
    assert camara.situacao(False, t(5, "ARQUIVADO PELA MANUTENÇÃO DO VETO."), status)[0] == "Vetado"
    assert camara.situacao(False, t(5, "ARQUIVADO. FIM DO PRAZO PARA RECURSO NA CCJRLP."), status)[0] == "Arquivado"
    assert camara.situacao(False, t(22), status)[0] == "Rejeitado em plenário"
    assert camara.situacao(False, t(17), status)[0] == "Retirado pelo autor"
    assert camara.situacao(True, t(3), status)[0] == "Em tramitação"
    assert camara.situacao(False, t(3), status)[0] == "Sem conclusão registrada"
    assert camara.situacao(False, None, status)[0] == "Sem conclusão registrada"


def test_grupo_de_cargo():
    assert camara.grupo_cargo("Comissionado", "10000307 - ASSESSOR PARLAMENTAR GABINETE VEREADOR - AP-GV") == \
        "Gabinetes dos vereadores"
    assert camara.grupo_cargo("Eletivo", "10000049 - V E R E A D O R") == "Vereadores"
    assert camara.grupo_cargo("À disposição", "10000349 - À DISPOSIÇÃO - PMJP") == "Cedidos por outros órgãos"
    assert camara.grupo_cargo("Comissionado", "10001021 - ASSESSOR ESPECIAL DA MESA DIRETORA-DSAL-3") == \
        "Mesa Diretora e Presidência"
    assert camara.grupo_cargo("Efetivo", "10000031 - TECNICO LEGISLATIVO-201") == "Administração e apoio"
