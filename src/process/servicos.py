"""Serviços públicos e acesso por bairro: escolas (INEP), unidades de saúde (CNES) e áreas verdes.

Entradas (data/raw): inep/catalogo_escolas_PB.csv, cnes/*.json, filipeia/ (parques, tabela de
praças, quadras e bairros), geodata_jp/{pracas,escolas_publicas}.geojson, osm/*.json,
ibge_censo2022/PB_setores_CD2022.gpkg e PB_bairros_CD2022.gpkg; população por bairro de data/processed/indicadores_bairros.csv.

Saídas em data/processed/servicos/ (ver README). Distâncias e áreas sempre em SIRGAS 2000 /
UTM 25S (EPSG:31985), nunca em graus.

Uso: python -m src.process.servicos
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import shapely.ops

from src.collect.download import load_manifest
from src.config import COD_MUNICIPIO, CRS_METRICO, CRS_WEB, DATA_PROCESSED, DATA_RAW
from src.process import censo2022

SAIDA = DATA_PROCESSED / "servicos"

# --- Escolas (INEP)
ESCOLA_REGULAR = "Escola"
ESCOLA_COMPLEMENTAR = "Escola de atividade complementar ou AEE"

# --- Saúde (CNES): tipos de unidade pedidos, agrupados
GRUPOS_SAUDE = {
    1: "UBS/USF", 2: "UBS/USF",
    4: "Policlínica",
    73: "UPA / pronto atendimento", 20: "UPA / pronto atendimento", 21: "UPA / pronto atendimento",
    5: "Hospital", 7: "Hospital", 15: "Hospital",
}

STATUS_BAIRRO = "bairro"
STATUS_FORA_BAIRRO = "fora_de_bairro"  # dentro do município, em área que o IBGE não atribui a bairro
STATUS_FORA_MUNICIPIO = "fora_do_municipio"
STATUS_SEM_COORD = "sem_coordenada"

# Bairros com menos moradores que isto ficam fora do ranking "mais gente e menos serviços"
POP_MIN_RANKING = 1000


# --- leitura das fontes


def _num(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(serie.astype(str).str.strip().str.replace(",", ".", regex=False), errors="coerce")


def escolas() -> tuple[pd.DataFrame, dict]:
    """Escolas públicas em funcionamento em João Pessoa, com a origem da coordenada."""
    cat = pd.read_csv(DATA_RAW / "inep" / "catalogo_escolas_PB.csv", dtype=str, encoding="utf-8-sig")
    if set(cat["UF"]) != {"PB"}:
        raise ValueError("catálogo do INEP com escolas de fora da PB")
    jp = cat[cat["Município"] == "João Pessoa"]
    pub = jp[jp["Categoria Administrativa"] == "Pública"]
    restricao = pub["Restrição de Atendimento"].fillna("")
    fechada = restricao.str.contains("PARALISADA|EXTINTA")
    ativ = pub[~fechada].copy()
    funil = {
        "catalogo_PB": int(len(cat)),
        "joao_pessoa": int(len(jp)),
        "publicas": int(len(pub)),
        "paralisadas_ou_extintas": int(fechada.sum()),
        "publicas_em_funcionamento": int(len(ativ)),
    }
    ativ["subtipo"] = np.where(
        ativ["Restrição de Atendimento"].str.contains("EXCLUSIVA"), ESCOLA_COMPLEMENTAR, ESCOLA_REGULAR
    )
    ativ["lat"], ativ["lon"] = _num(ativ["Latitude"]), _num(ativ["Longitude"])
    ativ["fonte_coordenada"] = np.where(ativ["lat"].notna() & ativ["lon"].notna(), "INEP, Catálogo de Escolas", None)

    # Coordenada ausente no catálogo: usa a do geodata-jp (versão de 2022 do mesmo catálogo), se houver
    gd = gpd.read_file(DATA_RAW / "geodata_jp" / "escolas_publicas.geojson")
    gd = gd.assign(cod=gd["cod_inep"].astype(str), glon=gd.geometry.x, glat=gd.geometry.y)
    # Um mesmo ponto repetido em várias escolas de endereços diferentes é marcador genérico, não
    # localização (no geodata-jp, 12 escolas em -7.145192, -34.859117): esse ponto não é usado.
    repetida = gd.duplicated(["glat", "glon"], keep=False)
    funil["geodata_jp_coordenada_repetida_descartada"] = int(
        ativ["fonte_coordenada"].isna().where(ativ["Código INEP"].isin(gd.loc[repetida, "cod"]), False).sum()
    )
    gd = gd[~repetida].set_index("cod")
    falta = ativ["fonte_coordenada"].isna() & ativ["Código INEP"].isin(gd.index)
    ativ.loc[falta, "lat"] = ativ.loc[falta, "Código INEP"].map(gd["glat"])
    ativ.loc[falta, "lon"] = ativ.loc[falta, "Código INEP"].map(gd["glon"])
    ativ.loc[falta, "fonte_coordenada"] = "geodata-jp (Catálogo de Escolas do INEP, versão de 2022)"
    funil["coordenada_completada_pelo_geodata_jp"] = int(falta.sum())

    # Ainda sem coordenada: usa o elemento do OpenStreetMap conferido à mão (ver src/collect/osm.py)
    osm = _escolas_osm()
    falta = ativ["fonte_coordenada"].isna() & ativ["Código INEP"].isin(osm.index)
    ativ.loc[falta, "lat"] = ativ.loc[falta, "Código INEP"].map(osm["lat"])
    ativ.loc[falta, "lon"] = ativ.loc[falta, "Código INEP"].map(osm["lon"])
    ativ.loc[falta, "fonte_coordenada"] = "OpenStreetMap (" + ativ.loc[falta, "Código INEP"].map(osm["elemento"]) + ")"
    funil["coordenada_completada_pelo_openstreetmap"] = int(falta.sum())

    out = pd.DataFrame({
        "id": "inep:" + ativ["Código INEP"],
        "camada": "escola",
        "subtipo": ativ["subtipo"],
        "nome": ativ["Escola"],
        "detalhe": "Rede " + ativ["Dependência Administrativa"].str.lower(),
        "endereco": ativ["Endereço"],
        "lat": ativ["lat"], "lon": ativ["lon"],
        "fonte_coordenada": ativ["fonte_coordenada"],
        "arquivo_origem": "inep/catalogo_escolas_PB.csv",
    })
    return out.reset_index(drop=True), funil


def _escolas_osm() -> pd.DataFrame:
    """Coordenada das escolas de ESCOLAS_OSM, indexada pelo código INEP (ponto do OSM ou centro do contorno)."""
    from src.collect.osm import ESCOLAS_OSM

    resp = json.loads((DATA_RAW / "osm" / "escolas.json").read_text(encoding="utf-8"))
    linhas = []
    for cod, elemento in ESCOLAS_OSM.items():
        els = resp[elemento]["elements"]
        if elemento.startswith("node/"):
            lon, lat = els[0]["lon"], els[0]["lat"]
        else:
            nos = {e["id"]: (e["lon"], e["lat"]) for e in els if e["type"] == "node"}
            via = next(e for e in els if e["type"] == "way")
            c = shapely.Polygon([nos[n] for n in via["nodes"]]).centroid
            lon, lat = c.x, c.y
        linhas.append({"cod": cod, "elemento": elemento, "lat": lat, "lon": lon})
    return pd.DataFrame(linhas).set_index("cod")


def saude() -> tuple[pd.DataFrame, dict]:
    """Rede SUS ativa dos tipos pedidos (UBS/USF, policlínicas, UPAs e hospitais)."""
    e = pd.DataFrame(json.loads((DATA_RAW / "cnes" / "estabelecimentos_250750.json").read_text(encoding="utf-8")))
    tipos = json.loads((DATA_RAW / "cnes" / "tipounidades.json").read_text(encoding="utf-8"))["tipos_unidade"]
    nome_tipo = {int(t["codigo_tipo_unidade"]): t["descricao_tipo_unidade"] for t in tipos}
    if set(e["codigo_municipio"].astype(str)) != {COD_MUNICIPIO[:6]}:
        raise ValueError("CNES com estabelecimentos de outro município")
    funil = {"cnes_joao_pessoa": int(len(e))}
    e = e[e["codigo_tipo_unidade"].isin(GRUPOS_SAUDE)]
    funil["tipos_pedidos"] = int(len(e))
    e = e[e["codigo_motivo_desabilitacao_estabelecimento"].isna()]
    funil["ativos"] = int(len(e))
    publico = e["descricao_natureza_juridica_estabelecimento"].astype(str).str.startswith("1")
    sus = e["estabelecimento_faz_atendimento_ambulatorial_sus"] == "SIM"
    e = e[publico | sus]
    funil["rede_sus_publicos_ou_atendem_sus"] = int(len(e))
    # Cadastros de regulação (ex.: "HOSPITAL X REGULACAO SESPB") não são unidades de atendimento
    regulacao = e["nome_fantasia"].fillna("").str.contains("REGULACAO")
    e = e[~regulacao]
    funil["sem_cadastros_de_regulacao"] = int(len(e))
    nat_pub = e["descricao_natureza_juridica_estabelecimento"].astype(str).str.startswith("1")
    out = pd.DataFrame({
        "id": "cnes:" + e["codigo_cnes"].astype(str),
        "camada": "saude",
        "subtipo": e["codigo_tipo_unidade"].map(GRUPOS_SAUDE),
        "nome": e["nome_fantasia"].str.strip(),
        "detalhe": np.where(nat_pub, "Pública", "Privada ou filantrópica que atende pelo SUS")
                   + " · " + e["codigo_tipo_unidade"].map(nome_tipo).str.capitalize(),
        "endereco": (e["endereco_estabelecimento"].fillna("") + ", " + e["numero_estabelecimento"].fillna("")
                     + " - " + e["bairro_estabelecimento"].fillna("")).str.strip(" ,-"),
        "lat": pd.to_numeric(e["latitude_estabelecimento_decimo_grau"], errors="coerce"),
        "lon": pd.to_numeric(e["longitude_estabelecimento_decimo_grau"], errors="coerce"),
        "fonte_coordenada": "CNES",
        "arquivo_origem": "cnes/estabelecimentos_250750.json",
        "cnes_atualizado_em": e["data_atualizacao"],
    })
    out.loc[out["lat"].isna() | out["lon"].isna(), "fonte_coordenada"] = None
    return out.reset_index(drop=True), funil


def setores() -> gpd.GeoDataFrame:
    g = gpd.read_file(DATA_RAW / "ibge_censo2022" / "PB_setores_CD2022.gpkg")
    g = g[g["CD_MUN"] == COD_MUNICIPIO]
    pop = pd.to_numeric(g["v0001"], errors="raise").astype(int)
    return gpd.GeoDataFrame(
        {"cd_setor": g["CD_SETOR"], "cd_bairro": g["CD_BAIRRO"].where(g["CD_BAIRRO"] != "."), "pop": pop},
        geometry=g.geometry, crs=g.crs,
    ).to_crs(CRS_METRICO).reset_index(drop=True)


# --- geoprocessamento


def atribuir_bairro(pontos: pd.DataFrame, bairros: gpd.GeoDataFrame, municipio) -> gpd.GeoDataFrame:
    """Classifica cada ponto e atribui exatamente um bairro aos que caem dentro de um."""
    g = gpd.GeoDataFrame(
        pontos, geometry=gpd.points_from_xy(pontos["lon"], pontos["lat"]), crs=CRS_WEB
    ).to_crs(CRS_METRICO)
    sem = pontos["lat"].isna() | pontos["lon"].isna()
    g.loc[sem, "geometry"] = None
    g["status"] = STATUS_SEM_COORD
    com = ~sem
    dentro = pd.Series(False, index=g.index)
    dentro[com] = g.loc[com].geometry.within(municipio)
    g.loc[com & ~dentro, "status"] = STATUS_FORA_MUNICIPIO
    g.loc[com & dentro, "status"] = STATUS_FORA_BAIRRO
    # 'intersects' pega também pontos exatamente na divisa; se cair em dois bairros, fica com o de menor código
    j = gpd.sjoin(g.loc[com & dentro, ["geometry"]], bairros[["cd_bairro", "geometry"]], predicate="intersects")
    j = j.sort_values("cd_bairro")
    na_divisa = int(j.index.duplicated().sum())
    j = j[~j.index.duplicated(keep="first")]
    g["cd_bairro"] = j["cd_bairro"].reindex(g.index)
    g.loc[g["cd_bairro"].notna(), "status"] = STATUS_BAIRRO
    g.attrs["pontos_na_divisa"] = na_divisa
    return g


def _poligonos(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Geometrias válidas, só as partes de área, uma linha por feição original."""
    g = g.to_crs(CRS_METRICO)
    g["geometry"] = shapely.make_valid(g.geometry.values)
    g = g.explode(index_parts=False)
    g = g[g.geom_type.isin(["Polygon", "MultiPolygon"])]
    return g.dissolve(level=0).reset_index(drop=True)  # junta de volta as partes de cada feição


