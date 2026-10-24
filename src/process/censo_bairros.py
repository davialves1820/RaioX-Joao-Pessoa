"""Censo 2022 por bairro: rendimento, saneamento e crianças por faixa de idade.

Usa as tabelas do IBGE já agregadas por bairro (em João Pessoa não há valores sigilosos "X" nelas;
nas tabelas por setor há, em setores pequenos, e somar setores deixaria pessoas de fora). Se
aparecer um "X", o valor fica vazio e é contado em metadados (nunca estimado).

Saída: data/processed/censo_bairros.csv (+ metadados em data/processed/censo_bairros_meta.json).

Uso: python -m src.process.censo_bairros
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd

from src.config import COD_MUNICIPIO, DATA_PROCESSED, DATA_RAW

PASTA = DATA_RAW / "ibge_censo2022"
ARQ = {
    "demografia": "Agregados_por_bairros_demografia_BR.zip",
    "domicilio1": "Agregados_por_bairros_caracteristicas_domicilio1_BR_20261021.zip",
    "domicilio2": "Agregados_por_bairros_caracteristicas_domicilio2_BR_20250417.zip",
    "renda": "Agregados_por_bairros_renda_responsavel_BR_20260508_csv.zip",
}

# coluna de saída -> (tabela, variável do IBGE, descrição)
VARIAVEIS = {
    "domicilios": ("domicilio1", "V00001", "Domicílios particulares permanentes ocupados"),
    "dom_agua_rede": ("domicilio2", "V00111", "... que utilizam a rede geral de distribuição de água"),
    "dom_esgoto_rede_direto": ("domicilio2", "V00309", "... com esgoto na rede geral ou pluvial"),
    "dom_esgoto_fossa_rede": ("domicilio2", "V00310", "... com esgoto em fossa séptica ou fossa filtro ligada à rede"),
    "dom_lixo_coletado_porta": ("domicilio2", "V00397", "... com lixo coletado no domicílio por serviço de limpeza"),
    "dom_lixo_cacamba": ("domicilio2", "V00398", "... com lixo depositado em caçamba de serviço de limpeza"),
    "responsaveis": ("renda", "V06001", "Pessoas responsáveis por domicílios particulares permanentes ocupados"),
    "renda_media": ("renda", "V06004", "Rendimento nominal médio mensal das pessoas responsáveis com rendimento"),
    "renda_mediana": ("renda", "V06006", "Rendimento nominal mediano mensal das pessoas responsáveis com rendimento"),
    "pop_0a4": ("demografia", "V01031", "Pessoas de 0 a 4 anos"),
    "pop_5a9": ("demografia", "V01032", "Pessoas de 5 a 9 anos"),
    "pop_10a14": ("demografia", "V01033", "Pessoas de 10 a 14 anos"),
    "pop_15a19": ("demografia", "V01034", "Pessoas de 15 a 19 anos"),
}


def numero(texto) -> float | None:
    """Lê um número do IBGE. A vírgula é o separador decimal, mas algumas medianas vêm com ponto
    ("6598.5"); separador de milhar não aparece nesses arquivos, e um texto com os dois é rejeitado."""
    if texto is None or pd.isna(texto):
        return None
    t = str(texto).strip()
    if t in ("", "X"):
        return None
    if "," in t and "." in t:
        raise ValueError(f"número ambíguo no arquivo do IBGE: {t!r}")
    return float(t.replace(",", "."))


def _ler(tabela: str, pasta: Path = PASTA) -> pd.DataFrame:
    with zipfile.ZipFile(pasta / ARQ[tabela]) as z:
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        d = pd.read_csv(z.open(nome), sep=";", dtype=str, encoding="latin-1")
    d = d.rename(columns={c: c.upper() for c in d.columns})
    return d[d["CD_BAIRRO"].str.startswith(COD_MUNICIPIO)].set_index("CD_BAIRRO")


def montar(pasta: Path = PASTA) -> tuple[pd.DataFrame, dict]:
    tabelas = {t: _ler(t, pasta) for t in ARQ}
    out = pd.DataFrame(index=sorted(set().union(*(t.index for t in tabelas.values()))))
    sigilosos, ausentes = {}, {}
    for col, (tab, var, _) in VARIAVEIS.items():
        bruto = tabelas[tab][var].reindex(out.index)
        sigilosos[col] = int((bruto.str.strip() == "X").sum())
        ausentes[col] = sorted(out.index[bruto.isna()].tolist())
        out[col] = bruto.map(numero)
    out["dom_esgoto_rede"] = out["dom_esgoto_rede_direto"] + out["dom_esgoto_fossa_rede"]
    out["dom_lixo_coletado"] = out["dom_lixo_coletado_porta"] + out["dom_lixo_cacamba"]
    for c in ["agua_rede", "esgoto_rede", "lixo_coletado"]:
        out[f"pct_{c}"] = (100 * out[f"dom_{c}"] / out["domicilios"]).round(1)
    out["pop_0a14"] = out[["pop_0a4", "pop_5a9", "pop_10a14"]].sum(axis=1, min_count=3)
    meta = {
        "arquivos": {t: f"ibge_censo2022/{a}" for t, a in ARQ.items()},
        "variaveis": {c: {"tabela": t, "variavel": v, "descricao": d} for c, (t, v, d) in VARIAVEIS.items()},
        "valores_sigilosos_X": sigilosos,
        "bairros_sem_linha": {c: v for c, v in ausentes.items() if v},
        "esgoto_rede": "ligado à rede: direto na rede geral ou pluvial (V00309) + fossa séptica ou fossa filtro "
                       "ligada à rede (V00310)",
        "lixo_coletado": "coletado no domicílio (V00397) + depositado em caçamba de serviço de limpeza (V00398)",
        "renda": "rendimento nominal mensal das pessoas responsáveis COM rendimento (o IBGE não inclui "
                 "responsáveis sem rendimento nessas médias e medianas); valores de 2022, sem correção",
    }
    return out.rename_axis("cd_bairro").reset_index(), meta


def main() -> None:
    df, meta = montar()
    nomes = pd.read_csv(DATA_PROCESSED / "indicadores_bairros.csv", dtype={"cd_bairro": str})[["cd_bairro", "nm_bairro"]]
    df = nomes.merge(df, on="cd_bairro", how="left")
    df.to_csv(DATA_PROCESSED / "censo_bairros.csv", index=False)
    (DATA_PROCESSED / "censo_bairros_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                                                            encoding="utf-8")
    print(df.describe().round(1).to_string())
    print(json.dumps({k: meta[k] for k in ["valores_sigilosos_X", "bairros_sem_linha"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
