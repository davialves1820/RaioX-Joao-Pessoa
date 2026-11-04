"""Página "Câmara Municipal de João Pessoa": vereadores, produção legislativa, projetos de lei e pessoal."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.app import dados as dados_bairros
from src.app import dados_camara as d
from src.app import dados_despesas as dd
from src.app import tema

AVISO_QUANTIDADE = (
    "**Quantidade não mede trabalho.** Um requerimento de obra costuma ser um pedido curto e padronizado; "
    "um projeto de lei passa por comissões e plenário. Há vereadores com milhares de requerimentos e outros "
    "com poucos, por estilo de mandato. Por isso a lista está em ordem alfabética, sem ranking."
)

GLOSSARIO = """
- **Projeto de lei:** proposta de lei municipal (ordinária ou complementar). Vira lei se aprovada pela Câmara e
  sancionada pelo prefeito, ou se a Câmara derrubar o veto.
- **Indicação:** sugestão formal ao Executivo para que faça algo (uma obra, um serviço, uma política).
- **Requerimento de obras e serviços:** pedido ao órgão responsável (Seinfra, Emlur, Cagepa...) por um serviço
  num local específico, como iluminação, calçamento ou limpeza.
- **Votos de aplauso, pesar e similares:** manifestações da Câmara. O SAPL de João Pessoa não tem o tipo
  "moção"; elas são requerimentos (art. 171, X, do Regimento Interno).
- **Emenda impositiva:** emenda de vereador ao orçamento que destina recursos a uma entidade ou projeto e que
  o Executivo é obrigado a executar, salvo impedimento técnico.
- **Titular e suplente:** o suplente assume a cadeira quando o titular se afasta (por exemplo, para ocupar uma
  secretaria).
