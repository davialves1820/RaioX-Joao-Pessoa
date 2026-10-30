"""Cópia dos dados brutos em release do GitHub: restaurar (padrão) ou empacotar.

Se uma fonte mudar ou sair do ar, os arquivos usados na versão atual dos dados podem ser
restaurados a partir da cópia publicada como release. Cada arquivo só é gravado em data/raw/ se o
SHA-256 bater com o registrado em data/raw/manifest.json.

Só entram na cópia as fontes que podem ser redistribuídas sem expor dados pessoais (ver FORA):

- IBGE, INEP, SICONFI e a API do CNES: dados abertos do Executivo federal, de livre uso com
  citação da fonte (Decreto 8.777/2016, art. 2º, III);
- Câmara Municipal: texto de lei não é protegido por direito autoral (Lei 9.610/1998, art. 8º, IV);
- OpenStreetMap: ODbL, com crédito aos colaboradores do OpenStreetMap.

Uso:
  python -m src.collect.restaurar [--fonte inep osm ...] [--force]
  python -m src.collect.restaurar --empacotar PASTA   (gera os anexos de um novo release)
"""

from __future__ import annotations

import argparse
import hashlib
import io
import shutil
import urllib.request
import zipfile
from pathlib import Path

from src.collect.download import _sha256, load_manifest
from src.config import DATA_RAW, MANIFEST

REPO = "davialves1820/RaioX-Joao-Pessoa"
TAG = "dados-2026-10"
URL = f"https://github.com/{REPO}/releases/download/{TAG}/"

FONTES = ["ibge_censo2010", "ibge_censo2022", "ibge_sidra", "inep", "siconfi", "cnes", "camara_jp", "osm"]

# Prefixo do arquivo em data/raw -> motivo de ficar fora da cópia
FORA = {
    "tce_pb/": "traz CPF completo e nome de pessoas físicas credoras; baixar do TCE-PB",
    "cnes/BASE_DE_DADOS_CNES_": "traz nome, CPF parcial e CNS de todos os profissionais de saúde do país; "
                                "baixar do DATASUS",
    "filipeia/": "o portal da Prefeitura não declara licença; exportar à mão (ver src/collect/filipeia.py)",
    "geodata_jp/": "o repositório de origem não declara licença; baixar de lá",
}


def motivo_fora(chave: str) -> str | None:
    return next((m for p, m in FORA.items() if chave.startswith(p)), None)


def arquivos_da_copia(manifest: dict) -> dict[str, list[str]]:
    """Arquivos do manifesto que entram na cópia, por fonte (pasta de data/raw)."""
    por_fonte: dict[str, list[str]] = {f: [] for f in FONTES}
    for chave in sorted(manifest):
        pasta = chave.split("/")[0]
        if pasta in por_fonte and motivo_fora(chave) is None:
            por_fonte[pasta].append(chave)
    return por_fonte


def conferir(dados: bytes, chave: str, manifest: dict) -> bool:
    return hashlib.sha256(dados).hexdigest() == manifest[chave]["sha256"]


def restaurar_zip(conteudo: bytes, manifest: dict, destino: Path = DATA_RAW, force: bool = False) -> dict:
    """Extrai um anexo do release em `destino`, gravando só arquivos com o SHA-256 do manifesto."""
    res = {"gravados": [], "ja_existiam": [], "divergentes": [], "fora_do_manifesto": []}
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        for nome in z.namelist():
            if nome.endswith("/"):
                continue
            if nome not in manifest:
                res["fora_do_manifesto"].append(nome)
                continue
            alvo = destino / nome
            if alvo.exists() and not force and _sha256(alvo) == manifest[nome]["sha256"]:
                res["ja_existiam"].append(nome)
                continue
            dados = z.read(nome)
            if not conferir(dados, nome, manifest):
                res["divergentes"].append(nome)
                continue
            alvo.parent.mkdir(parents=True, exist_ok=True)
            tmp = alvo.with_name(alvo.name + ".part")
            tmp.write_bytes(dados)
            tmp.replace(alvo)
            res["gravados"].append(nome)
    return res


def restaurar(fontes: list[str], force: bool = False) -> None:
    manifest = load_manifest()
    for fonte in fontes:
        url = URL + fonte + ".zip"
        print(f"[baixando] {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "raio-x-jp/0.1"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            res = restaurar_zip(resp.read(), manifest, force=force)
        print(f"[{fonte}] gravados: {len(res['gravados'])}, já existiam: {len(res['ja_existiam'])}")
        for chave in res["divergentes"]:
            print(f"[erro] SHA-256 diferente do manifesto, não gravado: {chave}")
        for chave in res["fora_do_manifesto"]:
            print(f"[aviso] fora do manifesto, ignorado: {chave}")
    print("Fora da cópia (baixar da fonte original):")
    for prefixo, motivo in FORA.items():
        print(f"  {prefixo}: {motivo}")


def empacotar(saida: Path) -> None:
    """Gera os anexos do release: um .zip por fonte, o manifesto e SHA256SUMS."""
    manifest = load_manifest()
    saida.mkdir(parents=True, exist_ok=True)
    somas = []
    for fonte, chaves in arquivos_da_copia(manifest).items():
        with zipfile.ZipFile(saida / f"{fonte}.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for chave in chaves:
                caminho = DATA_RAW / chave
                if _sha256(caminho) != manifest[chave]["sha256"]:
                    raise SystemExit(f"{chave}: o arquivo local não bate com o manifesto")
                z.write(caminho, chave)
                somas.append(f"{manifest[chave]['sha256']}  {chave}")
        print(f"[ok] {fonte}.zip ({len(chaves)} arquivos)")
    shutil.copy(MANIFEST, saida / "manifest.json")
    (saida / "SHA256SUMS").write_text("\n".join(somas) + "\n", encoding="utf-8")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fonte", nargs="+", choices=FONTES, default=FONTES, help="fontes a restaurar")
    p.add_argument("--force", action="store_true", help="regrava mesmo arquivos que já conferem")
    p.add_argument("--empacotar", type=Path, metavar="PASTA", help="gera os anexos de um release")
    a = p.parse_args()
    if a.empacotar:
        empacotar(a.empacotar)
    else:
        restaurar(a.fonte, a.force)
