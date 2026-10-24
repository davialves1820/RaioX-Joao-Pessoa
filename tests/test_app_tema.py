"""Testes do tema claro/escuro (cores, escala de cor do mapa e legendas)."""

from src.app import dados as d
from src.app import tema


def test_os_dois_temas_tem_as_mesmas_chaves():
    assert set(tema.CLARO) == set(tema.ESCURO)
    assert tema.CLARO["mapa"] == "carto-positron" and tema.ESCURO["mapa"] == "carto-darkmatter"


def test_rampa_do_escuro_comeca_perto_do_fundo():
    # no claro o tom perto de zero é o mais claro; no escuro, o mais escuro (se confunde com o fundo)
    assert tema.CLARO["seq"][0] == tema.AZUL_SEQ[0]
    assert tema.ESCURO["seq"][0] == tema.AZUL_SEQ[-1]


def test_marcas_redondas_dentro_do_intervalo():
    assert tema.marcas(0, 70903) == [0, 20000, 40000, 60000]
    assert tema.marcas(347, 70903) == [20000, 40000, 60000]
    assert tema.marcas(0, 3.6) == [0, 1, 2, 3]
    assert tema.marcas(-60, 60) == [-50, -25, 0, 25, 50]


def test_escala_de_cor_em_pt_br():
    aj = d.ajuste_mapa(False, 660, 11.55)
    barra = tema.barra_de_cor(aj, tema.CLARO, 0, 70903, d.fmt_int, "hab.")
    assert barra["tickmode"] == "array"
    assert barra["ticktext"] == ["0", "20.000", "40.000", "60.000"]
    # variação da população: marcas fixas, com as pontas saturadas
    sat = tema.barra_de_cor(aj, tema.CLARO, -60, 60, d.fmt_int, valores=[-60, -30, 0, 30, 60],
                            rotulos={-60: "≤ −60", 60: "≥ +60"})
    assert sat["ticktext"] == ["≤ −60", "-30", "0", "30", "≥ +60"]


def test_legenda_de_tom_troca_no_escuro():
    s = "Quanto mais escuro, mais moradores. Bairros com muita área verde aparecem mais claros."
    assert tema.texto(s, tema.CLARO) == s
    assert tema.texto(s, tema.ESCURO) == ("Quanto mais claro, mais moradores. Bairros com muita área verde "
                                           "aparecem mais escuros.")
    assert tema.texto("Mais escuro = mais longe. Sem cor e com contorno escuro.", tema.ESCURO) == \
        "Mais claro = mais longe. Sem cor e com contorno claro."


def test_fora_do_streamlit_usa_o_tema_claro():
    assert tema.atual() is tema.CLARO


def test_renda_sem_centavos_quando_inteira():
    assert d.fmt_renda(1300.0) == "R$ 1.300"
    assert d.fmt_renda(6598.5) == "R$ 6.598,50"
    assert d.fmt_renda(float("nan")) == "—"