def pracas() -> tuple[gpd.GeoDataFrame, dict]:
    """Praças: contornos do geodata-jp, conferidos com a tabela oficial do Filipeia.

    O Filipeia não oferece o shapefile das praças, só a tabela. Cada praça do geodata-jp precisa ter
    na tabela uma linha com o mesmo nome e a mesma área (texto idêntico); senão o pipeline para.
    A posição é conferida com o código cartográfico (setor + quadra) e as quadras do Filipeia.
    """
    g = gpd.read_file(DATA_RAW / "geodata_jp" / "pracas.geojson")
    tab = pd.read_csv(DATA_RAW / "filipeia" / "pracas.csv", dtype=str)
    chave = lambda nome, area: nome.fillna("").str.strip() + "|" + area.fillna("").str.strip()  # noqa: E731
    k_geo, k_tab = chave(g["nome"], g["area"]), chave(tab["NOME"], tab["AREA"])
    if len(g) != len(tab) or sorted(k_geo) != sorted(k_tab):
        raise ValueError("as praças do geodata-jp não batem com a tabela do Filipeia")

    g = g.assign(cod=k_geo.map(dict(zip(k_tab, tab["CODI_CART"].fillna("").str.strip()))))
    q = gpd.read_file(f"zip://{DATA_RAW / 'filipeia' / 'quadras_gerais.zip'}").to_crs(CRS_METRICO)
    quadra = q.assign(k=q["setor"] + q["qd_atual"]).dissolve("k").geometry
    g = _poligonos(g)
    com_cod = g["cod"].str.fullmatch(r"\d{9}") & (g["cod"] != "000000000") & g["cod"].str[:5].isin(quadra.index)
    dist = g[com_cod].geometry.distance(quadra.reindex(g.loc[com_cod, "cod"].str[:5]), align=False)
    info = {
        "pracas_conferidas_com_tabela_filipeia": int(len(g)),
        "pracas_com_quadra_no_cadastro_atual": int(com_cod.sum()),
        "pracas_dentro_ou_encostadas_na_quadra_5m": int((dist <= 5).sum()),
    }
    return g.assign(tipo="Praça", nome=g["nome"].str.strip())[["nome", "tipo", "geometry"]], info


