"""Tema claro/escuro do site: cores dos gráficos e do mapa, estilo das páginas e cabeçalho.

O Streamlit escolhe o tema (o do sistema, ou o escolhido no botão de tema do topo) e informa o tipo em
`st.context.theme.type`. As cores vêm da paleta validada (ver README, "Cores"): o modo escuro usa os
mesmos matizes, em tons escolhidos para o fundo escuro, e não uma inversão automática.
"""

from __future__ import annotations

import math
import re

import streamlit as st
import streamlit.components.v1 as components

AZUL_SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

CLARO = {
    "tipo": "light",
    "superficie": "#fcfcfb",
    "tinta": "#0b0b0b",
    "tinta_2": "#52514e",
    "mudo": "#898781",
    "grade": "#e1e0d9",
    "eixo": "#c3c2b7",
    "neutro": "#f0efec",  # ponto médio da escala divergente
    "vazio": "rgba(252,252,251,0.6)",  # bairro sem dado
    "fundo_legenda": "rgba(252,252,251,0.88)",
    "mapa": "carto-positron",
    "azul": "#2a78d6",
    "azul_claro": "#9ec5f4",  # anos incompletos ou parciais
    "vermelho": "#e34948",
    # sequencial: o tom perto de zero se confunde com o fundo (claro)
    "seq": AZUL_SEQ,
    "cat": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"],
    "escola": "#eda100",
    "ubs": "#6250d6",
    "outras_saude": "#e34948",
    "verde": "#1baf7a",
    "mata": "#008300",
}

ESCURO = {
    "tipo": "dark",
    "superficie": "#1a1a19",
    "tinta": "#f0efec",
    "tinta_2": "#c3c2b7",
    "mudo": "#898781",
    "grade": "#2c2c2a",
    "eixo": "#383835",
    "neutro": "#383835",
    "vazio": "rgba(26,26,25,0.55)",
    "fundo_legenda": "rgba(26,26,25,0.88)",
    "mapa": "carto-darkmatter",
    "azul": "#3987e5",
    "azul_claro": "#184f95",
    "vermelho": "#e66767",
    # no fundo escuro, o tom perto de zero é o mais escuro: a rampa vai do escuro ao claro
    "seq": AZUL_SEQ[::-1],
    "cat": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9"],
    # amarelo um pouco mais claro que o da paleta escura: com o vermelho das outras unidades de
    # saúde, o tom #c98500 ficava parecido demais (validador: ΔE 13,0 < 15); #e09a00 dá ΔE 15,7
    "escola": "#e09a00",
    "ubs": "#9085e9",
    "outras_saude": "#e66767",
    "verde": "#199e70",
    "mata": "#008300",
}


def atual() -> dict:
    """Cores do tema que o navegador está mostrando."""
    try:
        tipo = st.context.theme.type
    except Exception:  # fora do Streamlit (testes)
        tipo = None
    return ESCURO if tipo == "dark" else CLARO


def escala(t: dict) -> list:
    """Escala sequencial do Plotly a partir da rampa do tema."""
    seq = t["seq"]
    return [[i / (len(seq) - 1), c] for i, c in enumerate(seq)]


def texto(s: str, t: dict) -> str:
    """Ajusta legendas que falam de tom ("mais escuro = mais longe") ao tema escuro, onde a rampa inverte."""
    if t["tipo"] != "dark":
        return s
    troca = {"escur": "clar", "Escur": "Clar", "clar": "escur", "Clar": "Escur"}
    return re.sub(r"[Ee]scur|[Cc]lar", lambda m: troca[m.group(0)], s)


# --- escala de cor do mapa com números no padrão brasileiro


def _passo(amplitude: float, n: int) -> float:
    bruto = amplitude / max(n, 1)
    base = 10 ** math.floor(math.log10(bruto)) if bruto > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        if bruto <= m * base:
            return m * base
    return 10 * base


def marcas(zmin: float, zmax: float, n: int = 5) -> list[float]:
    """Valores "redondos" para a escala de cor (1, 2, 2,5 ou 5 × 10^k), dentro de [zmin, zmax]."""
    if zmax <= zmin:
        return [zmin]
    p = _passo(zmax - zmin, n)
    v = math.ceil(zmin / p) * p
    out = []
    while v <= zmax + 1e-9:
        out.append(round(v, 10))
        v += p
    return out


