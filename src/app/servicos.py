"""Página "Serviços públicos e acesso": escolas, unidades de saúde e áreas verdes por bairro."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import json

from src.app import dados as dados_bairros
from src.app import dados_despesas
from src.app import dados_servicos as d
from src.app.app import AZUL_SEQ, CENTRO_MAPA, SUPERFICIE, TINTA, TINTA_2, ZOOM_MAPA

fmt_int, fmt_dec = dados_bairros.fmt_int, dados_bairros.fmt_dec

ALTURA_MAPA = 740
# Cores das camadas (validadas com o validador da skill de dataviz, todos os pares; ver README).
# O mapa de fundo usa a rampa azul; as camadas usam matizes fora dela.
COR_CAMADA = {
    "escolas": "#eda100",
    "complementares": "#eda100",  # mesma cor, ponto menor e vazado: é escola, mas sem turmas regulares
    "ubs": "#6250d6",
    "outras_saude": "#e34948",
}
COR_VERDE = "#1baf7a"
COR_MATA = "#008300"  # mais escuro que o das praças e parques, e com menos opacidade (fica por baixo)
CREDITO_OSM = "Matas e áreas protegidas: © colaboradores do OpenStreetMap (ODbL)."
TAMANHO = {"escolas": 9, "complementares": 10, "ubs": 10, "outras_saude": 10}

INDICADORES = {
    "indice_acesso": "Índice de acesso",
    "dist_escola_m": "Até a escola",
    "dist_ubs_m": "Até a UBS/USF",
    "area_verde_m2_hab": "Área verde por morador",
    "hab_por_equipamento": "Moradores por escola ou UBS",
}
LEGENDA_INDICADOR = {
    "indice_acesso": "Quanto mais escuro, melhor a posição do bairro nos três componentes do índice "
                     "(fórmula mais abaixo).",
    "dist_escola_m": "Distância média, em linha reta, de quem mora no bairro até a escola pública mais "
                     "próxima (ponderada pela população dos setores censitários). Mais escuro = mais longe.",
    "dist_ubs_m": "Distância média, em linha reta, de quem mora no bairro até a UBS/USF mais próxima "
                  "(ponderada pela população dos setores censitários). Mais escuro = mais longe.",
    "area_verde_m2_hab": "Praças e parques do cadastro da Prefeitura dentro do bairro, por morador. "
                         "A cor satura no percentil 90 (valor exato ao passar o mouse).",
    "hab_por_equipamento": "Moradores por escola pública regular ou UBS/USF no bairro. Mais escuro = mais "
                           "gente para cada equipamento. Sem cor e com contorno escuro: bairro sem nenhum dos dois.",
}


@st.cache_data
def _carregar():
    return d.carregar(), dados_bairros.carregar_geojson()


@st.cache_data
def _gasto_saude_educacao():
    pasta = dados_despesas.PASTA
    meta = json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))
    cubo = pd.read_parquet(pasta / "despesas_cubo.parquet",
                           columns=["ano", "funcao", "intra", "poder", "empenhado_corrigido"])
    return dados_despesas.gasto_por_funcao(cubo, pd.read_csv(pasta / "populacao.csv"), meta), meta


def _hover_bairro(ind: pd.DataFrame) -> pd.Series:
    def linha(r):
        hab = "sem escola nem UBS/USF" if r.sem_escola_nem_ubs else f"{fmt_int(r.hab_por_equipamento)} hab. por escola ou UBS/USF"
        return "<br>".join([
            f"<b>{r.nm_bairro}</b>",
            f"Índice de acesso: {fmt_dec(r.indice_acesso)}",
            f"Escola mais próxima: {fmt_int(r.dist_escola_m)} m",
            f"UBS/USF mais próxima: {fmt_int(r.dist_ubs_m)} m",
            f"Área verde: {fmt_dec(r.area_verde_m2_hab, 1)} m²/hab",
            f"{fmt_int(r.escolas)} escolas · {fmt_int(r.ubs_usf)} UBS/USF · {hab}",
        ])

    return ind.apply(linha, axis=1)


def _hover_ponto(p: pd.DataFrame) -> pd.Series:
    def linha(r):
        partes = [f"<b>{r.nome}</b>", f"{r.subtipo} · {r.detalhe}", r.endereco or ""]
        if r.status != "bairro":
            partes.append(f"Fora dos bairros do IBGE ({d.STATUS_TEXTO[r.status]})")
        if r.fonte_coordenada and not r.fonte_coordenada.startswith(("INEP", "CNES")):
            partes.append(f"Coordenada: {r.fonte_coordenada}")
        return "<br>".join(x for x in partes if x)

    return p.apply(linha, axis=1)


def figura_mapa(dados: dict, geo: dict, indicador: str, camadas: list[str], verde: bool,
                selecionado: str | None, matas: bool = False, comparado: str | None = None,
                celular: bool = False) -> go.Figure:
    aj = dados_bairros.ajuste_mapa(celular, ALTURA_MAPA, ZOOM_MAPA)
    ind = dados["ind"].assign(hover=lambda x: _hover_bairro(x))
    fig = go.Figure()
    com_camadas = bool(camadas) or verde or matas
    comum = dict(geojson=geo, featureidkey="properties.cd_bairro", hovertemplate="%{hovertext}<extra></extra>",
                 marker_line_color=SUPERFICIE, marker_line_width=1)
    barra = dict(**aj["barra"], outlinewidth=0, tickfont=dict(color=TINTA_2), bgcolor="rgba(252,252,251,0.85)",
                 xpad=10, ypad=10, tickformat=",.0f")
    escala = [[i / (len(AZUL_SEQ) - 1), c] for i, c in enumerate(AZUL_SEQ)]

    base = ind[ind[indicador].notna()]
    z = base[indicador]
    zmax = None
    if indicador == "area_verde_m2_hab":
        zmax = float(z.quantile(0.9))
        z = z.clip(upper=zmax)
        barra["tickformat"] = ",.1f"
    fig.add_trace(go.Choroplethmap(
        locations=base.cd_bairro, z=z, hovertext=base.hover, colorscale=escala, zmin=0, zmax=zmax,
        colorbar=barra, marker_opacity=0.45 if com_camadas else 0.85, showlegend=False, **comum,
    ))
    sem = ind[ind[indicador].isna()]
    if len(sem):
        fig.add_trace(go.Choroplethmap(
            locations=sem.cd_bairro, z=[0] * len(sem), hovertext=sem.hover,
            colorscale=[[0, "rgba(252,252,251,0.6)"], [1, "rgba(252,252,251,0.6)"]], showscale=False,
            showlegend=False, **{**comum, "marker_line_color": TINTA_2, "marker_line_width": 1.5},
        ))

    if matas:
        feats = dados["matas"]["features"]
        fig.add_trace(go.Choroplethmap(
            geojson=dados["matas"], locations=[f["id"] for f in feats], z=[1] * len(feats),
            colorscale=[[0, COR_MATA], [1, COR_MATA]], showscale=False, marker_opacity=0.4,
            marker_line_width=0, name="Matas e áreas protegidas (OpenStreetMap)", showlegend=True,
            hovertext=[f"<b>{f['properties']['nome'] or 'Sem nome no OpenStreetMap'}</b><br>{f['properties']['tipo']} · "
                       f"{fmt_dec(f['properties']['area_m2'] / 1e4, 1)} ha<br>Fonte: OpenStreetMap ({f['properties']['osm']})"
                       for f in feats],
            hovertemplate="%{hovertext}<extra></extra>",
        ))

    if verde:
        feats = dados["verdes"]["features"]
        fig.add_trace(go.Choroplethmap(
            geojson=dados["verdes"], locations=[f["id"] for f in feats], z=[1] * len(feats),
            colorscale=[[0, COR_VERDE], [1, COR_VERDE]], showscale=False, marker_opacity=0.75,
            marker_line_width=0, name="Praças e parques", showlegend=True,
            hovertext=[f"<b>{f['properties']['nome'] or 'Sem nome'}</b><br>{f['properties']['tipo']} · "
                       f"{fmt_dec(f['properties']['area_m2'] / 1e4, 2)} ha" for f in feats],
            hovertemplate="%{hovertext}<extra></extra>",
        ))

    pontos = dados["pontos"]
    for camada in d.CAMADAS:
        if camada not in camadas:
            continue
        p = pontos[(pontos.camada_mapa == camada) & (pontos.status != "fora_do_municipio")]
        tam = TAMANHO[camada]
        # anel claro de 2 px em volta do ponto, para separá-lo do fundo e dos vizinhos
        fig.add_trace(go.Scattermap(lat=p.lat, lon=p.lon, mode="markers", hoverinfo="skip", showlegend=False,
                                    marker=dict(size=tam + 4, color=SUPERFICIE)))
        fig.add_trace(go.Scattermap(
            lat=p.lat, lon=p.lon, mode="markers", name=f"{d.CAMADAS[camada]} ({len(p)})",
            marker=dict(size=tam, color=COR_CAMADA[camada]),
            hovertext=_hover_ponto(p), hovertemplate="%{hovertext}<extra></extra>",
        ))
        if camada == "complementares":
            # miolo claro: ponto "vazado", diferente da escola regular além da cor
            fig.add_trace(go.Scattermap(lat=p.lat, lon=p.lon, mode="markers", hoverinfo="skip", showlegend=False,
                                        marker=dict(size=tam - 5, color=SUPERFICIE)))

    if comparado and comparado != selecionado:
        fig.add_trace(go.Choroplethmap(
            locations=[comparado], z=[0], colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
            showscale=False, showlegend=False, hoverinfo="skip", geojson=geo, featureidkey="properties.cd_bairro",
            marker_line_color=TINTA_2, marker_line_width=3,
        ))
    if selecionado:
        fig.add_trace(go.Choroplethmap(
            locations=[selecionado], z=[0], colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
            showscale=False, showlegend=False, hoverinfo="skip", geojson=geo, featureidkey="properties.cd_bairro",
            marker_line_color=TINTA, marker_line_width=3,
        ))

    fig.update_layout(
        map=dict(style="carto-positron", center=CENTRO_MAPA, zoom=aj["zoom"]),
        margin=dict(l=0, r=0, t=0, b=0), height=aj["altura"], separators=",.",
        legend=dict(x=0.015, y=0.97, xanchor="left", yanchor="top", bgcolor="rgba(252,252,251,0.9)",
                    font_size=10 if celular else None,
                    font=dict(color=TINTA), borderwidth=0),
    )
    return fig


def _metrica(col, rotulo: str, valor, media, unidade: str, distancia: bool, casas: int = 0, ajuda: str = ""):
    texto = (fmt_int(valor) if casas == 0 else fmt_dec(valor, casas)) + unidade
    comp = d.texto_comparacao(d.comparar(valor, media), distancia)
    media_txt = (fmt_int(media) if casas == 0 else fmt_dec(media, casas)) + unidade
    # Sem seta: a frase já diz se é melhor ou pior, e a seta para baixo em verde confundia
    col.metric(rotulo, texto, delta=comp[0] if comp else None, delta_color=comp[1] if comp else "off",
               delta_arrow="off", help=(ajuda + " " if ajuda else "") + f"Média da cidade: {media_txt}.")


def _n(v, um: str, varios: str) -> str:
    return f"{fmt_int(v)} {um if int(v) == 1 else varios}"


def painel_bairro(dados: dict, cd: str) -> None:
    ind, meta = dados["ind"], dados["meta"]
    media = meta["media_cidade"]
    r = ind.set_index("cd_bairro").loc[cd]
    comp = d.componentes_indice(ind).set_index("cd_bairro").loc[cd]
    st.subheader(r.nm_bairro)

    c1, c2 = st.columns(2)
    c1.metric("Índice de acesso", fmt_dec(r.indice_acesso),
              help="0 a 100, relativo aos 64 bairros. Fórmula na seção 'Como o índice é calculado'.")
    c2.metric("Moradores (2022)", fmt_int(r.pop_2022))
    st.caption("Etiquetas: comparação com a média da cidade (verde = melhor que a média, vermelho = pior).")
    c1, c2 = st.columns(2)
    _metrica(c1, "Até a escola", r.dist_escola_m, media["dist_escola_m"], " m", True,
             ajuda="Distância média em linha reta, ponderada pela população.")
    _metrica(c2, "Até a UBS/USF", r.dist_ubs_m, media["dist_ubs_m"], " m", True,
             ajuda="Distância média em linha reta, ponderada pela população.")
    _metrica(c1, "Escolas por 10 mil hab.", r.escolas_por_10mil, media["escolas_por_10mil"], "", False, 2)
    _metrica(c2, "UBS/USF por 10 mil hab.", r.ubs_usf_por_10mil, media["ubs_usf_por_10mil"], "", False, 2)
    _metrica(c1, "Área verde", r.area_verde_m2_hab, media["area_verde_m2_hab"], " m²/hab", False, 1)

    st.markdown(
        f"**No bairro:** {_n(r.escolas, 'escola pública', 'escolas públicas')}, {_n(r.ubs_usf, 'UBS/USF', 'UBS/USF')}, "
        f"{_n(r.policlinicas, 'policlínica', 'policlínicas')}, {_n(r.upas, 'UPA', 'UPAs')}, "
        f"{_n(r.hospitais, 'hospital', 'hospitais')}, {_n(r.pracas, 'praça', 'praças')} e "
        f"{_n(r.parques, 'parque', 'parques')}."
    )
    if r.sem_escola_nem_ubs:
        st.info("Não há escola pública regular nem UBS/USF dentro do bairro. A distância mostra o quanto "
                "os moradores andam até a mais próxima, em outro bairro.", icon="ℹ️")
    st.caption(
        f"Componentes do índice: escola {fmt_dec(comp.p_escola)}, UBS/USF {fmt_dec(comp.p_ubs)}, "
        f"área verde {fmt_dec(comp.p_verde)}. Do centro geométrico do bairro, a escola mais próxima fica a "
        f"{fmt_int(r.dist_escola_centroide_m)} m e a UBS/USF a {fmt_int(r.dist_ubs_centroide_m)} m."
    )

    lista = d.servicos_do_bairro(dados["pontos"], cd)
    with st.expander(f"Serviços no bairro ({len(lista)})"):
        if lista.empty:
            st.write("Nenhuma escola ou unidade de saúde com coordenada dentro do bairro.")
        else:
            st.dataframe(lista[["nome", "subtipo", "detalhe", "endereco"]], hide_index=True, width="stretch",
                         column_config={"nome": "Nome", "subtipo": "Tipo", "detalhe": "Rede", "endereco": "Endereço"})
        st.caption("Escolas: INEP, Catálogo de Escolas. Saúde: CNES. Código IBGE do bairro: " + cd + ".")


def figura_ranking(df: pd.DataFrame) -> go.Figure:
    hover = df.apply(lambda r: f"<b>{r.nm_bairro}</b><br>{fmt_int(r.pop_2022)} moradores<br>"
                               f"{fmt_int(r.escolas)} escolas · {fmt_int(r.ubs_usf)} UBS/USF", axis=1)
    fig = go.Figure(go.Bar(
        x=df.hab_por_equipamento, y=df.nm_bairro, orientation="h",
        marker=dict(color=AZUL_SEQ[4], cornerradius=4), text=df.hab_por_equipamento.map(fmt_int),
        textposition="outside", cliponaxis=False, hovertext=hover, hovertemplate="%{hovertext}<extra></extra>",
    ))
    fig.update_layout(height=36 * max(len(df), 1) + 40, margin=dict(l=0, r=60, t=10, b=10), bargap=0.35,
                      yaxis=dict(autorange="reversed", showgrid=False), xaxis=dict(visible=False),
                      separators=",.", showlegend=False)
    return fig


def secao_ranking(dados: dict) -> None:
    ind, meta = dados["ind"], dados["meta"]
    st.header("Bairros com mais gente e menos serviços")
    st.caption(
        f"Moradores para cada escola pública regular ou UBS/USF dentro do bairro. Só bairros com pelo menos "
        f"{fmt_int(meta['pop_min_ranking'])} moradores. A média da cidade é de "
        f"{fmt_int(meta['media_cidade']['pop_bairros'] / int(ind.equipamentos.sum()))} moradores por equipamento."
    )
    g1, g2 = st.columns([3, 2], gap="large")
    with g1:
        n = st.select_slider("Quantos bairros", options=[5, 10, 15], value=10)
        st.plotly_chart(figura_ranking(d.ranking_menos_servicos(ind, n)), config={"displayModeBar": False})
    with g2:
        sem = d.sem_escola_nem_ubs(ind)
        st.subheader(f"Sem escola pública nem UBS/USF ({len(sem)})")
        st.dataframe(
            dados_bairros.tabela_br(sem[["nm_bairro", "pop_2022", "dist_escola_m", "dist_ubs_m"]],
                                    inteiros=["pop_2022", "dist_escola_m", "dist_ubs_m"]),
            hide_index=True, width="stretch",
            column_config={"nm_bairro": "Bairro", "pop_2022": "Moradores", "dist_escola_m": "Até a escola (m)",
                           "dist_ubs_m": "Até a UBS/USF (m)"},
        )
        st.caption("Escolas e unidades de saúde privadas não estão contadas: estes bairros podem ter serviços "
                   "privados.")


def secao_indice(dados: dict) -> None:
    ind = dados["ind"]
    st.header("Como o índice de acesso é calculado")
    st.markdown(
        "O índice é a **média simples de três posições**, cada uma de 0 a 100, entre os 64 bairros:"
    )
    st.latex(r"\text{índice} = \frac{P_{\text{escola}} + P_{\text{UBS}} + P_{\text{verde}}}{3}")
    st.markdown(
        "- **P escola:** posição pela distância até a escola pública mais próxima (quanto mais perto, maior).\n"
        "- **P UBS:** o mesmo para a UBS/USF.\n"
        "- **P verde:** posição pela área de praças e parques por morador (quanto mais área, maior).\n\n"
        "Cada posição é o percentil do bairro: o melhor dos 64 recebe 100, o pior recebe 1,6 "
        "(empates ficam com a posição média). O índice é **relativo**: 100 seria o melhor bairro de "
        "João Pessoa nos três itens, não um padrão ideal. As distâncias são médias ponderadas pela "
        "população dos setores censitários do Censo 2022, em linha reta."
    )
    tab = ind[["nm_bairro", "pop_2022", "indice_acesso", "dist_escola_m", "dist_ubs_m", "area_verde_m2_hab",
               "escolas", "ubs_usf", "pracas", "parques"]].merge(
        d.componentes_indice(ind).assign(nm_bairro=ind.nm_bairro).drop(columns="cd_bairro"), on="nm_bairro"
    ).sort_values("indice_acesso", ascending=False)
    tab = tab[["nm_bairro", "indice_acesso", "p_escola", "p_ubs", "p_verde", "dist_escola_m", "dist_ubs_m",
               "area_verde_m2_hab", "pop_2022", "escolas", "ubs_usf", "pracas", "parques"]]
    st.dataframe(
        dados_bairros.tabela_br(tab, inteiros=["dist_escola_m", "dist_ubs_m", "pop_2022"],
                                decimais={"indice_acesso": 1, "p_escola": 1, "p_ubs": 1, "p_verde": 1,
                                          "area_verde_m2_hab": 1}),
        hide_index=True, width="stretch",
        column_config={
            "nm_bairro": "Bairro", "indice_acesso": "Índice", "p_escola": "P escola", "p_ubs": "P UBS",
            "p_verde": "P verde", "dist_escola_m": "Até a escola (m)", "dist_ubs_m": "Até a UBS/USF (m)",
            "area_verde_m2_hab": "Verde (m²/hab)", "pop_2022": "Moradores",
            "escolas": "Escolas", "ubs_usf": "UBS/USF", "pracas": "Praças", "parques": "Parques",
        },
    )
    st.download_button("Baixar CSV", (d.PASTA / "indicadores_servicos.csv").read_bytes(),
                       file_name="servicos_bairros_joao_pessoa.csv", mime="text/csv")

    st.subheader("O resultado depende dos pesos?")
    sens = pd.DataFrame(dados["meta"]["sensibilidade_indice"])
    dobrados = sens[sens.cenario.str.contains("dobrado")]
    st.markdown(
        "Pesos iguais são uma escolha. Para ver o quanto ela pesa, o índice foi recalculado com outros pesos. "
        f"Dobrando o peso de um dos três itens, a ordem dos bairros quase não muda: a correlação com o ranking "
        f"publicado fica entre {fmt_dec(dobrados.correlacao_spearman.min(), 2)} e "
        f"{fmt_dec(dobrados.correlacao_spearman.max(), 2)} (1 = mesma ordem), e os bairros mudam em média "
        f"{fmt_dec(dobrados.mudanca_media_posicoes.min(), 1)} a {fmt_dec(dobrados.mudanca_media_posicoes.max(), 1)} "
        "posições. Tirar um item muda bem mais, o que mostra que cada um acrescenta informação."
    )
    tab = sens.assign(pesos=sens.pesos.map(lambda p: " · ".join(str(x) for x in p)))
    n_top = int(sens.top10_publicado.iloc[0])
    st.dataframe(
        dados_bairros.tabela_br(
            tab[["cenario", "pesos", "correlacao_spearman", "mudanca_media_posicoes", "mudanca_maxima_posicoes",
                 "bairros_que_mudam_mais_de_10_posicoes", "top10_mantidos"]],
            decimais={"correlacao_spearman": 2, "mudanca_media_posicoes": 1}),
        hide_index=True, width="stretch",
        column_config={
            "cenario": "Cenário", "pesos": "Pesos (escola · UBS · verde)",
            "correlacao_spearman": "Correlação", "mudanca_media_posicoes": "Mudança média",
            "mudanca_maxima_posicoes": "Maior mudança", "bairros_que_mudam_mais_de_10_posicoes": "Mudam > 10 posições",
            "top10_mantidos": f"Dos {n_top} primeiros, continuam",
        },
    )
    st.caption("Correlação de Spearman com o ranking publicado (1 = mesma ordem); mudanças em número de posições, "
               "entre os 64 bairros. "
               + (f"Os primeiros colocados são {n_top}, e não 10, por empate na 10ª posição. " if n_top != 10 else "")
               + "A posição de cada bairro em cada cenário está em data/processed/servicos/sensibilidade_indice.csv.")


def _status_total(meta: dict, camada: str) -> dict:
    tot: dict = {}
    for chave, cont in meta["pontos_por_status"].items():
        if chave.startswith(camada + " | "):
            for k, v in cont.items():
                tot[k] = tot.get(k, 0) + v
    return tot


FONTES = pd.DataFrame([
    {"Dado": "Escolas públicas", "Origem": "INEP, Catálogo de Escolas",
     "Link": "https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/inep-data/catalogo-de-escolas",
     "Atualização da fonte": "situação do Censo Escolar 2024 (conferida com os microdados de 2024)",
     "Obtido em": "22/10/2026"},
    {"Dado": "Unidades de saúde", "Origem": "Ministério da Saúde, CNES (API de dados abertos)",
     "Link": "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos?codigo_municipio=250750",
     "Atualização da fonte": "cadastro mais recente atualizado em 16/10/2026", "Obtido em": "16/10/2026"},
    {"Dado": "Parques", "Origem": "Prefeitura de João Pessoa, Filipeia (shapefile exportado do portal)",
     "Link": "https://filipeia.joaopessoa.pb.gov.br/",
     "Atualização da fonte": "arquivo de 08/02/2021", "Obtido em": "23/10/2026"},
    {"Dado": "Praças", "Origem": "Prefeitura (Filipeia): tabela oficial; contornos da Prefeitura na cópia do geodata-jp, conferidos com a tabela e as quadras",
     "Link": "https://filipeia.joaopessoa.pb.gov.br/",
     "Atualização da fonte": "intervenções registradas até 2018; quadras de 02/10/2026", "Obtido em": "23/10/2026"},
    {"Dado": "Matas e áreas protegidas (só no mapa)", "Origem": "OpenStreetMap, © colaboradores do OpenStreetMap (ODbL)",
     "Link": "https://www.openstreetmap.org/", "Atualização da fonte": "consulta de 23/10/2026",
     "Obtido em": "23/10/2026"},
    {"Dado": "Coordenadas de apoio (escolas)", "Origem": "Catálogo do INEP de 2022 (via geodata-jp) e OpenStreetMap",
     "Link": "https://github.com/paulovitorweb/geodata-jp", "Atualização da fonte": "fev/2022; OSM: consulta de 23/10/2026",
     "Obtido em": "22–23/10/2026"},
    {"Dado": "Moradores por setor censitário e limites", "Origem": "IBGE, Censo 2022 (malha de setores e de bairros)",
     "Link": "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/",
     "Atualização da fonte": "Censo 2022", "Obtido em": "22/10/2026"},
])


def _matas_nomeadas(mt: dict) -> str:
    nomes = [f"{m['nome']} ({fmt_dec(m['ha'], 0)} ha)" for m in mt["com_nome"] if m["ha"] >= 100]
    return ("As maiores com nome: " + "; ".join(nomes) + ".") if nomes else ""


def _parques_novos(mt: dict) -> str:
    p = mt.get("parques_osm_fora_do_cadastro", [])
    return (", como " + ", ".join(f"{x['nome']} ({fmt_dec(x['ha'], 1)} ha)" for x in p[:5])) if p else ""


def secao_gasto() -> None:
    g, meta = _gasto_saude_educacao()
    ano = int(g.index.max())
    ultimo = g.loc[ano]
    st.header("Quanto a Prefeitura gasta em saúde e educação")
    ano_ref, mes_ref = meta["ipca"]["mes_referencia"].split("-")
    st.caption(
        f"Valor empenhado pelos órgãos municipais nas funções Saúde e Educação, declarado ao TCE-PB, corrigido pelo "
        f"IPCA (R\\$ de {mes_ref}/{ano_ref}), sem transferências entre órgãos do município. É o gasto da cidade toda: "
        "os empenhos não dizem em que bairro o dinheiro foi usado, por isso não há valor por bairro."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Saúde em {ano}", dados_despesas.fmt_reais(ultimo["Saúde"]))
    c2.metric("Por habitante", dados_bairros.fmt_reais(ultimo["Saúde por habitante"]))
    c3.metric(f"Educação em {ano}", dados_despesas.fmt_reais(ultimo["Educação"]))
    c4.metric("Por habitante", dados_bairros.fmt_reais(ultimo["Educação por habitante"]))
    fig = go.Figure()
    for funcao, cor in [("Saúde", COR_CAMADA["ubs"]), ("Educação", COR_CAMADA["escolas"])]:
        # anos sem valor (2016 incompleto, 2023 sem população) ficam como lacuna na linha
        serie = g[f"{funcao} por habitante"].reindex(range(int(g.index.min()), ano + 1))
        fig.add_trace(go.Scatter(
            x=serie.index, y=serie.values, mode="lines+markers", name=funcao, line=dict(color=cor, width=2),
            connectgaps=False,
            marker=dict(size=8, color=cor, line=dict(color=SUPERFICIE, width=2)),
            hovertext=[f"<b>{funcao} {a}</b><br>{dados_bairros.fmt_reais(v)} por habitante" for a, v in serie.items()],
            hovertemplate="%{hovertext}<extra></extra>",
        ))
        fig.add_annotation(x=ano, y=serie.loc[ano], text=funcao, showarrow=False, xanchor="left",
                           xshift=10, font=dict(color=TINTA))
    fig.update_layout(height=320, margin=dict(l=0, r=70, t=10, b=0), separators=",.", showlegend=True,
                      legend=dict(orientation="h", y=1.08, x=0), plot_bgcolor="rgba(0,0,0,0)",
                      yaxis=dict(title="R$ por habitante", gridcolor="#e7e6e2", tickformat=",.0f"),
                      xaxis=dict(showgrid=False, dtick=2))
    st.plotly_chart(fig, config={"displayModeBar": False})
    st.caption("Só anos completos: sem ponto em 2016 (incompleto no TCE-PB) e no ano em andamento (parcial). Sem "
               "ponto em 2023: o IBGE não publicou estimativa de população para esse ano.")
    st.markdown("Gasto por área, fornecedores e licitações na página **Para onde vai o dinheiro**.")


def secao_fontes(dados: dict) -> None:
    meta = dados["meta"]
    fe, fs, av, mt = meta["funil"]["escolas"], meta["funil"]["saude"], meta["areas_verdes"], meta["matas_osm"]
    se, ss = _status_total(meta, "escola"), _status_total(meta, "saude")
    st.header("Fontes e limitações")
    st.caption("Tudo o que está nesta página sai das fontes abaixo. Os números de contagem e de distância são "
               "calculados a partir delas; nada foi estimado ou preenchido à mão.")

    st.subheader("De onde vêm os dados")
    st.dataframe(FONTES, hide_index=True, width="stretch",
                 column_config={"Link": st.column_config.LinkColumn("Link", display_text="abrir")})
    st.markdown(f"""
