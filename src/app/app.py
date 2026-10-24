"""Dashboard Streamlit: Raio-X dos Bairros de João Pessoa.

Rode com: streamlit run streamlit_app.py
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.app import dados as d
from src.process.indicadores import COM_RESSALVA, NAO_COMPARAVEL

# Paleta (validada com o validador da skill de dataviz; ver README).
AZUL_SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
AZUL = "#2a78d6"   # polo positivo (crescimento)
VERMELHO = "#e34948"  # polo negativo (perda)
CINZA_MEIO = "#f0efec"  # ponto neutro da escala divergente
SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
ALTURA_MAPA = 740  # px; o mapa é o elemento principal da página
# Enquadramento inicial: centro e zoom que mostram todos os bairros (bbox da malha IBGE 2022)
CENTRO_MAPA = dict(lat=-7.147, lon=-34.875)
ZOOM_MAPA = 11.55
LIMITE_VAR_PCT = 60  # a escala de cor da variação satura em ±60% (o valor exato vai no tooltip)

INDICADORES = {
    "pop_2022": "População (2022)",
    "densidade_2022": "Densidade (hab/km², 2022)",
    "var_pct": "Variação da população 2010→2022 (%)",
}


@st.cache_data
def _carregar():
    return d.carregar_indicadores(), d.carregar_geojson(), d.carregar_totais(), d.carregar_metadados()


def _hover(ind: pd.DataFrame) -> pd.Series:
    def linha(r):
        partes = [
            f"<b>{r.nm_bairro}</b>",
            f"População 2022: {d.fmt_int(r.pop_2022)}",
            f"Densidade: {d.fmt_dec(r.densidade_2022, 0)} hab/km²",
        ]
        if r.comparabilidade == NAO_COMPARAVEL:
            partes.append("Variação 2010→2022: não comparável")
        else:
            nota = " (com ressalva)" if r.comparabilidade == COM_RESSALVA else ""
            partes.append(
                f"Variação 2010→2022: {d.fmt_var_pct(r.var_pct)} ({d.fmt_var_int(r.var_abs)}){nota}"
            )
        return "<br>".join(partes)

    return ind.apply(linha, axis=1)


def figura_mapa(ind: pd.DataFrame, geo: dict, indicador: str, selecionado: str | None) -> go.Figure:
    ind = ind.assign(hover=_hover(ind))
    comum = dict(
        geojson=geo,
        featureidkey="properties.cd_bairro",
        hovertemplate="%{hovertext}<extra></extra>",
        marker_line_color=SUPERFICIE,
        marker_line_width=1,
    )
    # Legenda de cores sobre o mapa (canto superior direito), para o mapa ocupar toda a largura
    barra = dict(
        thickness=12, len=0.45, outlinewidth=0, tickfont=dict(color=TINTA_2),
        x=0.985, xanchor="right", y=0.97, yanchor="top",
        bgcolor="rgba(252,252,251,0.85)", xpad=10, ypad=10,
    )
    fig = go.Figure()

    if indicador == "var_pct":
        comp = ind[ind.comparabilidade != NAO_COMPARAVEL]
        nao = ind[ind.comparabilidade == NAO_COMPARAVEL]
        ticks = [-LIMITE_VAR_PCT, -30, 0, 30, LIMITE_VAR_PCT]
        fig.add_trace(
            go.Choroplethmap(
                locations=comp.cd_bairro,
                z=comp.var_pct.clip(-LIMITE_VAR_PCT, LIMITE_VAR_PCT),
                hovertext=comp.hover,
                colorscale=[[0, VERMELHO], [0.5, CINZA_MEIO], [1, AZUL]],
                zmin=-LIMITE_VAR_PCT,
                zmax=LIMITE_VAR_PCT,
                colorbar=dict(
                    **barra,
                    title=dict(text="%", font=dict(color=TINTA_2)),
                    tickvals=ticks,
                    ticktext=[f"≤ −{LIMITE_VAR_PCT}", "−30", "0", "+30", f"≥ +{LIMITE_VAR_PCT}"],
                ),
                marker_opacity=0.85,
                **comum,
            )
        )
        # Não comparáveis: sem preenchimento de cor, só contorno escuro
        fig.add_trace(
            go.Choroplethmap(
                locations=nao.cd_bairro,
                z=[0] * len(nao),
                hovertext=nao.hover,
                colorscale=[[0, "rgba(252,252,251,0.6)"], [1, "rgba(252,252,251,0.6)"]],
                showscale=False,
                **{**comum, "marker_line_color": TINTA_2, "marker_line_width": 1.5},
            )
        )
    else:
        fig.add_trace(
            go.Choroplethmap(
                locations=ind.cd_bairro,
                z=ind[indicador],
                hovertext=ind.hover,
                colorscale=[[i / (len(AZUL_SEQ) - 1), c] for i, c in enumerate(AZUL_SEQ)],
                colorbar=dict(**barra, tickformat=",.0f"),
                marker_opacity=0.85,
                **comum,
            )
        )

    if selecionado:
        fig.add_trace(
            go.Choroplethmap(
                locations=[selecionado],
                z=[0],
                colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
                showscale=False,
                hoverinfo="skip",
                geojson=geo,
                featureidkey="properties.cd_bairro",
                marker_line_color=TINTA,
                marker_line_width=3,
            )
        )

    fig.update_layout(
        map=dict(style="carto-positron", center=CENTRO_MAPA, zoom=ZOOM_MAPA),
        margin=dict(l=0, r=0, t=0, b=0),
        height=ALTURA_MAPA,
        separators=",.",
    )
    return fig


def figura_ranking(df: pd.DataFrame, metrica: str, crescimento: bool) -> go.Figure:
    cor = AZUL if crescimento else VERMELHO
    fmt = d.fmt_var_pct if metrica == "var_pct" else d.fmt_var_int
    rotulos = df.apply(d.rotulo, axis=1)
    hover = df.apply(
        lambda r: f"<b>{r.nm_bairro}</b><br>2010: {d.fmt_int(r.pop_2010)}<br>2022: {d.fmt_int(r.pop_2022)}"
        f"<br>Variação: {d.fmt_var_int(r.var_abs)} ({d.fmt_var_pct(r.var_pct)})",
        axis=1,
    )
    fig = go.Figure(
        go.Bar(
            x=df[metrica].astype(float).abs(),  # comprimento = magnitude; o sinal vai no rótulo
            y=rotulos,
            orientation="h",
            marker=dict(color=cor, cornerradius=4),
            text=df[metrica].map(fmt),
            textposition="outside",
            cliponaxis=False,
            hovertext=hover,
            hovertemplate="%{hovertext}<extra></extra>",
        )
    )
    fig.update_layout(
        height=36 * max(len(df), 1) + 40,
        margin=dict(l=0, r=60, t=10, b=10),
        bargap=0.35,
        yaxis=dict(autorange="reversed", showgrid=False),
        xaxis=dict(visible=False, zeroline=True),
        separators=",.",
        showlegend=False,
    )
    return fig


def painel_bairro(ind: pd.DataFrame, cd: str, meta: dict) -> None:
    r = ind.set_index("cd_bairro").loc[cd]
    st.subheader(r.nm_bairro)

    c1, c2 = st.columns(2)
    c1.metric("População 2022", d.fmt_int(r.pop_2022))
    c2.metric("População 2010", d.fmt_int(r.pop_2010))
    c1.metric("Densidade (hab/km²)", d.fmt_dec(r.densidade_2022, 0))
    c2.metric("Área (km²)", d.fmt_dec(r.area_km2, 2))
    if r.comparabilidade == NAO_COMPARAVEL:
        c1.metric("Variação 2010→2022", "—", help="Não comparável: o limite do bairro mudou entre os censos.")
    else:
        c1.metric(
            "Variação 2010→2022",
            d.fmt_var_int(r.var_abs),
            delta=d.fmt_var_pct(r.var_pct).replace("−", "-"),  # Streamlit só reconhece o '-' ASCII
        )
    c2.metric("Domicílios 2022", d.fmt_int(r.domicilios_2022))

    if pd.isna(r.pop_2010):
        st.warning("Este bairro não existia no Censo 2010, por isso não há variação.", icon="⚠️")
    elif r.comparabilidade == NAO_COMPARAVEL:
        st.warning(
            f"O limite do bairro mudou muito entre os censos (sobreposição de "
            f"{d.fmt_dec(r.iou_limites_2010_2022 * 100, 0)}%; área de "
            f"{d.fmt_dec(r.area_km2_2010_calc, 1)} km² em 2010 e {d.fmt_dec(r.area_km2, 1)} km² em 2022). "
            "A variação misturaria crescimento com mudança de território, então não é exibida.",
            icon="⚠️",
        )
    elif r.comparabilidade == COM_RESSALVA:
        st.info(
            f"Comparável com ressalva: o limite mudou parcialmente entre os censos "
            f"(sobreposição de {d.fmt_dec(r.iou_limites_2010_2022 * 100, 0)}%).",
            icon="ℹ️",
        )

    linhas = []
    for col, texto in [
        ("pop_2022", "mais populoso"),
        ("densidade_2022", "mais denso"),
        ("var_pct", "em crescimento percentual"),
    ]:
        p = d.posicao(ind[ind.comparabilidade != NAO_COMPARAVEL] if col == "var_pct" else ind, cd, col)
        if p:
            linhas.append(f"- {p[0]}º {texto} entre {p[1]} bairros")
    if linhas:
        st.markdown("**Posição**\n" + "\n".join(linhas))

    with st.expander("De onde vêm estes números"):
        cols = meta["colunas"]
        st.markdown(
            "\n".join(
                f"- **{nome}**: {cols[c]}"
                for nome, c in [
                    ("População 2022", "pop_2022"),
                    ("Área", "area_km2"),
                    ("Densidade", "densidade_2022"),
                    ("População 2010", "pop_2010"),
                    ("Variação", "var_pct"),
                    ("Comparabilidade", "comparabilidade"),
                ]
            )
        )
        st.caption(f"Código IBGE do bairro: {cd}. Arquivos originais e URLs na seção *Sobre os dados*.")


def secao_sobre(meta: dict, totais: pd.DataFrame) -> None:
    with st.expander("Sobre os dados: fontes, método e limitações"):
        st.markdown(
            f"""
