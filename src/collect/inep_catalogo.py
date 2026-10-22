"""Coleta: INEP, Catálogo de Escolas (escolas da Paraíba, com latitude e longitude).

O catálogo não tem download direto: é um painel do Oracle Analytics em que se escolhem
filtros, clica-se em "Aplicar" e depois em "Exportar". Este script faz isso com um
navegador automatizado (Playwright + Chromium): UF = PB, sem outros filtros.

Requisitos:
- `pip install playwright` (está em requirements-dev.txt) e um Chromium. Se o Chromium não
  estiver no caminho padrão do Playwright, informe-o em PLAYWRIGHT_CHROMIUM.
- O servidor do INEP não envia o certificado intermediário da RNP. O Chromium no Linux não o
  busca sozinho, então o certificado (público) em certs/ é registrado no banco NSS do usuário
  (~/.pki/nssdb) com `certutil` antes da exportação. A verificação TLS continua ligada.

Se o INEP mudar o painel e o script quebrar, exporte à mão em
https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/inep-data/catalogo-de-escolas
(UF = PB, Aplicar, Exportar) e salve como data/raw/inep/catalogo_escolas_PB.csv; depois rode
`python -m src.collect.inep_catalogo --registrar` para registrá-lo no manifesto.

Uso: python -m src.collect.inep_catalogo [--force] [--registrar]
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
from pathlib import Path

from src.collect.download import registrar
from src.config import DATA_RAW, ROOT

PORTAL = (
    "https://anonymousdata.inep.gov.br/analytics/saw.dll?Portal&PortalPath="
    "%2Fshared%2FCenso%20da%20Educa%C3%A7%C3%A3o%20B%C3%A1sica%2F_portal%2FCat%C3%A1logo%20de%20Escolas"
)
FONTE = "INEP - Catálogo de Escolas (exportação do painel, UF = PB)"
DESTINO = DATA_RAW / "inep" / "catalogo_escolas_PB.csv"
CERT = ROOT / "certs" / "rnp-icpedu-gr46-ov-tls-ca-2025.pem"
NOME_CERT = "RNP ICPEdu GR46 OV TLS CA 2025"


def _garantir_certificado() -> None:
    nssdb = Path.home() / ".pki" / "nssdb"
    if not shutil.which("certutil") or not nssdb.exists():
        print("[aviso] certutil ou ~/.pki/nssdb ausente: se o Chromium recusar o certificado do INEP, "
              f"importe {CERT.name} como autoridade intermediária no navegador.")
        return
    lista = subprocess.run(["certutil", "-d", f"sql:{nssdb}", "-L"], capture_output=True, text=True).stdout
    if NOME_CERT not in lista:
        subprocess.run(["certutil", "-d", f"sql:{nssdb}", "-A", "-t", ",,", "-n", NOME_CERT, "-i", str(CERT)], check=True)
        print(f"[ok] certificado intermediário registrado: {NOME_CERT}")


def _marcar(pg, indice_campo: int, valor: str, tentativas: int = 3) -> None:
    """Abre o menu de um filtro (seta para baixo), marca a opção e confere se ficou marcada."""
    campo = pg.locator("input.promptTextField").nth(indice_campo)
    for _ in range(tentativas):
        campo.click()
        pg.keyboard.press("ArrowDown")
        rotulo = pg.locator(f'label.checkboxRadioButtonLabel:text-is("{valor}")').last
        rotulo.wait_for(state="attached", timeout=60000)
        pg.wait_for_timeout(3000)
        rotulo.evaluate("el => { const c = document.getElementById(el.htmlFor); if (!c.checked) c.click(); }")
        pg.wait_for_timeout(2000)
        pg.keyboard.press("Escape")
        pg.mouse.click(1000, 700)
        pg.wait_for_timeout(3000)
        if campo.input_value().strip() == valor:
            return
    raise RuntimeError(f"não foi possível marcar o filtro {valor!r} no painel do INEP")


def _conferir(caminho: Path) -> int:
    """O arquivo precisa ter só escolas da PB (a exportação do painel corta em 100 mil linhas)."""
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        ufs = {linha["UF"] for linha in csv.DictReader(f)}
    with caminho.open(encoding="utf-8-sig") as f:
        n = sum(1 for _ in f) - 1
    if ufs != {"PB"}:
        raise RuntimeError(f"exportação com UFs inesperadas: {sorted(ufs)[:5]}... ({n} linhas)")
    return n


def exportar() -> Path:
    from playwright.sync_api import sync_playwright

    _garantir_certificado()
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    tmp = DESTINO.with_name(DESTINO.name + ".part")
    with sync_playwright() as p:
        exe = os.environ.get("PLAYWRIGHT_CHROMIUM")
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        pg = b.new_page(viewport={"width": 1600, "height": 1200}, accept_downloads=True)
        print(f"[abrindo] {PORTAL}")
        pg.goto(PORTAL, timeout=180000, wait_until="domcontentloaded")
        pg.locator("input.promptTextField").nth(1).wait_for(timeout=120000)
        pg.wait_for_timeout(10000)
        _marcar(pg, 1, "PB")  # campo 1 = UF
        pg.get_by_role("link", name="Aplicar").click()
        exportar_link = pg.locator("a:visible", has_text="Exportar").first
        exportar_link.wait_for(timeout=180000)
        resumo = pg.locator("text=/Foram selecionadas/").first.inner_text()
        selecionadas = int(re.sub(r"\D", "", resumo.split("escolas")[0]))
        print(f"[ok] painel: {selecionadas} escolas selecionadas")
        if not 1000 < selecionadas < 20000:
            raise RuntimeError(f"seleção inesperada no painel: {resumo!r} (o filtro de UF pode não ter sido aplicado)")
        with pg.expect_download(timeout=600000) as dl:
            exportar_link.click()
        dl.value.save_as(tmp)
        b.close()
    print(f"[ok] arquivo conferido: {_conferir(tmp)} escolas, todas da PB")
    tmp.replace(DESTINO)
    return DESTINO


def main(force: bool = False, so_registrar: bool = False) -> None:
    if so_registrar:
        registrar(DESTINO, PORTAL, FONTE + " [exportação manual]")
        return
    if DESTINO.exists() and not force:
        print(f"[ok] já existe: {DESTINO.relative_to(DATA_RAW)}")
        return
    registrar(exportar(), PORTAL, FONTE)


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--force", action="store_true")
    a.add_argument("--registrar", action="store_true", help="só registra um arquivo exportado à mão")
    args = a.parse_args()
    main(args.force, args.registrar)
