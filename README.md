# Raio-X dos Bairros de João Pessoa

Dashboard aberto com indicadores por bairro de João Pessoa (PB), feito a partir de dados públicos.
Esta primeira fase trata de **população** (Censos 2010 e 2022), **variação populacional** e
**densidade demográfica** nos 64 bairros do município.

O dashboard tem: mapa coroplético dos bairros (população, densidade ou variação 2010→2022),
painel de detalhe ao clicar num bairro (com a origem de cada número), ranking dos bairros que mais
cresceram e mais perderam população, tabela completa com download em CSV e uma seção sobre fontes
e limitações.

## Como rodar

Requer Python 3.11+.

```bash
pip install -r requirements-dev.txt
python -m src.collect          # baixa os dados brutos para data/raw/ (reexecutável; --force rebaixa)
python -m src.process.build    # gera data/processed/
pytest                         # testes do pipeline e das funções do app
streamlit run streamlit_app.py # abre o dashboard em http://localhost:8501
```

### Deploy no Streamlit Community Cloud

1. Em [share.streamlit.io](https://share.streamlit.io), clique em **Create app** e escolha este repositório e a branch.
2. Em *Main file path*, use `streamlit_app.py` (é o padrão).
3. Em *Advanced settings*, escolha Python 3.11 ou superior.

O app lê apenas `data/processed/`, que está versionado; não é preciso rodar a coleta no deploy.

A coleta pode ser rodada quantas vezes quiser: um arquivo já baixado não é baixado de novo,
downloads interrompidos não deixam arquivos pela metade e cada arquivo fica registrado em
`data/raw/manifest.json` com URL, data de download e SHA-256. Os dados brutos não ficam no git
(são ~38 MB); os processados ficam, porque o app usa só eles.

## Estrutura

```
data/raw/          dados baixados, sem alteração (só o manifest.json é versionado)
data/processed/    dados limpos e prontos para o app
src/collect/       um script de download por fonte
src/process/       leitura, junções e cálculo dos indicadores (build.py orquestra)
src/app/           código do Streamlit (app.py: interface; dados.py: carga, ranking, formatação)
notebooks/         exploração inicial das fontes
tests/             testes do pipeline
```

## Fontes

Todos os arquivos foram baixados em **14/10/2026**. A data exata (UTC), a URL e o SHA-256 de cada
arquivo estão em [`data/raw/manifest.json`](data/raw/manifest.json).

| Dado | Origem | Arquivo | Uso |
|---|---|---|---|
| População e área por bairro, 2022 | IBGE, Censo 2022, Agregados por Setores Censitários | `Agregados_por_bairros_basico_BR_20260520.zip` | `v0001` (Total de pessoas), `v0002` (domicílios), `AREA_KM2` |
| População do município, 2022 | IBGE, idem | `Agregados_por_municipios_basico_BR_20260520.zip` | `v0001`, só para validação |
| Limites dos bairros, 2022 | IBGE, malha de bairros com atributos | `PB_bairros_CD2022.gpkg` | geometria do mapa |
| Dicionário de dados 2022 | IBGE | `dicionario_de_dados_agregados_por_setores_censitarios_20260520.xlsx` | referência |
| População por setor, 2010 | IBGE, Censo 2010, Resultados do Universo por setor | `PB_20260615.zip` | `Domicilio02` V001 somado por `Cod_bairro` do `Basico` |
| Setores censitários, 2010 | IBGE, malha de setores 2010 | `pb_setores_censitarios.zip` | limites de 2010, para medir mudanças de limite |
| Limites dos bairros (Prefeitura) | Filipeia/PMJP via [paulovitorweb/geodata-jp](https://github.com/paulovitorweb/geodata-jp) (commit `76f128b`) | `bairros.geojson` | só para a tabela de correspondência de nomes |

URLs base: `https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/`,
`https://ftp.ibge.gov.br/Censos/Censo_Demografico_2010/Resultados_do_Universo/Agregados_por_Setores_Censitarios/`
e `https://geoftp.ibge.gov.br/.../censo_2010/setores_censitarios_shp/pb/`.

### Limitações de cada fonte

**IBGE, Censo 2022, tabela por bairro**
- É a tabela oficial do IBGE por bairro; não somamos setores. Em João Pessoa não há valores sigilosos ("X").
- 3.143 pessoas (0,38% do município) moram em áreas que o IBGE não atribui a nenhum bairro. Por isso a
  soma dos bairros (830.789) é menor que o total do município (833.932).
- O IBGE inclui a data de revisão no nome do arquivo (`_20260520`). Se o arquivo for substituído no FTP,
  a URL antiga deixa de existir e é preciso atualizar `src/collect/ibge_censo2022.py`.

**IBGE, Censo 2010, setores**
- Não existe tabela oficial por bairro: a população de cada bairro é a soma dos seus setores
  (variável V001 de `Domicilio02`, moradores em domicílios particulares e coletivos). A soma de todos os
  setores do município é exatamente o total oficial (723.515).
- 4.596 pessoas (0,64%) estão em 14 setores sem bairro ("JOÃO PESSOA (demais setores)").
- Os bairros de 2010 são os da época: alguns mudaram de limite até 2022 (ver *Comparabilidade*).

**Malha de bairros do IBGE 2022 (geometria do mapa)**
- É o território exato em que a população foi contada, por isso foi escolhida no lugar do Filipeia.
- Cobre 167,8 km²; o município tem 210,0 km². A diferença são áreas fora de bairros.
- Para o mapa, a geometria foi simplificada com tolerância de 5 m, mantendo os bairros encaixados
  (sem buracos nem sobreposições). A densidade usa a área publicada pelo IBGE (`AREA_KM2`), não a
  área da geometria simplificada.

**Filipeia via geodata-jp**
- O repositório **não declara licença**. O dado de origem é do portal público da Prefeitura
  (filipeia.joaopessoa.pb.gov.br), mas o arquivo derivado não tem termos de redistribuição explícitos.
  Por isso não é usado no mapa, só na tabela de correspondência; o arquivo não é versionado aqui.
- Os limites de vários bairros diferem dos do IBGE (ver abaixo). O campo `densidade` do arquivo está
  quase todo vazio ou inválido e não é usado.
- O portal Filipeia respondeu 403 ao acesso automatizado em 14/10/2026.

## Metodologia

| Indicador | Cálculo |
|---|---|
| População 2022 | `v0001` da tabela por bairro do IBGE |
| População 2010 | soma de `Domicilio02` V001 dos setores com o mesmo `Cod_bairro` |
| Variação absoluta | `pop_2022 − pop_2010` |
| Variação percentual | `100 × (pop_2022 − pop_2010) / pop_2010` |
| Densidade 2022 | `pop_2022 / AREA_KM2` (hab/km²) |

A origem de cada coluna também está em `data/processed/metadados.json`.

### Comparabilidade 2010 → 2022

Os códigos de bairro do IBGE são os mesmos nos dois censos (001 a 063; o 064, Mussuré, só existe em 2022),
mas alguns limites mudaram. Para cada bairro, comparamos o polígono de 2010 (setores de 2010 dissolvidos
por bairro) com o de 2022 usando IoU (área da interseção ÷ área da união; 1 = idênticos):

| IoU | Classe | No dashboard |
|---|---|---|
| ≥ 0,90 | comparável (56 bairros) | variação exibida |
| 0,75 a 0,90 | comparável com ressalva (3) | variação exibida com aviso |
| < 0,75 ou sem bairro em 2010 | não comparável (5) | variação não exibida |

- **Não comparáveis:** Alto do Céu (IoU 0,42; área passou de 2,5 para 6,0 km²), Indústrias (0,46),
  Gramame (0,51; área dobrou, de 8,0 para 15,5 km²), Muçumagro (0,55) e Mussuré (não existia em 2010).
  Para eles, a variação não é calculada, porque misturaria crescimento com mudança de limite.
- **Com ressalva:** Mumbaba (0,75), Roger (0,80) e Barra de Gramame (0,83).

Os cortes 0,90 e 0,75 são uma escolha de projeto, configurável em `src/config.py`.

## Correspondência de nomes e casos ambíguos

A chave do projeto é o código IBGE do bairro (`cd_bairro`, 10 dígitos), igual em 2010 e 2022.
`data/processed/crosswalk_bairros.csv` liga cada bairro IBGE ao bairro Filipeia de maior sobreposição
(os 64 se correspondem um a um) e registra as divergências na coluna `observacoes`:

- **Nomes diferentes:** Estados × BAIRRO DOS ESTADOS; Indústrias × BAIRRO DAS INDUSTRIAS;
  Ipês × BAIRRO DOS IPÊS; Roger × RÓGER; Ernani Sátiro × ERNANI SATIRO.
- **Grafia de 2010:** o IBGE 2010 grafa "Mucumago"; em 2022, "Muçumagro" (mesmo código, 041).
- **Códigos:** os códigos do Filipeia não são os do IBGE a partir do 33 (o Filipeia pula o 33), e os
  cinco bairros do sul (Barra de Gramame, Costa do Sol, Gramame, Mumbaba, Mussuré) têm código "XX" no Filipeia.
- **Limites IBGE × Filipeia muito diferentes:** Mussuré (IoU 0,17; 2,6 × 14,9 km²),
  Mumbaba (0,21; 3,0 × 14,0 km²), Alto do Céu (0,41), Muçumagro (0,48), Indústrias (0,69).
  Ao cruzar dados municipais (próximas fases) com a população do IBGE, esses bairros exigem cuidado.

## Dados processados

| Arquivo | Conteúdo |
|---|---|
| `indicadores_bairros.csv` | uma linha por bairro: `cd_bairro`, `nm_bairro`, `area_km2`, `pop_2022`, `domicilios_2022`, `densidade_2022`, `nm_bairro_2010`, `pop_2010`, `setores_2010`, `var_abs`, `var_pct`, `iou_limites_2010_2022`, `area_km2_2010_calc`, `comparabilidade` |
| `bairros_jp.geojson` | polígonos dos bairros (EPSG:4326) com `cd_bairro` e `nm_bairro` |
| `crosswalk_bairros.csv` | nomes IBGE 2022, IBGE 2010 e Filipeia, IoUs e observações |
| `totais_municipio.csv` | total do município × soma dos bairros, por ano |
| `metadados.json` | origem de cada coluna, parâmetros e manifesto dos arquivos brutos |

## Decisões de visualização

- **Mapa:** Plotly (`Choroplethmap`, base CARTO/OpenStreetMap, sem token). População e densidade usam
  uma escala sequencial de um só tom (azul, claro → escuro). A variação usa uma escala divergente
  vermelho (perda) ↔ cinza (zero) ↔ azul (ganho), que satura em ±60% para que as perdas, que vão até
  −34%, não fiquem apagadas ao lado de ganhos de até +173%; o valor exato aparece no tooltip.
  Bairros não comparáveis ficam sem cor e com contorno escuro.
- **Ranking:** exclui bairros não comparáveis e, por padrão, bairros com menos de 1.000 habitantes em
  2010 (ajustável no app de 0 a 5.000). Sem esse corte, Barra de Gramame (347 → 802 pessoas, +131%)
  entraria no topo do ranking percentual. Bairros comparáveis com ressalva aparecem marcados com †.
- As cores foram checadas com um validador de paleta (contraste e separação para daltonismo).

## Testes

`pytest` verifica, entre outras coisas: soma dos bairros a até 1% do total do município (2010 e 2022),
nenhum bairro sem geometria (e geometrias válidas, sem sobreposição), nenhuma população negativa,
consistência da variação e da densidade, e que valores sigilosos do IBGE ("X") interrompem o pipeline
em vez de serem estimados.

## Próximas fases

Serviços públicos (escolas/INEP, saúde/CNES, praças, parques, ciclovias, comunidades), outros
indicadores do Censo 2022 (renda, saneamento, faixa etária) e indicadores de acesso por bairro.
