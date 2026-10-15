"""Regras de limpeza e classificação das despesas do TCE-PB (funções puras, testáveis)."""

from __future__ import annotations

import re
import unicodedata

# --- Colunas: o layout de 2003-2019 e o de 2020+ têm as mesmas 40 colunas, na mesma
# ordem; só 16 nomes mudam. Adotamos os nomes do layout atual.
COLUNAS = [
    "municipio", "codigo_unidade_gestora", "descricao_unidade_gestora", "numero_empenho",
    "data_empenho", "mes", "cpf_cnpj", "nome_credor", "valor_empenhado", "valor_liquidado",
    "valor_pago", "codigo_unidade_orcamentaria", "descricao_unidade_orcamentaria",
    "codigo_funcao", "funcao", "codigo_subfuncao", "subfuncao", "codigo_programa", "programa",
    "codigo_acao", "acao", "codigo_categoria_economica", "categoria_economica",
    "codigo_natureza", "grupo_natureza_despesa", "codigo_modalidade_aplicacao",
    "modalidade_aplicacao", "codigo_elemento_despesa", "elemento_despesa",
    "codigo_subelemento", "codigo_subelemento_exibicao", "numero_licitacao",
    "modalidade_licitacao", "numero_obra", "historico", "codigo_fonte_recurso",
    "descricao_fonte_recurso", "ano_fonte", "co", "descricao_co",
]

# --- Unidades gestoras de João Pessoa no SAGRES (código TCE-PB)
UNIDADES_GESTORAS = {
    "201095": ("Prefeitura Municipal", "Executivo", "Prefeitura"),
    "610095": ("Fundo Municipal de Saúde", "Executivo", "Fundo"),
    "609095": ("Fundo Municipal de Assistência Social", "Executivo", "Fundo"),
    "606095": ("Fundo Municipal de Urbanização", "Executivo", "Fundo"),
    "607095": ("Fundo Municipal de Cultura", "Executivo", "Fundo"),
    "601095": ("Fundo Municipal do Meio Ambiente", "Executivo", "Fundo"),
    "602095": ("Fundo Municipal de Defesa dos Direitos Difusos", "Executivo", "Fundo"),
    "605095": ("Fundo Empreender-JP", "Executivo", "Fundo"),
    "608095": ("Fundo Municipal dos Direitos da Criança e do Adolescente", "Executivo", "Fundo"),
    "611095": ("Fundo da Procuradoria-Geral (Funderm)", "Executivo", "Fundo"),
    "612095": ("Fundo Municipal do Idoso", "Executivo", "Fundo"),
    "613095": ("Fundo do Trabalho", "Executivo", "Fundo"),
    "302095": ("Instituto de Previdência do Município (IPM)", "Executivo", "Autarquia ou fundação"),
    "304095": ("Emlur (limpeza urbana)", "Executivo", "Autarquia ou fundação"),
    "301095": ("Semob/STTrans (transporte e trânsito)", "Executivo", "Autarquia ou fundação"),
    "603095": ("Fundação Cultural (Funjope)", "Executivo", "Autarquia ou fundação"),
    "303095": ("Instituto Cândida Vargas", "Executivo", "Autarquia ou fundação"),
    "101095": ("Câmara Municipal", "Legislativo", "Legislativo"),
    "614095": ("Fundo da Câmara Municipal (FEJP)", "Legislativo", "Legislativo"),
}

# --- Modalidade de licitação: os nomes mudam ao longo do tempo (ex.: Lei 14.133/2021).
# Agrupamos em categorias estáveis; o nome original continua disponível.
MODALIDADES = {
    "Sem Licitação": "Sem licitação",
    "Pregão Eletrônico": "Pregão",
    "Pregão Presencial": "Pregão",
    "Pregão (Eletrônico e Presencial)": "Pregão",
    "Pregão (Lei 14.133/21)": "Pregão",
    "Concorrência": "Concorrência",
    "Concorrência (Lei 14.133/21)": "Concorrência",
    "Dispensa por Valor": "Dispensa",
    "Dispensa por outros motivos": "Dispensa",
    "Dispensa (Lei 14.133/21)": "Dispensa",
    "Dispensa COVID-19 (Art. 4º da Lei 13.979/2020)": "Dispensa",
    "Dispensa (Medida Provisória 1.047/21)": "Dispensa",
    "Inexigível": "Inexigibilidade",
    "Inexigibilidade (Lei 14.133/21)": "Inexigibilidade",
    "Adesão a Registro de Preço": "Adesão a ata de registro de preços",
    "Adesão a Ata de Registro de Preços - (Lei Nº 14.133/2021)": "Adesão a ata de registro de preços",
    "Chamada Pública": "Chamada pública",
    "Credenciamento - (Lei Nº 14.133/2021)": "Credenciamento",
    "Licitação Credenciamento - (Lei Nº 8.666/93)": "Credenciamento",
    "Tomada de Preços": "Tomada de preços",
    "Convite": "Convite",
    "Concurso": "Concurso",
    "Concurso (Lei 14.133/21)": "Concurso",
    "Licitação Internacional Competitiva": "Licitação internacional",
    "Internacional (GN 2349-9)": "Licitação internacional",
    "Internacional (GN 2350-9)": "Licitação internacional",
    "Licitação Internacional (GN 2350-9)": "Licitação internacional",
    "Internacional Não Competitiva": "Licitação internacional",
    "Leilão": "Outras",
    "RDC - Regime Diferenciado de Contratações Públicas": "Outras",
}


