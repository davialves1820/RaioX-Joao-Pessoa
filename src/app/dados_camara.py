"""Carga e funções de apoio da página da Câmara Municipal (sem dependência do Streamlit)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from src.config import DATA_PROCESSED
from src.process.camara import SITUACOES, UGS_CAMARA
from src.process.despesas_regras import normalizar

PASTA = DATA_PROCESSED / "camara"

LEGISLATURAS = {18: (2021, 2024), 19: (2025, 2028)}
POR_PAGINA = 20

# Situações em que o projeto não está mais em tramitação e não virou lei
ENCERRADOS = ["Vetado", "Rejeitado em plenário", "Retirado pelo autor", "Arquivado"]
# Grupos de matéria que contam como "atuação" (pedidos e manifestações)
ATUACAO = ["Indicações", "Requerimentos de obras e serviços", "Votos de aplauso, pesar e similares",
           "Outros requerimentos"]


def carregar(pasta: Path = PASTA) -> dict:
    proj = pd.read_parquet(pasta / "projetos.parquet")
    mat = pd.read_parquet(pasta / "materias.parquet")
    normas = pd.read_parquet(pasta / "normas.parquet")
    for df, colunas in ((proj, ["ementa", "autores"]), (mat, ["ementa", "autores"]), (normas, ["ementa"])):
        df["busca"] = df[colunas].fillna("").agg(" ".join, axis=1).map(normalizar)
    return {
        "vereadores": pd.read_csv(pasta / "vereadores.csv"),
        "producao": pd.read_csv(pasta / "producao.csv"),
        "projetos": proj,
        "materias": mat,
        "normas": normas,
        "sessoes": pd.read_csv(pasta / "sessoes.csv"),
        "subsidio": pd.read_csv(pasta / "subsidio.csv", dtype={"ano_mes": str}),
        "folha": pd.read_csv(pasta / "folha_cargos.csv", dtype={"ano_mes": str}),
        "despesas": pd.read_csv(pasta / "despesas_por_elemento.csv"),
        "diarias": pd.read_csv(pasta / "diarias.csv"),
        "rgf": pd.read_csv(pasta / "rgf.csv"),
        "meta": json.loads((pasta / "metadados.json").read_text(encoding="utf-8")),
    }


# --- Vereadores


def vereadores_da_legislatura(ver: pd.DataFrame, leg: int) -> pd.DataFrame:
    """Um vereador por linha, em ordem alfabética, com o período de cada mandato na legislatura."""
    v = ver[ver["legislatura"] == leg].sort_values("inicio_mandato")
    g = v.groupby("id_parlamentar")
    out = g.agg(nome=("nome_parlamentar", "first"), nome_completo=("nome_completo", "first"),
                partido=("partido_atual", "first"), titular=("titular", "max"), foto=("foto", "first"),
                link=("link_sapl", "first"))
    out["periodos"] = g.apply(lambda x: list(zip(x["inicio_mandato"], x["fim_mandato"])), include_groups=False)
    out = out.reset_index()
    out["ordem"] = out["nome"].map(normalizar)
    return out.sort_values("ordem").drop(columns="ordem").reset_index(drop=True)


def contagem(prod: pd.DataFrame, id_parlamentar: int, leg: int) -> dict[str, int]:
    """Matérias do vereador por grupo nos anos da legislatura."""
    ini, fim = LEGISLATURAS[leg]
    p = prod[(prod["id_parlamentar"] == id_parlamentar) & prod["ano"].between(ini, fim)]
    return p.groupby("grupo")["materias"].sum().astype(int).to_dict()


def _do_vereador(df: pd.DataFrame, id_parlamentar: int) -> pd.Series:
    return df["autores_ids"].fillna("").str.split(";").map(lambda ids: str(id_parlamentar) in ids)


def projetos_do_vereador(proj: pd.DataFrame, id_parlamentar: int, leg: int) -> pd.DataFrame:
    ini, fim = LEGISLATURAS[leg]
    p = proj[_do_vereador(proj, id_parlamentar) & proj["ano"].between(ini, fim)]
    return p.sort_values(["data_apresentacao", "numero"], ascending=False)


def atuacao_do_vereador(mat: pd.DataFrame, id_parlamentar: int, leg: int) -> pd.DataFrame:
    ini, fim = LEGISLATURAS[leg]
    m = mat[mat["grupo"].isin(ATUACAO) & mat["ano"].between(ini, fim)]
    return m[_do_vereador(m, id_parlamentar)]


def resumo_projetos(p: pd.DataFrame) -> dict:
    """Quantos projetos em cada situação (todas as situações, mesmo as com zero)."""
    c = p["situacao"].value_counts()
    return {s: int(c.get(s, 0)) for s in SITUACOES}


def ultimo_subsidio(sub: pd.DataFrame, id_parlamentar: int) -> tuple[str, float, str] | None:
    """(mês AAAAMM, valor, cargo) do último pagamento do vereador, ou None."""
    s = sub[sub["id_parlamentar"] == id_parlamentar].sort_values("ano_mes")
    if s.empty:
        return None
    r = s.iloc[-1]
    return r["ano_mes"], float(r["valor"]), r["cargo"]


def subsidio_na_legislatura(sub: pd.DataFrame, id_parlamentar: int, leg: int) -> tuple[float, int]:
    """Soma do subsídio bruto pago na legislatura e em quantos meses (competências)."""
    ini, fim = LEGISLATURAS[leg]
    s = sub[(sub["id_parlamentar"] == id_parlamentar) & sub["ano_mes"].between(f"{ini}01", f"{fim}12")]
    return float(s["valor"].sum()), int(s["ano_mes"].nunique())


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


# --- Listas


def filtrar(df: pd.DataFrame, texto: str = "", ano: int | None = None, id_parlamentar: int | None = None,
            coluna_ano: str = "ano") -> pd.DataFrame:
    """Filtra por palavras (todas, sem acento e sem caixa, na ementa, nos autores e no número), ano e autor."""
    out = df
    if ano is not None:
        out = out[out[coluna_ano] == ano]
    if id_parlamentar is not None:
        out = out[_do_vereador(out, id_parlamentar)]
    for p in normalizar(texto).split():
        num = out["numero"].astype(str) == p.lstrip("0") if p.isdigit() else False
        out = out[out["busca"].str.contains(p, regex=False) | num]
    return out


def paginar(df: pd.DataFrame, pagina: int, por_pagina: int = POR_PAGINA) -> tuple[pd.DataFrame, int]:
    """Uma página da lista (a partir de 1) e o total de páginas."""
    paginas = max(1, math.ceil(len(df) / por_pagina))
    pagina = min(max(1, pagina), paginas)
    return df.iloc[(pagina - 1) * por_pagina: pagina * por_pagina], paginas


# --- Servidores, despesas, diárias e prestação de contas


def folha_do_mes(folha: pd.DataFrame, mes: str) -> pd.DataFrame:
    f = folha[folha["ano_mes"] == mes]
    return f.sort_values(["total"], ascending=False)[["cargo", "vinculo", "grupo_cargo", "pessoas", "total"]]


def despesas_do_ano(desp: pd.DataFrame, ano: int) -> pd.DataFrame:
    d = desp[desp["ano"] == ano].sort_values("empenhado", ascending=False)
    total = d["empenhado"].sum()
    return d.assign(pct=100 * d["empenhado"] / total if total else 0)


def fornecedores_da_camara(credores: pd.DataFrame, ano: int, n: int = 15) -> pd.DataFrame:
    c = credores[credores["cod_ug"].isin(UGS_CAMARA) & (credores["ano"] == ano) & ~credores["entidade_publica"]]
    return (c.groupby(["cnpj_formatado", "nome_credor"], as_index=False)[["empenhado", "pago"]].sum()
            .sort_values("empenhado", ascending=False).head(n))


def rgf_ultimo_por_ano(rgf: pd.DataFrame) -> pd.DataFrame:
    """O último quadrimestre publicado de cada ano (o 3º é o do ano fechado)."""
    return rgf.sort_values(["ano", "quadrimestre"]).groupby("ano").tail(1).sort_values("ano", ascending=False)


def situacao_rgf(pct: float, alerta: float, prudencial: float, maximo: float) -> str:
    if pct > maximo:
        return "Acima do limite máximo"
    if pct > prudencial:
        return "Acima do limite prudencial"
    if pct > alerta:
        return "Acima do limite de alerta"
    return "Dentro do limite"


# --- Formatos


def fmt_mes(ano_mes: str) -> str:
    return f"{ano_mes[4:]}/{ano_mes[:4]}"


def fmt_data(d) -> str:
    return f"{d[8:10]}/{d[5:7]}/{d[:4]}" if isinstance(d, str) and len(d) >= 10 else "—"


def fmt_periodo(inicio: str, fim: str | float | None) -> str:
    return f"{fmt_data(inicio)} a {fmt_data(fim)}" if isinstance(fim, str) else f"desde {fmt_data(inicio)}"
