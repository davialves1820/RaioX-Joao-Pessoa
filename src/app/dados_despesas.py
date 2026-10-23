"""Carga e funções de apoio da página de despesas (sem dependência do Streamlit)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from src.config import ANOS_INCOMPLETOS_DESPESAS, DATA_PROCESSED
from src.process.despesas_regras import normalizar

PASTA = DATA_PROCESSED / "despesas"

# Modalidades de licitação para o gráfico: no máximo 7 categorias, em ordem fixa
ORDEM_LICITACAO = [
    "Pregão", "Concorrência", "Dispensa", "Inexigibilidade",
    "Adesão a ata de registro de preços", "Outras modalidades", "Sem licitação",
]
_OUTRAS = {"Chamada pública", "Credenciamento", "Licitação internacional", "Tomada de preços",
           "Convite", "Concurso", "Outras"}

GRUPO_PESSOAL = "Pessoal e Encargos Sociais"


def carregar(pasta: Path = PASTA) -> dict:
    return {
        "cubo": pd.read_parquet(pasta / "despesas_cubo.parquet"),
        "credores": pd.read_parquet(pasta / "credores_pj.parquet"),
        "bairros": pd.read_csv(pasta / "bairros_citados.csv", dtype={"cd_bairro": str}),
        "cobertura": pd.read_csv(pasta / "bairros_cobertura.csv"),
        "populacao": pd.read_csv(pasta / "populacao.csv"),
        "validacao": pd.read_csv(pasta / "validacao_siconfi.csv"),
        "meta": json.loads((pasta / "metadados.json").read_text(encoding="utf-8")),
    }


def coluna(metrica: str, corrigido: bool) -> str:
    """'empenhado' ou 'pago', nominal ou corrigido pelo IPCA."""
    if metrica not in ("empenhado", "pago"):
        raise ValueError(metrica)
    return f"{metrica}_corrigido" if corrigido else metrica


def filtrar(cubo: pd.DataFrame, poder: str = "Todos", sem_intra: bool = True) -> pd.DataFrame:
    """Filtra por poder (Todos/Executivo/Legislativo) e tira as transferências entre órgãos do município."""
    df = cubo
    if poder != "Todos":
        df = df[df["poder"] == poder]
    if sem_intra:
        df = df[~df["intra"]]
    return df


def status_ano(ano: int, meta: dict) -> str | None:
    """'incompleto', 'parcial' ou None."""
    if ano in ANOS_INCOMPLETOS_DESPESAS:
        return "incompleto"
    if meta.get("ano_parcial") == ano:
        return "parcial"
    return None


def anos_comparaveis(ano: int, meta: dict) -> bool:
    return status_ano(ano, meta) is None


def meses_de_pico(df: pd.DataFrame, col: str, meta: dict) -> tuple[pd.Series, list[int]]:
    """Quantos anos completos tiveram cada mês como o de maior valor (mês -> nº de anos), e os anos usados."""
    anos = sorted(a for a in df["ano"].unique() if anos_comparaveis(int(a), meta))
    mensal = df[df["ano"].isin(anos)].groupby(["ano", "mes"])[col].sum().unstack()
    return mensal.idxmax(axis=1).value_counts(), [int(a) for a in anos]


def total_por_ano(df: pd.DataFrame, col: str) -> pd.Series:
    return df.groupby("ano")[col].sum()


def por_habitante(totais: pd.Series, populacao: pd.DataFrame) -> pd.Series:
    """Valor por habitante; anos sem população oficial (ex.: 2023) ficam vazios."""
    pop = populacao.set_index("ano")["populacao"]
    return (totais / pop.reindex(totais.index)).round(2)


def variacao_pct(totais: pd.Series, ano: int, meta: dict) -> float | None:
    """Variação em relação ao ano anterior, só entre anos completos."""
    anterior = ano - 1
    if anterior not in totais.index or ano not in totais.index:
        return None
    if not (anos_comparaveis(ano, meta) and anos_comparaveis(anterior, meta)):
        return None
    return float(100 * (totais[ano] / totais[anterior] - 1))


def grupo_licitacao(grupo_modalidade: pd.Series) -> pd.Series:
    return grupo_modalidade.where(~grupo_modalidade.isin(_OUTRAS), "Outras modalidades")


def participacao_licitacao(df: pd.DataFrame, col: str, sem_pessoal: bool = True) -> pd.DataFrame:
    """Participação (%) de cada modalidade no valor de cada ano."""
    if sem_pessoal:
        df = df[df["grupo_natureza"] != GRUPO_PESSOAL]
    t = (
        df.assign(modalidade=grupo_licitacao(df["grupo_modalidade"]))
        .pivot_table(index="ano", columns="modalidade", values=col, aggfunc="sum", fill_value=0)
        .reindex(columns=ORDEM_LICITACAO, fill_value=0)
    )
    return (100 * t.div(t.sum(axis=1), axis=0)).round(2)


def ranking_fornecedores(
    credores: pd.DataFrame, anos: tuple[int, int], col: str, n: int = 15, incluir_publicos: bool = False
) -> pd.DataFrame:
    """Empresas (CNPJ) que mais receberam no período. Pessoas físicas nunca entram."""
    df = credores[credores["ano"].between(*anos)]
    if not incluir_publicos:
        df = df[~df["entidade_publica"]]
    return (
        df.groupby(["cnpj", "cnpj_formatado", "nome_credor"], as_index=False)[col].sum()
        .sort_values(col, ascending=False)
        .head(n)
        .reset_index(drop=True)
    )


def buscar_credores(credores: pd.DataFrame, termo: str, limite: int = 30) -> pd.DataFrame:
    """Empresas cujo nome ou CNPJ contém o termo (sem acentos, maiúsculas e pontuação indiferentes)."""
    termo = (termo or "").strip()
    if len(termo) < 3:
        return credores.iloc[0:0][["cnpj", "cnpj_formatado", "nome_credor"]]
    nomes = credores.drop_duplicates("cnpj")[["cnpj", "cnpj_formatado", "nome_credor"]]
    digitos = re.sub(r"\D", "", termo)
    if len(digitos) >= 3 and len(digitos) >= len(termo.replace(" ", "")) - 4:
        achados = nomes[nomes["cnpj"].str.contains(digitos, regex=False)]
    else:
        achados = nomes[nomes["nome_credor"].map(normalizar).str.contains(normalizar(termo), regex=False)]
    return achados.sort_values("nome_credor").head(limite).reset_index(drop=True)


def resumo_credor(credores: pd.DataFrame, cnpj: str, col: str) -> dict:
    df = credores[credores["cnpj"] == cnpj]
    return {
        "total": float(df[col].sum()),
        "n_empenhos": int(df["n_empenhos"].sum()),
        "por_ano": df.groupby("ano")[col].sum(),
        "por_orgao": df.groupby("cod_ug")[col].sum().sort_values(ascending=False),
        "arquivos": sorted(df["arquivo_origem"].unique()),
    }


# --- formatação pt-BR


def fmt_reais(v: float) -> str:
    """R$ abreviado: 'R$ 4,86 bi', 'R$ 123,4 mi', 'R$ 12,3 mil', 'R$ 950'."""
    if v is None or pd.isna(v):
        return "—"
    a = abs(v)
    sinal = "−" if v < 0 else ""
    for lim, suf, casas in [(1e9, "bi", 2), (1e6, "mi", 1), (1e3, "mil", 1)]:
        if a >= lim:
            n = f"{a / lim:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")
            return f"{sinal}R$ {n} {suf}"
    return f"{sinal}R$ {a:,.0f}".replace(",", ".")


def fmt_reais_inteiro(v: float) -> str:
    """R$ com centavos: 'R$ 1.234.567,89'."""
    if v is None or pd.isna(v):
        return "—"
    s = f"{abs(v):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return ("−" if v < 0 else "") + "R$ " + s


# --- frases-resumo (texto calculado dos dados, para a leitura rápida de cada aba)


def fmt_pct(v: float, casas: int = 0) -> str:
    return f"{v:.{casas}f}%".replace(".", ",")


def lista_pt(itens: list[str]) -> str:
    """['a', 'b', 'c'] -> 'a, b e c'."""
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def resumo_areas(df: pd.DataFrame, ano: int, col: str, n: int = 3) -> str:
    """Ex.: 'Saúde (27%), Educação (22%) e Administração (14%) somaram 63% do valor.'"""
    f = df[df["ano"] == ano].groupby("funcao")[col].sum().sort_values(ascending=False)
    if f.sum() <= 0:
        return ""
    pct = 100 * f / f.sum()
    top = [f"{a} ({fmt_pct(p)})" for a, p in pct.head(n).items()]
    return f"{lista_pt(top)} somaram {fmt_pct(pct.head(n).sum())} do valor."


def resumo_licitacao(part: pd.DataFrame, ano: int) -> str:
    """Ex.: 'pregão 33%, concorrência 21% e sem licitação 25%'."""
    if ano not in part.index:
        return ""
    linha = part.loc[ano].sort_values(ascending=False)
    top = [f"{m.lower()} ({fmt_pct(p)})" for m, p in linha.head(3).items() if p > 0]
    return lista_pt(top)


def fatia_do_ranking(credores: pd.DataFrame, rk: pd.DataFrame, anos: tuple[int, int], col: str,
                     incluir_publicos: bool = False) -> float:
    """% do valor de todas as empresas do período que ficou com as empresas do ranking."""
    df = credores[credores["ano"].between(*anos)]
    if not incluir_publicos:
        df = df[~df["entidade_publica"]]
    total = df[col].sum()
    return float(100 * rk[col].sum() / total) if total else 0.0
