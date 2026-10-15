"""Testes sobre os arquivos em data/processed/despesas (gerados por src.process.despesas)."""

import json
import re

import pandas as pd
import pytest

from src.config import ANO_INICIAL_DESPESAS, DATA_PROCESSED, EXCECOES_SICONFI, TOLERANCIA_SICONFI
from src.process.despesas_regras import cnpj_valido

P = DATA_PROCESSED / "despesas"


@pytest.fixture(scope="module")
def cubo():
    return pd.read_parquet(P / "despesas_cubo.parquet")


@pytest.fixture(scope="module")
def credores():
    return pd.read_parquet(P / "credores_pj.parquet")


@pytest.fixture(scope="module")
def validacao():
    return pd.read_csv(P / "validacao_siconfi.csv")


@pytest.fixture(scope="module")
def meta():
    return json.loads((P / "metadados.json").read_text(encoding="utf-8"))


def test_total_anual_bate_com_siconfi(validacao):
    """Total empenhado por ano = total declarado ao Tesouro (DCA), dentro da tolerância."""
    com_ref = validacao[validacao.siconfi_empenhado.notna()]
    assert len(com_ref) >= 10
    fora = com_ref[com_ref.diferenca_pct.abs() > 100 * TOLERANCIA_SICONFI]
    assert set(fora.ano) <= set(EXCECOES_SICONFI), fora[["ano", "diferenca_pct"]]


def test_excecoes_documentadas_aparecem_na_validacao(validacao):
    marcadas = set(validacao.loc[validacao.excecao_documentada.notna(), "ano"])
    assert marcadas == set(EXCECOES_SICONFI)


def test_cubo_soma_igual_ao_total_validado(cubo, validacao):
    soma = cubo.groupby("ano")["empenhado"].sum().round(2)
    assert (soma - validacao.set_index("ano")["tce_empenhado"]).abs().max() < 0.05


def test_campos_essenciais_sem_nulos(cubo, credores):
    essenciais = ["ano", "mes", "cod_ug", "unidade_gestora", "poder", "codigo_funcao", "funcao",
                  "grupo_modalidade", "tipo_credor", "empenhado", "liquidado", "pago", "arquivo_origem"]
    assert not cubo[essenciais].isna().any().any()
    assert not credores[["cnpj", "nome_credor", "ano", "cod_ug", "empenhado"]].isna().any().any()


def test_datas_dentro_do_ano(cubo, meta):
    assert cubo["mes"].between(1, 12).all()
    assert cubo["ano"].between(ANO_INICIAL_DESPESAS, 2100).all()
    # o arquivo de origem é o do próprio ano
    assert (cubo["arquivo_origem"] == "despesas-" + cubo["ano"].astype(str) + ".zip").all()
    ultima = pd.Timestamp(meta["ultima_data_de_empenho"])
    assert not ((cubo.ano == ultima.year) & (cubo.mes > ultima.month)).any()


def test_valores_nao_negativos(cubo):
    assert (cubo[["empenhado", "liquidado", "pago"]] >= 0).all().all()


def test_ranking_so_de_empresas(credores):
    assert credores["cnpj"].map(cnpj_valido).all()


def test_nenhum_cpf_exposto():
    """Nenhum arquivo processado contém CPF completo (11 dígitos) ou documento de pessoa física."""
    # não colado a letras/dígitos (evita trechos de hashes SHA-256 dos metadados)
    cpf = re.compile(r"(?<![0-9A-Za-z])\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?![0-9A-Za-z])")
    for f in P.iterdir():
        # só colunas de texto: números (índices do IPCA, valores) não são documentos
        if f.suffix == ".parquet":
            texto = pd.read_parquet(f).select_dtypes(exclude=["number", "bool", "datetime"]).astype(str).to_csv(index=False)
        elif f.suffix == ".csv":
            texto = pd.read_csv(f).select_dtypes(exclude=["number", "bool", "datetime"]).astype(str).to_csv(index=False)
        else:
            meta = json.loads(f.read_text(encoding="utf-8"))
            meta.pop("arquivos_brutos", None)  # só URLs e hashes
            texto = json.dumps(meta, ensure_ascii=False)
        texto = re.sub(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", "", texto)  # CNPJ formatado
        texto = re.sub(r"\b\d{14}\b", "", texto)  # CNPJ só com dígitos
        assert not cpf.search(texto), f"possível CPF em {f.name}: {cpf.search(texto)[0]}"


def test_ipca_fator_no_mes_de_referencia_e_um(cubo, meta):
    ano, mes = map(int, meta["ipca"]["mes_referencia"].split("-"))
    ref = cubo[(cubo.ano == ano) & (cubo.mes == mes)]
    assert len(ref) and (ref["ipca_fator"] == 1).all()
    assert (cubo["empenhado_corrigido"] >= cubo["empenhado"] - 0.01).sum() / len(cubo) > 0.95


def test_populacao_sem_ano_estimado_por_nos():
    pop = pd.read_csv(P / "populacao.csv")
    assert pop["fonte"].notna().all() and (pop["populacao"] > 0).all()
    assert 2023 not in set(pop["ano"])  # o IBGE não publicou estimativa para 2023
