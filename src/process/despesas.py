"""Processa as despesas (empenhos) de João Pessoa declaradas ao TCE-PB.

Entradas (data/raw): tce_pb/despesas-AAAA.zip, siconfi/*.json, ibge_sidra/*.json e,
do módulo de bairros, data/processed/indicadores_bairros.csv e totais_municipio.csv.

Saídas:
- data/interim/empenhos.parquet (não versionado): um empenho por linha, já limpo,
  com CPF mascarado e sem nome de pessoa física.
- data/processed/despesas/: tabelas agregadas para o dashboard (ver README).

Uso: python -m src.process.despesas
"""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src.collect.download import load_manifest
from src.config import (
    ANO_INICIAL_DESPESAS,
    ANOS_INCOMPLETOS_DESPESAS,
    DATA_INTERIM,
    DATA_PROCESSED,
    DATA_RAW,
    EXCECOES_SICONFI,
    TOLERANCIA_SICONFI,
)
from src.process.despesas_bairros import bairros_citados, _padroes
from src.process.despesas_regras import (
    COLUNAS,
    UNIDADES_GESTORAS,
    centavos,
    data_iso,
    formatar_cnpj,
    grupo_modalidade,
    limpar_historico,
    mascarar_cpf,
    mascarar_cpf_no_texto,
    normalizar,
    tipo_documento,
)

RAW_TCE = DATA_RAW / "tce_pb"
SAIDA = DATA_PROCESSED / "despesas"

# Nomes oficiais das funções de governo (Portaria MOG 42/1999). O TCE-PB publica
# alguns com erro de digitação ("Encargos Especias") e o código com ou sem zero.
FUNCOES = {
    1: "Legislativa", 2: "Judiciária", 3: "Essencial à Justiça", 4: "Administração",
    5: "Defesa Nacional", 6: "Segurança Pública", 7: "Relações Exteriores",
    8: "Assistência Social", 9: "Previdência Social", 10: "Saúde", 11: "Trabalho",
    12: "Educação", 13: "Cultura", 14: "Direitos da Cidadania", 15: "Urbanismo",
    16: "Habitação", 17: "Saneamento", 18: "Gestão Ambiental", 19: "Ciência e Tecnologia",
    20: "Agricultura", 21: "Organização Agrária", 22: "Indústria", 23: "Comércio e Serviços",
    24: "Comunicações", 25: "Energia", 26: "Transporte", 27: "Desporto e Lazer",
    28: "Encargos Especiais", 99: "Reserva de Contingência", 0: "Não informada",
}


# --- leitura


def ler_ano(ano: int) -> pd.DataFrame:
    """CSV do ano, com as 40 colunas renomeadas para o layout atual (todas como texto)."""
    caminho = RAW_TCE / f"despesas-{ano}.zip"
    with zipfile.ZipFile(caminho) as z:
        (nome,) = [n for n in z.namelist() if n.endswith(".csv")]
        with z.open(nome) as f:
            df = pd.read_csv(
                f, sep=";", dtype=str, encoding="utf-8-sig", keep_default_na=False, quotechar='"'
            )
    if len(df.columns) != len(COLUNAS):
        raise ValueError(f"{caminho.name}: esperava {len(COLUNAS)} colunas, achei {len(df.columns)}")
    df.columns = COLUNAS
    df.insert(0, "ano", ano)
    df.insert(1, "arquivo_origem", caminho.name)
    return df