- **Escolas:** {fmt_int(fe['joao_pessoa'])} escolas de João Pessoa no catálogo; {fmt_int(fe['publicas'])} públicas;
  sem as {fmt_int(fe['paralisadas_ou_extintas'])} paralisadas ou extintas, ficam **{fmt_int(fe['publicas_em_funcionamento'])}**.
  O catálogo não tem download direto: é exportado do painel do INEP por um navegador automatizado, e o arquivo é
  conferido (todas as linhas da Paraíba). Para {fmt_int(fe['coordenada_completada_pelo_geodata_jp'])} escolas sem coordenada no catálogo,
  usa-se a da versão de 2022 do mesmo catálogo (geodata-jp); {fmt_int(fe['geodata_jp_coordenada_repetida_descartada'])} outras foram
  descartadas porque o geodata-jp põe várias escolas no mesmo ponto genérico. Para
  {fmt_int(fe['coordenada_completada_pelo_openstreetmap'])} escolas, usa-se o ponto do OpenStreetMap, conferido: mesmo nome e no bairro do endereço do INEP.
- **Saúde:** dos {fmt_int(fs['cnes_joao_pessoa'])} estabelecimentos do CNES em João Pessoa, {fmt_int(fs['tipos_pedidos'])} são
  UBS/USF, policlínicas, UPAs/prontos atendimentos ou hospitais; {fmt_int(fs['ativos'])} estão ativos;
  {fmt_int(fs['rede_sus_publicos_ou_atendem_sus'])} são públicos ou atendem pelo SUS; sem os cadastros de regulação, ficam
  **{fmt_int(fs['sem_cadastros_de_regulacao'])}**.