**Fontes.** População 2022: tabela do IBGE por bairro (Censo 2022, *Agregados por Setores
Censitários*, variável `v0001`). População 2010: soma dos setores censitários do Censo 2010
(`Domicilio02`, V001) pelo código de bairro. Limites: malha de bairros do IBGE do Censo 2022,
o mesmo território em que a população foi contada.

**Fora de bairros.** Parte da população mora em áreas que o IBGE não atribui a bairro:
{d.fmt_int(totais.loc[2022, 'fora_de_bairros'])} pessoas em 2022
({d.fmt_dec(totais.loc[2022, 'pct_fora_de_bairros'], 2)}%) e
{d.fmt_int(totais.loc[2010, 'fora_de_bairros'])} em 2010
({d.fmt_dec(totais.loc[2010, 'pct_fora_de_bairros'], 2)}%). Por isso a soma dos bairros
é menor que o total do município.

**Comparabilidade 2010→2022.** Os códigos de bairro são os mesmos nos dois censos, mas alguns
limites mudaram. Comparamos o polígono de cada bairro em 2010 e 2022 (interseção ÷ união):
≥ {d.fmt_dec(meta['parametros']['iou_comparavel'], 2)} é comparável;
entre {d.fmt_dec(meta['parametros']['iou_com_ressalva'], 2)} e
{d.fmt_dec(meta['parametros']['iou_comparavel'], 2)}, comparável com ressalva (marcado com †);
abaixo disso, ou se o bairro não existia em 2010, a variação não é exibida.