def transformar(df: pd.DataFrame) -> pd.DataFrame:
    """Tipos, nomes padronizados, classificação do credor e máscara de CPF."""
    out = pd.DataFrame(
        {
            "ano": df["ano"],
            "arquivo_origem": df["arquivo_origem"],
            "cod_ug": df["codigo_unidade_gestora"].str.strip(),
            "cod_uo": df["codigo_unidade_orcamentaria"].str.strip(),
            "unidade_orcamentaria": df["descricao_unidade_orcamentaria"].str.strip(),
            "numero_empenho": df["numero_empenho"].str.strip(),
            "data": pd.to_datetime(df["data_empenho"].map(data_iso)),
            "empenhado_c": df["valor_empenhado"].map(centavos).astype("int64"),
            "liquidado_c": df["valor_liquidado"].map(centavos).astype("int64"),
            "pago_c": df["valor_pago"].map(centavos).astype("int64"),
            "codigo_funcao": pd.to_numeric(df["codigo_funcao"].str.strip().replace("", "0")).astype(int),
            "codigo_subfuncao": pd.to_numeric(df["codigo_subfuncao"].str.strip().replace("", "0")).astype(int),
            "subfuncao": df["subfuncao"].str.strip(),
            "grupo_natureza": df["grupo_natureza_despesa"].str.strip(),
            "codigo_modalidade_aplicacao": df["codigo_modalidade_aplicacao"].str.strip(),
            "elemento_despesa": df["elemento_despesa"].str.strip(),
            "modalidade_licitacao": df["modalidade_licitacao"].str.strip(),
            "historico": df["historico"].map(limpar_historico),
        }
    )
    out["mes"] = out["data"].dt.month
    out["funcao"] = out["codigo_funcao"].map(FUNCOES)
    if out["funcao"].isna().any():
        raise ValueError(f"código de função sem nome: {sorted(out.loc[out.funcao.isna(), 'codigo_funcao'].unique())}")
    out["grupo_modalidade"] = out["modalidade_licitacao"].map(grupo_modalidade)
    out["intra"] = out["codigo_modalidade_aplicacao"] == "91"

    doc = df["cpf_cnpj"].str.strip()
    out["tipo_credor"] = [tipo_documento(d, n) for d, n in zip(doc, df["nome_credor"])]
    pj = out["tipo_credor"] == "PJ"
    out["documento"] = np.where(pj, doc, doc.map(mascarar_cpf))
    # Nome de pessoa física não segue para os dados processados
    # e o CPF que MEIs trazem no nome empresarial ("FULANO 12345678901") é mascarado
    out["nome_credor"] = np.where(pj, df["nome_credor"].str.strip().map(mascarar_cpf_no_texto), None)
    return out


def checar(e: pd.DataFrame) -> dict:
    """Checagens que interrompem o pipeline se falharem; devolve um resumo para os metadados."""
    fora = e[e["data"].dt.year != e["ano"]]
    if len(fora):
        raise ValueError(f"{len(fora)} empenhos com data fora do ano do arquivo")
    chave = ["ano", "cod_ug", "cod_uo", "numero_empenho"]
    if e.duplicated(chave).any():
        raise ValueError("empenhos duplicados pela chave (ano, UG, UO, número)")
    desconhecidas = set(e["cod_ug"]) - set(UNIDADES_GESTORAS)
    if desconhecidas:
        raise ValueError(f"unidades gestoras sem classificação: {desconhecidas}")
    essenciais = ["ano", "mes", "cod_ug", "codigo_funcao", "grupo_modalidade", "tipo_credor", "documento"]
    nulos = {c: int(e[c].isna().sum()) for c in essenciais if e[c].isna().any()}
    if nulos:
        raise ValueError(f"campos essenciais nulos: {nulos}")
    return {
        "empenhos": int(len(e)),
        "empenhos_zerados_anulados": int((e.empenhado_c == 0).sum()),
        "empenhos_valor_negativo": int((e.empenhado_c < 0).sum()),
        "credores_por_tipo": e["tipo_credor"].value_counts().to_dict(),
    }


# --- fontes auxiliares


def ler_ipca() -> pd.DataFrame:
    rows = json.loads((DATA_RAW / "ibge_sidra" / "ipca_tabela1737.json").read_text(encoding="utf-8"))[1:]
    df = pd.DataFrame({"periodo": [r["D3C"] for r in rows], "indice": [r["V"] for r in rows]})
    df = df[pd.to_numeric(df["indice"], errors="coerce").notna()]
    df["ano"] = df["periodo"].str[:4].astype(int)
    df["mes"] = df["periodo"].str[4:].astype(int)
    df["indice"] = df["indice"].astype(float)
    return df[["ano", "mes", "indice"]].sort_values(["ano", "mes"]).reset_index(drop=True)


