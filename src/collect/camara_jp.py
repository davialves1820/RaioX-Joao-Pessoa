"""Coleta: leis municipais de João Pessoa com os nomes oficiais dos órgãos (SAPL da Câmara Municipal).

O arquivo de despesas do TCE-PB só traz a sigla de cada órgão ("SEDEC - AÇÕES DE GOVERNO"). Os
nomes por extenso vêm de leis publicadas no SAPL da Câmara (https://sapl.joaopessoa.pb.leg.br/):

- LOA 2024 (Lei 15.066/2024): quadro por órgão, com o código ("ÓRGÃO : 10000 SECRETARIA MUNICIPAL DE
  EDUCAÇÃO E CULTURA"). É a última LOA publicada com os anexos; as de 2025 e 2026 no SAPL têm só
  o texto da lei, digitalizado.
- Leis 15.467, 15.468 e 15.469, de 20/02/2025: criam os órgãos 33, 34 e 35, que não existiam em 2024.
- Lei 15.399/2024: novo nome da secretaria das mulheres (órgão 28).

Uso: python -m src.collect.camara_jp [--force]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.collect.download import download

SAPL = "https://sapl.joaopessoa.pb.leg.br/media/sapl/public/normajuridica/"
FONTE = "Câmara Municipal de João Pessoa - SAPL (normas jurídicas)"
DOCUMENTOS = {
    "loa_2024_lei_15066.pdf": "2024/19767/lei_no_15066-2024_loa.pdf",
    "lei_15467_2025_inovacentro.pdf": "2025/22078/15.467_-_20.02.25_-_cria_a_secretaria_inovacentro_-_mp_60.pdf",
    "lei_15468_2025_sesuz.pdf": "2025/22079/15.468_-_20.02.25_-_cria_a_secretaria_de_servicos_urbanos_e_zeladoria-sesuz_-_mp_61.pdf",
    "lei_15469_2025_protecao_animal.pdf": "2025/22080/15.469_-_20.02.25_-_cria_a_secretaria_de_cuidado_e_protecao_animal_-_mp_64.pdf",
    "lei_15399_2024_mulheres.pdf": "2024/21947/15.399_-_11.12.24_-_altera_lei_11.902_transforma_secretaria_extraordinaria_politicas_publicas_mulheres.pdf",
}


def main(force: bool = False) -> None:
    for nome, caminho in DOCUMENTOS.items():
        download(SAPL + caminho, Path("camara_jp") / nome, fonte=FONTE, force=force)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--force", action="store_true")
    main(p.parse_args().force)
