"""Página "Para onde vai o dinheiro de João Pessoa" (despesas declaradas ao TCE-PB)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.app import dados as dados_bairros
from src.app import dados_despesas as d
from src.app import tema
from src.config import ANOS_INCOMPLETOS_DESPESAS, EXCECOES_SICONFI
from src.process.despesas_regras import UNIDADES_GESTORAS

# Cores: src/app/tema.py (paleta validada, modo claro e escuro; categóricas validadas para daltonismo).

AVISO = (
    "Valores **declarados** pela Prefeitura e demais órgãos municipais ao TCE-PB (SAGRES). "
    "Podem mudar após análise e auditoria do Tribunal."
)


GLOSSARIO = """
**Etapas da despesa pública**
- **Empenho:** o órgão reserva o dinheiro para uma despesa (por exemplo, um contrato). É o compromisso de gasto.
- **Liquidação:** o órgão confirma que o produto foi entregue ou o serviço foi feito.
- **Pagamento:** o dinheiro sai do caixa. Um valor empenhado pode ser pago meses depois, ou cancelado.

**Outros termos**
- **Unidade gestora:** quem executa a despesa no sistema do TCE-PB. Prefeitura, fundos municipais (como o de
  Saúde), autarquias (como Emlur e Semob), fundações e a Câmara Municipal.
- **Órgão:** secretaria, procuradoria, Câmara ou outra estrutura do orçamento, com as unidades ligadas a ela
  (ex.: a Secretaria de Educação e Cultura inclui a Funjope). Na aba "Por órgão", de 2022 em diante.
- **Área (função):** para que serve o gasto, numa classificação usada por todo o país: Saúde, Educação,
  Urbanismo, Previdência etc. A **subfunção** detalha a área (ex.: Educação → Ensino Fundamental).
- **Fornecedor:** empresa ou entidade com CNPJ que recebe pelo que vende ou presta.
- **Correção pela inflação (IPCA):** converte valores de anos diferentes para o poder de compra de hoje,
  para que possam ser comparados.
- **Transferência entre órgãos do município:** dinheiro que sai de um órgão municipal para outro (ex.:
  contribuição da Prefeitura à previdência dos servidores). Somar as duas pontas contaria o mesmo dinheiro duas vezes.
"""

MODALIDADES_EXPLICADAS = """
- **Pregão:** disputa pelo menor preço, geralmente eletrônica, para bens e serviços comuns.
- **Concorrência:** modalidade usada para obras, serviços de engenharia e contratos de maior valor.
- **Dispensa:** contratação direta que a lei permite sem licitação (ex.: valores baixos, emergências).
- **Inexigibilidade:** contratação direta quando não há como haver competição (ex.: fornecedor exclusivo).
- **Adesão a ata de registro de preços:** uso de preços já obtidos em licitação de outro órgão.
- **Outras modalidades:** chamada pública, credenciamento, licitação internacional, tomada de preços,
  convite, concurso e leilão.
- **Sem licitação:** despesas que não passam por licitação, como tributos, repasses, tarifas de serviços
  públicos (água, energia) e parcelas de contratos de anos anteriores.
