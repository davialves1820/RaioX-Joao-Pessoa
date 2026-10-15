"""Página "Para onde vai o dinheiro de João Pessoa" (despesas declaradas ao TCE-PB)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.app import dados as dados_bairros
from src.app import dados_despesas as d
from src.config import ANOS_INCOMPLETOS_DESPESAS, EXCECOES_SICONFI
from src.process.despesas_regras import UNIDADES_GESTORAS

# Paleta (mesma da página de bairros; categóricas validadas para daltonismo)
AZUL = "#2a78d6"
AZUL_CLARO = "#9ec5f4"  # anos incompletos ou parciais
AZUL_SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
CATEGORICAS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
SUPERFICIE = "#fcfcfb"
TINTA_2 = "#52514e"
GRADE = "#e1e0d9"

AVISO = (
    "Valores **declarados** pela Prefeitura e demais órgãos municipais ao TCE-PB (SAGRES). "
    "Podem mudar após análise e auditoria do Tribunal."
)


@st.cache_data
def _carregar():
    return d.carregar(), dados_bairros.carregar_geojson()


def _layout(fig: go.Figure, altura: int = 360, eixo_y: str = "") -> go.Figure:
    fig.update_layout(
        height=altura,
        margin=dict(l=0, r=10, t=10, b=0),
        separators=",.",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        bargap=0.3,
        yaxis=dict(title=eixo_y, gridcolor=GRADE, zeroline=False, tickfont=dict(color=TINTA_2), tickformat=",~r"),
        xaxis=dict(showgrid=False, tickfont=dict(color=TINTA_2)),
        hoverlabel=dict(bgcolor="white"),
    )
    return fig


def _reais(serie: pd.Series) -> pd.Series:
    """Coluna de valores formatada em R$ no padrão brasileiro (para tabelas)."""
    return serie.map(d.fmt_reais_inteiro)


def _pct(serie: pd.Series, casas: int = 1, sinal: bool = False) -> pd.Series:
    fmt = f"{{:+.{casas}f}}%" if sinal else f"{{:.{casas}f}}%"
    return serie.map(lambda v: "—" if pd.isna(v) else fmt.format(v).replace(".", ",").replace("-", "−"))


def _rotulo_valor(corrigido: bool, meta: dict) -> str:
    if corrigido:
        ano, mes = meta["ipca"]["mes_referencia"].split("-")
        return f"corrigidos pelo IPCA (R$ de {mes}/{ano})"
    return "nominais (sem correção pela inflação)"


def _nota_status(ano: int, meta: dict) -> str:
    s = d.status_ano(ano, meta)
    if s == "incompleto":
        return f"⚠️ {ano}: {ANOS_INCOMPLETOS_DESPESAS[ano]}."
    if s == "parcial":
        ult = pd.Timestamp(meta["ultima_data_de_empenho"]).strftime("%d/%m/%Y")
        return f"⏳ {ano} está em andamento: dados até {ult}."
    return ""


# --- abas


def aba_visao_geral(df, dados, col, corrigido, meta):
    totais = d.total_por_ano(df, col)
    anos = list(totais.index)
    ano = st.selectbox("Ano", anos[::-1], index=1 if len(anos) > 1 else 0, key="dv_ano")
    if nota := _nota_status(ano, meta):
        st.warning(nota)

    per_cap = d.por_habitante(totais, dados["populacao"])
    var = d.variacao_pct(totais, ano, meta)
    k1, k2, k3 = st.columns(3)
    k1.metric(f"Total em {ano}", d.fmt_reais(totais[ano]))
    k2.metric(
        "Por habitante",
        d.fmt_reais_inteiro(per_cap[ano]).replace(",00", "") if pd.notna(per_cap[ano]) else "sem população oficial",
        help="População: estimativas do IBGE (tabela 6579) e Censos 2010 e 2022. "
             "O IBGE não publicou estimativa para 2023.",
    )
    k3.metric(
        f"Variação frente a {ano - 1}",
        "—" if var is None else f"{var:+.1f}%".replace(".", ",").replace("-", "−"),
        help="Só entre anos completos (2016 e o ano em andamento ficam de fora). "
             "Para comparar anos, prefira valores corrigidos pelo IPCA.",
    )
    st.caption(f"Valores {_rotulo_valor(corrigido, meta)}.")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.subheader("Total por ano")
        cores = [AZUL if d.status_ano(a, meta) is None else AZUL_CLARO for a in anos]
        hover = [
            f"<b>{a}</b><br>{d.fmt_reais(v)}" + (f"<br>{d.status_ano(a, meta)}" if d.status_ano(a, meta) else "")
            for a, v in totais.items()
        ]
        fig = go.Figure(go.Bar(
            x=anos, y=totais.values / 1e9, marker=dict(color=cores, cornerradius=4),
            hovertext=hover, hovertemplate="%{hovertext}<extra></extra>",
        ))
        st.plotly_chart(_layout(fig, eixo_y="R$ bilhões"), config={"displayModeBar": False})
        st.caption("Barras claras: 2016 (dados incompletos no TCE-PB) e ano em andamento.")
    with c2:
        st.subheader("Por habitante")
        completos = pd.Series([a for a in anos if d.status_ano(a, meta) is None])
        linha = per_cap.reindex(range(min(anos), max(anos) + 1)).where(
            lambda s: s.index.isin(completos)
        )
        outros = per_cap[[a for a in anos if d.status_ano(a, meta)]].dropna()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(linha.index), y=linha.values, mode="lines+markers", connectgaps=False,
            line=dict(color=AZUL, width=2), marker=dict(size=8, color=AZUL),
            hovertext=[f"<b>{a}</b><br>{d.fmt_reais_inteiro(v)}" for a, v in linha.items()],
            hovertemplate="%{hovertext}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=list(outros.index), y=outros.values, mode="markers",
            marker=dict(size=9, color=SUPERFICIE, line=dict(color=AZUL_CLARO, width=2)),
            hovertext=[f"<b>{a}</b> ({d.status_ano(a, meta)})<br>{d.fmt_reais_inteiro(v)}" for a, v in outros.items()],
            hovertemplate="%{hovertext}<extra></extra>",
        ))
        fig.update_xaxes(range=[min(anos) - 0.5, max(anos) + 0.5])
        st.plotly_chart(_layout(fig, eixo_y="R$ por habitante"), config={"displayModeBar": False})
        st.caption(
            "Sem ponto em 2023: o IBGE não publicou estimativa de população para esse ano. "
            "Pontos vazios: 2016 (incompleto) e ano em andamento, fora da linha."
        )

    st.subheader(f"Mês a mês em {ano}")
    mensal = df[df["ano"] == ano].groupby("mes")[col].sum().reindex(range(1, 13))
    meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    fig = go.Figure(go.Bar(
        x=meses, y=mensal.values / 1e6, marker=dict(color=AZUL, cornerradius=4),
        hovertext=[f"<b>{m}/{ano}</b><br>{d.fmt_reais(v)}" for m, v in zip(meses, mensal.values)],
        hovertemplate="%{hovertext}<extra></extra>",
    ))
    st.plotly_chart(_layout(fig, 300, "R$ milhões"), config={"displayModeBar": False})
    st.caption("Mês da data do empenho. Dezembro costuma concentrar empenhos de fim de exercício.")


def aba_por_area(df, col, corrigido, meta):
    anos = sorted(df["ano"].unique())
    ano = st.selectbox("Ano", anos[::-1], index=1 if len(anos) > 1 else 0, key="pa_ano")
    if nota := _nota_status(ano, meta):
        st.warning(nota)
    sel = df[df["ano"] == ano]
    st.caption(
        "Área de governo segundo a **função** do orçamento (classificação nacional). "
        f"Clique numa área para ver as subfunções. Valores {_rotulo_valor(corrigido, meta)}."
    )
    f = sel.groupby(["funcao", "subfuncao"], as_index=False)[col].sum()
    f = f[f[col] > 0]
    tot_f = f.groupby("funcao")[col].sum()
    ids = list(tot_f.index) + [f"{a} / {s}" for a, s in zip(f.funcao, f.subfuncao)]
    labels = list(tot_f.index) + list(f.subfuncao)
    parents = [""] * len(tot_f) + list(f.funcao)
    values = list(tot_f.values) + list(f[col])
    total = tot_f.sum()
    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents, values=values, branchvalues="total",
        marker=dict(colors=values, colorscale=[[i / 6, c] for i, c in enumerate(AZUL_SEQ)],
                    line=dict(color=SUPERFICIE, width=2)),
        hovertext=[f"{d.fmt_reais(v)} ({100 * v / total:.1f}% do total)".replace(".", ",") for v in values],
        hovertemplate="<b>%{label}</b><br>%{hovertext}<extra></extra>",
        texttemplate="<b>%{label}</b><br>%{percentRoot:.1%}",
        maxdepth=2,
    ))
    fig.update_layout(height=520, margin=dict(l=0, r=0, t=0, b=0), separators=",.")
    st.plotly_chart(fig, config={"displayModeBar": False})

    totais_ant = df[df["ano"] == ano - 1].groupby("funcao")[col].sum()
    tot_f = tot_f.sort_values(ascending=False)
    tabela = pd.DataFrame({"Valor": _reais(tot_f), "% do total": _pct(100 * tot_f / total)})
    if d.anos_comparaveis(ano, meta) and d.anos_comparaveis(ano - 1, meta) and len(totais_ant):
        tabela[f"Variação frente a {ano - 1}"] = _pct(100 * (tot_f / totais_ant.reindex(tot_f.index) - 1), sinal=True)
    tabela = tabela.rename_axis("Área (função)")
    st.dataframe(tabela, width="stretch")

    st.subheader("Uma área ao longo dos anos")
    area = st.selectbox("Área", list(tabela.index), key="pa_area")
    serie = df[df["funcao"] == area].groupby("ano")[col].sum()
    cores = [AZUL if d.status_ano(a, meta) is None else AZUL_CLARO for a in serie.index]
    fig = go.Figure(go.Bar(
        x=list(serie.index), y=serie.values / 1e6, marker=dict(color=cores, cornerradius=4),
        hovertext=[f"<b>{a}</b><br>{d.fmt_reais(v)}" for a, v in serie.items()],
        hovertemplate="%{hovertext}<extra></extra>",
    ))
    st.plotly_chart(_layout(fig, 300, "R$ milhões"), config={"displayModeBar": False})


def aba_fornecedores(dados, metrica, corrigido, meta, poder):
    cred = dados["credores"]
    if poder != "Todos":
        cred = cred[cred["cod_ug"].map(lambda c: UNIDADES_GESTORAS[c][1]) == poder]
    col = d.coluna(metrica, corrigido)
    st.caption(
        "Só **empresas e entidades com CNPJ**. Pessoas físicas não aparecem em rankings nem na busca. "
        "Folha de pagamento, encargos e benefícios ficam de fora: nesses empenhos o credor é o próprio "
        f"órgão pagador, não um fornecedor. Valores {_rotulo_valor(corrigido, meta)}."
    )
    anos = sorted(cred["ano"].unique())
    c1, c2, c3 = st.columns([3, 1, 2])
    periodo = c1.select_slider("Período", options=anos, value=(max(anos[0], anos[-1] - 4), anos[-1]), key="fo_periodo")
    n = c2.selectbox("Quantos", [10, 15, 25], index=1, key="fo_n")
    publicos = c3.toggle("Incluir entidades públicas", value=False, key="fo_pub",
                         help="Ministérios, tribunais (precatórios), INSS e outros órgãos que recebem repasses ou tributos.")
    if any(d.status_ano(a, meta) for a in range(periodo[0], periodo[1] + 1)):
        st.info("O período inclui 2016 (incompleto no TCE-PB) ou o ano em andamento.")
    rk = d.ranking_fornecedores(cred, periodo, col, n, publicos)
    st.subheader(f"Maiores fornecedores, {periodo[0]}–{periodo[1]}" if periodo[0] != periodo[1] else f"Maiores fornecedores em {periodo[0]}")
    fig = go.Figure(go.Bar(
        x=rk[col] / 1e6, y=rk["nome_credor"].str.slice(0, 45), orientation="h",
        marker=dict(color=AZUL, cornerradius=4),
        text=rk[col].map(d.fmt_reais), textposition="outside", cliponaxis=False,
        hovertext=[f"<b>{nm}</b><br>CNPJ {c}<br>{d.fmt_reais_inteiro(v)}" for nm, c, v in zip(rk.nome_credor, rk.cnpj_formatado, rk[col])],
        hovertemplate="%{hovertext}<extra></extra>",
    ))
    fig = _layout(fig, 34 * len(rk) + 40)
    fig.update_layout(yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)"), xaxis=dict(visible=False), margin=dict(r=90))
    st.plotly_chart(fig, config={"displayModeBar": False})

    st.subheader("Buscar empresa por nome ou CNPJ")
    termo = st.text_input("Nome ou CNPJ (mínimo 3 caracteres)", key="fo_busca", placeholder="ex.: Energisa ou 09.095.183")
    achados = d.buscar_credores(cred, termo)
    if termo and achados.empty:
        st.write("Nenhuma empresa encontrada.")
    if not achados.empty:
        opcoes = dict(zip(achados.cnpj, achados.nome_credor + " — " + achados.cnpj_formatado))
        cnpj = st.selectbox(f"{len(achados)} resultado(s)", list(opcoes), format_func=opcoes.get, key="fo_sel")
        r = d.resumo_credor(cred, cnpj, col)
        a, b = st.columns(2)
        a.metric(f"Total {metrica} ({min(r['por_ano'].index)}–{max(r['por_ano'].index)})", d.fmt_reais(r["total"]))
        b.metric("Empenhos", f"{r['n_empenhos']:,}".replace(",", "."))
        g1, g2 = st.columns(2, gap="large")
        with g1:
            st.markdown("**Por ano**")
            pa = r["por_ano"]
            fig = go.Figure(go.Bar(
                x=list(pa.index), y=pa.values / 1e6, marker=dict(color=AZUL, cornerradius=4),
                hovertext=[f"<b>{a}</b><br>{d.fmt_reais_inteiro(v)}" for a, v in pa.items()],
                hovertemplate="%{hovertext}<extra></extra>",
            ))
            st.plotly_chart(_layout(fig, 260, "R$ milhões"), config={"displayModeBar": False})
        with g2:
            st.markdown("**Por órgão pagador**")
            po = r["por_orgao"]
            po = po[po > 0]
            st.dataframe(
                pd.DataFrame({"Órgão": [UNIDADES_GESTORAS[c][0] for c in po.index], "Valor": _reais(po).values}),
                hide_index=True, width="stretch",
            )
        st.caption("Arquivos de origem (TCE-PB): " + ", ".join(r["arquivos"]))


def aba_licitacao(df, col, corrigido, meta):
    sem_pessoal = st.toggle(
        "Excluir folha de pagamento e encargos", value=True, key="li_pessoal",
        help="Salários, encargos e benefícios não passam por licitação e dominariam a categoria 'Sem licitação'.",
    )
    part = d.participacao_licitacao(df, col, sem_pessoal)
    st.caption(
        "Participação de cada modalidade no valor de cada ano. 'Sem licitação' inclui despesas que não "
        "exigem licitação, como tributos, repasses, tarifas de serviços públicos e contratos de anos "
        "anteriores. 'Outras modalidades': chamada pública, credenciamento, licitação internacional, "
        "tomada de preços, convite, concurso e leilão."
    )
    fig = go.Figure()
    for i, m in enumerate(d.ORDEM_LICITACAO):
        fig.add_trace(go.Bar(
            x=list(part.index), y=part[m], name=m, marker=dict(color=CATEGORICAS[i], line=dict(color=SUPERFICIE, width=1)),
            hovertemplate=f"<b>{m}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
        ))
    fig = _layout(fig, 420, "% do valor do ano")
    fig.update_layout(barmode="stack", showlegend=True, legend=dict(orientation="h", y=-0.15, traceorder="normal"))
    st.plotly_chart(fig, config={"displayModeBar": False})
    st.caption("2016 está incompleto no TCE-PB; o ano em andamento é parcial. As participações são proporções do próprio ano.")
    with st.expander("Ver em tabela"):
        st.dataframe(part.apply(_pct).rename_axis("Ano"), width="stretch")


def aba_mapa(dados, geo, corrigido, meta):
    st.warning(
        "**Estimativa parcial e experimental.** O mapa mostra só empenhos cujo texto de descrição cita "
        "o nome de um bairro (ex.: \"pavimentação no bairro de Mangabeira\"). A maior parte do gasto, "
        "como folha, saúde e educação em rede, não cita bairro e não aparece aqui.",
        icon="🧪",
    )
    bairros, cob = dados["bairros"], dados["cobertura"]
    anos = sorted(cob["ano"].unique())
    periodo = st.select_slider("Período", options=anos, value=(max(anos[0], anos[-1] - 4), anos[-1]), key="ma_periodo")
    cobp = cob[cob["ano"].between(*periodo)]
    cobertura = 100 * cobp["um_bairro"].sum() / cobp["total"].sum()
    col = "empenhado_corrigido" if corrigido else "empenhado"
    v = bairros[bairros["ano"].between(*periodo)].groupby(["cd_bairro", "nm_bairro"], as_index=False)[col].sum()

    k1, k2, k3 = st.columns(3)
    k1.metric("Cobertura do valor empenhado", f"{cobertura:.1f}%".replace(".", ","),
              help="Parte do valor total empenhado no período cujo texto cita exatamente um bairro.")
    k2.metric("Associado a um bairro", d.fmt_reais(v[col].sum()))
    k3.metric("Citando vários bairros (fora do mapa)", d.fmt_reais(cobp["varios_bairros"].sum()))

    todos = pd.DataFrame(
        [(f["properties"]["cd_bairro"], f["properties"]["nm_bairro"]) for f in geo["features"]],
        columns=["cd_bairro", "nm_bairro"],
    )
    m = todos.merge(v[["cd_bairro", col]], on="cd_bairro", how="left")
    com = m[m[col] > 0]
    sem = m[~(m[col] > 0)]
    fig = go.Figure()
    fig.add_trace(go.Choroplethmap(
        geojson=geo, featureidkey="properties.cd_bairro", locations=sem.cd_bairro, z=[0] * len(sem),
        colorscale=[[0, "rgba(252,252,251,0.5)"], [1, "rgba(252,252,251,0.5)"]], showscale=False,
        marker_line_color="#c3c2b7", marker_line_width=1,
        hovertext=sem.nm_bairro + "<br>nenhum empenho cita o bairro", hovertemplate="%{hovertext}<extra></extra>",
    ))
    fig.add_trace(go.Choroplethmap(
        geojson=geo, featureidkey="properties.cd_bairro", locations=com.cd_bairro, z=com[col] / 1e6,
        colorscale=[[i / 6, c] for i, c in enumerate(AZUL_SEQ)], marker_opacity=0.85,
        marker_line_color=SUPERFICIE, marker_line_width=1,
        colorbar=dict(title=dict(text="R$ mi"), thickness=12, len=0.45, x=0.985, xanchor="right", y=0.97,
                      yanchor="top", bgcolor="rgba(252,252,251,0.85)", outlinewidth=0),
        hovertext=[f"<b>{n}</b><br>{d.fmt_reais(x)}" for n, x in zip(com.nm_bairro, com[col])],
        hovertemplate="%{hovertext}<extra></extra>",
    ))
    fig.update_layout(
        map=dict(style="carto-positron", center=dict(lat=-7.147, lon=-34.875), zoom=11.3),
        height=620, margin=dict(l=0, r=0, t=0, b=0), separators=",.",
    )
    st.plotly_chart(fig, config={"scrollZoom": True, "displaylogo": False})
    st.caption(
        "Regras: nomes que também são palavras comuns ou nomes de pessoas (Centro, Torre, José Américo...) "
        "só contam depois da palavra \"bairro\"; nomes precedidos de rua, avenida, praça ou escola não contam; "
        "empenhos que citam mais de um bairro ficam fora do mapa. Detalhes no README."
    )
    t = v.sort_values(col, ascending=False)
    st.dataframe(
        pd.DataFrame({"Bairro": t["nm_bairro"].values, "Valor citado": _reais(t[col]).values}),
        hide_index=True, width="stretch",
    )


def aba_sobre(dados, meta):
    st.markdown(
        f"""
{AVISO} O painel mostra **para onde vai o dinheiro**; não faz juízo sobre a regularidade de nenhuma despesa.