"""

# Grupos mostrados no gráfico da produção da Câmara; os demais entram em "Demais tipos"
GRUPOS_GRAFICO = ["Projetos de lei", "Indicações", "Requerimentos de obras e serviços",
                  "Votos de aplauso, pesar e similares", "Emendas impositivas ao orçamento"]
DEMAIS = "Demais tipos"

# Cor de cada situação (paleta categórica validada; ver tema.py)
COR_SITUACAO = {
    "Virou lei": 2, "Em tramitação": 0, "Arquivado": None, "Vetado": 1,
    "Rejeitado em plenário": 4, "Retirado pelo autor": 3, "Sem conclusão registrada": 6,
}


def _cor_situacao(s: str, T: dict) -> str:
    i = COR_SITUACAO[s]
    return T["mudo"] if i is None else T["cat"][i]


def _pergunta(titulo: str, explicacao: str) -> None:
    st.markdown(f"#### {titulo}")
    st.caption(explicacao)


@st.cache_data
def _carregar():
    desp = dd.carregar()
    return d.carregar(), desp["cubo"], desp["meta"]


def _layout(fig: go.Figure, altura: int = 340, eixo_y: str = "", legenda: bool = False) -> go.Figure:
    T = tema.atual()
    tema.layout_grafico(fig, T)
    fig.update_layout(height=altura, margin=dict(l=0, r=10, t=70 if legenda else 10, b=0), separators=",.",
                      bargap=0.3, showlegend=legenda,
                      legend=dict(orientation="h", y=1.04, yanchor="bottom", x=0, traceorder="normal"),
                      yaxis=dict(title=eixo_y, zeroline=False, tickformat=",~r"), xaxis=dict(showgrid=False))
    return fig


def _foto(url) -> str | None:
    return url.replace("http://", "https://", 1) if isinstance(url, str) and url else None


# --- abas


def aba_vereadores(dados: dict) -> None:
    _pergunta("Quem são os vereadores e o que apresentaram?",
              "Cada card mostra o mandato e as matérias apresentadas pelo vereador na legislatura, como autor ou "
              "coautor. Escolha um vereador abaixo dos cards para ver o detalhe.")
    st.info(AVISO_QUANTIDADE, icon="ℹ️")
    filtro = st.columns([1.5, 2, 2])
    leg = filtro[0].selectbox(
        "Legislatura", [19, 18], key="c_leg",
        format_func=lambda x: f"{x}ª ({d.LEGISLATURAS[x][0]}–{d.LEGISLATURAS[x][1]})" + (" · atual" if x == 19 else ""),
    )
    ver = d.vereadores_da_legislatura(dados["vereadores"], leg)
    prod = d.producao_por_vereador(dados["producao"], leg)
    proj = dados["projetos"]

    mostrar = filtro[1].radio("Mostrar", ["Todos", "Titulares", "Suplentes"], horizontal=True, key="cv_mostrar")
    if mostrar == "Titulares":
        ver = ver[ver["titular"]]
    elif mostrar == "Suplentes":
        ver = ver[~ver["titular"]]

    colunas = st.columns(3)
    for i, v in ver.iterrows():
        p = prod.loc[v["id_parlamentar"]] if v["id_parlamentar"] in prod.index else pd.Series(dtype=int)
        pj = d.projetos_do_vereador(proj, v["id_parlamentar"], leg)
        leis = int((pj["situacao"] == "Virou lei").sum())
        with colunas[list(ver.index).index(i) % 3].container(border=True):
            topo = st.columns([1, 3])
            if foto := _foto(v["foto"]):
                topo[0].image(foto, width=64)
            periodos = "; ".join(d.fmt_periodo(a, b) for a, b in v["periodos"])
            topo[1].markdown(f"**{v['nome']}**  \n{v['partido'] or 'sem partido registrado'} · "
                             f"{'titular' if v['titular'] else 'suplente'}")
            topo[1].caption(periodos)
            if parou := d.sem_subsidio_desde(dados["subsidio"], v["id_parlamentar"], leg, dados["meta"]["ultimo_mes_folha"]):
                topo[1].caption(f"Sem subsídio da Câmara desde {d.fmt_mes(parou)}.")
            m = st.columns(3)
            m[0].metric("Projetos de lei", dados_bairros.fmt_int(p.get("Projetos de lei", 0)),
                        help="Projetos de lei ordinária e complementar apresentados na legislatura.")
            m[1].metric("Viraram lei", dados_bairros.fmt_int(leis),
                        help="Projetos do vereador (autor ou coautor) que viraram lei até agora.")
            m[2].metric("Indicações", dados_bairros.fmt_int(p.get("Indicações", 0)))
            st.caption(f"Requerimentos de obras e serviços: {dados_bairros.fmt_int(p.get('Requerimentos de obras e serviços', 0))}"
                       f" · Votos de aplauso e pesar: {dados_bairros.fmt_int(p.get('Votos de aplauso, pesar e similares', 0))}")

    st.divider()
    st.subheader("Detalhe de um vereador")
    nomes = dict(zip(ver["id_parlamentar"], ver["nome"]))
    if not nomes:
        return
    pid = st.columns([2, 3])[0].selectbox("Vereador", list(nomes), format_func=nomes.get, key="cv_detalhe")
    detalhe_vereador(dados, ver[ver["id_parlamentar"] == pid].iloc[0], prod, leg)


def detalhe_vereador(dados: dict, v: pd.Series, prod: pd.DataFrame, leg: int) -> None:
    T = tema.atual()
    pj = d.projetos_do_vereador(dados["projetos"], v["id_parlamentar"], leg)
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("**Matérias apresentadas, por tipo**")
        p = prod.loc[v["id_parlamentar"]] if v["id_parlamentar"] in prod.index else pd.Series(dtype=int)
        p = p[p > 0].sort_values()
        if p.empty:
            st.caption("Nenhuma matéria com autoria registrada no SAPL nesta legislatura.")
        else:
            fig = go.Figure(go.Bar(x=p.values, y=p.index, orientation="h", marker=dict(color=T["azul"], cornerradius=4),
                                   text=[dados_bairros.fmt_int(x) for x in p.values], textposition="outside",
                                   hovertemplate="%{y}: %{x}<extra></extra>"))
            _layout(fig, 40 + 34 * len(p))
            fig.update_xaxes(showgrid=False, showticklabels=False)
            st.plotly_chart(fig, config={"displayModeBar": False})
    with c2:
        st.markdown("**Subsídio bruto mensal**")
        s = dados["subsidio"][dados["subsidio"]["id_parlamentar"] == v["id_parlamentar"]].sort_values("ano_mes")
        if s.empty:
            st.caption("Sem pagamento de subsídio na folha do TCE-PB no período.")
        else:
            ult = d.ultimo_subsidio(dados["subsidio"], v["id_parlamentar"])
            st.metric(f"Último mês na folha ({d.fmt_mes(ult[0])})", dd.fmt_reais_inteiro(ult[1]),
                      help=f"Cargo na folha: {ult[2]}. Valor bruto do mês, como publicado pelo TCE-PB.")
            fig = go.Figure(go.Bar(x=pd.to_datetime(s["ano_mes"], format="%Y%m"), y=s["valor"],
                                   marker=dict(color=T["azul"]), customdata=[d.fmt_mes(m) for m in s["ano_mes"]],
                                   hovertext=[dd.fmt_reais_inteiro(x) for x in s["valor"]],
                                   hovertemplate="%{customdata}: %{hovertext}<extra></extra>"))
            st.plotly_chart(_layout(fig, 220, "R$"), config={"displayModeBar": False})
            st.caption("Total bruto do mês: inclui 13º e meses proporcionais (posse ou saída no meio do mês). "
                       "Meses sem barra: o vereador não recebeu pela Câmara, por exemplo, porque estava "
                       "licenciado para assumir outro cargo.")

    st.markdown(f"**Projetos de lei ({len(pj)})**")
    if pj.empty:
        st.caption("Nenhum projeto de lei como autor ou coautor nesta legislatura.")
        return
    r = d.resumo_projetos(pj)
    st.caption(" · ".join(f"{s}: {n}" for s, n in r.items() if n))
    tabela_projetos(pj)


def tabela_projetos(pj: pd.DataFrame) -> None:
    t = pj.assign(projeto=pj["sigla"] + " " + pj["numero"].astype(str) + "/" + pj["ano"].astype(str),
                  norma=pj["norma"].fillna(""))
    st.dataframe(
        t[["projeto", "ementa", "autores", "situacao", "norma", "link_sapl"]],
        column_config={
            "projeto": "Projeto", "ementa": st.column_config.TextColumn("Ementa", width="large"),
            "autores": "Autores", "situacao": "Situação", "norma": "Lei",
            "link_sapl": st.column_config.LinkColumn("SAPL", display_text="abrir"),
        },
        hide_index=True, width="stretch",
    )


def aba_producao(dados: dict) -> None:
    T = tema.atual()
    _pergunta("O que a Câmara apresenta e o que vira lei?",
              "Todas as matérias apresentadas por ano, de vereadores, do Executivo e da Mesa, e a situação "
              "dos projetos de lei.")
    com_osm = st.toggle("Incluir requerimentos de obras e serviços", value=False, key="cp_osm",
                        help="São cerca de 80% das matérias. Com eles no gráfico, os outros tipos quase somem.")
    o = dados["origem"]
    if not com_osm:
        o = o[o["grupo"] != "Requerimentos de obras e serviços"]
    o = o.assign(g=o["grupo"].where(o["grupo"].isin(GRUPOS_GRAFICO), DEMAIS))
    t = o.pivot_table(index="ano", columns="g", values="materias", aggfunc="sum", fill_value=0)
    t = t.reindex(columns=[c for c in GRUPOS_GRAFICO + [DEMAIS] if c in t.columns])
    fig = go.Figure()
    for i, g in enumerate(t.columns):
        cor = T["mudo"] if g == DEMAIS else T["cat"][i]
        fig.add_bar(x=t.index, y=t[g], name=g, marker=dict(color=cor),
                    hovertemplate=f"<b>{g}</b><br>%{{x}}: %{{y:,}}<extra></extra>")
    fig.update_layout(barmode="stack")
    st.plotly_chart(_layout(fig, 380, "matérias", legenda=True), config={"displayModeBar": False})
    ano_atual = dados["meta"]["anos"][-1]
    osm = dados["origem"].query("grupo == 'Requerimentos de obras e serviços'").groupby("ano")["materias"].sum()
    st.caption(f"{ano_atual} está em andamento. Requerimentos de obras e serviços por ano: "
               + ", ".join(f"{a}: {dados_bairros.fmt_int(n)}" for a, n in osm.items()) + ".")

    st.subheader("Situação dos projetos de lei")
    origem = st.radio("Autoria", ["Todos", "Parlamentar", "Executivo"], horizontal=True, key="cp_origem",
                      format_func={"Todos": "Todos", "Parlamentar": "Vereadores", "Executivo": "Prefeitura (Executivo)"}.get)
    s = d.situacao_por_ano(dados["projetos"], None if origem == "Todos" else origem)
    fig = go.Figure()
    for sit in s.columns:
        fig.add_bar(x=s.index, y=s[sit], name=sit, marker=dict(color=_cor_situacao(sit, T)),
                    hovertemplate=f"<b>{sit}</b><br>%{{x}}: %{{y}}<extra></extra>")
    fig.update_layout(barmode="stack")
    st.plotly_chart(_layout(fig, 360, "projetos", legenda=True), config={"displayModeBar": False})
    st.caption("Ano de apresentação do projeto. Projetos recentes ainda estão em tramitação. A maior parte dos que "
               "não viram lei é arquivada na Comissão de Constituição e Justiça, depois de parecer contrário; "
               "rejeição em votação no plenário é rara.")

    st.subheader("Buscar projetos de lei")
    texto = st.text_input("Palavra na ementa ou nome de autor", key="cp_busca",
                          placeholder="ex.: ciclovia, saúde mental, Marcos Henriques")
    if texto:
        achados = d.buscar_projetos(dados["projetos"], texto)
        st.caption(f"{len(achados)} projeto(s) encontrado(s).")
        tabela_projetos(achados.head(200))


def aba_pessoal(dados: dict, cubo: pd.DataFrame, meta_desp: dict) -> None:
    T = tema.atual()
    _pergunta("Quanto custa a Câmara e quem trabalha nela?",
              "Despesas da Câmara declaradas ao TCE-PB e folha de pessoal mensal, por grupo de cargo.")
    leg = dd.filtrar(cubo, "Legislativo", True)
    tot = leg.groupby("ano")["empenhado_corrigido"].sum()
    tot = tot[tot.index >= 2013]
    cores = [T["azul_claro"] if a == meta_desp.get("ano_parcial") else T["azul"] for a in tot.index]
    fig = go.Figure(go.Bar(x=tot.index, y=tot.values / 1e6, marker=dict(color=cores, cornerradius=4),
                           hovertext=[dd.fmt_reais(v) for v in tot.values],
                           hovertemplate="<b>%{x}</b><br>%{hovertext}<extra></extra>"))
    st.markdown("**Despesa empenhada da Câmara por ano** (corrigida pelo IPCA)")
    st.plotly_chart(_layout(fig, 280, "R$ milhões"), config={"displayModeBar": False})
    st.caption("Fonte: despesas da Câmara no TCE-PB (a mesma base da página \"Para onde vai o dinheiro\"). "
               "Barra clara: ano em andamento.")

    folha = dados["folha"]
    mes, pessoas = d.pessoas_ultimo_mes(folha)
    mensal = d.folha_mensal(folha)
    st.markdown(f"**Folha de pessoal em {d.fmt_mes(mes)}**")
    c1, c2 = st.columns(2)
    ult = mensal.loc[mes].sort_values()
    fig = go.Figure(go.Bar(x=ult.values / 1e3, y=ult.index, orientation="h",
                           marker=dict(color=T["azul"], cornerradius=4),
                           customdata=[dados_bairros.fmt_int(pessoas.get(g, 0)) for g in ult.index],
                           hovertext=[dd.fmt_reais(v) for v in ult.values],
                           hovertemplate="<b>%{y}</b><br>%{hovertext}<br>%{customdata} pessoas<extra></extra>"))
    _layout(fig, 320, "")
    fig.update_xaxes(tickformat=",~r")
    c1.plotly_chart(fig, config={"displayModeBar": False})
    c1.caption("Total bruto do mês por grupo de cargo, em R$ mil. Passe o mouse para ver quantas pessoas.")
    serie = mensal.sum(axis=1)
    fig = go.Figure(go.Scatter(x=pd.to_datetime(serie.index, format="%Y%m"), y=serie.values / 1e6, mode="lines",
                               customdata=[d.fmt_mes(m) for m in serie.index],
                               line=dict(color=T["azul"], width=2),
                               hovertext=[dd.fmt_reais(v) for v in serie.values],
                               hovertemplate="%{customdata}: %{hovertext}<extra></extra>"))
    c2.plotly_chart(_layout(fig, 320, "R$ milhões por mês"), config={"displayModeBar": False})
    c2.caption("Total bruto da folha da Câmara por mês, em valores da época (sem correção pela inflação). "
               "Picos em junho e dezembro: 13º.")
    st.info("O custo dos gabinetes aparece só no total: a folha do TCE-PB não informa de qual vereador é cada "
            "assessor, então dividir esse valor por vereador seria uma estimativa.", icon="ℹ️")


def aba_sobre(dados: dict) -> None:
    meta = dados["meta"]
    st.markdown("#### Fontes")
    st.markdown(
        "- **SAPL da Câmara Municipal** ([API aberta](https://sapl.joaopessoa.pb.leg.br/api/)): vereadores, "
        "mandatos, partidos, matérias, autoria, normas e tramitações.\n"
        "- **TCE-PB, dados abertos do SAGRES:** folha de pessoal mensal e despesas da Câmara.\n"
        f"- **{meta['regras']['subsidio_legal']['norma']}** ([texto]({meta['regras']['subsidio_legal']['link']})): "
        "subsídio de R$ 26.000 por vereador e R$ 32.000 para o presidente, de 2025 a 2028."
    )
    st.markdown("#### Como os números são calculados")
    st.markdown(
        "- **Produção:** cada matéria conta uma vez para cada vereador autor ou coautor.\n"
        "- **Virou lei:** uma norma jurídica do SAPL aponta para o projeto. Nos demais, a situação vem da "
        "última tramitação.\n"
        "- **Subsídio:** valor bruto do mês na folha do TCE-PB, ligado ao vereador do SAPL pelo nome completo "
        "(ou por uma tabela conferida pelo período de mandato, quando o SAPL abrevia o nome).\n"
        "- **Folha:** pessoas e total bruto por mês e grupo de cargo, sem nomes."
    )
    st.markdown("#### O que não está aqui, e por quê")
    st.markdown(
        "- **Presença nas sessões.** O registro de presença do SAPL é incompleto: a ata da 7ª sessão "
        "ordinária (06/03/2025), por exemplo, lista vereadores presentes que o registro não tem. Um número "
        "de presença por vereador seria enganoso.\n"
        "- **Voto de cada vereador no plenário.** O SAPL guarda só o placar das votações em plenário.\n"
        "- **Custo por vereador.** A folha não diz de qual gabinete é cada assessor.\n"
        "- **Afastamentos.** O SAPL não registra licenças. Há titulares com mandato ativo que não recebem "
        "subsídio por meses, e meses pagos que o SAPL não registra como mandato (listados nos metadados)."
    )
    st.caption(f"Dados de {meta['anos'][0]} a {meta['anos'][-1]}; folha até {d.fmt_mes(meta['ultimo_mes_folha'])}. "
               f"Gerado em {meta['gerado_em'][:10]}. Detalhes em docs/camara.md no repositório.")


def main() -> None:
    dados, cubo, meta_desp = _carregar()
    tema.preparar_pagina(tema.atual())
    tema.cabecalho("Câmara Municipal de João Pessoa",
                   "Vereadores, produção legislativa, projetos de lei e pessoal, com dados do SAPL da Câmara e "
                   "do TCE-PB, de 2021 em diante.")
    with st.expander("Entenda os termos usados nesta página"):
        st.markdown(GLOSSARIO)
    abas = st.tabs(["Vereadores", "Produção e projetos", "Custo e pessoal", "Sobre os dados"])
    with abas[0]:
        aba_vereadores(dados)
    with abas[1]:
        aba_producao(dados)
    with abas[2]:
        aba_pessoal(dados, cubo, meta_desp)
    with abas[3]:
        aba_sobre(dados)
