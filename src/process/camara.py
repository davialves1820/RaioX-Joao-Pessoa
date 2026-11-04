"""Processa os dados da Câmara Municipal: vereadores, produção legislativa, projetos, presença,
subsídio e folha de pessoal.

Entradas (data/raw): camara_sapl/*.json (src/collect/camara_sapl.py) e tce_pb/servidores-AAAA.zip
(src/collect/tce_pb.py).

Saídas (data/processed/camara/):
- vereadores.csv     um mandato por linha (18ª e 19ª legislaturas), com partido atual
- producao.csv       matérias por vereador, ano e grupo de tipo (coautoria conta para cada autor)
- producao_origem.csv matérias por ano, grupo e origem (vereadores, Executivo, Mesa, comissões...)
- projetos.parquet   projetos de lei (ordinária e complementar), com autores e situação
- presenca.csv       presença nas sessões ordinárias por vereador e ano, só nas sessões em que
                     a Câmara registrou presença e em que o vereador estava no exercício do mandato
- subsidio.csv       valor bruto mensal pago a cada vereador (folha do TCE-PB)
- folha.csv          folha da Câmara por mês, vínculo e grupo de cargo: pessoas e total, sem nomes
- metadados.json

Uso: python -m src.process.camara
"""

from __future__ import annotations

import json
import re
import zipfile
from datetime import date, datetime, timezone

import pandas as pd

from src.collect.download import load_manifest
from src.config import ANO_INICIAL_CAMARA, DATA_PROCESSED, DATA_RAW, LEGISLATURAS_CAMARA
from src.process.despesas_regras import centavos, normalizar

RAW = DATA_RAW / "camara_sapl"
RAW_TCE = DATA_RAW / "tce_pb"
SAIDA = DATA_PROCESSED / "camara"
SAPL = "https://sapl.joaopessoa.pb.leg.br"
UG_CAMARA = "Câmara Municipal de João Pessoa"

# Siglas dos tipos de matéria do SAPL -> grupo exibido. Siglas fora daqui vão para "Outros".
GRUPOS = {
    "PLO": "Projetos de lei", "PLC": "Projetos de lei",
    "PELO": "Propostas de emenda à Lei Orgânica",
    "PRE": "Projetos de resolução",
    "PDL": "Projetos de decreto legislativo",
    "IND": "Indicações", "PI": "Indicações",
    "R-OSM": "Requerimentos de obras e serviços",
    # O SAPL de João Pessoa não tem o tipo "moção"; os votos de aplauso, pesar etc. são
    # requerimentos (art. 171, X, do Regimento Interno).
    "R-VOT": "Votos de aplauso, pesar e similares",
    "ELO-I": "Emendas impositivas ao orçamento", "EI-CO": "Emendas impositivas ao orçamento",
}
GRUPO_REQUERIMENTO = "Outros requerimentos"
GRUPO_EMENDA = "Emendas e substitutivos"
GRUPO_OUTROS = "Outros"
TIPOS_PROJETO = {"PLO", "PLC"}

SITUACOES = ["Virou lei", "Vetado", "Rejeitado em plenário", "Retirado pelo autor", "Arquivado",
             "Em tramitação", "Sem conclusão registrada"]

TIPO_SESSAO_ORDINARIA = "SESSÃO ORDINÁRIA"

# Vínculos da folha do TCE-PB, cujos nomes mudam entre os anos
VINCULOS = {
    "ELETIVO": "Eletivo", "ELETIVOS": "Eletivo",
    "COMISSIONADO": "Comissionado", "CARGO COMISSIONADO": "Comissionado",
    "EFETIVO": "Efetivo", "EFETIVOS": "Efetivo",
    "A DISPOSICAO": "À disposição",
    "INATIVOS/PENSIONISTAS": "Inativos e pensionistas", "INATIVOS / PENSIONISTAS": "Inativos e pensionistas",
}