def parques() -> gpd.GeoDataFrame:
    """Parques municipais: shapefile oficial do Filipeia (SAD69 / UTM 25S, reprojetado)."""
    g = _poligonos(gpd.read_file(f"zip://{DATA_RAW / 'filipeia' / 'Parques_Municipais.zip'}"))
    return g.assign(tipo="Parque", nome=g["Layer"].str.split().str.join(" "))[["nome", "tipo", "geometry"]]


def areas_verdes(bairros: gpd.GeoDataFrame, municipio) -> tuple[gpd.GeoDataFrame, pd.DataFrame, dict]:
    """Praças e parques (Filipeia): área por bairro, sem contar sobreposições duas vezes."""
    pr, info_pracas = pracas()
    verdes = gpd.GeoDataFrame(pd.concat([pr, parques()], ignore_index=True), geometry="geometry", crs=CRS_METRICO)
    uniao = verdes.geometry.union_all()
    info = {
        "pracas": int((verdes.tipo == "Praça").sum()),
        "parques": int((verdes.tipo == "Parque").sum()),
        "area_somada_m2": round(float(verdes.area.sum()), 1),
        "area_sem_sobreposicao_m2": round(float(uniao.area), 1),
        "fora_do_municipio_m2": round(float(uniao.difference(municipio).area), 1),
        **info_pracas,
    }
    area_bairro = bairros.set_index("cd_bairro").geometry.intersection(uniao).area
    # contagem: praça no bairro do seu ponto interno; parque em todo bairro que ele toca
    rp = gpd.GeoDataFrame(verdes[verdes.tipo == "Praça"].drop(columns="geometry"),
                          geometry=verdes[verdes.tipo == "Praça"].geometry.representative_point(), crs=CRS_METRICO)
    n_pracas = gpd.sjoin(rp, bairros[["cd_bairro", "geometry"]], predicate="within").groupby("cd_bairro").size()
    pq = verdes[verdes.tipo == "Parque"]
    n_parques = gpd.sjoin(pq, bairros[["cd_bairro", "geometry"]], predicate="intersects").groupby("cd_bairro").size()
    por_bairro = pd.DataFrame({"area_verde_m2": area_bairro.round(1), "pracas": n_pracas, "parques": n_parques})
    por_bairro[["pracas", "parques"]] = por_bairro[["pracas", "parques"]].fillna(0).astype(int)
    return verdes, por_bairro.rename_axis("cd_bairro").reset_index(), info