def grupo_modalidade(nome: str) -> str:
    """Categoria estável da modalidade; falha para nomes novos (para serem mapeados à mão)."""
    try:
        return MODALIDADES[nome.strip()]
    except KeyError:
        raise KeyError(f"modalidade de licitação sem mapeamento: {nome!r}") from None


# --- Valores e datas


def centavos(valor: str) -> int:
    """'1.234,56' -> 123456 (inteiro em centavos, para somas exatas)."""
    s = valor.strip().replace(".", "").replace(",", ".")
    if not re.fullmatch(r"-?\d+(\.\d{1,2})?", s):
        raise ValueError(f"valor monetário inválido: {valor!r}")
    inteiro, _, frac = s.partition(".")
    sinal = -1 if inteiro.startswith("-") else 1
    return sinal * (abs(int(inteiro)) * 100 + int((frac + "00")[:2]))


def data_iso(valor: str) -> str:
    """Aceita 'AAAA-MM-DD', 'AAAA-MM-DD hh:mm:ss.0' e 'DD/MM/AAAA'; devolve 'AAAA-MM-DD'."""
    s = valor.strip()
    if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?: .*)?", s):
        return f"{m[1]}-{m[2]}-{m[3]}"
    if m := re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", s):
        return f"{m[3]}-{m[2]}-{m[1]}"
    raise ValueError(f"data inválida: {valor!r}")


# --- Texto


def normalizar(texto: str) -> str:
    """Maiúsculas, sem acentos e com espaços simples (para buscas)."""
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(s.upper().split())


def limpar_historico(texto: str) -> str:
    """Remove a repetição do histórico (de 2021 em diante o TCE-PB publica 'TEXTO<espaços>TEXTO')."""
    s = " ".join((texto or "").split())
    palavras = s.split(" ")
    n = len(palavras)
    if n >= 2 and n % 2 == 0 and palavras[: n // 2] == palavras[n // 2 :]:
        return " ".join(palavras[: n // 2])
    return s


# --- CPF / CNPJ


def cpf_valido(d: str) -> bool:
    if not re.fullmatch(r"\d{11}", d) or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10 % 11) % 10 != int(d[n]):
            return False
    return True


def cnpj_valido(d: str) -> bool:
    if not re.fullmatch(r"\d{14}", d) or d == d[0] * 14:
        return False
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for n in (12, 13):
        soma = sum(int(d[i]) * pesos[i + 13 - n] for i in range(n))
        dv = 0 if soma % 11 < 2 else 11 - soma % 11
        if dv != int(d[n]):
            return False
    return True


# Sinais de pessoa jurídica no nome, usados só para desempatar documentos ambíguos
_NOME_PJ = re.compile(
    r"\b(?:S/?A|S\.A\.?|LTDA|BANCO|EIRELI|EPP|ME|CIA|COMPANHIA|ASSOCIACAO|INSTITUTO|FUNDACAO|"
    r"COOPERATIVA|CONSORCIO|SINDICATO|CONSELHO|MUNICIPIO|PREFEITURA|SECRETARIA|CAIXA|EMPRESA)\b"
)


def tipo_documento(doc: str, nome: str = "") -> str:
    """'PJ' (CNPJ), 'PF' (CPF) ou 'indefinido'.

    O TCE-PB publica o CPF com 14 dígitos ('000' + CPF). Alguns CNPJs também começam
    com '000' (ex.: agências do Banco do Brasil), por isso usamos os dígitos
    verificadores. Se o documento é válido como CPF e como CNPJ, desempatamos pelo
    nome (S/A, LTDA, BANCO...). Na dúvida, o credor é tratado como pessoa física: o
    CPF é mascarado e o credor não entra em rankings.
    """
    d = (doc or "").strip()
    pode_cpf = d.startswith("000") and cpf_valido(d[3:])
    pode_cnpj = cnpj_valido(d)
    if pode_cnpj and (not pode_cpf or _NOME_PJ.search(normalizar(nome or ""))):
        return "PJ"
    if pode_cpf:
        return "PF"
    return "indefinido"


def mascarar_cpf(doc: str) -> str:
    """'00012345678901' -> '***.456.789-**' (mostra só os 6 dígitos centrais, padrão do governo federal)."""
    d = (doc or "").strip()[-11:]
    if not re.fullmatch(r"\d{11}", d):
        return "***.***.***-**"
    return f"***.{d[3:6]}.{d[6:9]}-**"


def formatar_cnpj(d: str) -> str:
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


_CPF_NO_TEXTO = re.compile(r"(?<![0-9A-Za-z])(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})(?![0-9A-Za-z])")


def mascarar_cpf_no_texto(texto: str) -> str:
    """Mascara CPFs dentro de um texto. Ex.: nome de MEI 'FULANO 52998224725' -> 'FULANO ***.982.247-**'."""
    return _CPF_NO_TEXTO.sub(lambda m: f"***.{m[2]}.{m[3]}-**", texto or "")