- **Praças e parques:** {fmt_int(av['pracas'])} praças e {fmt_int(av['parques'])} parques do cadastro da Prefeitura. Onde se sobrepõem,
  a área conta uma vez. O portal oferece o arquivo dos parques, mas não o das praças; os contornos das praças vêm do
  geodata-jp e foram conferidos: as {fmt_int(av['pracas_conferidas_com_tabela_filipeia'])} têm nome e área idênticos aos da tabela oficial, e
  {fmt_int(av['pracas_dentro_ou_encostadas_na_quadra_5m'])} das {fmt_int(av['pracas_com_quadra_no_cadastro_atual'])} que têm código de quadra estão dentro ou encostadas na quadra indicada.
- **Matas e áreas protegidas** (OpenStreetMap): {fmt_dec(mt['area_uniao_ha'], 0)} ha no município, só no mapa, **fora do
  índice e da área verde por morador**, porque o critério é outro. {_matas_nomeadas(mt)}
- **Distâncias:** de cada setor censitário com moradores até o serviço mais próximo, em linha reta, com média
  ponderada pelo número de moradores do setor (Censo 2022). Calculadas em metros (SIRGAS 2000 / UTM 25S).
""")

    st.subheader("Limitações")
    st.markdown(f"""
- **Só serviços públicos ou do SUS.** Escolas particulares, clínicas e hospitais privados não estão contados.
  Um bairro "sem escola nem UBS" pode ter serviços privados.