def _osm_poligonos(arquivo: str) -> gpd.GeoDataFrame:
    """Polígonos de uma resposta 'out geom' do Overpass (vias fechadas e multipolígonos)."""
    linhas = []
    for e in json.loads((DATA_RAW / "osm" / arquivo).read_text(encoding="utf-8"))["elements"]:
        t, g = e.get("tags", {}), None
        if e["type"] == "way" and e.get("geometry"):
            c = [(p["lon"], p["lat"]) for p in e["geometry"]]
            if len(c) >= 4 and c[0] == c[-1]:
                g = shapely.Polygon(c)
        elif e["type"] == "relation":
            def aneis(papel):
                ls = [shapely.LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                      for m in e.get("members", []) if m.get("geometry") and m.get("role") in papel]
                return shapely.union_all(list(shapely.ops.polygonize(ls))) if ls else None
            externo, interno = aneis(("outer", "")), aneis(("inner",))
            g = externo.difference(interno) if externo is not None and interno is not None else externo
        if g is not None and not g.is_empty:
            tipo = ("Área protegida" if t.get("boundary") == "protected_area" else
                    "Mata" if t.get("natural") == "wood" or t.get("landuse") == "forest" else "Parque")
            linhas.append({"osm": f"{e['type']}/{e['id']}", "nome": t.get("name"), "tipo": tipo,
                           "geometry": shapely.make_valid(g)})
    return gpd.GeoDataFrame(linhas, geometry="geometry", crs=CRS_WEB).to_crs(CRS_METRICO)