"""

ORGAOS = {
    "Todos": "Todos os órgãos",
    "Executivo": "Prefeitura, fundos e autarquias (Executivo)",
    "Legislativo": "Câmara Municipal (Legislativo)",
}


def _md(texto: str) -> str:
    """Escapa '$' para o Markdown do Streamlit não interpretar 'R$ ... R$' como fórmula."""
    return texto.replace("$", "\\$")


def _pergunta(titulo: str, explicacao: str) -> None:
    """Abertura de cada aba: a pergunta que ela responde e como ler."""
    st.markdown(f"#### {titulo}")
    st.caption(explicacao)


@st.cache_data
def _carregar():
    return d.carregar(), dados_bairros.carregar_geojson()


def _layout(fig: go.Figure, altura: int = 360, eixo_y: str = "") -> go.Figure:
    T = tema.atual()
    fig.update_layout(
        height=altura,
        margin=dict(l=0, r=10, t=10, b=0),
        separators=",.",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        bargap=0.3,
        yaxis=dict(title=eixo_y, gridcolor=T["grade"], zeroline=False, tickfont=dict(color=T["tinta_2"]), tickformat=",~r"),
        xaxis=dict(showgrid=False, tickfont=dict(color=T["tinta_2"])),
        hoverlabel=dict(bgcolor=T["superficie"], bordercolor=T["eixo"], font=dict(color=T["tinta"])),
    )
    return fig


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


def aba_visao_geral(df, dados, col, corrigido, meta, metrica):
    T = tema.atual()
    _pergunta(
        "Quanto os órgãos municipais gastam por ano?",
        "Escolha um ano para ver o total, o valor por habitante e a distribuição ao longo dos meses.",
    )
    totais = d.total_por_ano(df, col)
    anos = list(totais.index)
    ano = st.columns([1, 4])[0].selectbox("Ano", anos[::-1], index=1 if len(anos) > 1 else 0, key="dv_ano")
    if nota := _nota_status(ano, meta):
        st.warning(nota)

    per_cap = d.por_habitante(totais, dados["populacao"])
    var = d.variacao_pct(totais, ano, meta)
    verbo = "empenharam" if metrica == "empenhado" else "pagaram"
    frase = f"Em {ano}, os órgãos municipais {verbo} **{d.fmt_reais(totais[ano])}**"
    if pd.notna(per_cap[ano]):
        frase += f", o equivalente a **{d.fmt_reais_inteiro(per_cap[ano]).replace(',00', '')} por habitante**"
    if var is not None:
        frase += f" ({d.fmt_pct(abs(var), 1)} {'a mais' if var >= 0 else 'a menos'} que em {ano - 1})"
    st.info(_md(frase + f". Valores {_rotulo_valor(corrigido, meta)}."), icon="💡")
    k1, k2, k3 = st.columns(3)
    k1.metric(f"Total {metrica} em {ano}", d.fmt_reais(totais[ano]))
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
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.subheader("Total por ano")
        st.caption(_md(f"R$ bilhões, valores {_rotulo_valor(corrigido, meta)}."))
        cores = [T["azul"] if d.status_ano(a, meta) is None else T["azul_claro"] for a in anos]
        hover = [
            f"<b>{a}</b><br>{d.fmt_reais(v)}" + (f"<br>{d.status_ano(a, meta)}" if d.status_ano(a, meta) else "")
            for a, v in totais.items()
        ]
        fig = go.Figure(go.Bar(
            x=anos, y=totais.values / 1e9, marker=dict(color=cores, cornerradius=4),
            hovertext=hover, hovertemplate="%{hovertext}<extra></extra>",
        ))
        st.plotly_chart(_layout(fig, eixo_y="R$ bilhões"), config={"displayModeBar": False})
        st.caption(tema.texto("Barras claras: 2016 (dados incompletos no TCE-PB) e ano em andamento.", T))
    with c2:
        st.subheader("Por habitante")
        st.caption("Total dividido pela população do ano, para comparar anos com populações diferentes.")
        completos = pd.Series([a for a in anos if d.status_ano(a, meta) is None])
        linha = per_cap.reindex(range(min(anos), max(anos) + 1)).where(
            lambda s: s.index.isin(completos)
        )
        outros = per_cap[[a for a in anos if d.status_ano(a, meta)]].dropna()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(linha.index), y=linha.values, mode="lines+markers", connectgaps=False,
            line=dict(color=T["azul"], width=2), marker=dict(size=8, color=T["azul"]),
            hovertext=[f"<b>{a}</b><br>{d.fmt_reais_inteiro(v)}" for a, v in linha.items()],
            hovertemplate="%{hovertext}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=list(outros.index), y=outros.values, mode="markers",
            marker=dict(size=9, color=T["superficie"], line=dict(color=T["azul_claro"], width=2)),
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
        x=meses, y=mensal.values / 1e6, marker=dict(color=T["azul"], cornerradius=4),
        hovertext=[f"<b>{m}/{ano}</b><br>{d.fmt_reais(v)}" for m, v in zip(meses, mensal.values)],
        hovertemplate="%{hovertext}<extra></extra>",
    ))
    st.plotly_chart(_layout(fig, 300, "R$ milhões"), config={"displayModeBar": False})
    pico, anos_pico = d.meses_de_pico(df, col, meta)
    nomes_mes = dict(enumerate(["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                                "setembro", "outubro", "novembro", "dezembro"], 1))
    mais = ", ".join(f"{nomes_mes[int(m)]} em {n}" for m, n in pico.head(2).items())
    st.caption(
        f"Pela data do empenho. Nos {len(anos_pico)} anos completos dos dados ({anos_pico[0]}–{anos_pico[-1]}, sem os "
        f"incompletos), o mês de maior valor foi {mais}."
    )


def aba_por_area(df, col, corrigido, meta):
    T = tema.atual()
    _pergunta(
        "Em que áreas o dinheiro é gasto?",
        "Cada retângulo tem tamanho proporcional ao valor. Clique numa área para ver o detalhe "
        "(subfunções) e clique no topo do quadro para voltar.",
    )
    anos = sorted(df["ano"].unique())
    ano = st.columns([1, 4])[0].selectbox("Ano", anos[::-1], index=1 if len(anos) > 1 else 0, key="pa_ano")
    if nota := _nota_status(ano, meta):
        st.warning(nota)
    sel = df[df["ano"] == ano]
    st.info(_md(f"Em {ano}, {d.resumo_areas(df, ano, col)} Valores {_rotulo_valor(corrigido, meta)}."), icon="💡")
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
        # mesma rampa nos dois temas, só nos tons em que o texto branco é legível
        marker=dict(colors=values, colorscale=[[i / 3, c] for i, c in enumerate(tema.AZUL_SEQ[3:])],
                    line=dict(color=T["superficie"], width=2)),
        hovertext=[f"{d.fmt_reais(v)} ({100 * v / total:.1f}% do total)".replace(".", ",") for v in values],
        hovertemplate="<b>%{label}</b><br>%{hovertext}<extra></extra>",
        texttemplate="<b>%{label}</b><br>%{percentRoot:.1%}", textfont=dict(color="#ffffff"),
        maxdepth=2,
    ))
    fig.update_layout(height=520, margin=dict(l=0, r=0, t=0, b=0), separators=",.")
    st.plotly_chart(fig, config={"displayModeBar": False})

    totais_ant = df[df["ano"] == ano - 1].groupby("funcao")[col].sum()
    tot_f = tot_f.sort_values(ascending=False)
    tabela = pd.DataFrame({"Valor": tot_f, "% do total": 100 * tot_f / total})
    variacao = f"Variação frente a {ano - 1}"
    if d.anos_comparaveis(ano, meta) and d.anos_comparaveis(ano - 1, meta) and len(totais_ant):
        tabela[variacao] = 100 * (tot_f / totais_ant.reindex(tot_f.index) - 1)
    tabela = tabela.rename_axis("Área (função)")
    st.dataframe(dados_bairros.tabela_br(tabela, reais=["Valor"], pct={"% do total": 1}, pct_sinal={variacao: 1}),
                 width="stretch")

    st.subheader("Uma área ao longo dos anos")
    st.caption(tema.texto("Escolha uma área para ver como o valor mudou desde 2009. Barras claras: 2016 (incompleto) e "
                          "ano em andamento.", T))
    area = st.columns([2, 3])[0].selectbox("Área", list(tabela.index), key="pa_area")
    serie = df[df["funcao"] == area].groupby("ano")[col].sum()
    cores = [T["azul"] if d.status_ano(a, meta) is None else T["azul_claro"] for a in serie.index]
    fig = go.Figure(go.Bar(
        x=list(serie.index), y=serie.values / 1e6, marker=dict(color=cores, cornerradius=4),
        hovertext=[f"<b>{a}</b><br>{d.fmt_reais(v)}" for a, v in serie.items()],
        hovertemplate="%{hovertext}<extra></extra>",
    ))
    st.plotly_chart(_layout(fig, 300, "R$ milhões"), config={"displayModeBar": False})


def aba_por_orgao(dados, col, corrigido, meta, poder, sem_intra):
    T = tema.atual()
    info = meta["orgaos"]
    _pergunta(
        "Quais órgãos gastam mais?",
        f"De {info['ano_inicial']} em diante, por órgão (secretaria, procuradoria, Câmara…) e pelas unidades de cada um "
        "(fundos, autarquias e a própria secretaria). Clique num órgão para abrir as unidades e no topo do quadro para "
        "voltar.",
    )
    df = d.filtrar(dados["orgaos"], poder, sem_intra)
    anos = sorted(df["ano"].unique())
    ano = st.columns([1, 4])[0].selectbox("Ano", anos[::-1], index=1 if len(anos) > 1 else 0, key="po_ano")
    if nota := _nota_status(ano, meta):
        st.warning(nota)
    res = d.resumo_orgaos(df, ano, col)
    if res.empty:
        st.write("Nenhum valor com essas opções.")
        return
    top = res.head(3)
    frase = d.lista_pt([f"{d.rotulo_orgao(r.orgao, r.sigla)} ({d.fmt_pct(r.pct)})" for r in top.itertuples()])
    st.info(_md(f"Em {ano}, {frase} somaram {d.fmt_pct(top.pct.sum())} do valor. Valores {_rotulo_valor(corrigido, meta)}."),
            icon="💡")

    # treemap órgão → unidade orçamentária
    a = df[df["ano"] == ano]
    u = a.groupby(["cod_orgao", "cod_uo", "unidade_orcamentaria"], as_index=False)[col].sum()
    u = u[u[col] > 0]
    nomes = res.set_index("cod_orgao")
    total = res["valor"].sum()
    ids = list(nomes.index) + [f"{o}/{c}" for o, c in zip(u.cod_orgao, u.cod_uo)]
    curto = [r.sigla if isinstance(r.sigla, str) else r.orgao for r in nomes.itertuples()]
    labels = curto + [d.nome_unidade(n) for n in u.unidade_orcamentaria]
    parents = [""] * len(nomes) + list(u.cod_orgao)
    values = list(nomes["valor"]) + list(u[col])
    completos = [d.rotulo_orgao(r.orgao, r.sigla) for r in nomes.itertuples()] + [
        f"{d.nome_unidade(n)}<br>{d.rotulo_orgao(nomes.loc[o, 'orgao'], nomes.loc[o, 'sigla'])}"
        for o, n in zip(u.cod_orgao, u.unidade_orcamentaria)]
    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents, values=values, branchvalues="total",
        marker=dict(colors=values, colorscale=[[i / 3, c] for i, c in enumerate(tema.AZUL_SEQ[3:])],
                    line=dict(color=T["superficie"], width=2)),
        customdata=completos,
        hovertext=[f"{d.fmt_reais(v)} ({100 * v / total:.1f}% do total)".replace(".", ",") for v in values],
        hovertemplate="<b>%{customdata}</b><br>%{hovertext}<extra></extra>",
        texttemplate="<b>%{label}</b><br>%{percentRoot:.1%}", textfont=dict(color="#ffffff"),
        maxdepth=2,
    ))
    fig.update_layout(height=520, margin=dict(l=0, r=0, t=0, b=0), separators=",.")
    st.plotly_chart(fig, config={"displayModeBar": False})

    ant = d.resumo_orgaos(df, ano - 1, col).set_index("cod_orgao")["valor"] if ano - 1 in anos else pd.Series(dtype=float)
    tabela = pd.DataFrame({
        "Órgão": res["orgao"], "Sigla": res["sigla"].fillna(""), "Valor": res["valor"], "% do total": res["pct"],
        "Área principal": [f"{a} ({d.fmt_pct(p)})" for a, p in zip(res.area_principal, res.pct_area_principal)],
    })
    variacao = f"Variação frente a {ano - 1}"
    if d.anos_comparaveis(ano, meta) and d.anos_comparaveis(ano - 1, meta) and len(ant):
        tabela[variacao] = 100 * (res["valor"].values / res["cod_orgao"].map(ant).values - 1)
    st.dataframe(dados_bairros.tabela_br(tabela, reais=["Valor"], pct={"% do total": 1}, pct_sinal={variacao: 1}),
                 hide_index=True, width="stretch")
    st.caption("Área principal: a função de governo em que o órgão mais empenhou no ano, com a parte do valor dele. "
               "O órgão inclui as unidades ligadas a ele no orçamento: a Secretaria da Administração inclui o IPM "
               "(previdência), e a de Gestão Governamental inclui a Emlur e a Semob, por isso as áreas delas aparecem ali.")

    st.subheader("Quem gasta em cada área")
    st.caption("Escolha uma área (função de governo) para ver quanto dela saiu de cada órgão no ano.")
    areas = a.groupby("funcao")[col].sum().sort_values(ascending=False)
    areas = list(areas[areas > 0].index)
    # abre na área dividida entre mais órgãos (Saúde e Educação saem quase só de uma secretaria)
    n_orgaos = a[a[col] > 0].groupby("funcao")["cod_orgao"].nunique()
    inicial = max(areas, key=lambda f: (n_orgaos.get(f, 0), -areas.index(f)))
    area = st.columns([2, 3])[0].selectbox("Área", areas, index=areas.index(inicial), key="po_area")
    oa = d.orgaos_da_area(df, ano, col, area)
    rotulos = [d.rotulo_orgao(n, s) for n, s in zip(oa.orgao, oa.sigla)]
    if len(oa) > 12:  # os 12 maiores; o resto somado numa barra só
        resto = oa.iloc[12:]
        rotulos = rotulos[:12] + [f"Outros {len(resto)} órgãos"]
        oa = pd.concat([oa.iloc[:12], pd.DataFrame([{"valor": resto["valor"].sum(), "pct": resto["pct"].sum()}])])
    fig = go.Figure(go.Bar(
        x=oa["valor"] / 1e6, y=rotulos, orientation="h",
        marker=dict(color=[T["azul_claro"] if r.startswith("Outros ") else T["azul"] for r in rotulos], cornerradius=4),
        text=[f"{d.fmt_reais(v)} · {d.fmt_pct(p)}" for v, p in zip(oa["valor"], oa["pct"])], textposition="outside",
        textfont=dict(color=T["tinta"]), cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>%{text}<extra></extra>",
    ))
    fig = _layout(fig, 40 * len(oa) + 40)
    fig.update_layout(yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)", tickfont=dict(color=T["tinta"])),
                      xaxis=dict(visible=False), margin=dict(r=140))
    st.plotly_chart(fig, config={"displayModeBar": False})

    st.subheader("Um órgão ao longo dos anos")
    st.caption(tema.texto(f"De {info['ano_inicial']} em diante. Barras claras: ano em andamento.", T))
    opcoes = dict(zip(res.cod_orgao, [d.rotulo_orgao(r.orgao, r.sigla) for r in res.itertuples()]))
    cod = st.columns([2, 3])[0].selectbox("Órgão", list(opcoes), format_func=opcoes.get, key="po_orgao")
    serie = df[df["cod_orgao"] == cod].groupby("ano")[col].sum()
    cores = [T["azul"] if d.status_ano(x, meta) is None else T["azul_claro"] for x in serie.index]
    fig = go.Figure(go.Bar(
        x=list(serie.index), y=serie.values / 1e6, marker=dict(color=cores, cornerradius=4),
        hovertext=[f"<b>{x}</b><br>{d.fmt_reais(v)}" for x, v in serie.items()],
        hovertemplate="%{hovertext}<extra></extra>",
    ))
    fig = _layout(fig, 280, "R$ milhões")
    fig.update_xaxes(dtick=1)
    st.plotly_chart(fig, config={"displayModeBar": False})

    with st.expander("De onde vêm os nomes dos órgãos"):
        st.markdown(
            "O arquivo do TCE-PB traz só o código da unidade orçamentária e uma sigla (\"SEDEC - AÇÕES DE GOVERNO\"). "
            "O órgão são os dois primeiros dígitos do código (10101 → órgão 10). Os nomes por extenso vêm da "
            "**LOA 2024** (Lei 15.066/2024, quadro por órgão) e, para os órgãos criados em 2025, das **leis de "
            "criação** (Leis 15.467, 15.468 e 15.469/2025), todas no SAPL da Câmara Municipal. A grafia foi ajustada "
            "só em maiúsculas, acentos e abreviações; a da lei aparece abaixo. Antes de 2022 a estrutura era outra e o "
            "arquivo só traz nomes de diretorias, por isso a divisão por órgão começa em 2022."
        )
        st.dataframe(pd.DataFrame([
            {"Código": c, "Sigla no TCE-PB": v["sigla"] or "", "Nome": v["nome"], "Como está na fonte": v["nome_na_fonte"],
             "Fonte": v["fonte_do_nome"]}
            for c, v in info["orgaos"].items()]), hide_index=True, width="stretch")
        st.caption("Nomes de unidades que terminam em \"…\" foram cortados pelo TCE-PB em 50 caracteres.")


def aba_fornecedores(dados, metrica, corrigido, meta, poder):
    T = tema.atual()
    cred = dados["credores"]
    if poder != "Todos":
        cred = cred[cred["cod_ug"].map(lambda c: UNIDADES_GESTORAS[c][1]) == poder]
    col = d.coluna(metrica, corrigido)
    _pergunta(
        "Quais empresas mais recebem?",
        "Só empresas e entidades com CNPJ. Pessoas físicas não aparecem em rankings nem na busca. "
        "Folha de pagamento, encargos e aposentadorias ficam de fora, porque não são compras de "
        "fornecedores. Estar na lista não indica nenhuma irregularidade: mostra apenas quem recebeu.",
    )
    anos = sorted(cred["ano"].unique())
    c1, c2, c3 = st.columns([3, 1, 2])
    periodo = c1.select_slider("Período", options=anos, value=(max(anos[0], anos[-1] - 4), anos[-1]), key="fo_periodo")
    n = c2.selectbox("Mostrar", [10, 15, 25], index=1, key="fo_n", format_func=lambda x: f"{x} empresas")
    publicos = c3.toggle("Incluir entidades públicas", value=False, key="fo_pub",
                         help="Ministérios, tribunais (precatórios), INSS e outros órgãos que recebem repasses ou tributos.")
    if any(d.status_ano(a, meta) for a in range(periodo[0], periodo[1] + 1)):
        st.info("O período inclui 2016 (incompleto no TCE-PB) ou o ano em andamento.")
    rk = d.ranking_fornecedores(cred, periodo, col, n, publicos)
    fatia = d.fatia_do_ranking(cred, rk, periodo, col, publicos)
    st.info(
        f"As {len(rk)} empresas abaixo ficaram com **{d.fmt_pct(fatia)}** do valor {metrica} a fornecedores "
        f"com CNPJ no período. Valores {_rotulo_valor(corrigido, meta)}.",
        icon="💡",
    )
    st.subheader(f"Maiores fornecedores, {periodo[0]}–{periodo[1]}" if periodo[0] != periodo[1] else f"Maiores fornecedores em {periodo[0]}")
    fig = go.Figure(go.Bar(
        x=rk[col] / 1e6, y=rk["nome_credor"].str.slice(0, 45), orientation="h",
        marker=dict(color=T["azul"], cornerradius=4),
        text=rk[col].map(d.fmt_reais), textposition="outside", cliponaxis=False,
        hovertext=[f"<b>{nm}</b><br>CNPJ {c}<br>{d.fmt_reais_inteiro(v)}" for nm, c, v in zip(rk.nome_credor, rk.cnpj_formatado, rk[col])],
        hovertemplate="%{hovertext}<extra></extra>",
    ))
    fig = _layout(fig, 34 * len(rk) + 40)
    fig.update_layout(yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)"), xaxis=dict(visible=False), margin=dict(r=90))
    st.plotly_chart(fig, config={"displayModeBar": False})

    st.subheader("Buscar empresa por nome ou CNPJ")
    st.caption("Veja quanto uma empresa recebeu em todos os anos, de quais órgãos, e em quais arquivos do TCE-PB isso está.")
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
                x=list(pa.index), y=pa.values / 1e6, marker=dict(color=T["azul"], cornerradius=4),
                hovertext=[f"<b>{a}</b><br>{d.fmt_reais_inteiro(v)}" for a, v in pa.items()],
                hovertemplate="%{hovertext}<extra></extra>",
            ))
            st.plotly_chart(_layout(fig, 260, "R$ milhões"), config={"displayModeBar": False})
        with g2:
            st.markdown("**Por órgão pagador**")
            po = r["por_orgao"]
            po = po[po > 0]
            st.dataframe(
                dados_bairros.tabela_br(
                    pd.DataFrame({"Órgão": [UNIDADES_GESTORAS[c][0] for c in po.index], "Valor": po.values}),
                    reais=["Valor"]),
                hide_index=True, width="stretch",
            )
        st.caption("Arquivos de origem (TCE-PB): " + ", ".join(r["arquivos"]))


def aba_licitacao(df, col, corrigido, meta):
    T = tema.atual()
    _pergunta(
        "Como as compras e contratações são feitas?",
        "Cada barra é um ano, dividida pela modalidade de licitação dos empenhos (soma 100%). "
        "Passe o mouse para ver os percentuais.",
    )
    with st.expander("O que significa cada modalidade?"):
        st.markdown(MODALIDADES_EXPLICADAS)
    sem_pessoal = st.toggle(
        "Excluir folha de pagamento e encargos", value=True, key="li_pessoal",
        help="Salários, encargos e benefícios não passam por licitação e dominariam a categoria 'Sem licitação'.",
    )
    part = d.participacao_licitacao(df, col, sem_pessoal)
    ref = max(a for a in part.index if d.status_ano(a, meta) is None)
    st.info(f"Em {ref}, as maiores fatias foram: {d.resumo_licitacao(part, ref)}.", icon="💡")
    fig = go.Figure()
    for i, m in enumerate(d.ORDEM_LICITACAO):
        fig.add_trace(go.Bar(
            x=list(part.index), y=part[m], name=m, marker=dict(color=T["cat"][i], line=dict(color=T["superficie"], width=1)),
            hovertemplate=f"<b>{m}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
        ))
    fig = _layout(fig, 420, "% do valor do ano")
    fig.update_layout(barmode="stack", showlegend=True, legend=dict(orientation="h", y=-0.15, traceorder="normal"))
    st.plotly_chart(fig, config={"displayModeBar": False})
    st.caption("2016 está incompleto no TCE-PB; o ano em andamento é parcial. As participações são proporções do próprio ano.")
    with st.expander("Ver em tabela"):
        st.dataframe(dados_bairros.tabela_br(part.rename_axis("Ano"), pct={c: 1 for c in part.columns}),
                     width="stretch")


def aba_mapa(dados, geo, corrigido, meta):
    T = tema.atual()
    _pergunta(
        "Onde o dinheiro aparece nos bairros?",
        tema.texto("Bairros mais escuros têm mais valor em empenhos que os citam. Bairros sem cor não são citados no "
                   "período.", T),
    )
    aj = dados_bairros.ajuste_mapa(dados_bairros.eh_celular(st.context.headers.get("User-Agent")), 620, 11.3)
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
              help="Parte do valor total empenhado no período cujo texto cita exatamente um bairro. "
                   "É o que aparece no mapa.")
    k2.metric("Associado a um único bairro (no mapa)", d.fmt_reais(v[col].sum()))
    k3.metric("Empenhos que citam 2 ou mais bairros (não entram no mapa)", d.fmt_reais(cobp["varios_bairros"].sum()),
              help="Empenhos cujo texto cita mais de um bairro de João Pessoa, como \"ruas em Mangabeira e "
                   "no Valentina\". O texto não diz quanto foi para cada bairro, e dividir o valor seria "
                   "inventar uma distribuição; por isso ficam fora do mapa.")

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
        colorscale=[[0, T["vazio"]], [1, T["vazio"]]], showscale=False,
        marker_line_color=T["eixo"], marker_line_width=1,
        hovertext=sem.nm_bairro + "<br>nenhum empenho cita o bairro", hovertemplate="%{hovertext}<extra></extra>",
    ))
    zmax = float((com[col] / 1e6).max()) if len(com) else 1.0
    fig.add_trace(go.Choroplethmap(
        geojson=geo, featureidkey="properties.cd_bairro", locations=com.cd_bairro, z=com[col] / 1e6,
        zmin=0, zmax=zmax, colorscale=tema.escala(T), marker_opacity=0.85,
        marker_line_color=T["superficie"], marker_line_width=1,
        colorbar=tema.barra_de_cor(aj, T, 0, zmax, lambda x: dados_bairros.fmt_dec(x, 0 if zmax >= 10 else 1), "R$ mi"),
        hovertext=[f"<b>{n}</b><br>{d.fmt_reais(x)}" for n, x in zip(com.nm_bairro, com[col])],
        hovertemplate="%{hovertext}<extra></extra>",
    ))
    tema.layout_mapa(fig, T, aj, dict(lat=-7.147, lon=-34.875))
    st.plotly_chart(fig, config={"scrollZoom": True, "displaylogo": False,
                                 "modeBarButtonsToRemove": ["select2d", "lasso2d"]})
    st.caption(
        "Regras: nomes que também são palavras comuns ou nomes de pessoas (Centro, Torre, José Américo...) "
        "só contam depois da palavra \"bairro\"; nomes precedidos de rua, avenida, praça ou escola não contam; "
        "empenhos que citam mais de um bairro ficam fora do mapa. Detalhes no README."
    )
    t = v.sort_values(col, ascending=False)
    st.dataframe(
        dados_bairros.tabela_br(pd.DataFrame({"Bairro": t["nm_bairro"].values, "Valor citado": t[col].values}),
                                reais=["Valor citado"]),
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
            "TCE-PB": v["tce_empenhado"].values,
            "SICONFI": v["siconfi_empenhado"].values,
            "Diferença": v["diferenca_pct"].values,
            "Situação": v["Situação"].values,
        }).pipe(dados_bairros.tabela_br, reais=["TCE-PB", "SICONFI"], pct_sinal={"Diferença": 2}),
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
    tema.preparar_pagina(tema.atual())
    ult = pd.Timestamp(meta["ultima_data_de_empenho"]).strftime("%d/%m/%Y")
    tema.cabecalho("Para onde vai o dinheiro de João Pessoa",
                   f"Despesas dos órgãos municipais, de 2009 a {ult}. {AVISO}")
    with st.expander("Entenda os termos usados nesta página"):
        st.markdown(GLOSSARIO)

    filtros = st.container(border=True)
    filtros.markdown('<p class="rx-kicker">Opções (valem para todas as abas)</p>', unsafe_allow_html=True)
    c1, c2, c3, c4 = filtros.columns([1.3, 1.6, 1.8, 2])
    metrica = c1.radio(
        "Valor mostrado", ["empenhado", "pago"],
        format_func={"empenhado": "Empenhado", "pago": "Pago"}.get, horizontal=True, key="g_metrica",
        help="Empenhado: dinheiro reservado para a despesa (compromisso). Pago: o que já saiu do caixa.",
    )
    corrigido = c2.radio(
        "Inflação", [True, False], format_func=lambda x: "Corrigido pelo IPCA" if x else "Sem correção",
        horizontal=True, key="g_corr",
        help="Corrigido: todos os anos no poder de compra de hoje, bom para comparar anos. "
             "Sem correção: valores da época.",
    )
    poder = c3.selectbox("Poder", list(ORGAOS), format_func=ORGAOS.get, key="g_poder")
    sem_intra = c4.toggle(
        "Sem dupla contagem de repasses internos", value=True, key="g_intra",
        help="Repasses entre órgãos do próprio município, como a contribuição da Prefeitura à previdência "
             "dos servidores (IPM), aparecem como gasto da Prefeitura e depois como gasto do IPM. Com a "
             "opção ligada, o mesmo dinheiro não é contado duas vezes.",
    )
    col = d.coluna(metrica, corrigido)
    df = d.filtrar(dados["cubo"], poder, sem_intra)

    abas = st.tabs(["Visão geral", "Por área", "Por órgão", "Fornecedores", "Licitação", "Mapa (experimental)",
                    "Sobre os dados"])
    with abas[0]:
        aba_visao_geral(df, dados, col, corrigido, meta, metrica)
    with abas[1]:
        aba_por_area(df, col, corrigido, meta)
    with abas[2]:
        aba_por_orgao(dados, col, corrigido, meta, poder, sem_intra)
    with abas[3]:
        aba_fornecedores(dados, metrica, corrigido, meta, poder)
    with abas[4]:
        aba_licitacao(df, col, corrigido, meta)
    with abas[5]:
        aba_mapa(dados, geo, corrigido, meta)
    with abas[6]:
        aba_sobre(dados, meta)