- **Distância em linha reta**, não pelas ruas. O caminho real é maior, e rios, mangues e vias expressas podem
  aumentá-lo bastante.
- **A distância não indica a unidade de referência.** Cada família é atendida pela UBS da sua área de
  abrangência, e essas áreas não estão nos dados. Aqui se mede só a unidade mais próxima.
- **Serviços de municípios vizinhos** não estão nos dados, então bairros na divisa podem ter um serviço mais
  perto do que o mostrado.
- **Área verde só do cadastro da Prefeitura.** Matas como a Mata do Buraquinho não são praça nem parque no cadastro
  e não entram na área verde por morador nem no índice; aparecem só na camada de matas do mapa. Bairros vizinhos a
  elas aparecem com menos área verde do que de fato têm.
- **Cadastro desatualizado.** Os parques são de um arquivo de 2021 e as praças registram intervenções até 2018. O
  OpenStreetMap tem parques que o cadastro não tem{_parques_novos(mt)}.
- **Escolas sem coordenada:** {fmt_int(se.get('sem_coordenada', 0))} escolas não têm localização no catálogo do INEP, nem uma
  localização confiável no geodata-jp ou no OpenStreetMap. Elas estão contadas no total, mas fora do mapa e das distâncias.
- **Coordenadas declaradas.** As localizações são as informadas ao INEP e ao CNES e não foram conferidas uma a
  uma. Uma UBS tem coordenada fora do município e não foi corrigida à mão.
