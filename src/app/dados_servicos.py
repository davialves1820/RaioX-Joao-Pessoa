"""Carga e funções de apoio da página de serviços públicos (sem dependência do Streamlit)."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from src.config import DATA_PROCESSED

PASTA = DATA_PROCESSED / "servicos"

# Camadas de pontos do mapa, em ordem fixa (a cor segue a camada, nunca a posição)
CAMADAS = {
    "escolas": "Escolas públicas",
    "complementares": "Escolas de atividade complementar ou AEE",
    "ubs": "UBS/USF",
    "outras_saude": "Policlínicas, UPAs e hospitais",
}
SUBTIPO_CAMADA = {
    "Escola": "escolas",
    "Escola de atividade complementar ou AEE": "complementares",
    "UBS/USF": "ubs",
    "Policlínica": "outras_saude",
    "UPA / pronto atendimento": "outras_saude",
    "Hospital": "outras_saude",
}
STATUS_TEXTO = {
    "bairro": "num bairro",
    "fora_de_bairro": "no município, em área sem bairro do IBGE",
    "fora_do_municipio": "coordenada fora do município",
    "sem_coordenada": "sem coordenada",
}


def carregar(pasta: Path = PASTA) -> dict:
    pontos = gpd.read_file(pasta / "pontos_servicos.geojson")
    pontos["camada_mapa"] = pontos["subtipo"].map(SUBTIPO_CAMADA)
    pontos["lon"], pontos["lat"] = pontos.geometry.x, pontos.geometry.y
    verdes = json.loads((pasta / "areas_verdes.geojson").read_text(encoding="utf-8"))
    for i, f in enumerate(verdes["features"]):
        f["id"] = str(i)
    matas = json.loads((pasta / "matas_osm.geojson").read_text(encoding="utf-8"))
    for i, f in enumerate(matas["features"]):
        f["id"] = str(i)
    ind = pd.read_csv(pasta / "indicadores_servicos.csv", dtype={"cd_bairro": str})
    # renda e saneamento do Censo 2022 por bairro (src.process.censo_bairros)
    censo = pd.read_csv(pasta.parent / "censo_bairros.csv", dtype={"cd_bairro": str})
    ind = ind.merge(censo[["cd_bairro", "renda_mediana", "pct_agua_rede", "pct_esgoto_rede", "pct_lixo_coletado"]],
                    on="cd_bairro", how="left")
    return {
        "matas": matas,
        "ind": ind,
        "pontos": pd.DataFrame(pontos.drop(columns="geometry")),
        "nao_atribuidos": pd.read_csv(pasta / "pontos_nao_atribuidos.csv"),
        "verdes": verdes,
        "meta": json.loads((pasta / "metadados.json").read_text(encoding="utf-8")),
    }


def sem_escola_nem_ubs(ind: pd.DataFrame) -> pd.DataFrame:
    """Bairros do ranking sem nenhuma escola regular nem UBS/USF, do mais populoso ao menos."""
    base = ind[ind.entra_no_ranking & ind.sem_escola_nem_ubs]
    return base.sort_values("pop_2022", ascending=False).reset_index(drop=True)


def ranking_menos_servicos(ind: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Bairros com mais habitantes por equipamento (escolas regulares + UBS/USF).

    Só bairros com população mínima (coluna entra_no_ranking) e com ao menos um equipamento;
    os que não têm nenhum ficam em sem_escola_nem_ubs().
    """
    base = ind[ind.entra_no_ranking & ~ind.sem_escola_nem_ubs]
    return base.sort_values("hab_por_equipamento", ascending=False).head(n).reset_index(drop=True)


def componentes_indice(ind: pd.DataFrame) -> pd.DataFrame:
    """As três posições percentuais (0-100) que formam o índice, como no pipeline."""
    out = pd.DataFrame({
        "cd_bairro": ind["cd_bairro"],
        "p_escola": ind["dist_escola_m"].rank(ascending=False, pct=True) * 100,
        "p_ubs": ind["dist_ubs_m"].rank(ascending=False, pct=True) * 100,
        "p_verde": ind["area_verde_m2_hab"].rank(ascending=True, pct=True) * 100,
    })
    return out.round(1)


