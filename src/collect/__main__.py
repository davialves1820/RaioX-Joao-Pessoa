"""Roda todas as coletas: python -m src.collect [--force]"""

import argparse

from src.collect import geodata_jp, ibge_censo2010, ibge_censo2022

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--force", action="store_true", help="rebaixa mesmo se o arquivo já existir")
force = p.parse_args().force

ibge_censo2022.main(force)
ibge_censo2010.main(force)
geodata_jp.main(force)
