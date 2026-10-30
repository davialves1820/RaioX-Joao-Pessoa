"""Testes unitários das regras de limpeza das despesas do TCE-PB."""

import pytest

from src.process.despesas_bairros import bairros_citados
from src.process.despesas_regras import (
    MODALIDADES,
    centavos,
    cnpj_valido,
    cpf_valido,
    data_iso,
    grupo_modalidade,
    limpar_historico,
    mascarar_cpf,
    mascarar_cpf_no_texto,
    tipo_documento,
)

NOMES = (
    ("2507507015", "Centro"),
    ("2507507039", "Mangabeira"),
    ("2507507032", "José Américo"),
    ("2507507003", "Altiplano Cabo Branco"),
    ("2507507013", "Cabo Branco"),
    ("2507507041", "Muçumagro"),
)


def test_centavos():
    assert centavos("1.234,56") == 123456
    assert centavos("0,5") == 50
    assert centavos("-10,00") == -1000
    with pytest.raises(ValueError):
        centavos("abc")


@pytest.mark.parametrize(
    "entrada", ["2018-03-19 00:00:00.0", "2018-03-19", "19/03/2018"]
)
def test_data_iso_aceita_os_tres_formatos(entrada):
    assert data_iso(entrada) == "2018-03-19"


def test_limpar_historico_remove_repeticao():
    assert limpar_historico("PAGAMENTO DE AGUA      PAGAMENTO DE AGUA") == "PAGAMENTO DE AGUA"
    assert limpar_historico("TEXTO UNICO") == "TEXTO UNICO"


def test_cpf_cnpj_validos():
    assert cpf_valido("52998224725")
    assert not cpf_valido("52998224726")
    assert not cpf_valido("11111111111")
    assert cnpj_valido("00000000000191")  # Banco do Brasil
    assert cnpj_valido("09123654000187")  # Cagepa
    assert not cnpj_valido("09123654000188")


def test_tipo_documento():
    assert tipo_documento("09123654000187") == "PJ"
    assert tipo_documento("00052998224725") == "PF"
    # válido como CPF e como CNPJ: desempate pelo nome; na dúvida, pessoa física
    assert tipo_documento("00000000429945", "BANCO DO BRASIL S/A") == "PJ"
    assert tipo_documento("00000000429945", "FULANO DE TAL") == "PF"
    assert tipo_documento("00077777777777") == "indefinido"


def test_mascarar_cpf_mostra_so_digitos_centrais():
    assert mascarar_cpf("00052998224725") == "***.982.247-**"
    assert mascarar_cpf("lixo") == "***.***.***-**"


def test_mascarar_cpf_em_nome_de_mei():
    assert mascarar_cpf_no_texto("FULANO DE TAL 52998224725") == "FULANO DE TAL ***.982.247-**"
    assert mascarar_cpf_no_texto("FULANO 529.982.247-25") == "FULANO ***.982.247-**"
    assert mascarar_cpf_no_texto("EMPRESA LTDA") == "EMPRESA LTDA"
    # CPF grudado no nome, como aparece em alguns MEIs do TCE-PB
    assert mascarar_cpf_no_texto("FULANO DE TAL M52998224725") == "FULANO DE TAL M***.982.247-**"
    # CNPJ (14 dígitos) não é confundido com CPF
    assert mascarar_cpf_no_texto("EMPRESA 11222333000181") == "EMPRESA 11222333000181"


def test_modalidades_mapeadas_e_nome_novo_falha():
    assert grupo_modalidade("Pregão (Lei 14.133/21)") == "Pregão"
    assert grupo_modalidade("Inexigível") == grupo_modalidade("Inexigibilidade (Lei 14.133/21)")
    assert set(MODALIDADES.values()) >= {"Sem licitação", "Pregão", "Dispensa", "Inexigibilidade"}
    with pytest.raises(KeyError):
        grupo_modalidade("Modalidade inventada")


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Pavimentação de 30 ruas no bairro de Mangabeira", {"2507507039"}),
        ("Reforma no bairro do Centro", {"2507507015"}),
        ("Material para o Centro de Saúde", set()),  # nome ambíguo sem "bairro"
        ("Obra na Avenida José Américo de Almeida", set()),  # via, não bairro
        ("Praça no Altiplano Cabo Branco", {"2507507003"}),  # não conta Cabo Branco
        ("Ruas em Mangabeira e no bairro Muçumagro", {"2507507039", "2507507041"}),
    ],
)
def test_bairros_citados(texto, esperado):
    assert bairros_citados(texto, NOMES) == esperado
