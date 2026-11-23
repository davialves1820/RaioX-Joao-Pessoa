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
# Abaixo disso a taxa por mil moradores não diz nada (Mussuré, área industrial, tem 3 moradores)
POP_MINIMA_TAXA = 1000

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
    dados = {
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
        "pedidos": pd.read_parquet(pasta / "requerimentos_bairros.parquet"),
        "emendas": _emendas(pasta),
        "emendas_empenhos": pd.read_parquet(pasta / "emendas_empenhos.parquet"),
        "meta_emendas": json.loads((pasta / "metadados_emendas.json").read_text(encoding="utf-8")),
        "presencas": pd.read_parquet(pasta / "presencas.parquet"),
        "atas": pd.read_csv(pasta / "atas_presenca.csv"),
        "votos": pd.read_parquet(pasta / "votos_comissoes.parquet"),
        "video": pd.read_csv(pasta / "sessoes_video.csv"),
        "meta_sessoes": json.loads((pasta / "metadados_sessoes.json").read_text(encoding="utf-8")),
        "meta_pedidos": json.loads((pasta / "metadados_pedidos.json").read_text(encoding="utf-8")),
        "meta": json.loads((pasta / "metadados.json").read_text(encoding="utf-8")),
    }
    dados["votacoes"] = votacoes(dados["votos"], dados["vereadores"])
    return dados


def _emendas(pasta: Path) -> pd.DataFrame:
    e = pd.read_parquet(pasta / "emendas.parquet")
    e["busca"] = e[["ementa", "meta", "autores"]].fillna("").agg(" ".join, axis=1).map(normalizar)
    return e


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


# --- Pedidos de obras por bairro


def filtrar_pedidos(rb: pd.DataFrame, ano: int | None = None, tema: str | None = None,
                    id_parlamentar: int | None = None) -> pd.DataFrame:
    out = rb
    if ano is not None:
        out = out[out["ano"] == ano]
    if tema is not None:
        out = out[out["temas"].str.split("; ").map(lambda ts: tema in ts)]
    if id_parlamentar is not None:
        out = out[_do_vereador(out, id_parlamentar)]
    return out


def pedidos_por_bairro(rb: pd.DataFrame, bairros: pd.DataFrame) -> pd.DataFrame:
    """Pedidos (requerimentos distintos) por bairro, por mil moradores (Censo 2022) e tema mais
    frequente. Todos os bairros aparecem, mesmo os sem pedido no filtro."""
    com = rb.dropna(subset=["cd_bairro"])
    n = com.groupby("cd_bairro")["id_materia"].nunique().rename("pedidos")
    temas = com.assign(tema=com["temas"].str.split("; ")).explode("tema")
    temas = temas[temas["tema"].fillna("") != ""]
    principal = (temas.groupby(["cd_bairro", "tema"]).size().reset_index(name="n")
                 .sort_values(["cd_bairro", "n", "tema"], ascending=[True, False, True])
                 .drop_duplicates("cd_bairro").set_index("cd_bairro")["tema"].rename("tema_principal"))
    out = bairros[["cd_bairro", "nm_bairro", "pop_2022"]].set_index("cd_bairro").join(n).join(principal)
    out["pedidos"] = out["pedidos"].fillna(0).astype(int)
    out["por_mil"] = (1000 * out["pedidos"] / out["pop_2022"]).where(out["pop_2022"] >= POP_MINIMA_TAXA)
    return out.reset_index()


def resumo_pedidos(rb: pd.DataFrame) -> dict:
    por_req = rb.drop_duplicates("id_materia")
    total = len(por_req)
    return {"pedidos": total, "com_bairro": int((por_req["n_bairros"] > 0).sum()),
            "sem_bairro": int((por_req["n_bairros"] == 0).sum())}


# --- Emendas impositivas


SITUACOES_EMENDA = ["Empenho encontrado", "Sem empenho encontrado"]


def filtrar_emendas(em: pd.DataFrame, texto: str = "", id_parlamentar: int | None = None,
                    situacao: str | None = None, conferencia: str | None = None) -> pd.DataFrame:
    out = em
    if id_parlamentar is not None:
        out = out[_do_vereador(out, id_parlamentar)]
    if situacao is not None:
        out = out[out["situacao"] == situacao]
    if conferencia is not None:
        out = out[out["conferencia"] == conferencia]
    for p in normalizar(texto).split():
        num = out["numero"].astype(str) == p.lstrip("0") if p.isdigit() else False
        out = out[out["busca"].str.contains(p, regex=False) | num]
    return out.sort_values(["ano", "numero"], ascending=[False, True])


def resumo_emendas(em: pd.DataFrame) -> dict:
    return {
        "emendas": int(len(em)),
        "valor": float(em["valor"].sum()),
        "sem_valor": int(em["valor"].isna().sum()),
        "com_empenho": int((em["situacao"] == "Empenho encontrado").sum()),
        "empenhado": float(em["empenhado"].sum()),
        "pago": float(em["pago"].sum()),
    }


def emendas_por_vereador(em: pd.DataFrame, ver: pd.DataFrame) -> pd.DataFrame:
    """Emendas, valor, empenhado e pago por vereador autor, em ordem alfabética."""
    e = em.assign(id_parlamentar=em["autores_ids"].fillna("").str.split(";")).explode("id_parlamentar")
    e = e[e["id_parlamentar"] != ""].astype({"id_parlamentar": int})
    t = e.groupby("id_parlamentar").agg(emendas=("id_materia", "nunique"), valor=("valor", "sum"),
                                        com_empenho=("situacao", lambda s: int((s == "Empenho encontrado").sum())),
                                        empenhado=("empenhado", "sum"), pago=("pago", "sum"))
    nomes = ver.drop_duplicates("id_parlamentar").set_index("id_parlamentar")["nome_parlamentar"]
    t = t.join(nomes).reset_index()
    t["ordem"] = t["nome_parlamentar"].map(normalizar)
    return t.sort_values("ordem").drop(columns="ordem")


