"""Testes dos pedidos de obras por bairro (src/process/camara_pedidos.py)."""

import json

import pandas as pd
import pytest

from src.config import DATA_PROCESSED
from src.process import camara_pedidos as cp

P = DATA_PROCESSED / "camara"


@pytest.fixture(scope="module")
def regras():
    oficiais, codigos = cp.carregar_bairros()
    return cp.padroes(oficiais), {**oficiais, **cp.VARIACOES}, codigos


# Trechos reais da amostra conferida à mão na investigação (issue #48)
CONFERIDOS = [
    ("Limpeza da rua Maria Alves da Silva no bairro de Mangabeira, nesta.", ["Mangabeira"]),
    ("Rua Maria Auxiliadora Patrício Gouveia - CEP 58079-040 - Funcionários.", ["Funcionários"]),
    ("Rua Josué Gomes de Almeida, Vizinho a casa de Nº 387, José Américo de Almeida, CEP: 58.074-084",
     ["José Américo"]),
    ("Avenida Florianópolis-Planalto da Boa Esperança, João Pessoa – PB", ["Planalto da Boa Esperança"]),
    ("limpeza e capinagem, da Rua Canadá, Cristo Redentor, CEP: 58070-608", ["Cristo Redentor"]),
    ("galerias pluviais da Rua Estevão Lopes Galvão, Valentina Figueiredo, nesta capital.", ["Valentina"]),
    ("RONDA POLICIAL na PRAÇA RIO BRANCO e na RUA GENERAL OSÓRIO, Centro, nesta Capital", ["Centro"]),
    ("LÂMPADAS DE LED NA RUA INTENDENTE CARLOS MARCELO, LOCALIZADA NO BAIRRO TORRE", ["Torre"]),
    ("RUA HARKEREZ HENRIQUES DE MIRANDA LOUREIRO, 159, CUIA,JOAO PESSOA - PB", ["Cuiá"]),
    ("Pavimentação da Rua José Barbalho Filho - Mandacaru", ["Mandacarú"]),
    ("semáforos com sinal sonoro em pontos estratégicos no bairro Mangabeira II.", ["Mangabeira"]),
    ("Escola Abraão Alves de Carvalho, localizada no bairro Muçumagro", ["Muçumagro"]),
]


@pytest.mark.parametrize("texto,esperado", CONFERIDOS)
def test_amostra_conferida(regras, texto, esperado):
    pats, nomes, _ = regras
    assert cp.casar(texto, pats, nomes) == esperado


def test_nomes_ambiguos_so_com_contexto(regras):
    pats, nomes, _ = regras
    assert cp.casar("reforma do Centro de Vigilância Sanitária", pats, nomes) == []
    assert cp.casar("instalação de torre de telefonia", pats, nomes) == []
    assert cp.casar("ronda no bairro do Centro", pats, nomes) == ["Centro"]


def test_nome_contido_em_outro_nao_conta_duas_vezes(regras):
    pats, nomes, _ = regras
    assert cp.casar("Rua X, Altiplano Cabo Branco", pats, nomes) == ["Altiplano Cabo Branco"]
    assert cp.casar("Rua X, Tambauzinho", pats, nomes) == ["Tambauzinho"]


def test_comunidade_sem_fonte_fica_sem_bairro(regras):
    pats, nomes, _ = regras
    assert cp.casar("Rua Bom Jesus, cruzamento com a Rua Rafael Mororó, Rangel, João Pessoa/PB", pats, nomes) == []


def test_variacoes_apontam_para_bairros_oficiais(regras):
    _, _, codigos = regras
    assert set(cp.VARIACOES.values()) <= set(codigos)


def test_tema_e_orgao():
    assert cp.temas("tapa-buraco e iluminação em LED na rua") == ["Pavimentação e buracos", "Iluminação"]
    assert cp.temas("homenagem") == []
    assert cp.orgao("encaminhem à EMLUR e à SEINFRA") == "EMLUR"
    assert cp.orgao("ao setor competente") is None


def test_saida_cobre_todos_os_requerimentos():
    rb = pd.read_parquet(P / "requerimentos_bairros.parquet")
    mat = pd.read_parquet(P / "materias.parquet")
    assert set(rb["id_materia"]) == set(mat.loc[mat["sigla"] == cp.SIGLA, "id_materia"])
    por_req = rb.groupby("id_materia").agg(n=("n_bairros", "first"), linhas=("id_materia", "size"))
    assert (por_req["linhas"] == por_req["n"].clip(lower=1)).all()
    assert rb.loc[rb["nm_bairro"].notna(), "cd_bairro"].str.fullmatch(r"2507507\d{3}").all()
    meta = json.loads((P / "metadados_pedidos.json").read_text(encoding="utf-8"))
    assert meta["com_um_bairro"] / meta["requerimentos"] >= 0.8