def barra_de_cor(aj: dict, t: dict, zmin: float, zmax: float, fmt, titulo: str = "",
                 rotulos: dict | None = None, valores: list | None = None) -> dict:
    """Colorbar com marcas formatadas em pt-BR (o Plotly mostrava 70,000 na escala do mapa).

    `valores` fixa as marcas (senão, valores redondos entre zmin e zmax); `rotulos` substitui o texto de
    marcas específicas (ex.: "≥ +60" quando a cor satura).
    """
    vals = valores if valores is not None else marcas(zmin, zmax)
    texto_marcas = [(rotulos or {}).get(v, fmt(v)) for v in vals]
    return dict(**aj["barra"], outlinewidth=0, tickfont=dict(color=t["tinta_2"]), bgcolor=t["fundo_legenda"],
                xpad=10, ypad=10, tickmode="array", tickvals=vals, ticktext=texto_marcas,
                title=dict(text=titulo, font=dict(color=t["tinta_2"])))


def layout_mapa(fig, t: dict, aj: dict, centro: dict, legenda: bool = False, celular: bool = False):
    """Mapa de fundo do tema, enquadramento e caixa de informação ao passar o mouse."""
    fig.update_layout(
        map=dict(style=t["mapa"], center=centro, zoom=aj["zoom"]),
        margin=dict(l=0, r=0, t=0, b=0), height=aj["altura"], separators=",.",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor=t["superficie"], bordercolor=t["eixo"], font=dict(color=t["tinta"], size=13)),
        uirevision="mapa",  # mantém zoom e posição quando a página atualiza (ex.: ao trocar o indicador)
    )
    if legenda:
        fig.update_layout(legend=dict(
            x=0.015, y=0.97, xanchor="left", yanchor="top", bgcolor=t["fundo_legenda"],
            font=dict(color=t["tinta"], size=10 if celular else 12), borderwidth=0,
            itemclick="toggle", itemdoubleclick="toggleothers",
        ))
    return fig


def layout_grafico(fig, t: dict):
    """Cores de texto, grade e caixa de informação dos gráficos comuns."""
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color=t["tinta_2"]),
        hoverlabel=dict(bgcolor=t["superficie"], bordercolor=t["eixo"], font=dict(color=t["tinta"])),
    )
    fig.update_xaxes(gridcolor=t["grade"], linecolor=t["eixo"], zerolinecolor=t["eixo"])
    fig.update_yaxes(gridcolor=t["grade"], linecolor=t["eixo"], zerolinecolor=t["eixo"])
    return fig


# --- página

_CSS = """
<style>
.block-container {padding-top: 2.2rem; padding-bottom: 3rem;}
h1 {font-size: 2.1rem !important; padding-bottom: 0.1rem !important;}
h2 {font-size: 1.45rem !important;}
h3 {font-size: 1.15rem !important;}
[data-testid="stMetricValue"] {font-size: 1.55rem;}
[data-testid="stMetricLabel"] p {font-size: 0.85rem;}
/* o observador do tema é um iframe sem altura: não deixa espaço na página */
.stElementContainer:has(iframe[title="st.iframe"][height="0"]) {display: none;}
@media (max-width: 640px) {
  .block-container {padding-top: 1.2rem;}
  h1 {font-size: 1.6rem !important;}
}
/* topo: só o botão de tema. Saem o menu ⋮ e os botões do Streamlit Cloud (Share, estrela, editar,
   que só o dono do app vê) e o "Deploy" local. O menu continua na página, escondido: o botão de
   tema usa a opção Claro/Escuro dele. */
[data-testid="stToolbarActions"], [data-testid="stAppDeployButton"] {display: none !important;}
/* o menu fica com 1 px e invisível, mas na página: escondido com display:none ele não abre */
[data-testid="stMainMenu"] {position: absolute !important; width: 1px !important; height: 1px !important;
                            overflow: hidden !important; opacity: 0 !important; right: 1rem; pointer-events: none;}
#rx-tema {background: transparent; border: 0; border-radius: 0.5rem; padding: 0.35rem; margin: 0 0.25rem;
          color: inherit; cursor: pointer; line-height: 0; display: inline-flex; align-items: center;}
#rx-tema:hover {background: rgba(128, 128, 128, 0.15);}
#rx-tema:focus-visible {outline: 2px solid currentColor; outline-offset: 2px;}
.rx-kicker {font-size: 0.8rem; letter-spacing: 0.06em; text-transform: uppercase; opacity: 0.7; margin: 0;}
</style>
"""