# Eletivos da folha cujo nome não é igual ao nome completo do SAPL (o SAPL às vezes abrevia ou
# grafa diferente). Cada par foi conferido pelo período: os meses na folha caem dentro do mandato
# registrado no SAPL.
CORRESPONDENCIA_FOLHA = {
    "ANTONIO FABIO SOARES CARNEIRO": 508,             # Fábio Carneiro, 19ª, desde 01/2025
    "EDER CAXIAS MENESES MAIA": 515,                  # Eder da Jampa, suplente, 08/05 a 08/09/2026
    "FABIO NOBREGA LOPES": 507,                       # Fábio Lopes, 19ª, desde 01/2025
    "FABIOLA LEVI MEIRA": 486,                        # Fabíola Rezende, suplente desde 05/04/2022
    "FERNANDO PAULO CARRILHO MILANES NETO": 455,      # Milanez Neto (Milanez com z no SAPL)
    "FRANCISCO RINALDO MARANHAO DE FIGUEIREDO": 489,  # Rinaldo Maranhão, suplente, 07/07 a 31/12/2022
    "ICARO FERNANDO DE OLIVEIRA CHAVES": 510,         # Ícaro Chaves, 19ª, desde 01/2025
    "JAILMA VASCONCELOS DE CARVALHO": 506,            # Jailma Carvalho, 19ª, desde 01/2025
    "KLEBER GERALDO LAURENTINO DOS SANTOS": 514,      # Kleber Geraldo, suplente desde 07/01/2026
    "MOISES FIGUEREDO FERREIRA LIMA": 505,            # Mô Lima, suplente (08–11/2024 e desde 03/2025)
    "PAULO TARCISIO PESSOA JARDIM": 484,              # Tarcísio Jardim
    "RAISSA GOMES LACERDA R DE AQUINO": 349,          # Raíssa Lacerda, suplente, 12/05/2023 a 21/10/2024
    "RICARDO DA SILVA ALMEIDA": 512,                  # Guguinha Moov Jampa ("Ricardo Almeida" na biografia do SAPL)
    "ROMULO LOPES DANTAS COELHO": 509,                # Rômulo Dantas, 19ª, desde 01/2025
    "VALDIR TRINDADE DOS SANTOS": 511,                # Valdir Trindade, 19ª, desde 01/2025
}


def _ler(nome: str):
    return json.loads((RAW / nome).read_text(encoding="utf-8"))


def _anos() -> list[int]:
    anos = sorted(int(re.search(r"(\d{4})", f.name)[1]) for f in RAW.glob("materias-*.json"))
    return [a for a in anos if a >= ANO_INICIAL_CAMARA]


def grupo(sigla: str) -> str:
    if sigla in GRUPOS:
        return GRUPOS[sigla]
    if sigla == "REQ" or sigla.startswith("R-"):
        return GRUPO_REQUERIMENTO
    if sigla.startswith(("E-", "ELO-")) or sigla in {"EMEND", "SUBEM", "SUBS"}:
        return GRUPO_EMENDA
    return GRUPO_OUTROS


# --- Cadastros


def cadastros() -> dict:
    autores = {a["id"]: a for a in _ler("autores.json")}
    tipos_autor = {t["id"]: t["descricao"] for t in _ler("tipos_autor.json")}
    return {
        "parlamentares": {p["id"]: p for p in _ler("parlamentares.json")},
        "autores": autores,
        "tipos_autor": tipos_autor,
        "tipos": {t["id"]: t for t in _ler("tipos_materia.json")},
        "status": {s["id"]: s for s in _ler("status_tramitacao.json")},
        "tipos_norma": {t["id"]: t["descricao"] for t in _ler("tipos_norma.json")},
        "partidos": {p["id"]: p["sigla"] for p in _ler("partidos.json")},
    }


def parlamentar_do_autor(autor: dict) -> int | None:
    """O autor do tipo 'Parlamentar' aponta para o parlamentar pelo object_id."""
    return int(autor["object_id"]) if autor["tipo"] == 1 else None


