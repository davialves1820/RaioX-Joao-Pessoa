"""Coleta: OpenStreetMap (Overpass API), © colaboradores do OpenStreetMap, licença ODbL.

Quatro arquivos JSON em data/raw/osm/ (todos, menos escolas.json, são respostas do Overpass):

- matas.json     matas e áreas protegidas (natural=wood, landuse=forest, boundary=protected_area):
                 camada separada no mapa, fora do índice de acesso;
- parques.json   parques (leisure=park/nature_reserve): só para listar, nas limitações, parques que
                 o cadastro da Prefeitura não tem;
- ruas.json      malha de ruas e caminhos (highway=*) para a distância pelas ruas; só a geometria
                 (out skel). Atenção: o servidor alternativo pode estar alguns meses atrasado em relação
                 ao OSM; a data da base usada fica no próprio arquivo (osm3s.timestamp_osm_base);
- escolas.json   os elementos do OSM das escolas que o INEP publica sem coordenada (ids fixos em
                 ESCOLAS_OSM, conferidos à mão: nome igual e ponto no bairro do endereço do INEP),
                 baixados um a um pela API principal do OSM, que é mais estável que o Overpass.

O OSM muda todo dia: a data da consulta fica no manifesto. O servidor principal do Overpass
costuma recusar consultas grandes; por isso há servidores alternativos.

Uso: python -m src.collect.osm [--force]
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request

from src.collect.download import registrar
from src.config import DATA_RAW

SERVIDORES = ["https://overpass.kumi.systems/api/interpreter", "https://overpass-api.de/api/interpreter",
              "https://overpass.private.coffee/api/interpreter"]
FONTE = "OpenStreetMap (Overpass API), © colaboradores do OpenStreetMap, ODbL"
BBOX = "(-7.25,-34.98,-7.04,-34.79)"  # retângulo que contém o município; o recorte exato é feito no processamento

# Vias por onde se anda (inclui ruas residenciais, de serviço, calçadas e caminhos; exclui as que não
# existem para pedestre, como construção e propostas). Retângulo um pouco maior que o do município, para
# caminhos que saem e voltam.
VIAS = ["motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street",
        "service", "pedestrian", "footway", "path", "steps", "track", "cycleway", "motorway_link", "trunk_link",
        "primary_link", "secondary_link", "tertiary_link"]
BBOX_RUAS = "(-7.27,-35.00,-7.02,-34.77)"

# Código INEP -> elemento do OSM
ESCOLAS_OSM = {"25092839": "node/6041727637", "25093851": "way/749962478"}

CONSULTAS = {
    "matas": f'nwr["natural"="wood"]{BBOX};nwr["landuse"="forest"]{BBOX};nwr["boundary"="protected_area"]{BBOX};',
    "parques": f'nwr["leisure"~"^(park|nature_reserve)$"]{BBOX};',
    "ruas": f'way["highway"~"^({"|".join(VIAS)})$"]{BBOX_RUAS};',
}
SAIDA = {"matas": "out geom;", "parques": "out geom;", "ruas": "(._;>;);out skel qt;"}
TIMEOUT = {"matas": 250, "parques": 250, "ruas": 600}
API = "https://api.openstreetmap.org/api/0.6"


def _consulta(nome: str) -> str:
    return f"[out:json][timeout:{TIMEOUT[nome]}];({CONSULTAS[nome]});{SAIDA[nome]}"


def _baixar(nome: str) -> bytes:
    dados = urllib.parse.urlencode({"data": _consulta(nome)}).encode()
    for tentativa in range(1, 4):
        for url in SERVIDORES:
            try:
                req = urllib.request.Request(url, data=dados, headers={"User-Agent": "raio-x-jp/0.1"})
                with urllib.request.urlopen(req, timeout=TIMEOUT[nome] + 300) as r:
                    corpo = r.read()
                json.loads(corpo)["elements"]  # resposta válida
                return corpo
            except (OSError, ValueError, KeyError) as e:
                print(f"[erro] {nome} em {url}: {e}")
        time.sleep(10 * tentativa)
    raise RuntimeError(f"Overpass indisponível para a consulta {nome!r}")


def _url_elemento(elemento: str) -> str:
    return f"{API}/{elemento}.json" if elemento.startswith("node/") else f"{API}/{elemento}/full.json"


def _baixar_escolas() -> bytes:
    """{"elemento": resposta da API} para cada escola de ESCOLAS_OSM."""
    saida = {}
    for elemento in ESCOLAS_OSM.values():
        req = urllib.request.Request(_url_elemento(elemento), headers={"User-Agent": "raio-x-jp/0.1"})
        with urllib.request.urlopen(req, timeout=60) as r:
            saida[elemento] = json.load(r)
    return json.dumps(saida, ensure_ascii=False).encode()


def main(force: bool = False) -> None:
    pasta = DATA_RAW / "osm"
    pasta.mkdir(parents=True, exist_ok=True)
    for nome in CONSULTAS:
        dest = pasta / f"{nome}.json"
        if dest.exists() and not force:
            print(f"[ok] já existe: osm/{nome}.json")
            continue
        tmp = dest.with_name(dest.name + ".part")
        tmp.write_bytes(_baixar(nome))
        tmp.replace(dest)
        registrar(dest, SERVIDORES[0] + "?data=" + urllib.parse.quote(_consulta(nome)), FONTE)
        print(f"[ok] osm/{nome}.json")
    dest = pasta / "escolas.json"
    if dest.exists() and not force:
        print("[ok] já existe: osm/escolas.json")
        return
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(_baixar_escolas())
    tmp.replace(dest)
    registrar(dest, " ; ".join(_url_elemento(e) for e in ESCOLAS_OSM.values()), FONTE)
    print("[ok] osm/escolas.json")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--force", action="store_true")
    main(p.parse_args().force)