def matas_osm(municipio) -> tuple[gpd.GeoDataFrame, dict]:
    """Matas e áreas protegidas do OpenStreetMap recortadas pelo município (fora do índice)."""
    g = _osm_poligonos("matas.json")
    g["geometry"] = g.geometry.intersection(municipio)
    g = g[~g.is_empty & (g.area > 0)].copy()
    g = g[g.geom_type.isin(["Polygon", "MultiPolygon"]) | (g.geom_type == "GeometryCollection")]
    g["geometry"] = g.geometry.apply(lambda x: shapely.union_all([p for p in getattr(x, "geoms", [x])
                                                                 if p.geom_type in ("Polygon", "MultiPolygon")]))
    g = g[~g.is_empty]
    nomeadas = g[g.nome.notna()].assign(ha=lambda x: (x.area / 1e4).round(1)).sort_values("ha", ascending=False)
    info = {
        "poligonos": int(len(g)),
        "area_uniao_ha": round(float(g.geometry.union_all().area) / 1e4, 1),
        "com_nome": [{"nome": r.nome, "tipo": r.tipo, "ha": float(r.ha), "osm": r.osm} for r in nomeadas.itertuples()],
    }
    return g, info


def parques_osm_fora_do_cadastro(verdes: gpd.GeoDataFrame, municipio, ha_min: float = 1.0) -> list[dict]:
    """Parques, hortos e bosques do OSM que ficam quase todos (>= 80%) fora das praças e parques do cadastro."""
    g = _osm_poligonos("parques.json")
    g["geometry"] = g.geometry.intersection(municipio)
    # só os que se apresentam como parque, horto ou bosque (o OSM também marca campos de futebol como "park")
    g = g[g.nome.fillna("").str.contains(r"Parque|Horto|Bosque", case=False) & ~g.is_empty]
    uniao = verdes.geometry.union_all()
    g = g[(g.area >= ha_min * 1e4) & (g.geometry.difference(uniao).area / g.area >= 0.8)]
    g = g.assign(ha=(g.area / 1e4).round(1)).sort_values("ha", ascending=False)
    return [{"nome": r.nome, "ha": float(r.ha), "osm": r.osm} for r in g.itertuples()]