def vereadores(c: dict) -> pd.DataFrame:
    filiacoes = pd.DataFrame(_ler("filiacoes.json"))
    atual = (filiacoes[filiacoes["data_desfiliacao"].isna()].sort_values("data")
             .groupby("parlamentar")["partido"].last())
    linhas = []
    for m in _ler("mandatos.json"):
        if m["legislatura"] not in LEGISLATURAS_CAMARA:
            continue
        p = c["parlamentares"][m["parlamentar"]]
        linhas.append({
            "id_parlamentar": p["id"],
            "nome_parlamentar": p["nome_parlamentar"].strip(),
            "nome_completo": p["nome_completo"].strip(),
            "legislatura": m["legislatura"],
            "titular": m["titular"],
            "inicio_mandato": m["data_inicio_mandato"],
            "fim_mandato": m["data_fim_mandato"],
            "partido_atual": c["partidos"].get(atual.get(p["id"])),
            "foto": p["fotografia"],
            "link_sapl": f"{SAPL}/parlamentar/{p['id']}",
        })
    return pd.DataFrame(linhas).sort_values(["legislatura", "nome_parlamentar", "inicio_mandato"])


# --- Matérias


def materias(c: dict, anos: list[int]) -> pd.DataFrame:
    linhas = []
    for ano in anos:
        for m in _ler(f"materias-{ano}.json"):
            sigla = c["tipos"][m["tipo"]]["sigla"]
            linhas.append({
                "id_materia": m["id"], "ano": m["ano"], "numero": m["numero"], "sigla": sigla,
                "tipo": c["tipos"][m["tipo"]]["descricao"], "grupo": grupo(sigla),
                "data_apresentacao": m["data_apresentacao"], "ementa": " ".join(m["ementa"].split()),
                "em_tramitacao": m["em_tramitacao"], "autores": m["autores"],
            })
    return pd.DataFrame(linhas)


def autoria(mat: pd.DataFrame, c: dict) -> pd.DataFrame:
    """Uma linha por matéria e autor, com o tipo do autor e o parlamentar (se for vereador)."""
    a = mat[["id_materia", "ano", "grupo", "sigla", "autores"]].explode("autores").dropna(subset=["autores"])
    a["autores"] = a["autores"].astype(int)
    a["tipo_autor"] = [c["tipos_autor"][c["autores"][i]["tipo"]] for i in a["autores"]]
    a["id_parlamentar"] = [parlamentar_do_autor(c["autores"][i]) for i in a["autores"]]
    return a.rename(columns={"autores": "id_autor"})


def producao(aut: pd.DataFrame) -> pd.DataFrame:
    v = aut.dropna(subset=["id_parlamentar"]).astype({"id_parlamentar": int})
    return (v.groupby(["id_parlamentar", "ano", "grupo"]).size().rename("materias").reset_index()
            .sort_values(["id_parlamentar", "ano", "grupo"]))


def producao_origem(mat: pd.DataFrame, aut: pd.DataFrame) -> pd.DataFrame:
    """Matérias por origem, contando cada matéria uma vez (pelo primeiro autor)."""
    primeiro = aut.drop_duplicates("id_materia").set_index("id_materia")["tipo_autor"]
    m = mat.assign(origem=mat["id_materia"].map(primeiro).fillna("Sem autor registrado"))
    return m.groupby(["ano", "grupo", "origem"]).size().rename("materias").reset_index()


# --- Projetos de lei e situação


def situacao(em_tramitacao: bool, ultima: dict | None, status: dict) -> tuple[str, str]:
    """Situação de um projeto que não virou lei, pela última tramitação. Devolve (situação, último status)."""
    if ultima is None:
        return ("Em tramitação" if em_tramitacao else "Sem conclusão registrada"), ""
    desc = status[ultima["status"]]["descricao"]
    txt = normalizar(f"{desc} {ultima['texto']}")
    if em_tramitacao:
        return "Em tramitação", desc
    if "VETO" in txt:
        return "Vetado", desc
    if desc == "Rejeitado em Votação Plenária":
        return "Rejeitado em plenário", desc
    if "PEDIDO DO AUTOR" in txt or desc == "Retirado a pedido do autor(ra)":
        return "Retirado pelo autor", desc
    if "ARQUIV" in txt:
        return "Arquivado", desc
    return "Sem conclusão registrada", desc


