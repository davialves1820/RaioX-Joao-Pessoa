"""Testes da cópia dos dados brutos (src/collect/restaurar.py)."""

import hashlib
import io
import zipfile

from src.collect import restaurar as r


def _zip(arquivos: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, dados in arquivos.items():
            z.writestr(nome, dados)
    return buf.getvalue()


def _manifest(arquivos: dict[str, bytes]) -> dict:
    return {k: {"sha256": hashlib.sha256(v).hexdigest()} for k, v in arquivos.items()}


def test_dados_pessoais_e_sem_licenca_ficam_fora():
    manifest = {k: {} for k in ["tce_pb/despesas-2025.zip", "cnes/BASE_DE_DADOS_CNES_202609.ZIP",
                                "cnes/estabelecimentos_250750.json", "filipeia/bairros.zip",
                                "geodata_jp/bairros.geojson", "osm/ruas.json", "inep/escolas.csv"]}
    copia = r.arquivos_da_copia(manifest)
    incluidos = {k for v in copia.values() for k in v}
    assert incluidos == {"cnes/estabelecimentos_250750.json", "osm/ruas.json", "inep/escolas.csv"}
    assert "tce_pb" not in copia and "filipeia" not in copia and "geodata_jp" not in copia


def test_so_grava_arquivo_que_confere_com_o_manifesto(tmp_path):
    bom = {"osm/a.json": b"conteudo certo"}
    manifest = _manifest(bom)
    manifest["osm/b.json"] = {"sha256": hashlib.sha256(b"outro").hexdigest()}
    conteudo = _zip({"osm/a.json": b"conteudo certo", "osm/b.json": b"alterado", "osm/c.json": b"x"})
    res = r.restaurar_zip(conteudo, manifest, destino=tmp_path)
    assert res["gravados"] == ["osm/a.json"]
    assert res["divergentes"] == ["osm/b.json"]
    assert res["fora_do_manifesto"] == ["osm/c.json"]
    assert (tmp_path / "osm/a.json").read_bytes() == b"conteudo certo"
    assert not (tmp_path / "osm/b.json").exists()
    # de novo: o arquivo já confere e não é regravado
    assert r.restaurar_zip(conteudo, manifest, destino=tmp_path)["ja_existiam"] == ["osm/a.json"]