def ler_populacao() -> pd.DataFrame:
    rows = json.loads(
        (DATA_RAW / "ibge_sidra" / "populacao_estimada_tabela6579.json").read_text(encoding="utf-8")
    )[1:]
    # Anos sem estimativa publicada (ex.: 2023) simplesmente não aparecem: não estimamos.
    est = pd.DataFrame(
        [{"ano": int(r["D3N"]), "populacao": int(r["V"])} for r in rows if r["V"].isdigit()]
    ).assign(fonte="IBGE, estimativa da população (SIDRA 6579)")
    censos = pd.read_csv(DATA_PROCESSED / "totais_municipio.csv")
    censos = pd.DataFrame(
        {"ano": censos["ano"], "populacao": censos["pop_municipio"], "fonte": "IBGE, Censo Demográfico"}
    )
    pop = pd.concat([est[~est.ano.isin(censos.ano)], censos]).sort_values("ano").reset_index(drop=True)
    return pop[["ano", "populacao", "fonte"]]


def ler_siconfi() -> pd.DataFrame:
    linhas = []
    for f in sorted((DATA_RAW / "siconfi").glob("dca-anexo-I-D-*.json")):
        ano = int(re.search(r"(\d{4})\.json$", f.name)[1])
        itens = json.loads(f.read_text(encoding="utf-8")).get("items", [])
        tot = [i["valor"] for i in itens if i["coluna"] == "Despesas Empenhadas" and i["conta"].startswith("Total Geral")]
        if tot:
            linhas.append({"ano": ano, "siconfi_empenhado": round(float(tot[0]), 2), "arquivo_siconfi": f.name})
    return pd.DataFrame(linhas)


# --- agregados


