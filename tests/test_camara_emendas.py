"""Testes das emendas impositivas (src/process/camara_emendas.py)."""

import json
import re

import pandas as pd
import pytest

from src.config import DATA_PROCESSED
from src.process import camara_emendas as ce

P = DATA_PROCESSED / "camara"

# Trechos reais de formulários (texto extraído dos PDFs e .docx do SAPL)
FORMULARIO_PDF = """
EMENDA AO PROJETO DE LEI Nº 575/2025. AUTOR: Luis da Padaria
EMENDA Nº ______________ / 2025 TIPO DA EMENDA: IMPOSITIVA
 ACRÉSCIMO À PROGRAMAÇÃO
Órgão
 72000 – Secretaria de Direitos Humanos e
 Cidadania
Unidade Orçamentária
 72303 - Fundo Municipal do Idoso
Classificação Funcional/programática
 08 241 5558.624371
Natureza da Despesa 33.50.43
Fonte de Recursos 1.5.00
Valor Acrescido (R$) 450.000,00
Meta /Unidade de Medida 01/Convênio. Subvenção social à CASC PB centro de ação social, CNPJ 13.036.902/0001-20.
CANCELAMENTO COMPENSATÓRIO Órgão 20.000 - Reserva de contingência CNPJ 99.999.999/0001-91
"""
FORMULARIO_DOCX = """EMENDA Nº / 2025 TIPO DA EMENDA: IMPOSITIVA ACRÉSCIMO À PROGRAMAÇÃO
Órgão 13000 - Secretaria Municipal de Saúde Unidade Orçamentária 13301 - Fundo Municipal de Saúde
Classificação Funcional/programática 10 302 5005.462871 Natureza da Despesa 33.50.43 Fonte de Recursos 1.5.00
Valor Acrescido (R$) R$ 50.000,00 Meta /Unidade de Medida 1/Convênio. Custeio das atividades da Casa da
Divina Misericórdia . CANCELAMENTO COMPENSATÓRIO Órgão 20000 - Reserva"""


def test_extrai_o_formulario():
    c = ce.extrair(FORMULARIO_PDF)
    assert c["valor"] == 450000.0
    assert c["orgao"].startswith("72000 – Secretaria de Direitos Humanos")
    assert c["unidade_orcamentaria"] == "72303 – Fundo Municipal do Idoso"
    assert c["natureza_despesa"] == "33.50.43"
    assert c["cnpj_beneficiario"] == "13036902000120"  # o da meta, não o do cancelamento compensatório
    assert "CASC" in c["meta"]


def test_extrai_formulario_do_word():
    c = ce.extrair(FORMULARIO_DOCX)
    assert c["valor"] == 50000.0 and c["unidade_orcamentaria"] == "13301 – Fundo Municipal de Saúde"
    assert c["cnpj_beneficiario"] is None and "Divina Misericórdia" in c["meta"]


def test_texto_vazio_nao_inventa_nada():
    assert all(v is None for v in ce.extrair("").values())


@pytest.mark.parametrize("historico,esperado", [
    ("VALOR QUE ORA EMPENHAMOS REFERE-SE A EMENDA IMPOSITIVA Nº 393/2025 EM FAVOR DA OSC CASA DA DIVINA "
     "MISERICORDIA, CONFORME PROCESSO ADMINISTRATIVO Nº 15.822/2026", [(393, 2025)]),
    ("VALOR EMPENHADO REFERENTE AO TERMO DE FOMENTO Nº 004/2026 EMENDA NUMERO 071/2025", [(71, 2025)]),
    ("TRANSFERENCIA DE RECURSOS ESTABELECIDOS PELAS EMENDAS MUNICIPAIS Nº(S): Nº(S) 77/2025, 78/2025, PARA "
     "EXECUCAO DO PROJETO", [(77, 2025), (78, 2025)]),
    # emendas federais têm outra numeração; processo e termo não são emenda
    ("REFERE-SE A EMENDA FEDERAL Nº 202544320008 EM FAVOR DA OSC NOSSO LAR, TERMO FOMENTO Nº 116/2026", []),
    ("PLANTOES EXTRAS EMENDA PARLAMENTAR PRESTADORES DE SERVICOS, PROC. ADMINISTRATIVO 33.380/2026", []),
])
def test_citacoes_de_emenda_no_historico(historico, esperado):
    assert ce.citacoes(historico) == esperado


def test_conferencia_da_ligacao():
    assert ce.conferir("13036902000120", "CASC", "13036902000120", "CENTRO DE AÇÃO SOCIAL") == "CNPJ confere"
    assert ce.conferir("24098782000454", "x", "24098782000101", "COMUNIDADE DOCE MÃE DE DEUS") == \
        "Mesma entidade (matriz/filial)"
    assert ce.conferir("41227018000100", "APEP", "54901373000162", "ASSOCIAÇÃO DA MARCHA") == "CNPJ diferente"
    assert ce.conferir(None, "Custeio da Casa da Divina Misericórdia", "1", "CASA DA DIVINA MISERICORDIA") == \
        "Nome confere"
    assert ce.conferir(None, "Equipamentos para o Hospital Infantil", "1", "WA MEDICAL EQUIPAMENTOS LTDA") == \
        "A conferir"


def test_saidas_consistentes():
    em = pd.read_parquet(P / "emendas.parquet")
    lig = pd.read_parquet(P / "emendas_empenhos.parquet")
    meta = json.loads((P / "metadados_emendas.json").read_text(encoding="utf-8"))
    assert em["id_materia"].is_unique and len(em) == meta["emendas"]
    assert set(lig["id_materia"]) <= set(em["id_materia"])
    assert lig["conferencia"].isin(ce.ORDEM_CONFERENCIA).all()
    tot = lig.groupby("id_materia")["empenhado"].sum()
    assert (em.set_index("id_materia").loc[tot.index, "empenhado"] - tot).abs().max() < 0.01
    assert (em["situacao"] == "Empenho encontrado").sum() == lig["id_materia"].nunique()
    # credor pessoa física: sem nome, sem histórico e CPF mascarado
    pf = lig[lig["nome_credor"].isna()]
    assert pf["historico"].isna().all()
    assert not lig["cnpj_credor"].str.fullmatch(r"\d{11}").any()
    assert not lig["historico"].dropna().str.contains(r"\d{3}\.\d{3}\.\d{3}-\d{2}").any()


def test_valores_lidos_sao_positivos():
    em = pd.read_parquet(P / "emendas.parquet")
    v = em["valor"].dropna()
    assert (v > 0).all() and len(v) / len(em) >= 0.7
    assert em["cnpj_beneficiario"].dropna().map(lambda c: bool(re.fullmatch(r"\d{14}", c))).all()
