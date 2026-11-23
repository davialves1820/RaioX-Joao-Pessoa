"""Presença nas sessões (pelas atas), votos nominais nas comissões e vídeo das sessões.

Entradas: data/raw/camara_sapl/sessoes.json, ordemdia.json, votoparlamentar.json, comissoes.json e
atas/<id>.pdf (src/collect/camara_sessoes.py); data/processed/camara/vereadores.csv, materias.parquet
e projetos.parquet (src/process/camara.py). Requer o pdftotext (poppler-utils).

Saídas (data/processed/camara/):
- presencas.parquet: uma linha por sessão e vereador listado na ata, com a situação (presente, presente
  de forma virtual, ausente com justificativa, ausente). Só atas conferidas (ver abaixo).
- atas_presenca.csv: uma linha por ata lida, com quantos vereadores ela lista, as cadeiras e se foi
  conferida; as não conferidas ficam fora de presencas.parquet, com o motivo.
- votos_comissoes.parquet: um voto nominal por linha (reuniões de comissão), com a matéria, o
  resultado e a comissão.
- sessoes_video.csv: link do vídeo de cada sessão, quando o SAPL tem.
- metadados_sessoes.json

Regras (investigação na issue #51):
- A ata de cada sessão ordinária e extraordinária traz, antes da abertura, a composição da mesa e as
  listas de presentes em plenário, presentes de forma virtual, ausentes com justificativa e ausentes,
  com nome completo e partido. Cada nome é ligado a um vereador do SAPL da mesma legislatura pelo nome
  completo, pelo nome parlamentar ou pela maioria das palavras do nome completo.
- Ata conferida: cada vereador aparece numa só situação (a mesa conta como presente), todo nome
  listado foi ligado e o total listado é igual ao número de cadeiras (titulares que tomaram posse no
  primeiro dia da legislatura, no SAPL: 27 na 18ª e 29 na 19ª). As outras não entram na presença.
- A lista é a da abertura dos trabalhos: quem chega depois aparece como ausente na ata.
- Plenário: o SAPL não tem voto nominal (só o resultado). Os votos nominais são das comissões.

Uso: python -m src.process.camara_sessoes
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.collect.download import load_manifest
from src.config import ANO_INICIAL_CAMARA, DATA_PROCESSED, DATA_RAW
from src.process.despesas_regras import normalizar

RAW = DATA_RAW / "camara_sapl"
SAIDA = DATA_PROCESSED / "camara"
SAPL = "https://sapl.joaopessoa.pb.leg.br"

SITUACOES = ["Presente", "Presente (virtual)", "Ausente com justificativa", "Ausente"]
# Cabeçalhos do bloco de presença das atas, na ordem em que aparecem
SECOES = [
    ("Mesa", re.compile(r"Composi[çc][ãa]o da mesa", re.I)),
    ("Presente", re.compile(r"presentes (?:em plen[áa]rio|de forma presencial)", re.I)),
    ("Presente (virtual)", re.compile(r"presentes (?:de forma (?:virtual|remota)|remotamente)", re.I)),
    ("Ausente com justificativa", re.compile(r"Ausentes? com justificativa[^:]{0,25}:", re.I)),
    ("Ausente", re.compile(r"Ausentes(?: os vereadores| \(sem justificativa\))?\s*:|Lista de vereadores ausentes", re.I)),
]
# fim do bloco de presença: o título "ABERTURA" ou, sem ele, o horário de abertura ("Às 10h04, o Sr. Presidente")
_FIM_BLOCO = re.compile(r"\bABERTURA\b|Às \d{1,2}h\d{0,2}")
_CABECALHO_PAGINA = re.compile(r"(?:\d+\s+)?(?:C[óo]pia\s+)?Estado da Para[íi]ba C[âa]mara Municipal de (?:Jo[ãa]o )?Pessoa "
                               r"Casa Napole[ãa]o Laureano N[úu]cleo de Reda[çc][ãa]o de Atas", re.I)
# Separadores entre nomes: partido entre parênteses, "Vereador(a)", ponto e vírgula, vírgula e " e "
_SEPARA = re.compile(r"\([^)]*\)|\bVereador(?:a|es|as)?\b|;|,|\s+e\s+(?=[A-ZÁÉÍÓÚÂÊÔ])")
_CARGO = re.compile(r"\b(Presidente|Vice-Presidente|Primeir[oa]|Segund[oa]|Terceir[oa]|Secret[áa]ri[oa]|ad[ -]hoc|"
                    r"na abertura dos trabalhos|Lista|vereador(?:a|es|as)?|presentes?|ausentes?|com|justificativa|"
                    r"oral|forma|virtual|remota|remotamente|presencial|em plen[áa]rio|os|as|N[ãa]o houve|"
                    r"C[óo]pia)\b|[-–]", re.I)
_PARTICULAS = {"DE", "DA", "DO", "DOS", "DAS", "E"}
# Votos registrados no SAPL num cadastro antigo do mesmo vereador. O id 45 ("Marcos Vinicius", MARCOS VINICIUS SALES
# DA NÓBREGA) só tem mandato em 2001-2004, mas vota na CCJRLP em abril de 2025, quando o vereador em exercício com esse
# nome é o id 382 (Marcos Vinícius Sales Nóbrega); o id 382 não vota nessas mesmas votações.
CADASTRO_DUPLICADO = {45: 382}
_COMISSAO = re.compile(r" em \d+ª Reunião (?:da |de )?(\w+) da ")


def _ler(nome: str):
    return json.loads((RAW / nome).read_text(encoding="utf-8"))


def texto_pdf(caminho: Path) -> str:
    r = subprocess.run(["pdftotext", str(caminho), "-"], capture_output=True, text=True, check=False)
    return " ".join(r.stdout.split())


def cadeiras(ver: pd.DataFrame) -> dict[int, int]:
    """Cadeiras por legislatura: titulares cujo mandato começa no primeiro dia da legislatura."""
    tit = ver[ver["titular"]]
    inicio = tit.groupby("legislatura")["inicio_mandato"].min()
    return {int(leg): int(((tit["legislatura"] == leg) & (tit["inicio_mandato"] == ini)).sum())
            for leg, ini in inicio.items()}


def bloco_presenca(texto: str) -> dict[str, str]:
    """Trechos de cada lista do bloco de presença (antes de "ABERTURA")."""
    texto = texto.replace("\u200b", "")
    inicio = SECOES[0][1].search(texto)
    texto = texto[inicio.start():] if inicio else texto
    fim = _FIM_BLOCO.search(texto)
    t = _CABECALHO_PAGINA.sub(" ", texto[:fim.start()] if fim else texto[:8000])
    achados = sorted((m.start(), m.end(), nome) for nome, r in SECOES for m in [r.search(t)] if m)
    return {nome: t[b:prox[0]] for (_, b, nome), prox in zip(achados, achados[1:] + [(len(t), 0, "")])}


def ligar(trecho: str, ver_leg: pd.DataFrame) -> int | None:
    """id_parlamentar do nome citado, ou None."""
    n = normalizar(re.sub(r"[^\w\s]", " ", _CARGO.sub(" ", trecho)))
    if len(n) < 3:
        return None
    palavras = set(n.split())
    candidatos = []
    for r in ver_leg.itertuples():
        completo, apelido = normalizar(r.nome_completo), normalizar(r.nome_parlamentar)
        if re.search(rf"\b{re.escape(completo)}\b", n) or re.search(rf"\b{re.escape(apelido)}\b", n):
            candidatos.append((len(completo), r.id_parlamentar))
            continue
        alvo = set(completo.split()) - _PARTICULAS
        if len(alvo) >= 2 and len(alvo & palavras) >= max(2, len(alvo) - 1):
            candidatos.append((0, r.id_parlamentar))
    ids = {i for _, i in candidatos}
    if len(ids) == 1:
        return ids.pop()
    if candidatos:  # o nome mais longo que aparece inteiro desempata ("Marcos Henriques" x "Marcos Henriques e Silva")
        candidatos.sort(reverse=True)
        if candidatos[0][0] > 0 and (len(candidatos) == 1 or candidatos[0][0] > candidatos[1][0]):
            return candidatos[0][1]
    return None


def _pedacos(trecho: str) -> list[str]:
    pedacos = [p.strip(" .:") for p in _SEPARA.split(trecho)]
    # sobra de cargo, partido ou conectivo não é nome
    return [p for p in pedacos if len(set(normalizar(re.sub(r"[^\w\s]", " ", _CARGO.sub(" ", p)))
                                         .split()) - _PARTICULAS) >= 1]


def presenca_da_ata(texto: str, ver_leg: pd.DataFrame) -> tuple[dict[int, str], list[str], list[int]]:
    """({id_parlamentar: situação}, nomes não ligados, ids em mais de uma situação)."""
    situacao: dict[int, str] = {}
    sem_ligacao, conflitos = [], []
    for secao, trecho in bloco_presenca(texto).items():
        for p in _pedacos(trecho):
            i = ligar(p, ver_leg)
            if i is None:
                # pedaço de uma palavra só (sobrenome partido por " e ", por exemplo) não é nome
                if len(normalizar(p).split()) >= 2:
                    sem_ligacao.append(p)
                continue
            s = "Presente" if secao == "Mesa" else secao
            if i in situacao and situacao[i] != s:
                # o presidente aparece na mesa e na lista de presentes: os dois são "presente"
                if not (situacao[i] == "Presente" and secao in ("Mesa", "Presente")):
                    conflitos.append(i)
            situacao.setdefault(i, s)
    return situacao, sem_ligacao, conflitos


def presencas(ver: pd.DataFrame, sessoes: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    tipos = {1: "Sessão ordinária", 4: "Sessão extraordinária"}
    vagas = cadeiras(ver)
    linhas, atas = [], []
    for s in sessoes:
        arq = RAW / "atas" / f"{s['id']}.pdf"
        if s["tipo"] not in tipos or not arq.exists():
            continue
        leg = int(s["legislatura"])
        ver_leg = ver[ver["legislatura"] == leg].drop_duplicates("id_parlamentar")
        sit, sem, conf = presenca_da_ata(texto_pdf(arq), ver_leg)
        motivo = ("bloco de presença não encontrado" if not sit else
                  f"nome sem ligação: {'; '.join(sem)}" if sem else
                  "vereador em mais de uma situação" if conf else
                  f"lista {len(sit)} vereadores para {vagas.get(leg)} cadeiras" if len(sit) != vagas.get(leg) else "")
        atas.append({"id_sessao": s["id"], "data": s["data_inicio"], "tipo": tipos[s["tipo"]],
                     "numero": s["numero"], "legislatura": leg, "cadeiras": vagas.get(leg), "listados": len(sit),
                     "conferida": not motivo, "motivo": motivo or None,
                     "link_ata": s["upload_ata"].replace("http://", "https://", 1)})
        if not motivo:
            linhas += [{"id_sessao": s["id"], "data": s["data_inicio"], "tipo": tipos[s["tipo"]],
                        "numero": s["numero"], "legislatura": leg, "id_parlamentar": int(i), "situacao": v}
                       for i, v in sit.items()]
    return pd.DataFrame(linhas), pd.DataFrame(atas).sort_values("data", ascending=False, ignore_index=True)


def votos_comissoes(materias: pd.DataFrame) -> pd.DataFrame:
    votos = pd.DataFrame(_ler("votoparlamentar.json"))
    votos = votos[votos["data_hora"].str[:4] >= str(ANO_INICIAL_CAMARA)]
    ordem = pd.DataFrame(_ler("ordemdia.json"))[["id", "materia", "sessao_plenaria", "resultado", "observacao"]]
    v = votos.merge(ordem.rename(columns={"id": "ordem"}), on="ordem", how="left")
    v["sigla_comissao"] = v["__str__"].str.extract(_COMISSAO)[0]
    nomes = {c["sigla"]: " ".join(c["nome"].split()) for c in _ler("comissoes.json")}
    v["comissao"] = v["sigla_comissao"].map(nomes)
    # a ordem do dia traz a matéria; o texto do voto ("... - Projeto de Lei Ordinária nº 1889 de 2023 em ...")
    # serve quando o voto é de um item do expediente
    v["descricao"] = v["__str__"].str.extract(r"Expediente: \d+ - (.+?) em \d+ª")[0]
    v = v.merge(materias, left_on="materia", right_on="id_materia", how="left")
    v["resultado"] = v["resultado"].replace({"APROVAD0": "Aprovado", "Aprovado em Comissão": "Aprovado", "REJEITADO": "Rejeitado",
                                         "Rejeitado na Comissão": "Rejeitado", "RETIRADO": "Retirado"}).replace("", None)
    return pd.DataFrame({
        "id_votacao": v["votacao"].astype(int), "data": v["data_hora"].str[:10],
        "sigla_comissao": v["sigla_comissao"], "comissao": v["comissao"],
        "id_sessao": v["sessao_plenaria"].astype("Int64"), "id_materia": v["materia"].astype("Int64"),
        "materia": v["descricao"], "sigla": v["sigla"], "tipo": v["tipo"], "numero": v["numero"].astype("Int64"),
        "ano": v["ano"].astype("Int64"), "ementa": v["ementa"],
        "observacao": v["observacao"].map(lambda t: " ".join(t.split()) if isinstance(t, str) and t.strip() else None),
        "resultado": v["resultado"], "id_parlamentar": v["parlamentar"].replace(CADASTRO_DUPLICADO).astype(int),
        "voto": v["voto"],
        "link_sapl": v["materia"].map(lambda m: f"{SAPL}/materia/{int(m)}" if pd.notna(m) else None),
    }).sort_values(["data", "id_votacao"], ascending=[False, True], ignore_index=True)


def main() -> None:
    ver = pd.read_csv(SAIDA / "vereadores.csv")
    sessoes = _ler("sessoes.json")
    pres, atas = presencas(ver, sessoes)
    pres.to_parquet(SAIDA / "presencas.parquet", index=False)
    atas.to_csv(SAIDA / "atas_presenca.csv", index=False)

    colunas = ["id_materia", "sigla", "tipo", "numero", "ano", "ementa"]
    # projetos.parquet não traz o nome do tipo; os nomes são os do SAPL ("Projeto de Lei Ordinária nº ...")
    projetos = pd.read_parquet(SAIDA / "projetos.parquet", columns=[c for c in colunas if c != "tipo"])
    projetos["tipo"] = projetos["sigla"].map({"PLO": "Projeto de Lei Ordinária", "PLC": "Projeto de Lei Complementar"})
    materias = pd.concat([projetos[colunas],
                          pd.read_parquet(SAIDA / "materias.parquet", columns=colunas)]).drop_duplicates("id_materia")
    votos = votos_comissoes(materias)
    votos.to_parquet(SAIDA / "votos_comissoes.parquet", index=False)

    video = pd.DataFrame([{"id_sessao": s["id"], "url_video": s["url_video"].strip()} for s in sessoes
                          if (s.get("url_video") or "").strip()])
    video.to_csv(SAIDA / "sessoes_video.csv", index=False)

    manifest = load_manifest()
    meta = {
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "atas_lidas": int(len(atas)),
        "atas_conferidas": int(atas["conferida"].sum()),
        "atas_nao_conferidas": atas.loc[~atas["conferida"], ["id_sessao", "data", "motivo"]].to_dict("records"),
        "cadeiras": cadeiras(ver),
        "presencas": pres["situacao"].value_counts().reindex(SITUACOES, fill_value=0).to_dict(),
        "votos_comissoes": int(len(votos)),
        "votacoes_comissoes": int(votos["id_votacao"].nunique()),
        "votos": votos["voto"].value_counts().to_dict(),
        "votos_sem_materia": int(votos["id_materia"].isna().sum()),
        "votos_de_parlamentar_sem_mandato": int((~votos["id_parlamentar"].isin(ver["id_parlamentar"])).sum()),
        "cadastro_duplicado": {str(k): v for k, v in CADASTRO_DUPLICADO.items()},
        "sessoes_com_video": int(len(video)),
        "regras": {
            "presenca": ("lista de presentes e ausentes da ata, na abertura dos trabalhos; só atas em que cada "
                         "vereador aparece uma vez, todos os nomes foram ligados ao SAPL e o total é igual ao "
                         "número de cadeiras"),
            "cadeiras": "titulares cujo mandato começa no primeiro dia da legislatura (SAPL)",
            "votos": "votos nominais do SAPL; existem só nas reuniões de comissão (o plenário vota de forma simbólica)",
        },
        "arquivos_brutos": {k: v for k, v in manifest.items()
                            if k.startswith("camara_sapl/atas/") or k in {
                                f"camara_sapl/{n}.json" for n in ("sessoes", "ordemdia", "votoparlamentar", "comissoes")}},
    }
    (SAIDA / "metadados_sessoes.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"atas: {meta['atas_conferidas']} conferidas de {meta['atas_lidas']}; presenças: {meta['presencas']}; "
          f"votos nas comissões: {meta['votos_comissoes']} em {meta['votacoes_comissoes']} votações; "
          f"sessões com vídeo: {meta['sessoes_com_video']}")


if __name__ == "__main__":
    main()
