"""Emendas impositivas dos vereadores ao orçamento e sua execução nos empenhos do TCE-PB.

Entradas: data/raw/camara_sapl/emendas.json e emendas/<id>.<ext> (src/collect/camara_emendas.py),
data/raw/tce_pb/despesas-AAAA.zip (src/collect/tce_pb.py) e data/processed/camara/vereadores.csv.
Requer o pdftotext (poppler-utils) para ler os PDFs.

Saídas (data/processed/camara/):
- emendas.parquet: uma linha por emenda, com autor, valor, dotação, beneficiário (nome e CNPJ),
  valores empenhado e pago nos empenhos ligados e a conferência da ligação.
- emendas_empenhos.parquet: os empenhos que citam o número de uma emenda, com a conferência.
- metadados_emendas.json

Regras (investigação na issue #49):
- O texto original é um formulário padrão: valor acrescido, órgão, unidade orçamentária, natureza da
  despesa e meta (com o beneficiário). O que não for encontrado fica vazio; nada é estimado.
- O empenho cita a emenda no histórico ("EMENDA IMPOSITIVA Nº 393/2025"); a ligação é pelo número e
  pelo ano da emenda, e um histórico pode citar várias.
- A ligação é conferida: CNPJ igual ao da emenda; mesma raiz de CNPJ (matriz e filial); CNPJ diferente;
  ou, sem CNPJ na emenda, nome parecido. O resto fica "a conferir" (pode ser um fornecedor comprando
  para a entidade). Nada é descartado.
- "Sem empenho encontrado" não quer dizer "não executada": o empenho pode não citar o número.
- Credor pessoa física: CPF mascarado e sem nome nem histórico.

Uso: python -m src.process.camara_emendas
"""

from __future__ import annotations

import json
import re
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.collect.download import load_manifest
from src.config import DATA_PROCESSED, DATA_RAW
from src.process.despesas_regras import centavos, mascarar_cpf, normalizar, tipo_documento

RAW = DATA_RAW / "camara_sapl"
RAW_TCE = DATA_RAW / "tce_pb"
SAIDA = DATA_PROCESSED / "camara"
SAPL = "https://sapl.joaopessoa.pb.leg.br"
TIPOS = {65: "ELO-I", 66: "EI-CO"}

_CNPJ = re.compile(r"(?<!\d)(\d{2})\.?(\d{3})\.?(\d{3})\s*/?\s*(\d{4})\s*-?\s*(\d{2})(?!\d)")
_VALOR = re.compile(r"VALOR ACR[EÉ]SCIDO\s*\(R\$\)\s*(?:R\$\s*)?([\d.]+,\d{2})", re.I)
_ORGAO = re.compile(r"ÓRGÃO\s+(\d[\d.]*)\s*[–-]\s*(.+?)\s+UNIDADE OR", re.I | re.S)
_UO = re.compile(r"UNIDADE OR[ÇC]AMENT[ÁA]RIA\s+(\d[\d.]*)\s*[–-]\s*(.+?)\s+CLASSIFICA", re.I | re.S)
_NATUREZA = re.compile(r"NATUREZA DA DESPESA\s+.*?(\d\.?\d\.?\d{2}\.\d{2})", re.I | re.S)
_META = re.compile(r"META\s*/\s*UNIDADE DE MEDIDA\s+(.+?)(?:CANCELAMENTO|JUSTIFICATIVA|$)", re.I | re.S)
# "EMENDA(S) ... Nº 393/2025", "EMENDAS MUNICIPAIS Nº(S): 77/2025, 78/2025"
_CITACAO = re.compile(r"EMENDAS?\b(.{0,90})")
_NUMERO = re.compile(r"(?<![\d.])0*(\d{1,3})\s*/\s*(20\d{2})\b")
_FIM_CITACAO = re.compile(r"\b(PROCESSO|TERMO|PROGRAMACAO|CONTRATO|CONVENIO|PROC)\b")


# --- Texto das emendas


def texto_documento(caminho: Path) -> str:
    """Texto de um PDF (pdftotext) ou de um .docx (XML do Word, sem dependências)."""
    if caminho.suffix.lower() == ".docx" or zipfile.is_zipfile(caminho):
        with zipfile.ZipFile(caminho) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        # O Word divide o texto em pedaços (w:r); juntar sem espaço, separando só parágrafos e células
        return re.sub(r"<[^>]+>", "", re.sub(r"</w:p>|</w:tc>", "\n", xml))
    r = subprocess.run(["pdftotext", "-layout", str(caminho), "-"], capture_output=True, text=True, check=True)
    return r.stdout


