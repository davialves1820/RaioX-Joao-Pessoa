"""Testes da presença pelas atas e dos votos nas comissões (src/process/camara_sessoes.py)."""

import json

import pandas as pd
import pytest

from src.config import DATA_PROCESSED
from src.process import camara_sessoes as cs

P = DATA_PROCESSED / "camara"

# Vereadores com os nomes como estão no SAPL (abreviados ou diferentes dos da ata, de propósito)
VER = pd.DataFrame([
    (1, "Dinho", "Valdir José Dowsley"), (2, "Marcos Henriques", "Marcos Henriques e Silva"),
    (3, "Mô Lima", "Mô Lima"), (4, "Raoni Mendes", "Raoni Barreto Mendes"),
    (5, "Fabíola Rezende", "Fabíola Levi Meira Rezende do Carmo"), (6, "Tarcísio Jardim", "Paulo Tarcísio Pessoa"),
    (7, "Guga Pet", "Carlos Gustavo Gomes de Oliveira"), (8, "Chico do Sindicato", "Francisco Henrique da Silva"),
    (9, "Eliza Virgínia", "Eliza Virgínia de  Souza Fernandes"), (10, "Fábio Lopes", "Fábio Lopes"),
], columns=["id_parlamentar", "nome_parlamentar", "nome_completo"])

# Trechos reais de atas (sessões 1622, 1881, 993 e 719), encurtados
ATA = (
    "Composição da mesa na abertura dos trabalhos Presidente Vereador Marcos Henriques e Silva (PT) "
    "Primeiro-Secretário ad-hoc Vereador Valdir José Dowsley – Dinho (PSD) Lista de vereadores presentes em "
    "plenário Vereador Marcos Henriques e Silva (PT) Vereador Moisés Figueiredo Ferreira Lima – Mô Lima Vereador "
    "Raoni Barreto Mendes (DC) Vereador Fábio Nóbrega Lopes (PL) Lista de vereadores presentes de forma virtual "
    "Vereadora Eliza Virgínia de Souza Fernandes (PP) Ausentes com justificativa: Vereadora Fabíola Levi Meira – "
    "Fabíola Rezende (PSB) e Vereador Paulo Tarcísio Pessoa Jardim (PATRIOTA) Ausentes: Vereadores Carlos "
    "Gustavo Gomes de Oliveira – Guga Pet (PP), Francisco Henrique da Silva – Chico do Sindicato (AVANTE). "
    "1 CÓPIA Estado da Paraíba Câmara Municipal de João Pessoa Casa Napoleão Laureano NÚCLEO DE REDAÇÃO DE ATAS "
    "ABERTURA Às 10h04, o Sr. Presidente disse: “Sob a proteção de Deus”. O vereador Guga Pet chegou depois."
)


def test_presenca_da_ata():
    sit, sem, conflitos = cs.presenca_da_ata(ATA, VER)
    assert not sem and not conflitos
    assert sit == {2: "Presente", 1: "Presente", 3: "Presente", 4: "Presente", 10: "Presente",
                   9: "Presente (virtual)", 5: "Ausente com justificativa", 6: "Ausente com justificativa",
                   7: "Ausente", 8: "Ausente"}


def test_bloco_termina_no_horario_sem_titulo_abertura():
    sem_titulo = ATA.replace("ABERTURA ", "")
    assert cs.presenca_da_ata(sem_titulo, VER)[0] == cs.presenca_da_ata(ATA, VER)[0]


def test_nome_desconhecido_e_situacao_dupla_sao_apontados():
    sit, sem, _ = cs.presenca_da_ata(ATA.replace("Raoni Barreto Mendes", "Fulano Beltrano Sicrano"), VER)
    assert sem == ["Fulano Beltrano Sicrano"] and 4 not in sit
    dupla = ATA.replace("Ausentes: Vereadores", "Ausentes: Vereador Raoni Barreto Mendes (DC), Vereadores")
    assert cs.presenca_da_ata(dupla, VER)[2] == [4]


def test_cadeiras():
    ver = pd.read_csv(P / "vereadores.csv")
    assert cs.cadeiras(ver) == {18: 27, 19: 29}


def test_saidas_consistentes():
    atas = pd.read_csv(P / "atas_presenca.csv")
    pres = pd.read_parquet(P / "presencas.parquet")
    meta = json.loads((P / "metadados_sessoes.json").read_text(encoding="utf-8"))
    ver = pd.read_csv(P / "vereadores.csv")
    assert atas["id_sessao"].is_unique and len(atas) == meta["atas_lidas"]
    assert atas["conferida"].sum() == meta["atas_conferidas"] and atas["conferida"].mean() >= 0.85
    assert (atas["conferida"] == atas["motivo"].isna()).all()
    # só atas conferidas, cada uma com um vereador por cadeira, cada vereador uma vez
    assert set(pres["id_sessao"]) == set(atas.loc[atas["conferida"], "id_sessao"])
    por_ata = pres.groupby("id_sessao").agg(n=("id_parlamentar", "size"), u=("id_parlamentar", "nunique"),
                                            leg=("legislatura", "first"))
    assert (por_ata["n"] == por_ata["u"]).all()
    assert (por_ata["n"] == por_ata["leg"].map({int(k): v for k, v in meta["cadeiras"].items()})).all()
    assert pres["situacao"].isin(cs.SITUACOES).all()
    # cada vereador listado tem mandato na legislatura da sessão
    mandatos = set(zip(ver["id_parlamentar"], ver["legislatura"]))
    assert all(par in mandatos for par in zip(pres["id_parlamentar"], pres["legislatura"]))


def test_votos_das_comissoes():
    votos = pd.read_parquet(P / "votos_comissoes.parquet")
    meta = json.loads((P / "metadados_sessoes.json").read_text(encoding="utf-8"))
    assert len(votos) == meta["votos_comissoes"] and votos["id_votacao"].nunique() == meta["votacoes_comissoes"]
    assert votos["sigla_comissao"].notna().all() and votos["comissao"].notna().all()
    assert votos["voto"].isin(["Sim", "Não", "Abstenção", "Não Votou"]).all()
    assert not votos.duplicated(["id_votacao", "id_parlamentar"]).any()
    assert votos["id_materia"].isna().sum() == meta["votos_sem_materia"] <= 0.01 * len(votos)


@pytest.mark.parametrize("arquivo", ["sessoes_video.csv"])
def test_video(arquivo):
    v = pd.read_csv(P / arquivo)
    assert v["id_sessao"].is_unique and v["url_video"].str.startswith("http").all()
