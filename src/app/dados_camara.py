"""Carga e funções de apoio da página da Câmara Municipal (sem dependência do Streamlit)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.config import DATA_PROCESSED
from src.process.camara import SITUACOES
from src.process.despesas_regras import normalizar

PASTA = DATA_PROCESSED / "camara"

LEGISLATURAS = {18: (2021, 2024), 19: (2025, 2028)}

# Ordem dos grupos nos gráficos e nos cards (os demais vêm depois, em "Outros")
ORDEM_GRUPOS = [
    "Projetos de lei", "Propostas de emenda à Lei Orgânica", "Projetos de resolução",
    "Projetos de decreto legislativo", "Indicações", "Requerimentos de obras e serviços",
    "Votos de aplauso, pesar e similares", "Emendas impositivas ao orçamento", "Emendas e substitutivos",
    "Outros requerimentos", "Outros",
]
ORDEM_GRUPOS_FOLHA = [
    "Vereadores", "Gabinetes dos vereadores", "Mesa Diretora e Presidência", "Comissões", "Lideranças",
    "Comunicação e cerimonial", "Administração e apoio", "Cedidos por outros órgãos",
]


def carregar(pasta: Path = PASTA) -> dict:
    return {
        "vereadores": pd.read_csv(pasta / "vereadores.csv"),
        "producao": pd.read_csv(pasta / "producao.csv"),
        "origem": pd.read_csv(pasta / "producao_origem.csv"),
        "projetos": pd.read_parquet(pasta / "projetos.parquet"),
        "subsidio": pd.read_csv(pasta / "subsidio.csv", dtype={"ano_mes": str}),
        "folha": pd.read_csv(pasta / "folha.csv", dtype={"ano_mes": str}),
        "meta": json.loads((pasta / "metadados.json").read_text(encoding="utf-8")),
    }


def anos_da_legislatura(leg: int, anos_disponiveis) -> list[int]:
    ini, fim = LEGISLATURAS[leg]
    return [a for a in sorted(anos_disponiveis) if ini <= a <= fim]


def vereadores_da_legislatura(ver: pd.DataFrame, leg: int) -> pd.DataFrame:
    """Um vereador por linha, em ordem alfabética, com o período de cada mandato na legislatura."""
    v = ver[ver["legislatura"] == leg].sort_values("inicio_mandato")
    g = v.groupby("id_parlamentar")
    out = g.agg(nome=("nome_parlamentar", "first"), partido=("partido_atual", "first"),
                titular=("titular", "max"), foto=("foto", "first"), link=("link_sapl", "first"))
    out["periodos"] = g.apply(lambda x: list(zip(x["inicio_mandato"], x["fim_mandato"])), include_groups=False)
    out = out.reset_index()
    out["ordem"] = out["nome"].map(normalizar)
    return out.sort_values("ordem").drop(columns="ordem").reset_index(drop=True)


def producao_por_vereador(prod: pd.DataFrame, leg: int) -> pd.DataFrame:
    """Matérias por vereador (linhas) e grupo (colunas) nos anos da legislatura."""
    ini, fim = LEGISLATURAS[leg]
    p = prod[(prod["ano"] >= ini) & (prod["ano"] <= fim)]
    t = p.pivot_table(index="id_parlamentar", columns="grupo", values="materias", aggfunc="sum", fill_value=0)
    return t.reindex(columns=[c for c in ORDEM_GRUPOS if c in t.columns])


def projetos_do_vereador(proj: pd.DataFrame, id_parlamentar: int, leg: int) -> pd.DataFrame:
    ini, fim = LEGISLATURAS[leg]
    autor = proj["autores_ids"].fillna("").str.split(";").map(lambda ids: str(id_parlamentar) in ids)
    p = proj[autor & proj["ano"].between(ini, fim)]
    return p.sort_values(["ano", "numero"], ascending=False)


def resumo_projetos(p: pd.DataFrame) -> dict:
    """Quantos projetos em cada situação (todas as situações, mesmo as com zero)."""
    c = p["situacao"].value_counts()
    return {s: int(c.get(s, 0)) for s in SITUACOES}


def situacao_por_ano(proj: pd.DataFrame, origem: str | None = None) -> pd.DataFrame:
    p = proj if origem is None else proj[proj["origem"] == origem]
    t = pd.crosstab(p["ano"], p["situacao"])
    return t.reindex(columns=SITUACOES, fill_value=0)


def ultimo_subsidio(sub: pd.DataFrame, id_parlamentar: int) -> tuple[str, float, str] | None:
    """(mês AAAAMM, valor, cargo) do último pagamento do vereador, ou None."""
    s = sub[sub["id_parlamentar"] == id_parlamentar].sort_values("ano_mes")
    if s.empty:
        return None
    r = s.iloc[-1]
    return r["ano_mes"], float(r["valor"]), r["cargo"]


def sem_subsidio_desde(sub: pd.DataFrame, id_parlamentar: int, leg: int, mes_folha: str) -> str | None:
    """Primeiro mês (AAAAMM) sem subsídio, quando o vereador recebeu na legislatura mas parou antes do
    último mês da folha. None se recebe até o fim da folha ou nunca recebeu na legislatura."""
    ini, fim = LEGISLATURAS[leg]
    s = sub[(sub["id_parlamentar"] == id_parlamentar) & sub["ano_mes"].between(f"{ini}01", f"{fim}12")]
    if s.empty:
        return None
    ultimo = s["ano_mes"].max()
    if ultimo >= min(mes_folha, f"{fim}12"):
        return None
    seguinte = pd.Period(year=int(ultimo[:4]), month=int(ultimo[4:]), freq="M") + 1
    return seguinte.strftime("%Y%m")


def buscar_projetos(proj: pd.DataFrame, texto: str) -> pd.DataFrame:
    """Projetos cuja ementa ou autores contêm todas as palavras do texto (sem acento e sem caixa)."""
    palavras = normalizar(texto).split()
    if not palavras:
        return proj.iloc[0:0]
    alvo = (proj["ementa"].fillna("") + " " + proj["autores"].fillna("")).map(normalizar)
    ok = pd.Series(True, index=proj.index)
    for p in palavras:
        ok &= alvo.str.contains(p, regex=False)
    return proj[ok].sort_values(["ano", "numero"], ascending=False)


def folha_mensal(folha: pd.DataFrame) -> pd.DataFrame:
    """Total bruto por mês (linhas) e grupo de cargo (colunas), na ordem fixa."""
    t = folha.pivot_table(index="ano_mes", columns="grupo_cargo", values="total", aggfunc="sum", fill_value=0)
    return t.reindex(columns=[c for c in ORDEM_GRUPOS_FOLHA if c in t.columns])


def pessoas_ultimo_mes(folha: pd.DataFrame) -> tuple[str, pd.Series]:
    mes = folha["ano_mes"].max()
    p = folha[folha["ano_mes"] == mes].groupby("grupo_cargo")["pessoas"].sum()
    return mes, p.reindex([c for c in ORDEM_GRUPOS_FOLHA if c in p.index])


def fmt_mes(ano_mes: str) -> str:
    return f"{ano_mes[4:]}/{ano_mes[:4]}"


def fmt_periodo(inicio: str, fim: str | float | None) -> str:
    def br(d):
        return f"{d[8:10]}/{d[5:7]}/{d[:4]}"
    return f"{br(inicio)} a {br(fim)}" if isinstance(fim, str) else f"desde {br(inicio)}"
