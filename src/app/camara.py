"""Página "Câmara Municipal de João Pessoa": vereadores, matérias, normas, sessões, pessoal e contas.

A página é organizada em seções (botões no topo) com listas pesquisáveis, no lugar de gráficos
agregados: quem visita quer achar o que o seu vereador apresentou, o que virou lei, a ata de uma
sessão, quem trabalha na Câmara e quanto ela gasta.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app import dados as dados_bairros
from src.app import dados_camara as d
from src.app import dados_despesas as dd
from src.app import tema

SECOES = ["Vereadores", "Projetos de lei", "Indicações", "Requerimentos", "Votos e moções", "Leis",
          "Resoluções", "Decretos legislativos", "Pautas e atas", "Servidores", "Despesas", "Diárias",
          "Prestação de contas", "Sobre os dados"]

AVISO_QUANTIDADE = (
    "Quantidade não mede trabalho: um requerimento de obra costuma ser um pedido curto e padronizado; um "
    "projeto de lei passa por comissões e plenário. Por isso a lista está em ordem alfabética, sem ranking."
)

COR_SITUACAO = {
    "Virou lei": "green", "Em tramitação": "orange", "Arquivado": "gray", "Vetado": "red",
    "Rejeitado em plenário": "red", "Retirado pelo autor": "gray", "Sem conclusão registrada": "violet",
}


def _md(texto: str) -> str:
    """Escapa '$' para o Markdown do Streamlit não interpretar 'R$ ... R$' como fórmula."""
    return texto.replace("$", "\\$")


def _int(v) -> str:
    return dados_bairros.fmt_int(v)


def _reais(v) -> str:
    return dd.fmt_reais_inteiro(v)


def _foto(url) -> str | None:
    return url.replace("http://", "https://", 1) if isinstance(url, str) and url else None


@st.cache_data(show_spinner="Carregando os dados da Câmara...")
def _carregar():
    desp = dd.carregar()
    return d.carregar(), desp["credores"]


def _legislatura(chave: str) -> int:
    return st.selectbox(
        "Legislatura", [19, 18], key=chave,
        format_func=lambda x: f"{x}ª ({d.LEGISLATURAS[x][0]}–{d.LEGISLATURAS[x][1]})" + (" · atual" if x == 19 else ""),
    )


def _cartao(rotulo: str, valor: str, nota: str = "") -> None:
    with st.container(border=True):
        st.markdown(f'<p class="rx-kicker">{rotulo}</p>', unsafe_allow_html=True)
        st.markdown(f"### {_md(valor)}")
        if nota:
            st.caption(_md(nota))


def _tabela(df: pd.DataFrame, nomes: dict, reais=(), inteiros=(), pct: dict | None = None) -> None:
    """Tabela com cabeçalhos em português e números no padrão brasileiro."""
    t = df[list(nomes)].rename(columns=nomes)
    st.dataframe(dados_bairros.tabela_br(t, inteiros=[nomes[c] for c in inteiros], reais=[nomes[c] for c in reais],
                                         pct={nomes[c]: k for c, k in (pct or {}).items()}),
                 hide_index=True, width="stretch")


# --- itens das listas


def _item_projeto(p: pd.Series) -> None:
    with st.container(border=True):
        topo = st.columns([5, 1])
        tipo = "Projeto de Lei Complementar" if p["sigla"] == "PLC" else "Projeto de Lei"
        cor = COR_SITUACAO[p["situacao"]]
        topo[0].markdown(f"**{tipo} nº {p['numero']}/{p['ano']}** :{cor}-badge[{p['situacao']}]")
        topo[1].markdown(f"<div style='text-align:right;opacity:.7'>{d.fmt_data(p['data_apresentacao'])}</div>",
                         unsafe_allow_html=True)
        st.markdown(_md(p["ementa"]))
        links = [f"[Ver no SAPL]({p['link_sapl']})"]
        if isinstance(p["link_norma"], str):
            links.append(f"[{p['norma']}]({p['link_norma']})")
        st.caption(f"Origem: {p['origem']} · Autoria: {p['autores'] or 'não registrada'} · " + " · ".join(links))


NOMES_TIPO = {
    "R-OSM": "Requerimento de obras e serviços", "IND": "Indicação", "PI": "Projeto de indicação",
    "R-VOT": "Requerimento de voto (aplauso, pesar e similares)",
}


def _nome_tipo(sigla: str, tipo: str) -> str:
    if sigla in NOMES_TIPO:
        return NOMES_TIPO[sigla]
    t = tipo.strip().rstrip(".")
    return "Requerimento: " + t[4:].strip().lower() if t.upper().startswith("REQ-") else t


def _item_materia(m: pd.Series) -> None:
    with st.container(border=True):
        topo = st.columns([5, 1])
        tram = " :orange-badge[Em tramitação]" if m["em_tramitacao"] else ""
        topo[0].markdown(f"**{_nome_tipo(m['sigla'], m['tipo'])} nº {m['numero']}/{m['ano']}**{tram}")
        topo[1].markdown(f"<div style='text-align:right;opacity:.7'>{d.fmt_data(m['data_apresentacao'])}</div>",
                         unsafe_allow_html=True)
        st.markdown(_md(m["ementa"]))
        st.caption(f"Autoria: {m['autores'] or 'não registrada'} · [Ver no SAPL]({m['link_sapl']})")


def _item_norma(n: pd.Series) -> None:
    with st.container(border=True):
        topo = st.columns([5, 1])
        topo[0].markdown(f"**{n['tipo']} nº {n['numero']}/{n['ano']}**")
        topo[1].markdown(f"<div style='text-align:right;opacity:.7'>{d.fmt_data(n['data'])}</div>",
                         unsafe_allow_html=True)
        st.markdown(_md(n["ementa"]))
        links = [f"[Ver no SAPL]({n['link_sapl']})"]
        if isinstance(n["link_texto"], str):
            links.insert(0, f"[Texto da norma]({n['link_texto']})")
        st.caption(" · ".join(links))


def _lista(df: pd.DataFrame, item, chave: str, dados: dict, coluna_ano: str = "ano", com_autor: bool = True,
           placeholder: str = "Buscar por ementa, número ou autor") -> None:
    """Busca, filtros de ano e de vereador, contagem e paginação."""
    filtros = st.columns([3, 1, 2] if com_autor else [3, 1])
    texto = filtros[0].text_input("Buscar", key=f"{chave}_texto", placeholder=placeholder, label_visibility="collapsed")
    anos = sorted(df[coluna_ano].dropna().astype(int).unique(), reverse=True)
    ano = filtros[1].selectbox("Ano", [None] + anos, key=f"{chave}_ano", label_visibility="collapsed",
                               format_func=lambda a: "Todos os anos" if a is None else str(a))
    pid = None
    if com_autor:
        ver = dados["vereadores"].drop_duplicates("id_parlamentar")
        ver = ver.assign(o=ver["nome_parlamentar"].map(d.normalizar)).sort_values("o")
        nomes = dict(zip(ver["id_parlamentar"], ver["nome_parlamentar"]))
        pid = filtros[2].selectbox("Vereador", [None] + list(nomes), key=f"{chave}_autor",
                                   label_visibility="collapsed",
                                   format_func=lambda i: "Todos os autores" if i is None else nomes[i])
    achados = d.filtrar(df, texto, ano, pid, coluna_ano)
    pagina_atual = st.session_state.get(f"{chave}_pagina", 1)
    pagina, paginas = d.paginar(achados, pagina_atual)
    st.caption(f"{_int(len(achados))} resultado(s)" + (f" · página {min(pagina_atual, paginas)} de {paginas}"
                                                       if paginas > 1 else ""))
    for _, r in pagina.iterrows():
        item(r)
    if paginas > 1:
        st.number_input("Página", 1, paginas, key=f"{chave}_pagina", step=1)


# --- seções


def secao_vereadores(dados: dict) -> None:
    pid = st.query_params.get("vereador")
    if pid and pid.isdigit() and int(pid) in set(dados["vereadores"]["id_parlamentar"]):
        perfil_vereador(dados, int(pid))
        return
    topo = st.columns([1.5, 2, 3])
    with topo[0]:
        leg = _legislatura("cv_leg")
    mostrar = topo[1].radio("Mostrar", ["Todos", "Titulares", "Suplentes"], horizontal=True, key="cv_mostrar")
    st.caption(AVISO_QUANTIDADE)
    ver = d.vereadores_da_legislatura(dados["vereadores"], leg)
    if mostrar != "Todos":
        ver = ver[ver["titular"] == (mostrar == "Titulares")]
    colunas = st.columns(3)
    for n, (_, v) in enumerate(ver.iterrows()):
        with colunas[n % 3].container(border=True):
            _card_vereador(dados, v, leg)


def _card_vereador(dados: dict, v: pd.Series, leg: int) -> None:
    c = d.contagem(dados["producao"], v["id_parlamentar"], leg)
    pj = d.resumo_projetos(d.projetos_do_vereador(dados["projetos"], v["id_parlamentar"], leg))
    topo = st.columns([1, 3])
    if foto := _foto(v["foto"]):
        topo[0].image(foto, width=64)
    topo[1].markdown(f"**{v['nome']}**  \n{v['partido'] or 'sem partido registrado'} · "
                     f"{'titular' if v['titular'] else 'suplente'}")
    topo[1].caption("; ".join(d.fmt_periodo(a, b) for a, b in v["periodos"]))
    if parou := d.sem_subsidio_desde(dados["subsidio"], v["id_parlamentar"], leg, dados["meta"]["ultimo_mes_folha"]):
        st.caption(f"⚠️ Sem subsídio da Câmara desde {d.fmt_mes(parou)}.")
    m = st.columns(3)
    m[0].metric("Projetos de lei", _int(c.get("Projetos de lei", 0)))
    m[1].metric("Viraram lei", _int(pj["Virou lei"]))
    m[2].metric("Encerrados", _int(sum(pj[s] for s in d.ENCERRADOS)),
                help="Projetos do vereador que não viraram lei e não estão mais em tramitação: arquivados, "
                     "vetados, rejeitados em plenário ou retirados pelo autor.")
    m = st.columns(3)
    m[0].metric("Indicações", _int(c.get("Indicações", 0)))
    m[1].metric("Requerimentos", _int(c.get("Requerimentos de obras e serviços", 0) + c.get("Outros requerimentos", 0)),
                help="Requerimentos de obras e serviços e demais requerimentos.")
    m[2].metric("Votos e moções", _int(c.get("Votos de aplauso, pesar e similares", 0)),
                help="Votos de aplauso, pesar e similares (o SAPL de João Pessoa não tem o tipo 'moção').")
    if ult := d.ultimo_subsidio(dados["subsidio"], v["id_parlamentar"]):
        st.caption(_md(f"Subsídio em {d.fmt_mes(ult[0])}: **{_reais(ult[1])}**"))
    if st.button("Ver perfil", key=f"perfil_{v['id_parlamentar']}_{leg}", width="stretch"):
        st.query_params["vereador"] = str(v["id_parlamentar"])
        st.rerun()


def perfil_vereador(dados: dict, pid: int) -> None:
    if st.button("← Vereadores", key="voltar"):
        del st.query_params["vereador"]
        st.rerun()
    legs = sorted(dados["vereadores"].loc[dados["vereadores"]["id_parlamentar"] == pid, "legislatura"].unique(),
                  reverse=True)
    v_leg = dados["vereadores"][dados["vereadores"]["id_parlamentar"] == pid]
    cab = st.columns([1, 5])
    if foto := _foto(v_leg["foto"].iloc[0]):
        cab[0].image(foto, width=140)
    leg = legs[0]
    with cab[1]:
        st.markdown(f"## {v_leg['nome_parlamentar'].iloc[0]}")
        st.markdown(f"{v_leg['partido_atual'].iloc[0] or 'sem partido registrado'} · {v_leg['nome_completo'].iloc[0]}")
        if len(legs) > 1:
            leg = st.radio("Legislatura", legs, horizontal=True, key="pf_leg",
                           format_func=lambda x: f"{x}ª ({d.LEGISLATURAS[x][0]}–{d.LEGISLATURAS[x][1]})")
    v = d.vereadores_da_legislatura(dados["vereadores"], leg).set_index("id_parlamentar").loc[pid]

    ult = d.ultimo_subsidio(dados["subsidio"], pid)
    total, meses = d.subsidio_na_legislatura(dados["subsidio"], pid, leg)
    c = d.contagem(dados["producao"], pid, leg)
    pj = d.projetos_do_vereador(dados["projetos"], pid, leg)
    r = d.resumo_projetos(pj)
    atuacao = sum(c.get(g, 0) for g in d.ATUACAO)
    k = st.columns(4)
    with k[0]:
        _cartao("Subsídio no último mês", _reais(ult[1]) if ult else "—",
                f"{d.fmt_mes(ult[0])} · {ult[2]} · valor bruto" if ult else "sem pagamento na folha do TCE-PB")
    with k[1]:
        _cartao("Subsídio recebido na legislatura", _reais(total),
                f"soma de {meses} mês(es) na folha do TCE-PB")
    with k[2]:
        _cartao("Atuação", _int(atuacao), "indicações, requerimentos e votos")
    with k[3]:
        _cartao("Projetos de lei", _int(len(pj)), f"{r['Virou lei']} viraram lei · {r['Em tramitação']} em tramitação")
    with st.container(border=True):
        st.markdown(f'<p class="rx-kicker">Mandato · {"titular" if v["titular"] else "suplente"}</p>',
                    unsafe_allow_html=True)
        st.markdown("  \n".join(d.fmt_periodo(a, b) for a, b in v["periodos"]))
        if parou := d.sem_subsidio_desde(dados["subsidio"], pid, leg, dados["meta"]["ultimo_mes_folha"]):
            st.caption(f"Sem subsídio da Câmara desde {d.fmt_mes(parou)}. O SAPL não registra licenças e afastamentos.")
        st.caption(f"[Página do vereador no SAPL]({v['link']})")
    st.caption("O custo do gabinete não aparece aqui: a folha do TCE-PB não informa de qual vereador é cada "
               "assessor, então qualquer valor por vereador seria uma estimativa.")

    st.markdown(f"#### Projetos de lei ({len(pj)})")
    if pj.empty:
        st.caption("Nenhum projeto de lei como autor ou coautor nesta legislatura.")
    for _, p in pj.head(20).iterrows():
        _item_projeto(p)
    if len(pj) > 20:
        st.caption("Mostrando os 20 mais recentes. Todos estão na seção *Projetos de lei*, filtrando pelo vereador.")

    at = d.atuacao_do_vereador(dados["materias"], pid, leg)
    st.markdown(f"#### Atuação parlamentar (últimas 20 de {_int(len(at))})")
    for _, m in at.head(20).iterrows():
        _item_materia(m)
    if len(at) > 20:
        st.caption("Todas estão nas seções *Indicações*, *Requerimentos* e *Votos e moções*, filtrando pelo vereador.")


def secao_materias(dados: dict, grupos: list[str], chave: str, explicacao: str) -> None:
    st.caption(explicacao)
    m = dados["materias"]
    _lista(m[m["grupo"].isin(grupos)], _item_materia, chave, dados)


def secao_normas(dados: dict, tipo: str, chave: str, explicacao: str) -> None:
    st.caption(explicacao)
    n = dados["normas"]
    _lista(n[n["tipo"] == tipo], _item_norma, chave, dados, com_autor=False, placeholder="Buscar por ementa ou número")


def secao_sessoes(dados: dict) -> None:
    st.caption("Sessões plenárias, audiências e reuniões de comissão cadastradas no SAPL, com a pauta e a ata "
               "oficial quando publicadas. As atas existem para praticamente todas as sessões; as pautas de "
               "2025 e 2026 quase nunca foram publicadas no SAPL.")
    s = dados["sessoes"]
    f = st.columns([2, 1])
    tipos = sorted(s["tipo"].dropna().unique())
    tipo = f[0].selectbox("Tipo", [None] + tipos, key="ss_tipo", label_visibility="collapsed",
                          format_func=lambda t: "Todos os tipos" if t is None else t)
    anos = sorted(s["data"].str[:4].astype(int).unique(), reverse=True)
    ano = f[1].selectbox("Ano", anos, key="ss_ano", label_visibility="collapsed")
    s = s[s["data"].str.startswith(str(ano))]
    if tipo:
        s = s[s["tipo"] == tipo]
    pagina, paginas = d.paginar(s, st.session_state.get("ss_pagina", 1))
    st.caption(f"{_int(len(s))} sessão(ões)")
    for _, r in pagina.iterrows():
        with st.container(border=True):
            cols = st.columns([4, 2])
            cols[0].markdown(f"**{r['numero']}ª {r['tipo']}** · {d.fmt_data(r['data'])}")
            links = [f"[Pauta]({r['link_pauta']})" if isinstance(r["link_pauta"], str) else "pauta não publicada",
                     f"[Ata]({r['link_ata']})" if isinstance(r["link_ata"], str) else "ata não publicada",
                     f"[SAPL]({r['link_sapl']})"]
            cols[1].markdown(" · ".join(links))
    if paginas > 1:
        st.number_input("Página", 1, paginas, key="ss_pagina", step=1)


def secao_servidores(dados: dict) -> None:
    folha = dados["folha"]
    meses = sorted(folha["ano_mes"].unique(), reverse=True)
    mes = st.columns([1, 4])[0].selectbox("Mês", meses, format_func=d.fmt_mes, key="sv_mes")
    tab = d.folha_do_mes(folha, mes)
    k = st.columns(3)
    with k[0]:
        _cartao("Pessoas na folha", _int(tab["pessoas"].sum()), f"em {d.fmt_mes(mes)}")
    with k[1]:
        _cartao("Total bruto do mês", _reais(tab["total"].sum()), "inclui 13º e férias quando pagos no mês")
    with k[2]:
        gab = tab[tab["grupo_cargo"] == "Gabinetes dos vereadores"]
        _cartao("Cargos de gabinete", _int(gab["pessoas"].sum()), f"{_reais(gab['total'].sum())} no mês")
    st.caption("Uma linha por cargo, com o número de pessoas e o total bruto pago no mês, conforme a folha "
               "publicada pelo TCE-PB. Os nomes dos servidores não são mostrados. A folha não informa de qual "
               "gabinete é cada assessor.")
    _tabela(tab, {"cargo": "Cargo", "vinculo": "Vínculo", "grupo_cargo": "Grupo", "pessoas": "Pessoas",
                  "total": "Total bruto"}, reais=["total"], inteiros=["pessoas"])


def secao_despesas(dados: dict, credores: pd.DataFrame) -> None:
    desp = dados["despesas"]
    anos = sorted(desp["ano"].unique(), reverse=True)
    ano = st.columns([1, 4])[0].selectbox("Ano", anos, key="dp_ano")
    tab = d.despesas_do_ano(desp, ano)
    k = st.columns(2)
    with k[0]:
        _cartao("Empenhado", _reais(tab["empenhado"].sum()), f"{ano}, valores da época")
    with k[1]:
        _cartao("Pago", _reais(tab["pago"].sum()), f"{_int(tab['empenhos'].sum())} empenhos")
    st.markdown("#### Para onde vai o dinheiro da Câmara")
    _tabela(tab, {"elemento_despesa": "Tipo de despesa (elemento)", "empenhado": "Empenhado", "pago": "Pago",
                  "pct": "% do empenhado"}, reais=["empenhado", "pago"], pct={"pct": 1})
    st.markdown("#### Maiores fornecedores")
    forn = d.fornecedores_da_camara(credores, ano)
    if forn.empty:
        st.caption("Nenhum fornecedor (pessoa jurídica) no ano.")
    else:
        _tabela(forn, {"nome_credor": "Fornecedor", "cnpj_formatado": "CNPJ", "empenhado": "Empenhado", "pago": "Pago"},
                reais=["empenhado", "pago"])
    st.caption("Empenhos da Câmara e do fundo da Câmara (FEJP) declarados ao TCE-PB. Só empresas aparecem com "
               "nome; pessoas físicas não. Mais detalhes na página *Para onde vai o dinheiro*.")


def secao_diarias(dados: dict) -> None:
    di = dados["diarias"]
    st.caption("Diárias pagas pela Câmara para viagens a serviço. Como quem recebe são pessoas físicas "
               "(vereadores e servidores), só os totais são mostrados.")
    anual = di.groupby("ano")[["empenhado", "pago", "empenhos"]].sum().sort_index(ascending=False).reset_index()
    _tabela(anual.assign(ano=anual["ano"].astype(str)),
            {"ano": "Ano", "empenhado": "Empenhado", "pago": "Pago", "empenhos": "Empenhos"},
            reais=["empenhado", "pago"], inteiros=["empenhos"])
    ano = st.columns([1, 4])[0].selectbox("Ver os meses de", list(anual["ano"]), key="di_ano")
    mensal = di[di["ano"] == ano].assign(mes=lambda x: x["mes"].map(lambda m: f"{m:02d}/{ano}"))
    _tabela(mensal, {"mes": "Mês", "empenhado": "Empenhado", "pago": "Pago", "empenhos": "Empenhos"},
            reais=["empenhado", "pago"], inteiros=["empenhos"])


def secao_contas(dados: dict) -> None:
    T = tema.atual()
    rgf = dados["rgf"]
    st.caption("Indicadores fiscais da Câmara declarados ao Tesouro Nacional (SICONFI), no Relatório de Gestão "
               "Fiscal (RGF), publicado a cada quadrimestre.")
    with st.expander("O que é prestação de contas?"):
        st.markdown(
            "A Lei de Responsabilidade Fiscal limita o quanto cada Poder pode gastar com pessoal, em relação à "
            "**Receita Corrente Líquida (RCL)** do município (a receita do ano, descontadas as transferências "
            "obrigatórias). Para a Câmara, o limite máximo é **6% da RCL** (art. 20, III, a). Ao passar de 90% "
            "do limite (5,4%), o Tribunal de Contas emite um alerta; acima de 95% (5,7%, limite prudencial), a "
            "Câmara fica proibida de criar cargos e dar aumentos. A despesa é a dos últimos 12 meses."
        )
    u = rgf.iloc[-1]
    sit = d.situacao_rgf(u["pct_rcl"], u["limite_alerta_pct"], u["limite_prudencial_pct"], u["limite_maximo_pct"])
    cor = T["verde"] if sit == "Dentro do limite" else T["vermelho"]
    with st.container(border=True):
        st.markdown(f"**Despesa com pessoal (Lei de Responsabilidade Fiscal)** · RGF {int(u['quadrimestre'])}º "
                    f"quadrimestre de {int(u['ano'])}")
        k = st.columns(3)
        k[0].metric("Gasto com pessoal (12 meses)", _reais(u["despesa_pessoal"]))
        k[1].metric("% da Receita Corrente Líquida", dados_bairros.fmt_pct(u["pct_rcl"], 2))
        k[2].markdown(f"<p style='opacity:.7;margin-bottom:.2rem'>Situação</p>"
                      f"<p style='color:{cor};font-weight:600;font-size:1.2rem'>{sit}</p>", unsafe_allow_html=True)
        st.markdown(_barra_rgf(u, T), unsafe_allow_html=True)
        st.caption(_md(f"Marcas: limite de alerta ({dados_bairros.fmt_pct(u['limite_alerta_pct'], 1)}) e prudencial "
                       f"({dados_bairros.fmt_pct(u['limite_prudencial_pct'], 1)}). RCL ajustada: {_reais(u['rcl_ajustada'])}."))
    st.markdown("**Histórico (% da RCL, último quadrimestre publicado de cada ano)**")
    hist = d.rgf_ultimo_por_ano(rgf)
    linhas = "".join(
        f"<div style='display:flex;align-items:center;gap:.8rem;margin:.25rem 0'>"
        f"<span style='width:7rem'>{int(r['ano'])} ({int(r['quadrimestre'])}º q.)</span>"
        f"<div style='flex:1;background:{T['grade']};border-radius:4px;height:.6rem'>"
        f"<div style='width:{100 * r['pct_rcl'] / r['limite_maximo_pct']:.1f}%;background:{T['verde']};"
        f"height:.6rem;border-radius:4px'></div></div>"
        f"<span style='width:4rem;text-align:right'>{dados_bairros.fmt_pct(r['pct_rcl'], 2)}</span></div>"
        for _, r in hist.iterrows()
    )
    st.markdown(linhas, unsafe_allow_html=True)
    st.caption("Barra cheia = limite máximo de 6%. Fonte: SICONFI, RGF Anexo 01 do Poder Legislativo de João Pessoa.")


def _barra_rgf(u: pd.Series, T: dict) -> str:
    maximo = u["limite_maximo_pct"]

    def pos(x):
        return 100 * x / maximo

    marcas = "".join(
        f"<div style='position:absolute;left:{pos(u[c]):.1f}%;top:-3px;width:2px;height:16px;background:{T['cat'][1]}'></div>"
        for c in ("limite_alerta_pct", "limite_prudencial_pct")
    )
    rotulos = (
        f"<div style='position:relative;height:1.2rem;font-size:.8rem;opacity:.8'>"
        f"<span style='position:absolute;left:0'>0%</span>"
        f"<span style='position:absolute;left:{pos(u['limite_alerta_pct']):.1f}%;transform:translateX(-100%);"
        f"color:{T['cat'][1]}'>Alerta {dados_bairros.fmt_pct(u['limite_alerta_pct'], 1)}</span>"
        f"<span style='position:absolute;right:0'>Máx. {dados_bairros.fmt_pct(maximo, 0)}</span></div>"
    )
    return (f"<div style='position:relative;background:{T['grade']};border-radius:6px;height:10px;margin:.6rem 0 .3rem'>"
            f"<div style='width:{pos(u['pct_rcl']):.1f}%;background:{T['verde']};height:10px;border-radius:6px'></div>"
            f"{marcas}</div>{rotulos}")


def secao_sobre(dados: dict) -> None:
    meta = dados["meta"]
    st.markdown("#### Fontes")
    st.markdown(
        "- **SAPL da Câmara Municipal** ([API aberta](https://sapl.joaopessoa.pb.leg.br/api/)): vereadores, "
        "mandatos, partidos, matérias, autoria, normas, tramitações e sessões.\n"
        "- **TCE-PB, dados abertos do SAGRES:** folha de pessoal mensal e despesas (empenhos) da Câmara.\n"
        "- **Tesouro Nacional, SICONFI:** Relatório de Gestão Fiscal (RGF) do Poder Legislativo.\n"
        f"- **{meta['regras']['subsidio_legal']['norma']}** ([texto]({meta['regras']['subsidio_legal']['link']})): "
        "subsídio de R$ 26.000 por vereador e R$ 32.000 para o presidente, de 2025 a 2028."
    )
    st.markdown("#### Como os números são calculados")
    st.markdown(
        "- **Contagens dos vereadores:** cada matéria conta uma vez para cada vereador autor ou coautor.\n"
        "- **Virou lei:** uma norma jurídica do SAPL aponta para o projeto. Nos demais, a situação vem da "
        "última tramitação. *Encerrados* são os arquivados, vetados, rejeitados em plenário ou retirados.\n"
        "- **Subsídio:** valor bruto do mês na folha do TCE-PB (inclui 13º e meses proporcionais), ligado ao "
        "vereador do SAPL pelo nome completo, ou por uma tabela conferida pelo período de mandato.\n"
        "- **Servidores:** pessoas e total bruto por cargo e mês, sem nomes."
    )
    st.markdown("#### O que não está aqui, e por quê")
    st.markdown(
        "- **Presença nas sessões.** O registro de presença do SAPL é incompleto: a ata da 7ª sessão "
        "ordinária (06/03/2025), por exemplo, lista vereadores presentes que o registro não tem.\n"
        "- **Voto de cada vereador no plenário.** O SAPL guarda só o placar das votações em plenário.\n"
        "- **Custo do gabinete por vereador.** A folha não diz de qual gabinete é cada assessor.\n"
        "- **Licitações, contratos e orçamento da Câmara.** Dependem de fontes que ainda não foram integradas "
        "(issues #57 e #59 no repositório)."
    )
    st.caption(f"Dados de {meta['anos'][0]} a {meta['anos'][-1]}; folha até {d.fmt_mes(meta['ultimo_mes_folha'])}. "
               f"Gerado em {meta['gerado_em'][:10]}. Detalhes em docs/camara.md no repositório.")


def main() -> None:
    dados, credores = _carregar()
    tema.preparar_pagina(tema.atual())
    tema.cabecalho("Câmara Municipal de João Pessoa",
                   "Vereadores, projetos, pedidos, leis, sessões, servidores e contas da Câmara, com dados do SAPL "
                   "da Câmara, do TCE-PB e do Tesouro Nacional, de 2021 em diante.")
    # Link direto para um perfil (?vereador=ID) abre a seção de vereadores; ao trocar de seção, o perfil fecha
    if st.query_params.get("vereador") and "c_secao" not in st.session_state:
        st.session_state["c_secao"] = "Vereadores"
    secao = st.pills("Seção", SECOES, default="Vereadores", key="c_secao", label_visibility="collapsed") or "Vereadores"
    if secao != "Vereadores" and "vereador" in st.query_params:
        del st.query_params["vereador"]
    st.divider()
    if secao == "Vereadores":
        secao_vereadores(dados)
    elif secao == "Projetos de lei":
        st.caption("Projetos de lei ordinária e complementar apresentados de 2021 em diante, de vereadores, do "
                   "Executivo e da Mesa, com a situação de cada um.")
        _lista(dados["projetos"], _item_projeto, "pl", dados)
    elif secao == "Indicações":
        secao_materias(dados, ["Indicações"], "ind",
                       "Sugestões formais dos vereadores ao Executivo para que faça algo: uma obra, um serviço, "
                       "uma política.")
    elif secao == "Requerimentos":
        secao_materias(dados, ["Requerimentos de obras e serviços", "Outros requerimentos"], "req",
                       "Pedidos de obras e serviços a órgãos como Seinfra, Emlur e Cagepa (a maior parte), e "
                       "requerimentos de informação, de sessão especial, de urgência e outros.")
    elif secao == "Votos e moções":
        secao_materias(dados, ["Votos de aplauso, pesar e similares"], "vot",
                       "Votos de aplauso, pesar, congratulação e similares. O SAPL de João Pessoa não tem o tipo "
                       "\"moção\": essas manifestações são requerimentos (art. 171, X, do Regimento Interno).")
    elif secao == "Leis":
        secao_normas(dados, "Lei", "lei", "Leis municipais publicadas de 2021 em diante, com o texto oficial.")
    elif secao == "Resoluções":
        secao_normas(dados, "Resolução", "res",
                     "Resoluções da Câmara: normas sobre o funcionamento interno, como o regimento e a estrutura.")
    elif secao == "Decretos legislativos":
        secao_normas(dados, "Decreto Legislativo", "dl",
                     "Decretos legislativos: atos da Câmara como títulos de cidadania, honrarias e o julgamento "
                     "das contas do prefeito.")
    elif secao == "Pautas e atas":
        secao_sessoes(dados)
    elif secao == "Servidores":
        secao_servidores(dados)
    elif secao == "Despesas":
        secao_despesas(dados, credores)
    elif secao == "Diárias":
        secao_diarias(dados)
    elif secao == "Prestação de contas":
        secao_contas(dados)
    else:
        secao_sobre(dados)
