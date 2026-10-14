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

# --- Módulo "Para onde vai o dinheiro" (despesas da Prefeitura, TCE-PB)
DATA_INTERIM = ROOT / "data" / "interim"

# Código de João Pessoa no portal de dados abertos do TCE-PB
COD_MUNICIPIO_TCE = "095"
# Primeiro ano da série: 2009 é o primeiro com todas as unidades gestoras e com
# valor liquidado preenchido (2003-2008 ficam fora; ver README).
ANO_INICIAL_DESPESAS = 2009
# Anos com dados sabidamente incompletos no TCE-PB: exibidos com aviso e
# excluídos das comparações entre anos.
ANOS_INCOMPLETOS_DESPESAS = {2016: "dados incompletos no TCE-PB (só Prefeitura e Câmara; −42% frente ao SICONFI)"}
# Conferência com o SICONFI (despesa empenhada declarada ao Tesouro, DCA Anexo I-D)
TOLERANCIA_SICONFI = 0.002
EXCECOES_SICONFI = {
    2016: "arquivo do TCE-PB incompleto (−42%)",
    2020: "TCE-PB soma 3,1% a mais que o SICONFI; diferença não explicada pelas fontes disponíveis",
}