def projetos(mat: pd.DataFrame, aut: pd.DataFrame, c: dict, anos: list[int]) -> pd.DataFrame:
    normas = pd.DataFrame([n for ano in range(anos[0], date.today().year + 1)
                           if (RAW / f"normas-{ano}.json").exists() for n in _ler(f"normas-{ano}.json")])
    normas = normas[normas["materia"].notna()].sort_values("data").drop_duplicates("materia", keep="first")
    norma = normas.set_index("materia")
    tram = {int(k): v for ano in anos for k, v in _ler(f"tramitacoes_projetos-{ano}.json").items()}

    nomes = {}
    for _, r in aut.iterrows():
        a = c["autores"][r["id_autor"]]
        nome = (c["parlamentares"][r["id_parlamentar"]]["nome_parlamentar"].strip()
                if r["id_parlamentar"] is not None and r["id_parlamentar"] == r["id_parlamentar"] else a["nome"])
        nomes.setdefault(r["id_materia"], []).append(nome)
    origem = aut.drop_duplicates("id_materia").set_index("id_materia")["tipo_autor"]

    p = mat[mat["sigla"].isin(TIPOS_PROJETO)].copy()
    linhas = []
    for _, m in p.iterrows():
        ts = tram.get(m["id_materia"], [])
        ultima = max(ts, key=lambda t: (t["data_tramitacao"], t["id"])) if ts else None
        if m["id_materia"] in norma.index:
            n = norma.loc[m["id_materia"]]
            sit, ult = "Virou lei", ""
            lei = {"norma": f"{c['tipos_norma'][n['tipo']]} nº {n['numero']}/{n['ano']}",
                   "data_norma": n["data"], "link_norma": f"{SAPL}/norma/{n['id']}"}
        else:
            sit, ult = situacao(m["em_tramitacao"], ultima, c["status"])
            lei = {"norma": None, "data_norma": None, "link_norma": None}
        linhas.append({
            "id_materia": m["id_materia"], "sigla": m["sigla"], "numero": m["numero"], "ano": m["ano"],
            "data_apresentacao": m["data_apresentacao"], "ementa": m["ementa"],
            "origem": origem.get(m["id_materia"], "Sem autor registrado"),
            "autores": "; ".join(nomes.get(m["id_materia"], [])),
            "situacao": sit, "ultimo_status": ult,
            "data_ultima_tramitacao": ultima["data_tramitacao"] if ultima else None,
            **lei, "link_sapl": f"{SAPL}/materia/{m['id_materia']}",
        })
    out = pd.DataFrame(linhas)
    out["autores_ids"] = out["id_materia"].map(
        aut.dropna(subset=["id_parlamentar"]).groupby("id_materia")["id_parlamentar"]
        .apply(lambda s: ";".join(str(int(x)) for x in s)))
    return out


# --- Presença nas sessões ordinárias