def distancia_mais_proxima(origens: gpd.GeoSeries, destinos: gpd.GeoSeries) -> np.ndarray:
    """Distância em linha reta (metros, EPSG:31985) de cada origem ao destino mais próximo."""
    if origens.crs != CRS_METRICO or destinos.crs != CRS_METRICO:
        raise ValueError("distâncias só em EPSG:31985")
    arvore = shapely.STRtree(destinos.values)
    idx = arvore.nearest(origens.values)
    return shapely.distance(origens.values, destinos.values[idx])


def indice_acesso(ind: pd.DataFrame, pesos: tuple[float, float, float] = (1, 1, 1)) -> pd.Series:
    """Média de três posições percentuais (0-100) entre os bairros: perto da escola, perto da UBS/USF
    e mais área verde por habitante. 100 = melhor posição nos três. `pesos` = (escola, UBS, verde);
    o índice publicado usa pesos iguais."""
    p_escola = ind["dist_escola_m"].rank(ascending=False, pct=True) * 100
    p_ubs = ind["dist_ubs_m"].rank(ascending=False, pct=True) * 100
    p_verde = ind["area_verde_m2_hab"].rank(ascending=True, pct=True) * 100
    comp = pd.concat([p_escola, p_ubs, p_verde], axis=1)
    return (comp * list(pesos)).sum(axis=1).div(sum(pesos)).round(1)


# Cenários de pesos (escola, UBS/USF, área verde) para medir o quanto o ranking depende da escolha
CENARIOS_PESOS = {
    "pesos iguais (publicado)": (1, 1, 1),
    "escola com peso dobrado": (2, 1, 1),
    "UBS/USF com peso dobrado": (1, 2, 1),
    "área verde com peso dobrado": (1, 1, 2),
    "sem área verde": (1, 1, 0),
    "só escola": (1, 0, 0),
    "só UBS/USF": (0, 1, 0),
}


