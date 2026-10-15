"""Ponto de entrada do Streamlit (Community Cloud procura este arquivo na raiz)."""

import streamlit as st

from src.app import app, despesas

st.set_page_config(page_title="Raio-X dos Bairros de João Pessoa", layout="wide")
st.navigation(
    [
        st.Page(app.main, title="Bairros e população", url_path="bairros", default=True),
        st.Page(despesas.main, title="Para onde vai o dinheiro", url_path="dinheiro"),
    ],
    position="top",
).run()
