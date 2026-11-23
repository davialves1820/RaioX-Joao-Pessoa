"""Coleta: texto original das emendas impositivas ao orçamento (SAPL da Câmara Municipal).

A ementa das emendas no SAPL é incompleta (só um terço traz o valor ou o CNPJ do beneficiário). O
texto original, um formulário padrão em PDF (às vezes em Word), traz valor, dotação e beneficiário.

- data/raw/camara_sapl/emendas.json: as matérias dos tipos "Emenda ao PL Orçamentário Anual -
  IMPOSITIVA" (ELO-I) e "Emenda Impositiva à LOA (corrigida)" (EI-CO), de ANO_INICIAL_CAMARA em diante.
- data/raw/camara_sapl/emendas/<id da matéria>.<extensão>: o texto original de cada uma.

Uso: python -m src.collect.camara_emendas [--force]
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from src.collect.camara_sapl import API, FONTE, PASTA, _salvar, consultar
from src.collect.download import download
from src.config import ANO_INICIAL_CAMARA

# ids em materia/tipomaterialegislativa do SAPL de João Pessoa
TIPOS_EMENDA_IMPOSITIVA = {65: "ELO-I", 66: "EI-CO"}


def main(force: bool = False) -> None:
    lista = PASTA / "emendas.json"
    if force or not lista.exists():
        emendas = [m for tipo in TIPOS_EMENDA_IMPOSITIVA for ano in range(ANO_INICIAL_CAMARA, date.today().year + 1)
                   for m in consultar("materia/materialegislativa/", tipo=tipo, ano=ano)]
        _salvar("emendas.json", emendas, f"{API}materia/materialegislativa/?tipo=65|66&ano=AAAA")
    emendas = json.loads(lista.read_text(encoding="utf-8"))
    for m in emendas:
        url = (m.get("texto_original") or "").replace("http://", "https://", 1)
        if not url:
            print(f"[aviso] emenda {m['id']} sem texto original no SAPL")
            continue
        ext = Path(url).suffix.lower() or ".pdf"
        download(url, Path("camara_sapl/emendas") / f"{m['id']}{ext}", fonte=FONTE, force=force, tentativas=8)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--force", action="store_true")
    main(p.parse_args().force)