def _cnpj(texto: str) -> str | None:
    m = _CNPJ.search(texto)
    return "".join(m.groups()) if m else None


def extrair(texto: str) -> dict:
    """Campos do formulário da emenda. O que não for encontrado fica None."""
    t = " ".join(texto.split())
    corpo = re.split(r"CANCELAMENTO COMPENSAT", t, flags=re.I)[0]  # o resto descreve de onde sai o dinheiro
    valor = _VALOR.search(t)
    orgao = _ORGAO.search(corpo)
    uo = _UO.search(corpo)
    nat = _NATUREZA.search(corpo)
    meta = _META.search(corpo)
    return {
        "valor": centavos(valor[1]) / 100 if valor else None,
        "orgao": f"{orgao[1]} – {orgao[2].strip()}" if orgao else None,
        "unidade_orcamentaria": f"{uo[1]} – {uo[2].strip()}" if uo else None,
        "natureza_despesa": nat[1] if nat else None,
        "meta": meta[1].strip()[:400] if meta else None,
        "cnpj_beneficiario": _cnpj(meta[1]) if meta and _cnpj(meta[1]) else _cnpj(corpo),
    }


# --- Ligação com os empenhos


def citacoes(historico: str) -> list[tuple[int, int]]:
    """(número, ano) das emendas citadas num histórico de empenho. Só números de até 3 dígitos
    (as emendas federais têm outra numeração, de 11 dígitos), logo depois da palavra EMENDA."""
    h = normalizar(historico)
    achados = []
    for m in _CITACAO.finditer(h):
        trecho = _FIM_CITACAO.split(m[1])[0]
        achados += [(int(n), int(a)) for n, a in _NUMERO.findall(trecho)]
    return list(dict.fromkeys(achados))


def _palavras(texto: str) -> set[str]:
    return {p for p in normalizar(texto).split() if len(p) > 3}


def conferir(cnpj_emenda: str | None, beneficiario: str | None, cnpj_credor: str, nome_credor: str) -> str:
    cnpj_emenda = cnpj_emenda if isinstance(cnpj_emenda, str) else None  # NaN vindo do DataFrame
    beneficiario = beneficiario if isinstance(beneficiario, str) else None
    if cnpj_emenda:
        if cnpj_emenda == cnpj_credor:
            return "CNPJ confere"
        if cnpj_emenda[:8] == cnpj_credor[:8]:
            return "Mesma entidade (matriz/filial)"
        return "CNPJ diferente"
    a, b = _palavras(beneficiario or ""), _palavras(nome_credor or "")
    if b and len(a & b) / len(b) >= 0.5:
        return "Nome confere"
    return "A conferir"


ORDEM_CONFERENCIA = ["CNPJ confere", "Mesma entidade (matriz/filial)", "Nome confere", "A conferir", "CNPJ diferente"]


def ler_empenhos(anos: list[int]) -> pd.DataFrame:
    partes = []
    for ano in anos:
        caminho = RAW_TCE / f"despesas-{ano}.zip"
        if not caminho.exists():
            continue
        with zipfile.ZipFile(caminho) as z, z.open(z.namelist()[0]) as f:
            df = pd.read_csv(f, sep=";", dtype=str, encoding="utf-8-sig")
        partes.append(df.assign(ano_empenho=ano))
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def empenhos_das_emendas(emp: pd.DataFrame, emendas: pd.DataFrame) -> pd.DataFrame:
    chave = {(int(n), int(a)): r for n, a, r in zip(emendas["numero"], emendas["ano"], emendas.index)}
    linhas = []
    for e in emp.itertuples():
        for n, a in citacoes(e.historico or ""):
            if (n, a) not in chave:
                continue
            em = emendas.loc[chave[(n, a)]]
            doc = re.sub(r"\D", "", e.cpf_cnpj or "")
            pj = tipo_documento(doc, e.nome_credor or "") == "PJ"
            linhas.append({
                "id_materia": em["id_materia"], "numero_emenda": n, "ano_emenda": a,
                "unidade_gestora": e.descricao_unidade_gestora, "numero_empenho": e.numero_empenho,
                "data_empenho": e.data_empenho, "cnpj_credor": doc if pj else mascarar_cpf(doc),
                "nome_credor": (e.nome_credor or "").strip() if pj else None,
                "empenhado": centavos(e.valor_empenhado) / 100, "pago": centavos(e.valor_pago) / 100,
                "historico": " ".join((e.historico or "").split()) if pj else None,
                "conferencia": conferir(em["cnpj_beneficiario"], em["meta"], doc, e.nome_credor or "") if pj
                else "A conferir",
            })
    return pd.DataFrame(linhas)


