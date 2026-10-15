"""Mapa experimental: bairros citados no histórico do empenho.

É uma estimativa parcial. Regras:
- Procuramos os 64 nomes oficiais (IBGE 2022) e grafias alternativas conhecidas,
  sem acentos e como palavra inteira.
- Nomes que também são palavras comuns, datas ou nomes de pessoas, escolas e
  hotéis (Centro, Torre, Treze de Maio, José Américo...) só contam quando vêm
  depois da palavra "bairro" (ex.: "no bairro do Centro").
- Nomes precedidos de rua, avenida, praça etc. não contam: "Avenida Valentina"
  seria uma via, não o bairro.
- Um empenho que cita mais de um bairro não é dividido entre eles: fica na conta
  "vários bairros" e fora do mapa.
"""

from __future__ import annotations

import re
from functools import lru_cache

from src.process.despesas_regras import normalizar

# Grafias alternativas, por código IBGE do bairro
ALIASES = {
    "2507507007": ["BAIRRO DOS ESTADOS"],
    "2507507008": ["BAIRRO DAS INDUSTRIAS"],
    "2507507009": ["BAIRRO DOS IPES"],
    "2507507041": ["MUCUMAGO"],
}

# Só valem depois de "bairro": palavras comuns, datas e nomes de pessoas/lugares
AMBIGUOS = {
    "CENTRO", "TORRE", "PENHA", "ESTADOS", "IPES", "ROGER", "CUIA", "SAO JOSE", "INDUSTRIAS",
    "FUNCIONARIOS", "EXPEDICIONARIOS", "TAMBIA", "ANATOLIA", "GROTAO", "AEROCLUBE",
    "TREZE DE MAIO", "COSTA E SILVA", "CASTELO BRANCO", "ERNESTO GEISEL", "JOAO PAULO II",
    "JOAO AGRIPINO", "PADRE ZE", "PEDRO GONDIM", "ERNANI SATIRO", "JOSE AMERICO", "VALENTINA",
    "MIRAMAR", "BRISAMAR", "CABO BRANCO", "PORTAL DO SOL", "COSTA DO SOL", "CRISTO REDENTOR",
}

_ANTES_VIA = re.compile(
    r"\b(?:RUA|R|AV|AVENIDA|TRAVESSA|TV|PRACA|RODOVIA|ALAMEDA|VIADUTO|LARGO|ESTRADA|ESCOLA|EMEF|EEEF|CREI|CMEI)"
    r"\.?(?: D[OAE]S?)? $"
)
_PREFIXO_BAIRRO = r"BAIRROS?(?: D[OAE]S?)? "


@lru_cache(maxsize=4)
def _padroes(nomes_oficiais: tuple[tuple[str, str], ...]) -> tuple[tuple[str, str, re.Pattern], ...]:
    padroes = []
    for cd, nome in nomes_oficiais:
        for v in {normalizar(nome), *ALIASES.get(cd, [])}:
            prefixo = _PREFIXO_BAIRRO if v in AMBIGUOS else ""
            padroes.append((cd, v, re.compile(rf"\b{prefixo}{re.escape(v)}\b")))
    # nomes mais longos primeiro: "ALTIPLANO CABO BRANCO" antes de "CABO BRANCO"
    return tuple(sorted(padroes, key=lambda p: -len(p[1])))


def bairros_citados(historico: str, nomes_oficiais: tuple[tuple[str, str], ...]) -> set[str]:
    """Códigos IBGE dos bairros citados no texto, segundo as regras do módulo."""
    texto = normalizar(historico or "")
    achados: set[str] = set()
    for cd, _, rx in _padroes(nomes_oficiais):
        for m in rx.finditer(texto):
            if _ANTES_VIA.search(texto[: m.start()]):
                continue
            achados.add(cd)
            # apaga o trecho para um nome contido nele não casar de novo
            texto = texto[: m.start()] + " " * (m.end() - m.start()) + texto[m.end():]
            break
    return achados