**Densidade** usa a área de cada bairro publicada pelo IBGE (`AREA_KM2`).
"""
        )
        arquivos = pd.DataFrame(
            [
                {"arquivo": k, "fonte": v["fonte"], "baixado em (UTC)": v["baixado_em"], "url": v["url"]}
                for k, v in meta["arquivos_brutos"].items()
            ]
        )
        st.dataframe(arquivos, hide_index=True, width="stretch")
        st.caption(f"Dados processados em {meta['gerado_em']} (UTC).")


def main() -> None:
    ind, geo, totais, meta = _carregar()

    # Menos espaço acima do título, para o mapa caber inteiro na primeira tela
    st.markdown("<style>.block-container{padding-top:2rem}</style>", unsafe_allow_html=True)
    st.title("Raio-X dos Bairros de João Pessoa")
    st.caption(
        "População dos 64 bairros nos Censos 2010 e 2022 do IBGE. Arraste para mover o mapa, use a roda "
        "do mouse para aproximar e clique num bairro para ver o detalhe."
    )

    # --- estado do bairro selecionado
    maior = ind.loc[ind.pop_2022.idxmax()]
    nomes = ind.sort_values("nm_bairro").set_index("cd_bairro").nm_bairro
    if "bairro" not in st.session_state:
        # o bairro pode vir do link (?bairro=mangabeira) na primeira carga da página
        st.session_state.bairro = d.codigo_por_slug(ind, st.query_params.get("bairro")) or maior.cd_bairro

    col_mapa, col_det = st.columns([7, 3], gap="medium")
    with col_mapa:
        indicador = st.radio(
            "Indicador do mapa", list(INDICADORES), format_func=INDICADORES.get, horizontal=True,
            label_visibility="collapsed",
        )
        evento = st.plotly_chart(
            figura_mapa(ind, geo, indicador, st.session_state.bairro),
            on_select="rerun",
            selection_mode="points",
            key="mapa",
            config={"scrollZoom": True, "displaylogo": False},
        )
        pontos = (evento or {}).get("selection", {}).get("points", []) if evento else []
        clicado = pontos[0].get("location") if pontos else None
        if clicado and clicado != st.session_state.get("ultimo_clique") and clicado in nomes.index:
            st.session_state.ultimo_clique = clicado
            st.session_state.bairro = clicado
            st.rerun()
        if indicador == "var_pct":
            st.caption(
                "Azul: ganhou população; vermelho: perdeu. A cor satura em ±60% (valor exato ao passar o mouse). "
                "Bairros sem cor e com contorno escuro: variação não comparável."
            )
        elif indicador == "pop_2022":
            st.caption(
                "Quanto mais escuro, mais moradores. Bairros grandes em área tendem a ter mais gente; "
                "para comparar a concentração de moradores, use a densidade."
            )
        else:
            st.caption(
                "Moradores por km²: quanto mais escuro, mais gente vivendo em cada pedaço do bairro. "
                "Bairros com muita área verde, industrial ou de praia aparecem mais claros."
            )

    with col_det:
        st.selectbox(
            "Bairro",
            nomes.index,
            format_func=nomes.get,
            key="bairro",
        )
        painel_bairro(ind, st.session_state.bairro, meta)
    st.query_params["bairro"] = d.slug(nomes[st.session_state.bairro])  # link compartilhável do bairro

    # --- números do município
    st.divider()
    p10, p22 = totais.loc[2010, "pop_municipio"], totais.loc[2022, "pop_municipio"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("População de João Pessoa (2022)", d.fmt_int(p22))
    k2.metric(
        "Variação desde 2010",
        d.fmt_var_int(p22 - p10),
        delta=d.fmt_var_pct(100 * (p22 - p10) / p10).replace("−", "-"),
    )
    k3.metric(f"Bairro mais populoso ({d.fmt_int(maior.pop_2022)} hab.)", maior.nm_bairro)
    k4.metric("Bairros", "64")

    # --- ranking
    st.header("Quem mais cresceu e quem mais perdeu população (2010→2022)")
    st.caption(
        "Compara o Censo 2010 com o de 2022. Só entram bairros cujos limites não mudaram muito entre os "
        "dois censos; caso contrário, a variação misturaria crescimento com mudança de território."
    )
    r1, r2, r3 = st.columns([2, 2, 3])
    metrica = r1.radio(
        "Medida", ["var_pct", "var_abs"],
        format_func={"var_pct": "Variação %", "var_abs": "Variação em habitantes"}.get, horizontal=True,
    )
    n = r2.select_slider("Quantos bairros", options=[5, 10, 15], value=10)
    pop_min = r3.slider(
        "População mínima em 2010", 0, 5000, 1000, step=250,
        help="Evita que bairros muito pequenos dominem o ranking percentual "
             "(ex.: Barra de Gramame passou de 347 para 802 pessoas, +131%).",
    )
    g1, g2 = st.columns(2, gap="large")
    for col, cresc, titulo in [(g1, True, "Mais cresceram"), (g2, False, "Mais perderam")]:
        with col:
            st.subheader(titulo)
            df = d.ranking(ind, crescimento=cresc, metrica=metrica, n=n, pop_min_2010=pop_min)
            if df.empty:
                st.write("Nenhum bairro com esses filtros.")
            else:
                st.plotly_chart(figura_ranking(df, metrica, cresc), config={"displayModeBar": False})
    excl = ind[ind.comparabilidade == NAO_COMPARAVEL].nm_bairro.tolist()
    st.caption(
        "† comparável com ressalva (limite mudou parcialmente). Fora do ranking por limite não comparável: "
        + ", ".join(excl) + "."
    )

    # --- tabela
    st.header("Tabela completa")
    st.caption("Todos os bairros, ordenados por população. Clique no título de uma coluna para reordenar.")
    tabela = ind[
        ["nm_bairro", "pop_2010", "pop_2022", "var_abs", "var_pct", "area_km2", "densidade_2022",
         "domicilios_2022", "comparabilidade", "cd_bairro"]
    ].sort_values("pop_2022", ascending=False)
    st.dataframe(
        d.tabela_br(tabela, inteiros=["pop_2010", "pop_2022", "densidade_2022", "domicilios_2022"],
                    variacao_int=["var_abs"], pct_sinal={"var_pct": 1}, decimais={"area_km2": 2}),
        hide_index=True,
        width="stretch",
        column_config={
            "nm_bairro": "Bairro",
            "pop_2010": "Pop. 2010",
            "pop_2022": "Pop. 2022",
            "var_abs": "Variação",
            "var_pct": "Variação %",
            "area_km2": "Área (km²)",
            "densidade_2022": "hab/km²",
            "domicilios_2022": "Domicílios",
            "comparabilidade": "Comparabilidade 2010→2022",
            "cd_bairro": "Código IBGE",
        },
    )
    st.download_button(
        "Baixar CSV",
        (d.DATA_PROCESSED / "indicadores_bairros.csv").read_bytes(),
        file_name="indicadores_bairros_joao_pessoa.csv",
        mime="text/csv",
    )

    secao_sobre(meta, totais)
    st.caption("Código e metodologia: README do repositório. Dados: IBGE, Censos Demográficos 2010 e 2022.")


if __name__ == "__main__":
    main()
