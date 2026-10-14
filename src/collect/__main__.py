"""Roda todas as coletas: python -m src.collect [--force] [--atualizar]

--force      rebaixa todos os arquivos
--atualizar  rebaixa só o que muda com o tempo (despesas do ano corrente, IPCA, população)
"""

import argparse

from src.collect import geodata_jp, ibge_censo2010, ibge_censo2022, ibge_sidra, siconfi, tce_pb

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--force", action="store_true", help="rebaixa mesmo se o arquivo já existir")
p.add_argument("--atualizar", action="store_true", help="rebaixa o que muda com o tempo")
a = p.parse_args()

ibge_censo2022.main(a.force)
ibge_censo2010.main(a.force)
geodata_jp.main(a.force)
tce_pb.main(a.force, a.atualizar)
siconfi.main(a.force)
ibge_sidra.main(a.force, a.atualizar)
