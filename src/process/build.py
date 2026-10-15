"""Gera os dados prontos para o app em data/processed/.

Saídas:
- bairros_jp.geojson         geometria dos bairros (malha IBGE 2022, simplificada para web)
- indicadores_bairros.csv    população 2010/2022, variação, densidade, comparabilidade
- crosswalk_bairros.csv      correspondência de nomes IBGE 2022 x IBGE 2010 x Filipeia
- totais_municipio.csv       total do município x soma dos bairros, por ano
- metadados.json             origem de cada coluna e dos arquivos brutos (URL, data, SHA-256)

Uso: python -m src.process.build
"""

from __future__ import annotations

import json
import unicodedata
from datetime import datetime, timezone

import geopandas as gpd
import pandas as pd
import shapely

from src.collect.download import load_manifest
from src.config import (
    CRS_METRICO,
    CRS_WEB,
    DATA_PROCESSED,
    DATA_RAW,
    IOU_COM_RESSALVA,
    IOU_COMPARAVEL,
    TOLERANCIA_TOTAL_MUNICIPIO,
)
from src.process import censo2010, censo2022
from src.process.indicadores import classificar_comparabilidade, densidade, iou, variacao

# Tolerância da simplificação da geometria para o mapa (metros). A simplificação
# é feita em conjunto (coverage_simplify), então bairros vizinhos continuam
# encaixados, sem buracos nem sobreposições. A área usada na densidade é a
# publicada pelo IBGE, não a da geometria simplificada.
TOLERANCIA_SIMPLIFICACAO_M = 5.0


def _normalizar(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.upper().split())


