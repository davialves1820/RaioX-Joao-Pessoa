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

# --- Nome oficial de cada órgão (dois primeiros dígitos da unidade orçamentária). O arquivo do TCE-PB
# só traz a sigla ("SEDEC - AÇÕES DE GOVERNO"). Fontes (data/raw/camara_jp, ver src/collect/camara_jp.py):
# - LOA 2024, Lei 15.066/2024: quadro "ÓRGÃO : XX000 NOME", página indicada (numeração do PDF). Grafia
#   ajustada só em maiúsculas/minúsculas, acentos e abreviações ("SEC. MUNIC." → "Secretaria Municipal");
#   a grafia da lei fica no segundo campo.
# - Órgãos criados em 2025: a lei de criação (art. 1º).
# Um órgão novo, que não esteja aqui, interrompe o pipeline até ser incluído com a fonte.
LOA_2024 = "LOA 2024 (Lei 15.066/2024)"
NOMES_ORGAOS = {
    "01": ("Câmara Municipal", "CAMARA MUNICIPAL", f"{LOA_2024}, p. 269"),
    "03": ("Gabinete do Vice-Prefeito", "GABINETE DO VICE-PREFEITO", f"{LOA_2024}, p. 270"),
    "05": ("Procuradoria Geral do Município", "PROCURADORIA GERAL DO MUNICIPIO", f"{LOA_2024}, p. 270"),
    "06": ("Secretaria da Administração", "SECRETARIA DA ADMINISTRACAO", f"{LOA_2024}, p. 271"),
    "07": ("Secretaria das Finanças", "SECRETARIA DAS FINANCAS", f"{LOA_2024}, p. 272"),
    "08": ("Secretaria de Planejamento", "SECRETARIA DE PLANEJAMENTO", f"{LOA_2024}, p. 272"),
    "09": ("Secretaria Municipal do Desenvolvimento Urbano", "SEC. MUNIC. DO DESENVOLVIMENTO URBANO",
           f"{LOA_2024}, p. 274"),
    "10": ("Secretaria Municipal de Educação e Cultura", "SECRETARIA MUNICIPAL DE EDUCAÇÃO E CULTURA",
           f"{LOA_2024}, p. 276"),
    "11": ("Secretaria de Infraestrutura", "SECRETARIA DE INFRAESTRUTURA", f"{LOA_2024}, p. 278"),
    "12": ("Secretaria Municipal do Meio Ambiente", "SECRETARIA MUNICIPAL DO MEIO-AMBIENTE", f"{LOA_2024}, p. 279"),
    "13": ("Secretaria Municipal de Saúde", "SECRETARIA MUNICIPAL DE SAUDE", f"{LOA_2024}, p. 280"),
    "14": ("Secretaria de Desenvolvimento Social", "SECRETARIA DE DESENVOLVIMENTO SOCIAL", f"{LOA_2024}, p. 281"),
    "15": ("Secretaria de Turismo", "SECRETARIA DE TURISMO", f"{LOA_2024}, p. 283"),
    "16": ("Encargos Gerais do Município", "ENCARGOS GERAIS DO MUNÍCIPIO", f"{LOA_2024}, p. 284"),
    "21": ("Secretaria de Desenvolvimento Econômico e Trabalho", "SECRETARIA DE DESENVOLVIMENTO ECONÔMICO E TRABALHO",
           f"{LOA_2024}, p. 286"),
    "22": ("Gabinete de Comunicação Social", "GABINETE DE COMUNICACAO SOCIAL", f"{LOA_2024}, p. 287"),
    "24": ("Secretaria Municipal de Habitação Social", "SECRETARIA MUNICIPAL DE HABITAÇÃO SOCIAL", f"{LOA_2024}, p. 287"),
    "25": ("Secretaria Municipal da Juventude, Esporte e Recreação", "SEC. MUNIC. DA JUVENTUDE, ESPORTE E RECREAÇÃO",
           f"{LOA_2024}, p. 288"),
    "26": ("Secretaria da Receita Municipal", "SECRETARIA DA RECEITA MUNICIPAL", f"{LOA_2024}, p. 289"),
    "27": ("Secretaria Municipal de Ciência e Tecnologia", "SECRETARIA MUNICIPAL DE CIÊNCIA E TECNOLOGIA",
           f"{LOA_2024}, p. 290"),
    # Na LOA 2024: "SECRETARIA EXTRAORDINÁRIA DE POLÍTICAS PÚBLICAS PARA AS MULHERES" (p. 291); novo nome a
    # partir de 11/12/2024
    "28": ("Secretaria Municipal de Políticas Públicas para Mulheres",
           "Secretaria Municipal de Políticas Públicas para Mulheres", "Lei 15.399/2024, art. 1º"),
    "29": ("Secretaria Municipal de Segurança Urbana e Cidadania", "SECRETARIA MUNICIPAL DE SEGURANÇA URBANA E CIDADANIA",
           f"{LOA_2024}, p. 291"),
    # a LOA escreve "COORDENADORA"; a sigla do órgão no TCE-PB é COMPDEC
    "30": ("Coordenadoria Municipal de Proteção e Defesa Civil de João Pessoa",
           "COORDENADORA MUNICIPAL DE PROTEÇÃO E DEFESA CIVIL DE JOÃO PESSOA", f"{LOA_2024}, p. 292"),
    "31": ("Secretaria Municipal de Proteção e Defesa do Consumidor",
           "SECRETARIA MUNICIPAL DE PROTEÇÃO E DEFESA DO CONSUMIDOR", f"{LOA_2024}, p. 293"),
    "32": ("Controladoria Geral do Município", "CONTROLADORIA GERAL DO MUNICÍPIO", f"{LOA_2024}, p. 293"),
    "33": ("Secretaria Municipal de Preservação, Revitalização e Inovação do Centro Histórico",
           "Secretaria Municipal de Preservação, Revitalização e Inovação do Centro Histórico (INOVACENTRO)",
           "Lei 15.467/2025, art. 1º"),
    "34": ("Secretaria Municipal de Serviços Urbanos e Zeladoria",
           "Secretaria Municipal de Serviços Urbanos e Zeladoria - SESUZ", "Lei 15.468/2025, art. 1º"),
    # A lei não dá sigla; o TCE-PB usa SMCPA e os contratos, SECUPA. Que o órgão 35 é esta secretaria se vê
    # nos próprios empenhos (folha "da Sec. Mun. de Cuidado e Proteção Animal").
    "35": ("Secretaria Municipal de Cuidado e Proteção Animal", "SECRETARIA MUNICIPAL DE CUIDADO E PROTEÇÃO ANIMAL",
           "Lei 15.469/2025, art. 1º"),
    "71": ("Secretaria de Gestão Governamental", "SECRETARIA DE GESTÃO GOVERNAMENTAL", f"{LOA_2024}, p. 294"),
    "72": ("Secretaria de Direitos Humanos e Cidadania", "SECRETARIA DE DIREITOS HUMANOS E CIDADANIA",
           f"{LOA_2024}, p. 297"),
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


# Só não pode estar colado a outros dígitos: o CPF de MEI às vezes vem grudado no nome ("FULANO M52998224725")
_CPF_NO_TEXTO = re.compile(r"(?<!\d)(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})(?!\d)")


def mascarar_cpf_no_texto(texto: str) -> str:
    """Mascara CPFs dentro de um texto. Ex.: nome de MEI 'FULANO 52998224725' -> 'FULANO ***.982.247-**'."""
    return _CPF_NO_TEXTO.sub(lambda m: f"***.{m[2]}.{m[3]}-**", texto or "")