# Quando o tema muda pelo menu, a página escurece na hora, mas o Python só vê o novo tema na próxima
# atualização (limitação do Streamlit, issue #11920). Este observador compara a cor de fundo da página
# com o tema usado nos gráficos e, se forem diferentes, pede uma atualização (atalho "R" do Streamlit).
# No máximo duas vezes a cada 10 s, para nunca entrar em ciclo (o botão de tema zera essa conta, porque a
# troca foi pedida pela pessoa).
_OBSERVADOR = """
<script>
const esperado = "%s";
const doc = window.parent.document;
function atual() {
  const app = doc.querySelector('[data-testid="stApp"]');
  if (!app) return esperado;
  const c = getComputedStyle(app).backgroundColor.match(/\\d+/g).map(Number);
  return (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) < 128 ? "dark" : "light";
}
function podePedir() {
  try {
    const agora = Date.now();
    const h = JSON.parse(window.parent.sessionStorage.getItem("rx_tema") || "[]").filter(x => agora - x < 10000);
    if (h.length >= 2) return false;
    h.push(agora);
    window.parent.sessionStorage.setItem("rx_tema", JSON.stringify(h));
    return true;
  } catch (e) { return false; }
}
// Botão de tema no topo (no lugar do menu ⋮): abre o menu escondido do Streamlit e escolhe Claro ou
// Escuro, como faria quem usasse o menu. O botão fica no documento da página e é religado a cada execução.
const SOL = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
  'stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4' +
  'M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
const LUA = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
  'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';
function desenhar(botao) {
  const escuro = atual() === "dark";
  botao.innerHTML = escuro ? SOL : LUA;
  const rotulo = escuro ? "Usar tema claro" : "Usar tema escuro";
  botao.title = rotulo;
  botao.setAttribute("aria-label", rotulo);
}
function trocarTema() {
  const menu = doc.querySelector('[data-testid="stMainMenuButton"]') ||
               doc.querySelector('[data-testid="stMainMenu"] button');
  if (!menu) return;
  const alvo = atual() === "dark" ? "Light" : "Dark";
  // troca pedida pela pessoa: zera o limite de atualizações automáticas, que só protege contra ciclos
  try { window.parent.sessionStorage.removeItem("rx_tema"); } catch (e) {}
  menu.click();
  let tentativas = 0;
  const procurar = setInterval(() => {
    const opcao = doc.querySelector('[data-testid="stMainMenuItem-theme-' + alvo + '"]');
    if (opcao) {
      // a lista do menu abre por um instante: fica invisível até fechar
      let caixa = opcao.closest('[data-testid="stMainMenuList"]');
      while (caixa && caixa.parentElement && caixa.parentElement !== doc.body) caixa = caixa.parentElement;
      if (caixa) caixa.style.opacity = "0";
    }
    if (opcao || ++tentativas > 20) {
      clearInterval(procurar);
      if (opcao) opcao.click();
      if (menu.getAttribute("aria-expanded") === "true") menu.click();  // fecha, se continuar aberto
    }
  }, 30);
}
function ligarBotao() {
  const ancora = doc.querySelector('[data-testid="stMainMenu"]');
  if (!ancora) return;
  let botao = doc.getElementById("rx-tema");
  if (!botao) {
    botao = doc.createElement("button");
    botao.id = "rx-tema";
    botao.type = "button";
    ancora.insertAdjacentElement("beforebegin", botao);
  }
  botao.onclick = trocarTema;  // religa a esta execução (a anterior pode ter sido descartada)
  desenhar(botao);
}
// Às vezes a primeira atualização ainda recebe o tema antigo; tenta de novo depois de 2,5 s (sempre dentro
// do limite de podePedir).
let pedido = 0;
setInterval(() => {
  ligarBotao();
  if (Date.now() - pedido > 2500 && atual() !== esperado && podePedir()) {
    pedido = Date.now();
    // o atalho não funciona com o foco num botão (o do menu, depois de uma troca): tira o foco antes
    if (doc.activeElement && doc.activeElement !== doc.body) doc.activeElement.blur();
    // keydown e keyup: sem o keyup, as próximas teclas "R" contam como repetição e são ignoradas
    const tecla = {key: "r", code: "KeyR", keyCode: 82, which: 82, bubbles: true};
    doc.dispatchEvent(new KeyboardEvent("keydown", tecla));
    doc.dispatchEvent(new KeyboardEvent("keyup", tecla));
  }
}, 400);
</script>
"""


def preparar_pagina(t: dict) -> None:
    """Estilo comum, botão de tema e observador do tema; chamar no início de cada página."""
    st.markdown(_CSS, unsafe_allow_html=True)
    components.html(_OBSERVADOR % t["tipo"], height=0)


def cabecalho(titulo: str, subtitulo: str) -> None:
    st.title(titulo)
    st.caption(subtitulo)