def servicos_do_bairro(pontos: pd.DataFrame, cd_bairro: str) -> pd.DataFrame:
    p = pontos[(pontos.status == "bairro") & (pontos.cd_bairro == cd_bairro)]
    ordem = {c: i for i, c in enumerate(SUBTIPO_CAMADA)}
    return p.assign(o=p.subtipo.map(ordem)).sort_values(["o", "nome"]).drop(columns="o").reset_index(drop=True)


def comparar(valor, media) -> float | None:
    """Diferença percentual do bairro em relação à média da cidade."""
    if pd.isna(valor) or not media:
        return None
    return 100 * (float(valor) - float(media)) / float(media)


def texto_comparacao(dif: float | None, distancia: bool) -> tuple[str, str] | None:
    """Frase curta e cor da comparação com a média da cidade, sem sinal nem seta.

    Distância: menor é melhor ("mais perto" em verde). Contagens e área: maior é melhor.
    """
    if dif is None:
        return None
    n = f"{abs(dif):.0f}%"
    if n == "0%":
        return "na média", "gray"
    if distancia:
        return (f"{n} mais perto", "green") if dif < 0 else (f"{n} mais longe", "red")
    return (f"{n} acima", "green") if dif > 0 else (f"{n} abaixo", "red")


# (indicador, coluna, coluna da média da cidade ou None, casas decimais, sufixo)
INDICADORES_COMPARACAO = [
    ("Moradores (2022)", "pop_2022", None, 0, ""),
    ("Índice de acesso (0–100)", "indice_acesso", "indice_acesso_mediana", 1, ""),
    ("Distância até a escola", "dist_escola_m", "dist_escola_m", 0, " m"),
    ("Distância até a UBS/USF", "dist_ubs_m", "dist_ubs_m", 0, " m"),
    ("Até a escola, pelas ruas", "dist_escola_rede_m", "dist_escola_rede_m", 0, " m"),
    ("Até a UBS/USF, pelas ruas", "dist_ubs_rede_m", "dist_ubs_rede_m", 0, " m"),
    ("Escolas públicas", "escolas", None, 0, ""),
    ("UBS/USF", "ubs_usf", None, 0, ""),
    ("Escolas por 10 mil hab.", "escolas_por_10mil", "escolas_por_10mil", 2, ""),
    ("UBS/USF por 10 mil hab.", "ubs_usf_por_10mil", "ubs_usf_por_10mil", 2, ""),
    ("Equipes de Saúde da Família por 10 mil hab.", "equipes_esf_por_10mil", "equipes_esf_por_10mil", 2, ""),
    ("Área verde por morador", "area_verde_m2_hab", "area_verde_m2_hab", 1, " m²/hab"),
    ("Educação infantil por 100 crianças de 0–4", "vagas_infantil_por_100", "vagas_infantil_por_100", 1, ""),
    ("Fundamental por 100 crianças de 5–14", "vagas_fund_por_100", "vagas_fund_por_100", 1, ""),
    ("Médio por 100 jovens de 15–19", "vagas_medio_por_100", "vagas_medio_por_100", 1, ""),
    ("Renda mediana do responsável (R$, 2022)", "renda_mediana", None, 0, ""),
    ("Domicílios com esgoto ligado à rede (%)", "pct_esgoto_rede", None, 1, ""),
    ("Praças", "pracas", None, 0, ""),
    ("Parques", "parques", None, 0, ""),
]


def tabela_comparacao(a: pd.Series, b: pd.Series, media: dict) -> pd.DataFrame:
    """Indicadores de dois bairros lado a lado, já formatados, com a média da cidade quando existe.

    A coluna de referência do índice é a mediana dos bairros (o índice é uma posição relativa).
    """
    from src.app.dados import fmt_dec, fmt_int

    def f(v, casas, suf):
        if pd.isna(v):
            return "—"
        return (fmt_int(round(v)) if casas == 0 else fmt_dec(v, casas)) + suf

    linhas = []
    for rotulo, col, col_media, casas, suf in INDICADORES_COMPARACAO:
        linhas.append({
            "Indicador": rotulo,
            a["nm_bairro"]: f(a[col], casas, suf),
            b["nm_bairro"]: f(b[col], casas, suf),
            "Cidade": f(media[col_media], casas, suf) if col_media else "—",
        })
    return pd.DataFrame(linhas)


def correlacao_spearman(x: pd.Series, y: pd.Series) -> float:
    """Spearman = Pearson entre as posições (empates com posição média); sem depender do scipy."""
    return float(pd.Series(x).rank().corr(pd.Series(y).rank()))
