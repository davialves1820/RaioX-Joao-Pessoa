"""Coleta: SAPL da Câmara Municipal de João Pessoa (API aberta).

O SAPL (https://sapl.joaopessoa.pb.leg.br/api/) é o sistema legislativo da Câmara: matérias
(projetos, requerimentos, indicações...), autoria, normas jurídicas, parlamentares, mandatos,
sessões e presença. Cada consulta é salva como recebida, numa lista JSON, em data/raw/camara_sapl/,
e registrada no manifesto.

- Cadastros (parlamentares, mandatos, filiações, autores, tipos): um arquivo cada.
- Matérias e normas: um arquivo por ano, de ANO_INICIAL_CAMARA ao ano corrente.
- Tramitações: só dos projetos de lei (ordinária e complementar), um arquivo por ano, no formato
  {id da matéria: [tramitações]}. A API não filtra tramitações por ano, então a consulta é feita
  matéria por matéria.
- Sessões plenárias e presença: um arquivo cada (todas as sessões cadastradas).

O servidor derruba conexões com frequência e responde 503 quando sobrecarregado: as consultas usam
no máximo 2 conexões simultâneas, e cada página é tentada até 8 vezes.

Uso: python -m src.collect.camara_sapl [--force] [--atualizar]
  --force      rebaixa tudo
  --atualizar  rebaixa os cadastros, as sessões e o ano corrente
"""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from src.collect.download import registrar
from src.config import ANO_INICIAL_CAMARA, DATA_RAW

API = "https://sapl.joaopessoa.pb.leg.br/api/"
FONTE = "Câmara Municipal de João Pessoa - SAPL (API de dados abertos)"
PASTA = DATA_RAW / "camara_sapl"
TENTATIVAS = 8
POR_PAGINA = 100
PARALELO = 2

CADASTROS = {
    "parlamentares": "parlamentares/parlamentar/",
    "legislaturas": "parlamentares/legislatura/",
    "mandatos": "parlamentares/mandato/",
    "filiacoes": "parlamentares/filiacao/",
    "partidos": "parlamentares/partido/",
    "autores": "base/autor/",
    "tipos_autor": "base/tipoautor/",
    "tipos_materia": "materia/tipomaterialegislativa/",
    "status_tramitacao": "materia/statustramitacao/",
    "tipos_norma": "norma/tiponormajuridica/",
    "tipos_sessao": "sessao/tiposessaoplenaria/",
}
SESSOES = {
    "sessoes": "sessao/sessaoplenaria/",
    "presencas": "sessao/sessaoplenariapresenca/",
}
# Projeto de Lei Ordinária e Projeto de Lei Complementar (ids em materia/tipomaterialegislativa)
TIPOS_PROJETO = (1, 5)


def _get(caminho: str, **params) -> dict:
    url = API + caminho + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "raio-x-jp/0.1"})
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except OSError as e:  # URLError, reset de conexão, timeout
            if tentativa == TENTATIVAS:
                raise
            espera = min(2**tentativa, 30)
            print(f"[erro] {e}; nova tentativa em {espera}s ({tentativa}/{TENTATIVAS})")
            time.sleep(espera)


def consultar(caminho: str, paralelo: int = PARALELO, **params) -> list[dict]:
    """Todas as páginas de uma consulta à API, na ordem."""
    primeira = _get(caminho, page_size=POR_PAGINA, page=1, **params)
    total = primeira["pagination"]["total_entries"]
    paginas = math.ceil(total / POR_PAGINA)
    with ThreadPoolExecutor(paralelo) as ex:
        res = [primeira["results"]] + list(ex.map(
            lambda p: _get(caminho, page_size=POR_PAGINA, page=p, **params)["results"], range(2, paginas + 1)))
    linhas = [r for pagina in res for r in pagina]
    if len(linhas) != total:
        raise RuntimeError(f"{caminho} {params}: {len(linhas)} linhas, a API informa {total}")
    return linhas


def _salvar(nome: str, dados, url: str) -> None:
    dest = PASTA / nome
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    tmp.replace(dest)
    registrar(dest, url, FONTE)


def _precisa(nome: str, force: bool) -> bool:
    if (PASTA / nome).exists() and not force:
        print(f"[ok] já existe: camara_sapl/{nome}")
        return False
    return True


def tramitacoes(ids: list[int]) -> dict[str, list[dict]]:
    def uma(i):
        return str(i), consultar("materia/tramitacao/", paralelo=1, materia=i)
    with ThreadPoolExecutor(PARALELO) as ex:
        return dict(ex.map(uma, ids))


def main(force: bool = False, atualizar: bool = False) -> None:
    ano_corrente = date.today().year
    for nome, caminho in {**CADASTROS, **SESSOES}.items():
        if _precisa(f"{nome}.json", force or atualizar):
            _salvar(f"{nome}.json", consultar(caminho), API + caminho)
    for ano in range(ANO_INICIAL_CAMARA, ano_corrente + 1):
        refazer = force or (atualizar and ano == ano_corrente)
        if _precisa(f"materias-{ano}.json", refazer):
            _salvar(f"materias-{ano}.json", consultar("materia/materialegislativa/", ano=ano),
                    f"{API}materia/materialegislativa/?ano={ano}")
        if _precisa(f"normas-{ano}.json", refazer):
            _salvar(f"normas-{ano}.json", consultar("norma/normajuridica/", ano=ano),
                    f"{API}norma/normajuridica/?ano={ano}")
        if _precisa(f"tramitacoes_projetos-{ano}.json", refazer):
            materias = json.loads((PASTA / f"materias-{ano}.json").read_text(encoding="utf-8"))
            ids = [m["id"] for m in materias if m["tipo"] in TIPOS_PROJETO]
            _salvar(f"tramitacoes_projetos-{ano}.json", tramitacoes(ids),
                    f"{API}materia/tramitacao/?materia=<id> (projetos de lei de {ano})")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--force", action="store_true")
    p.add_argument("--atualizar", action="store_true")
    a = p.parse_args()
    main(a.force, a.atualizar)