def emendas(ver: pd.DataFrame) -> pd.DataFrame:
    lista = json.loads((RAW / "emendas.json").read_text(encoding="utf-8"))
    autores = {a["id"]: a for a in json.loads((RAW / "autores.json").read_text(encoding="utf-8"))} \
        if (RAW / "autores.json").exists() else {}
    nomes = ver.drop_duplicates("id_parlamentar").set_index("id_parlamentar")["nome_parlamentar"]
    linhas = []
    for m in lista:
        arquivos = sorted((RAW / "emendas").glob(f"{m['id']}.*"))
        campos = extrair(texto_documento(arquivos[0])) if arquivos else extrair("")
        ids = [int(autores[a]["object_id"]) for a in m["autores"] if a in autores and autores[a]["tipo"] == 1]
        linhas.append({
            "id_materia": m["id"], "sigla": TIPOS[m["tipo"]], "numero": int(m["numero"]), "ano": int(m["ano"]),
            "data_apresentacao": m["data_apresentacao"], "ementa": " ".join(m["ementa"].split()),
            "autores": "; ".join(nomes.get(i, str(i)) for i in ids), "autores_ids": ";".join(map(str, ids)),
            **campos,
            "texto_lido": bool(arquivos),
            "link_sapl": f"{SAPL}/materia/{m['id']}",
            "link_texto": (m.get("texto_original") or "").replace("http://", "https://", 1) or None,
        })
    return pd.DataFrame(linhas)


def main() -> None:
    ver = pd.read_csv(SAIDA / "vereadores.csv")
    em = emendas(ver)
    # Emendas impositivas de um ano mexem no orçamento do ano seguinte; a execução é procurada dali em diante
    anos = sorted({a for ano in em["ano"].unique() for a in range(ano + 1, ano + 3)})
    emp = ler_empenhos(anos)
    ligados = empenhos_das_emendas(emp, em) if len(emp) else pd.DataFrame()
    if len(ligados):
        tot = ligados.groupby("id_materia").agg(empenhado=("empenhado", "sum"), pago=("pago", "sum"),
                                                empenhos=("numero_empenho", "nunique"))
        melhor = (ligados.assign(o=ligados["conferencia"].map(ORDEM_CONFERENCIA.index))
                  .sort_values("o").drop_duplicates("id_materia").set_index("id_materia")["conferencia"])
        em = em.join(tot, on="id_materia").join(melhor, on="id_materia")
    em["empenhos"] = em.get("empenhos", pd.Series(dtype=float)).fillna(0).astype(int)
    em["situacao"] = em["empenhos"].map(lambda n: "Empenho encontrado" if n else "Sem empenho encontrado")
    em.to_parquet(SAIDA / "emendas.parquet", index=False)
    ligados.to_parquet(SAIDA / "emendas_empenhos.parquet", index=False)

    datas = pd.to_datetime(emp["data_empenho"], format="%d/%m/%Y", errors="coerce") if len(emp) else pd.Series()
    manifest = load_manifest()
    meta = {
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "emendas": int(len(em)),
        "com_texto_lido": int(em["texto_lido"].sum()),
        "com_valor": int(em["valor"].notna().sum()),
        "com_cnpj": int(em["cnpj_beneficiario"].notna().sum()),
        "com_empenho": int((em["empenhos"] > 0).sum()),
        "empenhado": round(float(em["empenhado"].sum()), 2) if "empenhado" in em else 0.0,
        "pago": round(float(em["pago"].sum()), 2) if "pago" in em else 0.0,
        "conferencia": ligados["conferencia"].value_counts().to_dict() if len(ligados) else {},
        "anos_tce": anos,
        "ultima_data_de_empenho": datas.max().strftime("%Y-%m-%d") if len(datas.dropna()) else None,
        "regras": {
            "valor": "campo 'Valor acrescido' do formulário original; vazio se não encontrado",
            "ligacao": "número e ano da emenda citados no histórico do empenho (todas as citações)",
            "conferencia": ORDEM_CONFERENCIA,
            "aviso": ("'Sem empenho encontrado' não quer dizer 'não executada': o empenho pode não citar o "
                      "número da emenda. Emenda não executada também não é irregularidade."),
        },
        "arquivos_brutos": {k: v for k, v in manifest.items()
                            if k.startswith("camara_sapl/emendas") or k in {f"tce_pb/despesas-{a}.zip" for a in anos}},
    }
    (SAIDA / "metadados_emendas.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{meta['emendas']} emendas: {meta['com_valor']} com valor, {meta['com_cnpj']} com CNPJ, "
          f"{meta['com_empenho']} com empenho; conferência: {meta['conferencia']}")


if __name__ == "__main__":
    main()