# --- Presença nas sessões (pelas atas) e votos nas comissões

SITUACOES_PRESENCA = ["Presente", "Presente (virtual)", "Ausente com justificativa", "Ausente"]
CANAL_CAMARA = "https://www.youtube.com/@TvCamaraJP"


def presenca_por_vereador(pres: pd.DataFrame, ver: pd.DataFrame, leg: int, ano: int | None = None) -> pd.DataFrame:
    """Uma linha por vereador listado nas atas conferidas, em ordem alfabética, com as sessões por situação."""
    p = pres[pres["legislatura"] == leg]
    if ano:
        p = p[p["data"].str.startswith(str(ano))]
    t = p.pivot_table(index="id_parlamentar", columns="situacao", values="id_sessao", aggfunc="count", fill_value=0)
    t = t.reindex(columns=SITUACOES_PRESENCA, fill_value=0)
    t["sessoes"] = t.sum(axis=1)
    t["pct_presente"] = 100 * (t["Presente"] + t["Presente (virtual)"]) / t["sessoes"]
    nomes = ver.drop_duplicates("id_parlamentar").set_index("id_parlamentar")["nome_parlamentar"]
    t = t.reset_index().assign(nome_parlamentar=lambda x: x["id_parlamentar"].map(nomes))
    return t.assign(o=t["nome_parlamentar"].map(normalizar)).sort_values("o").drop(columns="o").reset_index(drop=True)


def presenca_do_vereador(pres: pd.DataFrame, id_parlamentar: int, leg: int) -> dict[str, int]:
    p = pres[(pres["legislatura"] == leg) & (pres["id_parlamentar"] == id_parlamentar)]
    return {s: int((p["situacao"] == s).sum()) for s in SITUACOES_PRESENCA}


def presenca_da_sessao(pres: pd.DataFrame, ver: pd.DataFrame, id_sessao: int) -> dict[str, list[str]]:
    """Nomes por situação numa sessão, em ordem alfabética (vazio se a ata não foi conferida)."""
    nomes = ver.drop_duplicates("id_parlamentar").set_index("id_parlamentar")["nome_parlamentar"]
    p = pres[pres["id_sessao"] == id_sessao]
    return {s: sorted(p.loc[p["situacao"] == s, "id_parlamentar"].map(nomes), key=normalizar)
            for s in SITUACOES_PRESENCA if (p["situacao"] == s).any()}


def votacoes(votos: pd.DataFrame, ver: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por votação nas comissões, com os nomes por voto, da mais recente para a mais antiga."""
    nomes = ver.drop_duplicates("id_parlamentar").set_index("id_parlamentar")["nome_parlamentar"]
    v = votos.assign(nome=votos["id_parlamentar"].map(nomes))
    g = v.groupby("id_votacao")
    out = g.first()[["data", "sigla_comissao", "comissao", "id_materia", "materia", "sigla", "tipo", "numero", "ano",
                     "ementa", "observacao", "resultado", "link_sapl"]]
    for voto, col in (("Sim", "sim"), ("Não", "nao"), ("Abstenção", "abstencao"), ("Não Votou", "nao_votou")):
        out[col] = g.apply(lambda x, vt=voto: sorted(x.loc[x["voto"] == vt, "nome"].dropna(), key=normalizar),
                           include_groups=False)
    out["ids"] = g["id_parlamentar"].apply(lambda x: set(x))
    out["divergencia"] = out["nao"].map(len) + out["abstencao"].map(len) > 0
    out["busca"] = out[["materia", "ementa", "observacao"]].fillna("").agg(" ".join, axis=1).map(normalizar)
    return out.reset_index().sort_values(["data", "id_votacao"], ascending=[False, False], ignore_index=True)


def filtrar_votacoes(vt: pd.DataFrame, texto: str = "", comissao: str | None = None, ano: int | None = None,
                     id_parlamentar: int | None = None, so_divergencia: bool = False) -> pd.DataFrame:
    if texto:
        vt = vt[vt["busca"].str.contains(normalizar(texto), regex=False)]
    if comissao:
        vt = vt[vt["sigla_comissao"] == comissao]
    if ano:
        vt = vt[vt["data"].str.startswith(str(ano))]
    if id_parlamentar:
        vt = vt[vt["ids"].map(lambda ids: id_parlamentar in ids)]
    if so_divergencia:
        vt = vt[vt["divergencia"]]
    return vt


def votos_do_vereador(votos: pd.DataFrame, id_parlamentar: int, leg: int) -> pd.DataFrame:
    ini, fim = LEGISLATURAS[leg]
    v = votos[(votos["id_parlamentar"] == id_parlamentar) & votos["data"].str[:4].astype(int).between(ini, fim)]
    return v.sort_values("data", ascending=False, ignore_index=True)


# --- Formatos


def fmt_mes(ano_mes: str) -> str:
    return f"{ano_mes[4:]}/{ano_mes[:4]}"


def fmt_data(d) -> str:
    return f"{d[8:10]}/{d[5:7]}/{d[:4]}" if isinstance(d, str) and len(d) >= 10 else "—"


def fmt_periodo(inicio: str, fim: str | float | None) -> str:
    return f"{fmt_data(inicio)} a {fmt_data(fim)}" if isinstance(fim, str) else f"desde {fmt_data(inicio)}"