**Fonte.** Empenhos de todos os órgãos municipais de João Pessoa (Prefeitura, fundos, autarquias,
fundações e Câmara) no portal de dados abertos do TCE-PB, de 2009 a {pd.Timestamp(meta['ultima_data_de_empenho']).strftime('%d/%m/%Y')}.
O valor **empenhado** é o compromisso de gasto; o **pago** é o que de fato saiu do caixa.
Anulações já vêm descontadas pelo TCE-PB.

**Transferências entre órgãos do município** (por exemplo, a contribuição da Prefeitura à previdência
municipal) contam o mesmo dinheiro duas vezes; por padrão ficam de fora (opção no topo da página).

**Correção pela inflação:** IPCA (IBGE) até {meta['ipca']['mes_referencia']}. Todos os gráficos dizem se o
valor é nominal ou corrigido.

**Pessoas físicas:** CPF mascarado e nome omitido; não há rankings nem busca de pessoas.
"""
    )
    st.markdown("**Conferência com o total declarado ao Tesouro (SICONFI)**")
    v = dados["validacao"].dropna(subset=["siconfi_empenhado"]).copy()
    v["Situação"] = v["ano"].map(lambda a: EXCECOES_SICONFI.get(a, "dentro da tolerância de 0,2%"))
    st.dataframe(
        pd.DataFrame({
            "Ano": v["ano"].astype(str).values,
            "TCE-PB": _reais(v["tce_empenhado"]).values,
            "SICONFI": _reais(v["siconfi_empenhado"]).values,
            "Diferença": _pct(v["diferenca_pct"], 2, sinal=True).values,
            "Situação": v["Situação"].values,
        }),
        hide_index=True, width="stretch",
    )
    arquivos = pd.DataFrame(
        [{"arquivo": k, "baixado em (UTC)": x["baixado_em"], "url": x["url"]}
         for k, x in meta["arquivos_brutos"].items() if k.startswith("tce_pb/despesas")]
    )
    with st.expander("Arquivos de origem"):
        st.dataframe(arquivos, hide_index=True, width="stretch")
    st.caption(f"Dados processados em {meta['gerado_em']} (UTC). Metodologia completa no README do repositório.")


def main() -> None:
    dados, geo = _carregar()
    meta = dados["meta"]
    st.markdown("<style>.block-container{padding-top:2rem}</style>", unsafe_allow_html=True)
    st.title("Para onde vai o dinheiro de João Pessoa")
    ult = pd.Timestamp(meta["ultima_data_de_empenho"]).strftime("%d/%m/%Y")
    st.caption(f"Despesas empenhadas pelos órgãos municipais, 2009 a {ult}. {AVISO}")

    c1, c2, c3, c4 = st.columns([1.2, 1.6, 1.4, 2])
    metrica = c1.radio("Valor", ["empenhado", "pago"], format_func=str.capitalize, horizontal=True, key="g_metrica",
                       help="Empenhado: compromisso de gasto. Pago: o que saiu do caixa.")
    corrigido = c2.radio("Inflação", [True, False], format_func=lambda x: "Corrigido (IPCA)" if x else "Nominal",
                         horizontal=True, key="g_corr")
    poder = c3.selectbox("Órgãos", ["Todos", "Executivo", "Legislativo"], key="g_poder")
    sem_intra = c4.toggle("Excluir transferências entre órgãos do município", value=True, key="g_intra",
                          help="Ex.: contribuição da Prefeitura à previdência municipal (IPM). Incluí-las conta o mesmo dinheiro duas vezes.")
    col = d.coluna(metrica, corrigido)
    df = d.filtrar(dados["cubo"], poder, sem_intra)

    abas = st.tabs(["Visão geral", "Por área", "Fornecedores", "Licitação", "Mapa (experimental)", "Sobre os dados"])
    with abas[0]:
        aba_visao_geral(df, dados, col, corrigido, meta)
    with abas[1]:
        aba_por_area(df, col, corrigido, meta)
    with abas[2]:
        aba_fornecedores(dados, metrica, corrigido, meta, poder)
    with abas[3]:
        aba_licitacao(df, col, corrigido, meta)
    with abas[4]:
        aba_mapa(dados, geo, corrigido, meta)
    with abas[5]:
        aba_sobre(dados, meta)
