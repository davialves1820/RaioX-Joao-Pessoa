"""Coleta: atas, ordem do dia e votos nominais das sessões (SAPL da Câmara Municipal).

- data/raw/camara_sapl/sessoes.json: todas as sessões (o mesmo arquivo de src.collect.camara_sapl;
  traz o link do vídeo, quando cadastrado).
- data/raw/camara_sapl/ordemdia.json: os itens da ordem do dia de sessões e reuniões de comissão.
- data/raw/camara_sapl/votoparlamentar.json: os votos nominais registrados no SAPL (só existem em
  reuniões de comissão).
- data/raw/camara_sapl/comissoes.json: nome e sigla das comissões.
- data/raw/camara_sapl/atas/<id da sessão>.pdf: a ata das sessões ordinárias e extraordinárias, de
  ANO_INICIAL_CAMARA em diante. A lista de presentes e ausentes sai daí.

Uso: python -m src.collect.camara_sessoes [--force] [--atualizar]
  --force      rebaixa tudo
  --atualizar  rebaixa as listas (sessões, ordem do dia, votos) e as atas que faltam
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.collect.camara_sapl import API, FONTE, PASTA, _precisa, _salvar, consultar
from src.collect.download import download
from src.config import ANO_INICIAL_CAMARA

LISTAS = {
    "sessoes": "sessao/sessaoplenaria/",
    "ordemdia": "sessao/ordemdia/",
    "votoparlamentar": "sessao/votoparlamentar/",
    "comissoes": "comissoes/comissao/",
}
# ids em sessao/tiposessaoplenaria do SAPL de João Pessoa
TIPOS_SESSAO_COM_PRESENCA = {1: "Sessão ordinária", 4: "Sessão extraordinária"}


def atas(sessoes: list[dict]) -> list[tuple[int, str]]:
    """(id, url) das atas das sessões ordinárias e extraordinárias do recorte."""
    return [(s["id"], s["upload_ata"].replace("http://", "https://", 1)) for s in sessoes
            if s["tipo"] in TIPOS_SESSAO_COM_PRESENCA and s.get("upload_ata")
            and s["data_inicio"][:4] >= str(ANO_INICIAL_CAMARA)]


def main(force: bool = False, atualizar: bool = False) -> None:
    for nome, caminho in LISTAS.items():
        if _precisa(f"{nome}.json", force or atualizar):
            _salvar(f"{nome}.json", consultar(caminho), API + caminho + "?o=id")
    sessoes = json.loads((PASTA / "sessoes.json").read_text(encoding="utf-8"))
    for sid, url in atas(sessoes):
        download(url, Path("camara_sapl/atas") / f"{sid}.pdf", fonte=FONTE, force=force, tentativas=8)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--force", action="store_true")
    p.add_argument("--atualizar", action="store_true")
    a = p.parse_args()
    main(a.force, a.atualizar)