def sensibilidade_indice(ind: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Posição de cada bairro em cada cenário de pesos e o quanto ela muda em relação à publicada."""
    base = indice_acesso(ind).rank(ascending=False, method="min")
    posicoes, resumo = {}, []
    for nome, pesos in CENARIOS_PESOS.items():
        pos = indice_acesso(ind, pesos).rank(ascending=False, method="min")
        posicoes[nome] = pos.astype(int)
        mudanca = (pos - base).abs()
        top10 = set(base[base <= 10].index)
        resumo.append({
            "cenario": nome, "pesos": list(pesos),
            # Spearman = Pearson entre as posições (sem depender do scipy)
            "correlacao_spearman": round(float(base.rank().corr(pos.rank())), 3),
            "mudanca_media_posicoes": round(float(mudanca.mean()), 1),
            "mudanca_maxima_posicoes": int(mudanca.max()),
            "bairros_que_mudam_mais_de_10_posicoes": int((mudanca > 10).sum()),
            "top10_publicado": len(top10),  # pode passar de 10 com empates na 10ª posição
            "top10_mantidos": len(top10 & set(pos[pos <= 10].index)),
        })
    return pd.DataFrame(posicoes), resumo


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    bairros = censo2022.malha_bairros_2022().to_crs(CRS_METRICO)
    st = setores()
    municipio = st.geometry.union_all()
    pop_bairro = pd.read_csv(DATA_PROCESSED / "indicadores_bairros.csv", dtype={"cd_bairro": str}).set_index("cd_bairro")["pop_2022"]

    esc, funil_esc = escolas()
    sau, funil_sau = saude()
    pontos = atribuir_bairro(pd.concat([esc, sau], ignore_index=True), bairros, municipio)
    if pontos["id"].duplicated().any():
        raise ValueError("pontos com id repetido")

    verdes, verde_bairro, info_verde = areas_verdes(bairros, municipio)
    matas, info_matas = matas_osm(municipio)
    info_matas["parques_osm_fora_do_cadastro"] = parques_osm_fora_do_cadastro(verdes, municipio)

    # --- distâncias (só destinos dentro do município)
    no_mun = pontos["status"].isin([STATUS_BAIRRO, STATUS_FORA_BAIRRO])
    dest = {
        "escola": pontos[no_mun & (pontos.subtipo == ESCOLA_REGULAR)].geometry,
        "ubs": pontos[no_mun & (pontos.subtipo == "UBS/USF")].geometry,
    }
    centroides = bairros.set_index("cd_bairro").geometry.centroid
    sc = st[st["pop"] > 0].copy()
    sc_cent = sc.geometry.centroid
    dist = pd.DataFrame(index=bairros["cd_bairro"])
    cidade = {}
    for nome, d in dest.items():
        dist[f"dist_{nome}_centroide_m"] = distancia_mais_proxima(centroides, d).round(0)
        sc[f"d_{nome}"] = distancia_mais_proxima(sc_cent, d)
        pond = sc.dropna(subset=["cd_bairro"]).groupby("cd_bairro").apply(
            lambda x: np.average(x[f"d_{nome}"], weights=x["pop"]), include_groups=False
        )
        dist[f"dist_{nome}_m"] = pond.round(0)
        cidade[f"dist_{nome}_m"] = round(float(np.average(sc[f"d_{nome}"], weights=sc["pop"])), 0)

    # --- contagens por bairro
    atrib = pontos[pontos.status == STATUS_BAIRRO]
    cont = atrib.pivot_table(index="cd_bairro", columns="subtipo", values="id", aggfunc="count", fill_value=0)
    colunas = {ESCOLA_REGULAR: "escolas", ESCOLA_COMPLEMENTAR: "escolas_complementares", "UBS/USF": "ubs_usf",
               "Policlínica": "policlinicas", "UPA / pronto atendimento": "upas", "Hospital": "hospitais"}
    cont = cont.reindex(columns=list(colunas), fill_value=0).rename(columns=colunas)

    ind = bairros[["cd_bairro", "nm_bairro"]].set_index("cd_bairro")
    ind["area_km2_calc"] = (bairros.set_index("cd_bairro").area / 1e6).round(3)
    ind["pop_2022"] = pop_bairro
    ind = ind.join(cont).fillna({c: 0 for c in colunas.values()})
    ind[list(colunas.values())] = ind[list(colunas.values())].astype(int)
    ind = ind.join(verde_bairro.set_index("cd_bairro")).join(dist)
    for c in ["escolas", "ubs_usf"]:
        ind[f"{c}_por_10mil"] = (10000 * ind[c] / ind["pop_2022"]).round(2)
    ind["area_verde_m2_hab"] = (ind["area_verde_m2"] / ind["pop_2022"]).round(2)
    ind["equipamentos"] = ind["escolas"] + ind["ubs_usf"]
    ind["hab_por_equipamento"] = (ind["pop_2022"] / ind["equipamentos"].replace(0, np.nan)).round(0)
    ind["sem_escola_nem_ubs"] = ind["equipamentos"] == 0
    ind["entra_no_ranking"] = ind["pop_2022"] >= POP_MIN_RANKING
    ind["indice_acesso"] = indice_acesso(ind)
    posicoes, sensibilidade = sensibilidade_indice(ind)
    posicoes.insert(0, "nm_bairro", ind["nm_bairro"])
    ind = ind.reset_index()
    ind.to_csv(SAIDA / "indicadores_servicos.csv", index=False)
    posicoes.rename_axis("cd_bairro").reset_index().to_csv(SAIDA / "sensibilidade_indice.csv", index=False)

    # --- média da cidade (para a comparação na página do bairro)
    pop_total = int(ind["pop_2022"].sum())
    media = {
        "pop_bairros": pop_total,
        "escolas_por_10mil": round(10000 * int(ind["escolas"].sum()) / pop_total, 2),
        "ubs_usf_por_10mil": round(10000 * int(ind["ubs_usf"].sum()) / pop_total, 2),
        "area_verde_m2_hab": round(float(ind["area_verde_m2"].sum()) / pop_total, 2),
        **cidade,
        "indice_acesso_mediana": float(ind["indice_acesso"].median()),
    }

    # --- camadas para o mapa e pontos não atribuídos
    com_geo = pontos[pontos.geometry.notna()].to_crs(CRS_WEB)
    cols = ["id", "camada", "subtipo", "nome", "detalhe", "endereco", "fonte_coordenada", "status", "cd_bairro", "arquivo_origem"]
    if (SAIDA / "pontos_servicos.geojson").exists():
        (SAIDA / "pontos_servicos.geojson").unlink()
    com_geo[cols + ["geometry"]].to_file(SAIDA / "pontos_servicos.geojson", driver="GeoJSON")
    # Para os pontos fora dos bairros do IBGE, o bairro da Prefeitura (Filipeia), só como informação
    fb = gpd.read_file(f"zip://{DATA_RAW / 'filipeia' / 'bairros.zip'}").to_crs(CRS_METRICO)
    nao = pontos[pontos.status != STATUS_BAIRRO]
    j = gpd.sjoin(nao[nao.geometry.notna()][["geometry"]], fb[["N_BAIRRO", "geometry"]], predicate="within")
    nao = nao.assign(bairro_prefeitura=j[~j.index.duplicated()]["N_BAIRRO"].str.title().reindex(nao.index))
    nao[["id", "camada", "subtipo", "nome", "endereco", "status", "bairro_prefeitura", "lat", "lon"]].to_csv(
        SAIDA / "pontos_nao_atribuidos.csv", index=False
    )
    v = verdes.copy()
    v["area_m2"] = v.area.round(1)
    v["geometry"] = v.geometry.simplify(1.0)
    if (SAIDA / "areas_verdes.geojson").exists():
        (SAIDA / "areas_verdes.geojson").unlink()
    v.to_crs(CRS_WEB).to_file(SAIDA / "areas_verdes.geojson", driver="GeoJSON")
    m = matas.copy()
    m["area_m2"] = m.area.round(1)
    m["geometry"] = m.geometry.simplify(2.0)
    if (SAIDA / "matas_osm.geojson").exists():
        (SAIDA / "matas_osm.geojson").unlink()
    m.to_crs(CRS_WEB).to_file(SAIDA / "matas_osm.geojson", driver="GeoJSON")

    resumo = pontos.groupby(["camada", "subtipo", "status"]).size().unstack(fill_value=0)
    manifest = load_manifest()
    meta = {
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "crs_calculos": CRS_METRICO,
        "funil": {"escolas": funil_esc, "saude": funil_sau},
        "pontos_por_status": {f"{c} | {s}": row.to_dict() for (c, s), row in resumo.iterrows()},
        "total_fonte_filtrada": {"escola": int(len(esc)), "saude": int(len(sau))},
        "pontos_na_divisa_entre_bairros": pontos.attrs.get("pontos_na_divisa", 0),
        "areas_verdes": info_verde,
        "matas_osm": info_matas,
        "sensibilidade_indice": sensibilidade,
        "media_cidade": media,
        "setores": {"total": int(len(st)), "com_moradores": int(len(sc)), "pop_total": int(st["pop"].sum()),
                    "pop_fora_de_bairro": int(st.loc[st.cd_bairro.isna(), "pop"].sum())},
        "pop_min_ranking": POP_MIN_RANKING,
        "arquivos_brutos": {k: x for k, x in manifest.items()
                            if k.startswith(("inep/", "cnes/", "filipeia/", "osm/", "geodata_jp/pracas",
                                             "geodata_jp/escolas", "ibge_censo2022/PB_setores"))},
    }
    (SAIDA / "metadados.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({k: meta[k] for k in ["funil", "pontos_por_status", "areas_verdes", "media_cidade"]}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