def _geometria_web(malha: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    m = malha.to_crs(CRS_METRICO)
    m["geometry"] = shapely.coverage_simplify(m.geometry.values, TOLERANCIA_SIMPLIFICACAO_M)
    m = m.to_crs(CRS_WEB)
    m["geometry"] = shapely.set_precision(m.geometry.values, 1e-6)  # ~0,1 m
    return m


def _iou_2010_2022(malha22: gpd.GeoDataFrame, malha10: gpd.GeoDataFrame) -> pd.DataFrame:
    m22 = malha22.to_crs(CRS_METRICO).set_index("cd_bairro")
    m10 = malha10.to_crs(CRS_METRICO).set_index("cd_bairro")
    linhas = []
    for cd, geom in m22.geometry.items():
        if cd in m10.index:
            g10 = m10.geometry[cd]
            linhas.append((cd, round(iou(geom, g10), 3), round(g10.area / 1e6, 3)))
        else:
            linhas.append((cd, None, None))
    return pd.DataFrame(linhas, columns=["cd_bairro", "iou_limites_2010_2022", "area_km2_2010_calc"])


def _crosswalk(ind: pd.DataFrame, malha22: gpd.GeoDataFrame) -> pd.DataFrame:
    """Liga cada bairro IBGE ao bairro Filipeia de maior sobreposição e registra divergências."""
    fil = gpd.read_file(DATA_RAW / "geodata_jp" / "bairros.geojson").to_crs(CRS_METRICO)
    m22 = malha22.to_crs(CRS_METRICO)
    linhas = []
    for _, b in m22.iterrows():
        inter = fil.intersection(b.geometry).area
        k = inter.idxmax()
        f = fil.loc[k]
        linhas.append(
            {
                "cd_bairro": b.cd_bairro,
                "nm_filipeia": f["nome"],
                "cod_filipeia": f["cod"],
                "iou_ibge2022_filipeia": round(iou(b.geometry, f.geometry), 3),
            }
        )
    cw = ind[["cd_bairro", "nm_bairro", "nm_bairro_2010", "iou_limites_2010_2022"]].merge(
        pd.DataFrame(linhas), on="cd_bairro", how="left"
    )
    cw = cw.rename(columns={"nm_bairro": "nm_ibge_2022", "nm_bairro_2010": "nm_ibge_2010"})

    if cw["nm_filipeia"].duplicated().any():
        raise ValueError("dois bairros IBGE caíram no mesmo bairro Filipeia: revisar correspondência")

    def observacoes(r) -> str:
        obs = []
        n22 = _normalizar(r.nm_ibge_2022)
        if pd.isna(r.nm_ibge_2010):
            obs.append("bairro não existia no Censo 2010")
        elif _normalizar(r.nm_ibge_2010) != n22:
            obs.append("nome difere entre IBGE 2010 e 2022")
        if _normalizar(r.nm_filipeia) != n22:
            obs.append("nome difere entre IBGE e Filipeia")
        if r.cod_filipeia == "XX":
            obs.append("Filipeia sem código oficial (XX)")
        elif r.cod_filipeia != r.cd_bairro[-2:] and r.cd_bairro[-3:] != "0" + r.cod_filipeia:
            obs.append("código Filipeia diferente do código IBGE")
        if r.iou_ibge2022_filipeia < IOU_COMPARAVEL:
            obs.append(f"limite IBGE difere do Filipeia (IoU {r.iou_ibge2022_filipeia:.2f})")
        if pd.notna(r.iou_limites_2010_2022) and r.iou_limites_2010_2022 < IOU_COMPARAVEL:
            obs.append(f"limite mudou entre 2010 e 2022 (IoU {r.iou_limites_2010_2022:.2f})")
        return "; ".join(obs)

    cw["observacoes"] = cw.apply(observacoes, axis=1)
    return cw[
        ["cd_bairro", "nm_ibge_2022", "nm_ibge_2010", "nm_filipeia", "cod_filipeia",
         "iou_ibge2022_filipeia", "iou_limites_2010_2022", "observacoes"]
    ]


def main() -> None:
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    # --- 2022
    pop22 = censo2022.populacao_bairros_2022()
    malha22 = censo2022.malha_bairros_2022()
    total22 = censo2022.total_municipio_2022()
    if set(pop22.cd_bairro) != set(malha22.cd_bairro):
        raise ValueError("bairros da tabela 2022 e da malha 2022 não coincidem")

    # --- 2010
    setores = censo2010.setores_2010()
    pop10 = censo2010.populacao_bairros_2010(setores)
    malha10 = censo2010.malha_bairros_2010(setores)
    total10 = int(setores["pop"].sum())
    sem_bairro10 = setores[setores.cd_bairro == censo2010.COD_SEM_BAIRRO]
    bairros_2010_fora_de_2022 = set(pop10.cd_bairro) - set(pop22.cd_bairro)
    if bairros_2010_fora_de_2022:
        raise ValueError(f"bairros de 2010 sem correspondente em 2022: {bairros_2010_fora_de_2022}")

    # --- indicadores
    ind = pop22.merge(pop10, on="cd_bairro", how="left").merge(
        _iou_2010_2022(malha22, malha10), on="cd_bairro", how="left"
    )
    ind["pop_2010"] = ind["pop_2010"].astype("Int64")
    ind["setores_2010"] = ind["setores_2010"].astype("Int64")
    ind["comparabilidade"] = classificar_comparabilidade(ind["iou_limites_2010_2022"])
    ind = pd.concat([ind, variacao(ind.pop_2010, ind.pop_2022, ind.comparabilidade)], axis=1)
    ind["densidade_2022"] = densidade(ind.pop_2022, ind.area_km2)
    ind = ind[
        ["cd_bairro", "nm_bairro", "area_km2", "pop_2022", "domicilios_2022", "densidade_2022",
         "nm_bairro_2010", "pop_2010", "setores_2010", "var_abs", "var_pct",
         "iou_limites_2010_2022", "area_km2_2010_calc", "comparabilidade"]
    ]
    ind.to_csv(DATA_PROCESSED / "indicadores_bairros.csv", index=False)

    # --- geometria para o mapa
    geo = _geometria_web(malha22[["cd_bairro", "nm_bairro", "geometry"]])
    if (DATA_PROCESSED / "bairros_jp.geojson").exists():
        (DATA_PROCESSED / "bairros_jp.geojson").unlink()
    geo.to_file(DATA_PROCESSED / "bairros_jp.geojson", driver="GeoJSON")

    # --- correspondência de nomes
    _crosswalk(ind, malha22).to_csv(DATA_PROCESSED / "crosswalk_bairros.csv", index=False)

    # --- totais
    totais = pd.DataFrame(
        [
            {
                "ano": 2010,
                "pop_municipio": total10,
                "soma_bairros": int(pop10.pop_2010.sum()),
                "fonte_total": "soma de todos os setores de 2010 do município (Domicilio02 V001)",
            },
            {
                "ano": 2022,
                "pop_municipio": total22,
                "soma_bairros": int(pop22.pop_2022.sum()),
                "fonte_total": "Agregados_por_municipios_basico_BR, v0001",
            },
        ]
    )
    totais["fora_de_bairros"] = totais.pop_municipio - totais.soma_bairros
    totais["pct_fora_de_bairros"] = (100 * totais.fora_de_bairros / totais.pop_municipio).round(2)
    totais.to_csv(DATA_PROCESSED / "totais_municipio.csv", index=False)

    # --- metadados
    manifest = load_manifest()
    meta = {
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "parametros": {
            "iou_comparavel": IOU_COMPARAVEL,
            "iou_com_ressalva": IOU_COM_RESSALVA,
            "tolerancia_total_municipio": TOLERANCIA_TOTAL_MUNICIPIO,
            "tolerancia_simplificacao_m": TOLERANCIA_SIMPLIFICACAO_M,
        },
        "colunas": {
            "pop_2022": "ibge_censo2022/Agregados_por_bairros_basico_BR_20260520.zip, coluna v0001 (Total de pessoas)",
            "domicilios_2022": "ibge_censo2022/Agregados_por_bairros_basico_BR_20260520.zip, coluna v0002 (Total de domicílios)",
            "area_km2": "ibge_censo2022/Agregados_por_bairros_basico_BR_20260520.zip, coluna AREA_KM2",
            "densidade_2022": "pop_2022 / area_km2",
            "pop_2010": "ibge_censo2010/PB_20260615.zip, Domicilio02_PB.csv V001 somado por Cod_bairro do Basico_PB.csv",
            "var_abs": "pop_2022 - pop_2010 (vazio se não comparável)",
            "var_pct": "100 * (pop_2022 - pop_2010) / pop_2010 (vazio se não comparável)",
            "iou_limites_2010_2022": "interseção/união entre setores de 2010 dissolvidos por bairro (pb_setores_censitarios.zip) e o bairro na malha 2022 (PB_bairros_CD2022.gpkg), em EPSG:31985",
            "area_km2_2010_calc": "área calculada do bairro de 2010 (setores dissolvidos), não é número publicado pelo IBGE",
            "comparabilidade": f"IoU >= {IOU_COMPARAVEL}: comparável; >= {IOU_COM_RESSALVA}: com ressalva; abaixo ou sem bairro em 2010: não comparável",
            "geometria": "ibge_censo2022/PB_bairros_CD2022.gpkg, simplificada (coverage_simplify) para web",
        },
        "pop_sem_bairro_2010": {
            "setores": int(len(sem_bairro10)),
            "pessoas": int(sem_bairro10["pop"].sum()),
        },
        "arquivos_brutos": {
            k: v for k, v in manifest.items() if k.startswith(("ibge_censo2022/", "ibge_censo2010/", "geodata_jp/"))
        },
    }
    (DATA_PROCESSED / "metadados.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(totais.to_string(index=False))
    print(ind.comparabilidade.value_counts().to_string())
    print(f"arquivos em {DATA_PROCESSED}")


if __name__ == "__main__":
    main()