def agregar(e: pd.DataFrame, ipca: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Cubo mensal por unidade gestora, função/subfunção, modalidade e tipo de credor."""
    # Subfunção: o nome mais frequente de cada código
    nomes_sub = e.groupby("codigo_subfuncao")["subfuncao"].agg(lambda s: s.value_counts().index[0])
    dims = ["ano", "mes", "cod_ug", "intra", "codigo_funcao", "funcao", "codigo_subfuncao",
            "grupo_modalidade", "tipo_credor", "arquivo_origem"]
    cubo = (
        e.groupby(dims, as_index=False)
        .agg(empenhado_c=("empenhado_c", "sum"), liquidado_c=("liquidado_c", "sum"),
             pago_c=("pago_c", "sum"), n_empenhos=("empenhado_c", "size"))
    )
    cubo["subfuncao"] = cubo["codigo_subfuncao"].map(nomes_sub)

    # Correção pelo IPCA até o último mês publicado (mês de referência)
    ref = ipca.iloc[-1]
    idx = ipca.set_index(["ano", "mes"])["indice"]
    chave = pd.MultiIndex.from_frame(cubo[["ano", "mes"]])
    indice_mes = idx.reindex(chave).to_numpy()
    # Meses após o último IPCA publicado ficam com fator 1 (já estão em valores do período de referência)
    fator = np.where(np.isnan(indice_mes), 1.0, ref["indice"] / indice_mes)
    cubo["ipca_fator"] = fator.round(6)
    cubo["ipca_sem_indice_do_mes"] = np.isnan(indice_mes)
    for v in ["empenhado", "liquidado", "pago"]:
        cubo[v] = (cubo[f"{v}_c"] / 100).round(2)
        cubo[f"{v}_corrigido"] = (cubo[f"{v}_c"] / 100 * cubo["ipca_fator"]).round(2)
        cubo = cubo.drop(columns=f"{v}_c")
    ug = pd.DataFrame.from_dict(UNIDADES_GESTORAS, orient="index", columns=["unidade_gestora", "poder", "tipo_ug"])
    cubo = cubo.merge(ug, left_on="cod_ug", right_index=True, how="left")
    info = {"mes_referencia": f"{int(ref['ano'])}-{int(ref['mes']):02d}", "indice_referencia": float(ref["indice"])}
    return cubo, info


GRUPO_PESSOAL = "Pessoal e Encargos Sociais"
# Entidades públicas que aparecem como credor (repasses, tributos, convênios).
# Heurística pelo início do nome; serve só para separar esses credores no dashboard.
_ENTIDADE_PUBLICA = re.compile(
    r"^(?:SECRETARIA|FUNDO MUNICIPAL|FUNDO NACIONAL|FUNDO ESTADUAL|PREFEITURA|CAMARA MUNICIPAL|"
    r"MUNICIPIO DE|ESTADO DA|GOVERNO|MINISTERIO|INSTITUTO NACIONAL DO SEGURO SOCIAL|INSS|"
    r"INSTITUTO DE PREVIDENCIA|IPM|TRIBUNAL|RECEITA FEDERAL|TESOURO|SUPERINTENDENCIA|"
    r"UNIVERSIDADE FEDERAL|PODER JUDICIARIO)\b"
)


def credores_pj(e: pd.DataFrame) -> pd.DataFrame:
    """Valores por empresa (CNPJ), ano e unidade gestora.

    - Pessoas físicas não entram.
    - Folha de pagamento, encargos e benefícios (grupo "Pessoal e Encargos Sociais") não
      entram: nesses empenhos o "credor" é o próprio órgão pagador (ex.: Secretaria de
      Finanças) ou o INSS/IPM, não um fornecedor.
    - Entidades públicas que sobram (repasses, tributos) ficam marcadas em `entidade_publica`.
    """
    pj = e[(e["tipo_credor"] == "PJ") & (e["grupo_natureza"] != GRUPO_PESSOAL)]
    agg = (
        pj.groupby(["documento", "ano", "cod_ug", "arquivo_origem"], as_index=False)
        .agg(empenhado_c=("empenhado_c", "sum"), liquidado_c=("liquidado_c", "sum"),
             pago_c=("pago_c", "sum"), n_empenhos=("empenhado_c", "size"))
    )
    # nome mais recente de cada CNPJ (o mesmo CNPJ aparece com grafias diferentes)
    nome = pj.sort_values(["data"]).groupby("documento")["nome_credor"].last()
    agg["nome_credor"] = agg["documento"].map(nome)
    agg["cnpj_formatado"] = agg["documento"].map(formatar_cnpj)
    agg["entidade_publica"] = agg["nome_credor"].map(lambda n: bool(_ENTIDADE_PUBLICA.search(normalizar(n))))
    for v in ["empenhado", "liquidado", "pago"]:
        agg[v] = (agg[f"{v}_c"] / 100).round(2)
        agg = agg.drop(columns=f"{v}_c")
    return agg.rename(columns={"documento": "cnpj"})


def bairros(e: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ind = pd.read_csv(DATA_PROCESSED / "indicadores_bairros.csv", dtype={"cd_bairro": str})
    nomes = tuple(zip(ind.cd_bairro, ind.nm_bairro))
    # Filtro rápido: só textos que contêm algum dos nomes passam pelas regras completas
    qualquer = re.compile(r"\b(?:" + "|".join(re.escape(v) for _, v, _ in _padroes(nomes)) + r")\b")
    norm = e["historico"].map(normalizar)
    candidatos = norm.str.contains(qualquer)
    achados = pd.Series([set()] * len(e), index=e.index, dtype=object)
    achados[candidatos] = e.loc[candidatos, "historico"].map(lambda h: bairros_citados(h, nomes))
    n = achados.map(len)

    um = e[n == 1].assign(cd_bairro=achados[n == 1].map(lambda s: next(iter(s))))
    por_bairro = (
        um.groupby(["ano", "cd_bairro"], as_index=False)
        .agg(empenhado_c=("empenhado_c", "sum"), n_empenhos=("empenhado_c", "size"))
        .merge(ind[["cd_bairro", "nm_bairro"]], on="cd_bairro")
    )
    por_bairro["empenhado"] = (por_bairro.pop("empenhado_c") / 100).round(2)

    cob = (
        e.assign(cat=np.select([n == 1, n > 1], ["um_bairro", "varios_bairros"], "sem_bairro"))
        .pivot_table(index="ano", columns="cat", values="empenhado_c", aggfunc="sum", fill_value=0)
        .reindex(columns=["um_bairro", "varios_bairros", "sem_bairro"], fill_value=0)
    )
    cob = (cob / 100).round(2)
    cob["total"] = cob.sum(axis=1).round(2)
    cob["cobertura_pct"] = (100 * cob["um_bairro"] / cob["total"]).round(2)
    return por_bairro, cob.reset_index()


def validar_siconfi(e: pd.DataFrame) -> pd.DataFrame:
    tce = (e.groupby("ano")["empenhado_c"].sum() / 100).round(2).rename("tce_empenhado").reset_index()
    v = tce.merge(ler_siconfi(), on="ano", how="left")
    v["diferenca_pct"] = (100 * (v.tce_empenhado - v.siconfi_empenhado) / v.siconfi_empenhado).round(3)
    v["dentro_tolerancia"] = v["diferenca_pct"].abs() <= 100 * TOLERANCIA_SICONFI
    v["excecao_documentada"] = v["ano"].map(EXCECOES_SICONFI)
    return v


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    anos = sorted(
        int(re.search(r"(\d{4})", f.name)[1]) for f in RAW_TCE.glob("despesas-*.zip")
    )
    anos = [a for a in anos if a >= ANO_INICIAL_DESPESAS]
    e = pd.concat([transformar(ler_ano(a)) for a in anos], ignore_index=True)
    resumo_checagens = checar(e)
    e.to_parquet(DATA_INTERIM / "empenhos.parquet", index=False)

    ipca = ler_ipca()
    cubo, info_ipca = agregar(e, ipca)
    cubo.to_parquet(SAIDA / "despesas_cubo.parquet", index=False)
    credores_pj(e).to_parquet(SAIDA / "credores_pj.parquet", index=False)
    por_bairro, cobertura = bairros(e)
    por_bairro.to_csv(SAIDA / "bairros_citados.csv", index=False)
    cobertura.to_csv(SAIDA / "bairros_cobertura.csv", index=False)
    ler_populacao().to_csv(SAIDA / "populacao.csv", index=False)
    ipca.to_csv(SAIDA / "ipca.csv", index=False)
    validacao = validar_siconfi(e)
    validacao.to_csv(SAIDA / "validacao_siconfi.csv", index=False)

    ultimo = e["data"].max()
    manifest = load_manifest()
    meta = {
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "anos": anos,
        "ultima_data_de_empenho": ultimo.strftime("%Y-%m-%d"),
        "anos_incompletos": {str(k): v for k, v in ANOS_INCOMPLETOS_DESPESAS.items()},
        # O ano corrente está em andamento: o TCE-PB regenera o arquivo com frequência
        "ano_parcial": anos[-1] if anos[-1] >= datetime.now().year else None,
        "ipca": info_ipca,
        "checagens": resumo_checagens,
        "aviso": (
            "Valores declarados pela Prefeitura e demais órgãos municipais ao TCE-PB (SAGRES). "
            "Podem mudar após análise e auditoria do Tribunal."
        ),
        "arquivos_brutos": {
            k: v for k, v in manifest.items() if k.startswith(("tce_pb/", "siconfi/", "ibge_sidra/"))
        },
    }
    (SAIDA / "metadados.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"{len(e):,} empenhos de {anos[0]} a {anos[-1]} (último em {ultimo:%d/%m/%Y})")
    print(validacao.to_string(index=False))
    print(cobertura.to_string(index=False))


if __name__ == "__main__":
    main()
