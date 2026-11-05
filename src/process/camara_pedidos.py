"""Pedidos de obras e serviços dos vereadores por bairro, tema e órgão destinatário.

Entrada: data/processed/camara/materias.parquet (gerado por src.process.camara) e
data/processed/indicadores_bairros.csv (bairros oficiais do IBGE 2022).

Saída: data/processed/camara/requerimentos_bairros.parquet, uma linha por requerimento de obras,
serviços e melhoramentos (tipo R-OSM do SAPL) e bairro citado. Requerimento sem bairro identificado
fica com uma linha e o bairro vazio; requerimento com mais de um bairro tem uma linha por bairro.

Regras (investigação na issue #48):
- Bairro: os 64 nomes oficiais e variações do próprio nome (VARIACOES), sem acento e sem caixa.
  Nomes que também são palavras comuns (AMBIGUOS) só contam com contexto de endereço antes.
  Comunidades e loteamentos (Rangel, Novais, Colinas do Sul...) não são ligados a bairro: não há
  fonte oficial no projeto que diga onde fica cada um.
- Tema: palavras-chave (TEMAS); um pedido pode ter mais de um tema.
- Órgão: a primeira sigla de órgão citada no texto (ORGAOS).

Uso: python -m src.process.camara_pedidos (depois de python -m src.process.camara)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import pandas as pd

from src.config import DATA_PROCESSED
from src.process.despesas_regras import normalizar

SAIDA = DATA_PROCESSED / "camara"
SIGLA = "R-OSM"

# Variações do próprio nome oficial (grafia ou forma curta) -> nome oficial do IBGE 2022
VARIACOES = {
    "CRISTO": "Cristo Redentor",
    "GEISEL": "Ernesto Geisel",
    "ALTIPLANO": "Altiplano Cabo Branco",
    "COLIBRIS": "Cidade dos Colibris",
    "ERNANI SATYRO": "Ernani Sátiro",
    "MUSSUMAGRO": "Muçumagro",
    "PLANALTO BOA ESPERANCA": "Planalto da Boa Esperança",
    "PONTA DOS SEIXAS": "Ponta do Seixas",
    "JOSE AMERICO DE ALMEIDA": "José Américo",
    "VALENTINA FIGUEIREDO": "Valentina",
    "VALENTINA DE FIGUEIREDO": "Valentina",
    "VALENTINA FIGUEREDO": "Valentina",
}
# Nomes que também são palavras comuns ("centro de saúde", "torre de telefonia", "Estados Unidos"):
# só valem depois de "bairro (de/do/da/dos/das)", "conjunto", vírgula ou hífen
AMBIGUOS = {"CENTRO", "TORRE", "ESTADOS", "PENHA", "CUIA", "ROGER", "IPES"}
CONTEXTO = r"(?:\bBAIRRO(?: D[EOA]S?)?|\bCONJUNTO|,|-)\s*"

TEMAS = {
    "Limpeza e capinação": r"LIMPEZA|CAPINA|ENTULHO|MEIO.?FIO|LIXO|ROCAGEM|ZELADORIA",
    "Pavimentação e buracos": r"PAVIMENT|CALCAMENT|ASFALT|BURACO|TERRAPLAN|RECAPEAMENT",
    "Sinalização e trânsito": r"SINALIZA|FAIXA|SEMAFOR|LOMBADA|REDUTOR|TRANSITO|QUEBRA.?MOLA|PLACA",
    "Iluminação": r"ILUMINA|LAMPAD|\bLED\b|POSTE",
    "Drenagem e esgoto": r"DRENAGEM|GALERIA|BUEIRO|BOCA DE LOBO|ESGOTO|SANEAMENTO|ALAGAMENT|CANALETA",
    "Poda e áreas verdes": r"PODA|ARVORE|PRACA|PARQUE|JARDINAGEM",
    "Segurança": r"RONDA|POLICIA|SEGURANCA|CAMERA|GUARDA",
    "Saúde": r"\bUSF\b|\bPSF\b|SAUDE|\bUBS\b",
    "Educação": r"ESCOLA|CRECHE|EDUCACAO|\bCMEI\b",
    "Água": r"CAGEPA|ABASTECIMENTO|FALTA D.?AGUA",
}
ORGAOS = ["SEINFRA", "EMLUR", "SEMOB", "CAGEPA", "SEDURB", "SESUZ", "SEMUSB", "SEMAM", "SEDEC", "SEDES",
          "SEMHAB", "SMS", "SEDUC", "SEPLAN", "ENERGISA"]
_ORGAO = re.compile(r"\b(" + "|".join(ORGAOS) + r")\b")
_TEMAS = {t: re.compile(p) for t, p in TEMAS.items()}


def padroes(oficiais: dict[str, str]) -> list[tuple[str, re.Pattern]]:
    """(chave normalizada, padrão), dos nomes mais longos para os mais curtos."""
    todos = {**oficiais, **{k: v for k, v in VARIACOES.items()}}
    return sorted(((k, re.compile((CONTEXTO if k in AMBIGUOS else r"\b") + re.escape(k) + r"\b")) for k in todos),
                  key=lambda x: -len(x[0]))


def casar(texto: str, pats: list[tuple[str, re.Pattern]], nomes: dict[str, str]) -> list[str]:
    """Bairros oficiais citados no texto. Um nome contido noutro já achado (MANGABEIRA em
    NOVA MANGABEIRA, por exemplo) não conta de novo."""
    t = normalizar(texto)
    achados: list[str] = []
    for k, p in pats:
        if not any(k in a for a in achados) and p.search(t):
            achados.append(k)
    return sorted({nomes[k] for k in achados})


def temas(texto: str) -> list[str]:
    t = normalizar(texto)
    return [nome for nome, p in _TEMAS.items() if p.search(t)]


def orgao(texto: str) -> str | None:
    m = _ORGAO.search(normalizar(texto))
    return m[1] if m else None


def carregar_bairros() -> tuple[dict[str, str], dict[str, str]]:
    """(nome normalizado -> nome oficial, nome oficial -> código IBGE)."""
    ind = pd.read_csv(DATA_PROCESSED / "indicadores_bairros.csv", dtype={"cd_bairro": str})
    return ({normalizar(n): n for n in ind["nm_bairro"]}, dict(zip(ind["nm_bairro"], ind["cd_bairro"])))


def requerimentos_bairros(mat: pd.DataFrame) -> pd.DataFrame:
    oficiais, codigos = carregar_bairros()
    nomes = {**oficiais, **VARIACOES}
    faltam = set(VARIACOES.values()) - set(codigos)
    if faltam:
        raise ValueError(f"variações apontam para bairros que não existem: {sorted(faltam)}")
    pats = padroes(oficiais)
    r = mat[mat["sigla"] == SIGLA]
    linhas = []
    for m in r.itertuples():
        bairros = casar(m.ementa, pats, nomes)
        base = {"id_materia": m.id_materia, "ano": m.ano, "data_apresentacao": m.data_apresentacao,
                "n_bairros": len(bairros), "temas": "; ".join(temas(m.ementa)), "orgao": orgao(m.ementa),
                "autores_ids": m.autores_ids, "link_sapl": m.link_sapl}
        for b in bairros or [None]:
            linhas.append({**base, "nm_bairro": b, "cd_bairro": codigos.get(b)})
    return pd.DataFrame(linhas)


def main() -> None:
    mat = pd.read_parquet(SAIDA / "materias.parquet")
    rb = requerimentos_bairros(mat)
    rb.to_parquet(SAIDA / "requerimentos_bairros.parquet", index=False)
    por_req = rb.drop_duplicates("id_materia")
    n = len(por_req)
    resumo = {
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "requerimentos": n,
        "com_um_bairro": int((por_req["n_bairros"] == 1).sum()),
        "com_mais_de_um_bairro": int((por_req["n_bairros"] > 1).sum()),
        "sem_bairro": int((por_req["n_bairros"] == 0).sum()),
        "com_tema": int((por_req["temas"] != "").sum()),
        "com_orgao": int(por_req["orgao"].notna().sum()),
        "regras": {
            "bairro": ("nomes oficiais do IBGE 2022 e variações do próprio nome; nomes ambíguos só com "
                       "contexto de endereço; comunidades e loteamentos não são ligados a bairro"),
            "tema": "palavras-chave; um pedido pode ter mais de um tema",
            "orgao": "primeira sigla de órgão citada no texto",
            "variacoes": VARIACOES,
            "ambiguos": sorted(AMBIGUOS),
            "precisao_amostra": "59 de 60 requerimentos conferidos à mão com o bairro certo (issue #48)",
        },
    }
    (SAIDA / "metadados_pedidos.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False) + "\n",
                                                   encoding="utf-8")
    print(f"{n:,} requerimentos: {resumo['com_um_bairro']:,} com um bairro "
          f"({100 * resumo['com_um_bairro'] / n:.1f}%), {resumo['sem_bairro']:,} sem bairro")


if __name__ == "__main__":
    main()
