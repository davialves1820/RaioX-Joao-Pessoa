"""Ponto de entrada do Streamlit (Community Cloud procura este arquivo na raiz)."""

import importlib

import streamlit as st

import src.config

# O Streamlit Cloud reaproveita o processo entre os deploys e nem sempre recarrega módulos já
# importados: depois de um push que acrescenta uma constante em src/config.py, o processo antigo
# continua com a versão velha e o app quebra com ImportError (aconteceu no deploy da página da
# Câmara). Recarregar o config, que só tem constantes, a cada execução evita depender de um reboot.
importlib.reload(src.config)

from src.app import app, camara, despesas, servicos  # noqa: E402

st.set_page_config(page_title="Raio-X dos Bairros de João Pessoa", layout="wide")
st.navigation(
    [
        st.Page(app.main, title="Bairros e população", url_path="bairros", default=True),
        st.Page(servicos.main, title="Serviços e acesso", url_path="servicos"),
        st.Page(despesas.main, title="Para onde vai o dinheiro", url_path="dinheiro"),
        st.Page(camara.main, title="Câmara Municipal", url_path="camara"),
    ],
    position="top",
).run()