def presenca(ver: pd.DataFrame, c: dict) -> tuple[pd.DataFrame, dict]:
    tipos = {t["id"]: t["nome"] for t in _ler("tipos_sessao.json")}
    sessoes = pd.DataFrame(_ler("sessoes.json"))
    sessoes = sessoes[sessoes["tipo"].map(tipos) == TIPO_SESSAO_ORDINARIA].copy()
    sessoes["data"] = pd.to_datetime(sessoes["data_inicio"])
    sessoes = sessoes[(sessoes["data"].dt.year >= ANO_INICIAL_CAMARA)
                      & (sessoes["data"] <= pd.Timestamp(date.today()))]
    pres = pd.DataFrame(_ler("presencas.json"))
    com_registro = set(pres["sessao_plenaria"])
    presentes = set(zip(pres["sessao_plenaria"], pres["parlamentar"]))
    s = sessoes[sessoes["id"].isin(com_registro)]

    linhas = []
    for (pid, leg), mandatos in ver.groupby(["id_parlamentar", "legislatura"]):
        no_mandato = pd.Series(False, index=s.index)
        for _, m in mandatos.iterrows():
            no_mandato |= (s["data"] >= m["inicio_mandato"]) & (s["data"] <= (m["fim_mandato"] or "2100-01-01"))
        sm = s[no_mandato]
        for ano, g in sm.groupby(sm["data"].dt.year):
            linhas.append({"id_parlamentar": pid, "legislatura": leg, "ano": int(ano),
                           "sessoes_com_registro": len(g),
                           "presente": sum((i, pid) in presentes for i in g["id"])})
    resumo = {
        "sessoes_ordinarias": int(len(sessoes)),
        "sessoes_ordinarias_com_presenca_registrada": int(len(s)),
        "por_ano": {int(a): [int(len(g)), int(g["id"].isin(com_registro).sum())]
                    for a, g in sessoes.groupby(sessoes["data"].dt.year)},
    }
    return pd.DataFrame(linhas), resumo


# --- Folha de pessoal (TCE-PB)


def ler_folha(anos: list[int]) -> pd.DataFrame:
    partes = []
    for ano in anos:
        caminho = RAW_TCE / f"servidores-{ano}.zip"
        with zipfile.ZipFile(caminho) as z, z.open(z.namelist()[0]) as f:
            df = pd.read_csv(f, sep=";", dtype=str, encoding="utf-8-sig")
        partes.append(df[df["descricao_unidade_gestora"] == UG_CAMARA])
    df = pd.concat(partes, ignore_index=True)
    df["valor_centavos"] = df["valor_vantagem"].map(centavos)
    df["vinculo"] = df["tipo_cargo"].map(lambda t: VINCULOS.get(normalizar(t), "Outros"))
    return df


def grupo_cargo(vinculo: str, cargo: str) -> str:
    c = normalizar(cargo)
    if vinculo == "Eletivo":
        return "Vereadores"
    if vinculo == "À disposição":
        return "Cedidos por outros órgãos"
    if "VEREADOR" in c:
        return "Gabinetes dos vereadores"
    if "MESA" in c or "PRESIDEN" in c:
        return "Mesa Diretora e Presidência"
    if "COMISS" in c:
        return "Comissões"
    if "LIDERANCA" in c:
        return "Lideranças"
    if re.search(r"\bTV\b|RADIO|PORTAL|MIDIA|COMUNIC|CERIMONIAL", c):
        return "Comunicação e cerimonial"
    return "Administração e apoio"


def folha(df: pd.DataFrame) -> pd.DataFrame:
    df = df.assign(grupo_cargo=[grupo_cargo(v, c) for v, c in zip(df["vinculo"], df["descricao_cargo"])])
    out = (df.groupby(["ano_mes", "vinculo", "grupo_cargo"])
           .agg(pessoas=("matricula", "nunique"), total_centavos=("valor_centavos", "sum")).reset_index())
    out["total"] = out["total_centavos"] / 100
    return out.drop(columns="total_centavos")