- **Limites dos bairros:** o mapa usa os bairros do IBGE, porque a população do Censo é contada neles. A malha do
  IBGE cobre 168 km² dos 210 km² do município; a da Prefeitura (Filipeia, abril de 2026) cobre 194 km², e alguns
  bairros de borda são bem maiores nela. {fmt_int(meta['setores']['pop_fora_de_bairro'])}
  moradores vivem em setores sem bairro e entram só na média da cidade.
- **Índice relativo.** O índice compara os bairros entre si; não é uma nota de qualidade dos serviços.
""")

    st.subheader("Pontos contados mas não atribuídos a um bairro")
    st.caption(
        f"Escolas: {fmt_int(se.get('bairro', 0))} num bairro, {fmt_int(se.get('fora_de_bairro', 0))} no município fora dos bairros do IBGE, "
        f"{fmt_int(se.get('fora_do_municipio', 0))} com coordenada fora do município, {fmt_int(se.get('sem_coordenada', 0))} sem coordenada. "
        f"Saúde: {fmt_int(ss.get('bairro', 0))} num bairro, {fmt_int(ss.get('fora_de_bairro', 0))} no município fora dos bairros, "
        f"{fmt_int(ss.get('fora_do_municipio', 0))} com coordenada fora do município, {fmt_int(ss.get('sem_coordenada', 0))} sem coordenada."
    )
    na = dados["nao_atribuidos"].assign(status=lambda x: x.status.map(d.STATUS_TEXTO))
    st.dataframe(na[["nome", "subtipo", "status", "bairro_prefeitura", "endereco"]], hide_index=True, width="stretch",
                 column_config={"nome": "Nome", "subtipo": "Tipo", "status": "Situação",
                                "bairro_prefeitura": "Bairro pela malha da Prefeitura", "endereco": "Endereço"})

    with st.expander("Arquivos de origem (URL, data de download e SHA-256)"):
        arquivos = pd.DataFrame([
            {"arquivo": k, "fonte": v["fonte"], "obtido em (UTC)": v["baixado_em"], "url": v["url"], "sha256": v["sha256"]}
            for k, v in meta["arquivos_brutos"].items()
        ])
        st.dataframe(arquivos, hide_index=True, width="stretch")
        st.caption(f"Dados processados em {meta['gerado_em']} (UTC). Metodologia completa no README do repositório.")


def _atualizar_link(nomes: pd.Series) -> None:
    """Mantém o link da página com o bairro escolhido (e o comparado), para poder compartilhar."""
    st.query_params["bairro"] = dados_bairros.slug(nomes[st.session_state.bairro_servicos])
    if st.session_state.comparar_servicos:
        st.query_params["comparar"] = dados_bairros.slug(nomes[st.session_state.comparar_servicos])
    elif "comparar" in st.query_params:
        del st.query_params["comparar"]


def secao_comparacao(dados: dict, a: str, b: str) -> None:
    ind, media = dados["ind"].set_index("cd_bairro"), dados["meta"]["media_cidade"]
    ra, rb = ind.loc[a], ind.loc[b]
    st.divider()
    st.header(f"{ra.nm_bairro} e {rb.nm_bairro}")
    st.caption("Os dois bairros lado a lado, com a média da cidade como referência. No mapa, o primeiro tem "
               "contorno preto e o segundo, cinza.")
    tab = d.tabela_comparacao(ra, rb, media)
    st.dataframe(tab, hide_index=True, width="stretch", height=35 * (len(tab) + 1) + 3)
    st.caption("Distâncias: média em linha reta, ponderada pela população dos setores censitários. "
               "Na coluna Cidade, o índice é a mediana dos 64 bairros. "
               "Os serviços contam só escolas públicas e unidades do SUS.")


def main() -> None:
    dados, geo = _carregar()
    ind = dados["ind"]
    st.markdown("<style>.block-container{padding-top:2rem}</style>", unsafe_allow_html=True)
    st.title("Serviços públicos e acesso")
    st.caption(
        "Escolas públicas, unidades de saúde do SUS, praças e parques nos 64 bairros. Ligue e desligue as "
        "camadas, passe o mouse sobre um ponto para ver o nome e clique num bairro para ver o detalhe."
    )
    st.info(
        "Só escolas públicas e unidades do SUS; distâncias em linha reta; área verde só de praças e parques do "
        "cadastro da Prefeitura (matas aparecem no mapa, mas fora do índice). Fontes, datas e todas as limitações na seção **Fontes e limitações**, no fim da página.",
        icon="ℹ️",
    )

    nomes = ind.sort_values("nm_bairro").set_index("cd_bairro").nm_bairro
    # Bairro e comparação vêm do link (?bairro=mangabeira&comparar=bessa) na primeira carga da página
    if "bairro_servicos" not in st.session_state:
        st.session_state.bairro_servicos = (dados_bairros.codigo_por_slug(ind, st.query_params.get("bairro"))
                                            or ind.loc[ind.pop_2022.idxmax(), "cd_bairro"])
    if "comparar_servicos" not in st.session_state:
        st.session_state.comparar_servicos = dados_bairros.codigo_por_slug(ind, st.query_params.get("comparar")) or ""

    col_mapa, col_det = st.columns([7, 3], gap="medium")
    with col_mapa:
        indicador = st.radio("Cor dos bairros", list(INDICADORES), format_func=INDICADORES.get, horizontal=True)
        opcoes = list(d.CAMADAS) + ["verde", "matas"]
        rotulos = {**d.CAMADAS, "verde": "Praças e parques", "matas": "Matas e áreas protegidas"}
        ligadas = st.pills("Camadas", opcoes, format_func=rotulos.get, selection_mode="multi",
                           default=["escolas", "ubs"])
        evento = st.plotly_chart(
            figura_mapa(dados, geo, indicador, [c for c in ligadas if c in d.CAMADAS], "verde" in ligadas,
                        st.session_state.bairro_servicos, matas="matas" in ligadas,
                        comparado=st.session_state.comparar_servicos,
                        celular=dados_bairros.eh_celular(st.context.headers.get("User-Agent"))),
            on_select="rerun", selection_mode="points", key="mapa_servicos",
            config={"scrollZoom": True, "displaylogo": False},
        )
        pontos = (evento or {}).get("selection", {}).get("points", []) if evento else []
        clicado = next((p.get("location") for p in pontos if p.get("location") in nomes.index), None)
        if clicado and clicado != st.session_state.get("ultimo_clique_servicos"):
            st.session_state.ultimo_clique_servicos = clicado
            st.session_state.bairro_servicos = clicado
            st.rerun()
        st.caption(LEGENDA_INDICADOR[indicador] + (" " + CREDITO_OSM if "matas" in ligadas else ""))

    with col_det:
        st.selectbox("Bairro", nomes.index, format_func=nomes.get, key="bairro_servicos")
        st.selectbox("Comparar com", [""] + list(nomes.index), key="comparar_servicos",
                     format_func=lambda c: nomes[c] if c else "nenhum bairro",
                     help="Mostra os dois bairros lado a lado, abaixo do mapa, e o contorno do segundo no mapa.")
        painel_bairro(dados, st.session_state.bairro_servicos)
    _atualizar_link(nomes)

    if st.session_state.comparar_servicos and st.session_state.comparar_servicos != st.session_state.bairro_servicos:
        secao_comparacao(dados, st.session_state.bairro_servicos, st.session_state.comparar_servicos)

    st.divider()
    media = dados["meta"]["media_cidade"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Escolas públicas", fmt_int(dados["meta"]["total_fonte_filtrada"]["escola"]))
    k2.metric("Unidades de saúde do SUS", fmt_int(dados["meta"]["total_fonte_filtrada"]["saude"]))
    k3.metric("Distância média até a escola", f"{fmt_int(media['dist_escola_m'])} m")
    k4.metric("Distância média até a UBS/USF", f"{fmt_int(media['dist_ubs_m'])} m")

    secao_ranking(dados)
    secao_indice(dados)
    secao_gasto()
    secao_fontes(dados)
    st.caption("Dados: INEP, Ministério da Saúde (CNES), Prefeitura de João Pessoa (Filipeia), OpenStreetMap e IBGE (Censo 2022).")
