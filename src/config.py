"""Caminhos, códigos e parâmetros compartilhados pelo pipeline."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
MANIFEST = DATA_RAW / "manifest.json"

# Código IBGE do município de João Pessoa (PB)
COD_MUNICIPIO = "2507507"

# CRS projetado para cálculos de área e sobreposição (SIRGAS 2000 / UTM 25S)
CRS_METRICO = "EPSG:31985"
# CRS de saída para o app (WGS 84)
CRS_WEB = "EPSG:4326"

# Classificação de comparabilidade 2010 x 2022, pelo IoU (interseção / união)
# entre o bairro de 2010 (setores de 2010 dissolvidos) e o bairro de 2022.
IOU_COMPARAVEL = 0.90
IOU_COM_RESSALVA = 0.75

# Tolerância do teste "soma dos bairros ~ total do município"
TOLERANCIA_TOTAL_MUNICIPIO = 0.01