def subsidio(df: pd.DataFrame, ver: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Valor bruto mensal de cada vereador na folha, ligado ao SAPL pelo nome completo ou pela
    tabela CORRESPONDENCIA_FOLHA."""
    el = df[df["vinculo"] == "Eletivo"].copy()
    por_nome = {normalizar(n): i for i, n in zip(ver["id_parlamentar"], ver["nome_completo"])}
    por_nome.update(CORRESPONDENCIA_FOLHA)
    el["id_parlamentar"] = el["nome_servidor"].map(lambda n: por_nome.get(normalizar(n)))
    sem = sorted(el.loc[el["id_parlamentar"].isna(), "nome_servidor"].map(normalizar).unique())
    el = el.dropna(subset=["id_parlamentar"]).astype({"id_parlamentar": int})
    el["cargo"] = el["descricao_cargo"].map(lambda c: "Presidente" if "PRESIDENTE" in normalizar(c) else "Vereador")
    out = (el.groupby(["id_parlamentar", "ano_mes", "cargo"])["valor_centavos"].sum() / 100).rename("valor").reset_index()
    return out, sem


def checar(mat: pd.DataFrame, aut: pd.DataFrame, proj: pd.DataFrame, ver: pd.DataFrame) -> dict:
    """Checagens que interrompem o pipeline se falharem; devolve um resumo para os metadados."""
    sem_autor = int(mat["autores"].map(len).eq(0).sum())
    autores_vereadores = set(aut["id_parlamentar"].dropna().astype(int))
    fora = autores_vereadores - set(ver["id_parlamentar"])
    if fora:
        raise ValueError(f"autores parlamentares sem mandato nas legislaturas {LEGISLATURAS_CAMARA}: {sorted(fora)}")
    if not proj["situacao"].isin(SITUACOES).all():
        raise ValueError("situação desconhecida em projetos")
    return {
        "materias": int(len(mat)),
        "materias_sem_autor": sem_autor,
        "projetos_por_situacao": proj["situacao"].value_counts().to_dict(),
    }


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    anos = _anos()
    c = cadastros()
    ver = vereadores(c)
    mat = materias(c, anos)
    aut = autoria(mat, c)
    proj = projetos(mat, aut, c, anos)
    resumo = checar(mat, aut, proj, ver)
    pres, info_pres = presenca(ver, c)
    df_folha = ler_folha([a for a in anos if (RAW_TCE / f"servidores-{a}.zip").exists()])
    sub, sem_par = subsidio(df_folha, ver)

    ver.to_csv(SAIDA / "vereadores.csv", index=False)
    producao(aut).to_csv(SAIDA / "producao.csv", index=False)
    producao_origem(mat, aut).to_csv(SAIDA / "producao_origem.csv", index=False)
    proj.to_parquet(SAIDA / "projetos.parquet", index=False)
    pres.to_csv(SAIDA / "presenca.csv", index=False)
    sub.to_csv(SAIDA / "subsidio.csv", index=False)
    folha(df_folha).to_csv(SAIDA / "folha.csv", index=False)

    manifest = load_manifest()
    meta = {
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "anos": anos,
        "legislaturas": list(LEGISLATURAS_CAMARA),
        "ultimo_mes_folha": df_folha["ano_mes"].max(),
        "checagens": resumo,
        "presenca": info_pres,
        "eletivos_sem_correspondencia_no_sapl": sem_par,
        "regras": {
            "producao": "cada matéria conta uma vez para cada vereador autor ou coautor; grupos por tipo do SAPL",
            "situacao": ("'Virou lei' quando uma norma jurídica do SAPL aponta para o projeto; nos demais, "
                         "pela marcação 'em tramitação' e pelo status e texto da última tramitação"),
            "presenca": ("sessões ordinárias com presença registrada no SAPL, dentro do período de mandato; "
                         "faltas justificadas não são descontadas"),
            "subsidio": "campo valor_vantagem da folha do TCE-PB: total bruto do mês (inclui 13º e meses proporcionais)",
            "folha": "pessoas distintas (matrícula) e total bruto por mês, vínculo e grupo de cargo; sem nomes",
            "subsidio_legal": {
                "norma": "Lei 14.702/2022",
                "link": f"{SAPL}/media/sapl/public/normajuridica/2022/19248/lei_no_14702-2022.pdf",
                "vereador": 26000.0, "presidente": 32000.0, "vigencia": "2025-01-01 a 2028-12-31",
            },
        },
        "arquivos_brutos": {k: v for k, v in manifest.items()
                            if k.startswith("camara_sapl/") or k.startswith("tce_pb/servidores-")},
    }
    (SAIDA / "metadados.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(mat):,} matérias ({anos[0]}–{anos[-1]}), {len(proj):,} projetos de lei, "
          f"{ver['id_parlamentar'].nunique()} vereadores")
    print(resumo)
    if sem_par:
        print("Eletivos da folha sem correspondência no SAPL:", sem_par)


if __name__ == "__main__":
    main()
