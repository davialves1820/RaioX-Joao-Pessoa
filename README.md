# Raio-X dos Bairros de João Pessoa

Dashboard aberto, em Streamlit, com indicadores dos 64 bairros de João Pessoa (PB), feito só com
dados públicos. Cada número do site pode ser rastreado até o arquivo de origem: URL, data de download
e SHA-256 ficam em [`data/raw/manifest.json`](data/raw/manifest.json).

O site tem três páginas:

| Página | O que mostra | Fontes principais |
|---|---|---|
| [**Bairros e população**](#1-bairros-e-população) | população nos Censos 2010 e 2022, variação e densidade, com mapa, detalhe do bairro, ranking e tabela | IBGE |
| [**Serviços e acesso**](#2-serviços-públicos-e-acesso) | escolas públicas, unidades de saúde do SUS, praças, parques e matas; distância até a escola e a UBS mais próximas, área verde por morador e um índice de acesso | INEP, CNES, Prefeitura (Filipeia), OpenStreetMap, IBGE |
| [**Para onde vai o dinheiro**](#3-para-onde-vai-o-dinheiro-de-joão-pessoa) | despesas dos órgãos municipais: total por ano, por área, fornecedores, licitação e um mapa experimental | TCE-PB, SICONFI, IBGE |

## Princípios

- **Nada é inventado ou estimado.** Se uma fonte não está acessível, o dado fica de fora e isso é dito.
  Coordenadas que faltam não são adivinhadas pelo endereço.
- **Tudo é rastreável.** Cada arquivo bruto está no manifesto, e os dados processados trazem o arquivo
  de origem.
- **Nada é descartado em silêncio.** Pontos sem coordenada, fora dos bairros ou com problema são
  contados e listados.
- **A coleta é reexecutável** (`python -m src.collect`), com duas exceções exportadas à mão e documentadas:
  o Catálogo de Escolas do INEP, quando o navegador automatizado falha, e o Filipeia.
- **Linguagem neutra.** O site mostra os dados; não acusa nem dá nota a ninguém.
- **Fontes e limitações ficam visíveis no próprio site**, não só aqui.

## Como rodar

Requer Python 3.12 ou superior (as versões fixadas em `requirements.txt` não existem para o 3.11).

```bash
pip install -r requirements-dev.txt
python -m src.collect          # baixa os dados brutos para data/raw/ (ver as exceções abaixo)
python -m src.process.build    # bairros e população -> data/processed/
python -m src.process.despesas # despesas -> data/processed/despesas/ (depende do build)
python -m src.process.censo_bairros # renda, saneamento e idade por bairro -> data/processed/ (depende do build)
python -m src.process.servicos # serviços -> data/processed/servicos/ (depende do build e do censo_bairros)
pytest                         # testes do pipeline e das funções do app
streamlit run streamlit_app.py # abre o dashboard em http://localhost:8501
```

- **Arquivo já baixado não é baixado de novo** (`--force` rebaixa tudo). Downloads interrompidos não
  deixam arquivos pela metade.
- **Dados que mudam com o tempo** (despesas do ano corrente, IPCA, estimativas de população, CNES):
  rode `python -m src.collect --atualizar` e depois os passos de processamento.
- **INEP:** o Catálogo de Escolas é exportado por um navegador automatizado (Playwright + Chromium);
  para atualizar, use `python -m src.collect.inep_catalogo --force`. Se o painel mudar, o docstring do
  script explica a exportação manual.
- **Filipeia (Prefeitura):** o portal bloqueia acesso automatizado. As camadas são exportadas à mão para
  `data/raw/filipeia/` e registradas com `python -m src.collect.filipeia --registrar`; o docstring do
  script lista os arquivos.

Os dados brutos não ficam no git (são grandes e reprodutíveis); os processados ficam, porque o app usa só eles.

### Testes automáticos (CI)

O workflow [`.github/workflows/testes.yml`](.github/workflows/testes.yml) roda o `pytest` em todo PR e em
todo push na `main`, com Python 3.12 e 3.13. Ele instala só `requirements.txt` e o pytest; os testes que
dependem de `data/raw/` (não versionado) são pulados, e os demais usam `data/processed/`. Um PR com teste
quebrado aparece com o check **Testes** em vermelho.

### Atualizar as bibliotecas

`requirements.txt` fixa as versões exatas, porque o Streamlit Community Cloud instala esse arquivo a cada
deploy e uma versão nova pode quebrar o site sem mudança no código. Para atualizar:

1. Num ambiente limpo, instale as versões novas (`pip install -U` das bibliotecas listadas).
2. Rode o pipeline e `pytest`, e abra o app para conferir as três páginas.
3. Copie as versões de `pip freeze` para `requirements.txt` e abra um PR: o CI testa nas duas versões
   do Python.

### Deploy no Streamlit Community Cloud

1. Em [share.streamlit.io](https://share.streamlit.io), clique em **Create app** e escolha este
   repositório e a branch `main`.
2. Em *Main file path*, use `streamlit_app.py` (é o padrão).
3. Em *Advanced settings*, escolha Python 3.12 ou 3.13 (as versões testadas no CI). Não há segredos a configurar.

O app lê apenas `data/processed/`; não é preciso rodar a coleta no deploy. Cada push na `main`
atualiza o site.

### No celular

O Streamlit não informa a largura da tela, então o app usa o navegador (User-Agent) para reconhecer
celulares. Neles, os mapas ficam mais baixos (460 px), com zoom menor para a cidade inteira caber na
largura, e a escala de cor fica deitada no rodapé do mapa. As colunas empilham sozinhas, e a página não
rola na horizontal (conferido a 390 px de largura); só as tabelas largas rolam dentro delas.

## Estrutura

```
streamlit_app.py   entrada do Streamlit: liga as três páginas
src/collect/       um script de coleta por fonte (+ download.py, que mantém o manifesto)
src/process/       leitura, junções e cálculo dos indicadores
                   build.py (bairros e população), despesas*.py, servicos.py
src/app/           páginas: app.py + dados.py (bairros), servicos.py + dados_servicos.py,
                   despesas.py + dados_despesas.py
data/raw/          dados brutos, uma pasta por fonte (só o manifest.json é versionado)
data/interim/      tabela de empenhos linha a linha (não versionada; cerca de 40 MB)
data/processed/    dados prontos para o app (versionados)
certs/             certificado intermediário público usado na coleta do INEP
notebooks/         exploração inicial das fontes
tests/             testes do pipeline e das funções do app
```

## Fontes, em resumo

As datas exatas (UTC), as URLs e os SHA-256 de cada arquivo estão em `data/raw/manifest.json`. Os
detalhes e as limitações de cada fonte estão na seção da página que a usa.

| Fonte | Usada em | Como é obtida | Data dos dados |
|---|---|---|---|
| IBGE, Censo 2022 (bairros, setores e malhas) | as três páginas | download do FTP do IBGE | 2022 |
| IBGE, Censo 2010 (setores) | Bairros | download do FTP do IBGE | 2010 |
| IBGE, SIDRA (IPCA e estimativas de população do município) | Dinheiro | API do SIDRA | IPCA até set/2026 |
| INEP, Catálogo de Escolas | Serviços | exportação do painel por navegador automatizado | situação do Censo Escolar 2024 |
| Ministério da Saúde, CNES | Serviços | API de dados abertos | cadastros até 16/10/2026 |
| Prefeitura, Filipeia (parques, praças, quadras, bairros) | Serviços | exportação manual pelo navegador | parques: 2021; praças: intervenções até 2018 |
| OpenStreetMap (matas, áreas protegidas, 2 escolas) | Serviços (só no mapa e em 2 coordenadas) | Overpass API e API do OSM | consulta de 23/10/2026 |
| geodata-jp (cópia de camadas da Prefeitura e do INEP) | Bairros e Serviços, como apoio | download do GitHub (commit fixo) | fev/2022 |
| TCE-PB, SAGRES (empenhos) | Dinheiro | download do portal de dados abertos | 2009 a 09/10/2026 |
| Tesouro Nacional, SICONFI | Dinheiro (conferência dos totais) | API do SICONFI | 2014–2025 |

### Onde o geodata-jp ainda é usado

O [geodata-jp](https://github.com/paulovitorweb/geodata-jp) é um repositório que copiou, em fevereiro
de 2022, camadas do Filipeia (Prefeitura) e do Catálogo de Escolas do INEP. O repositório **não declara
licença**, por isso ele só entra onde não há alternativa oficial acessível, e sempre conferido:

| Uso | Por que não a fonte oficial | Como é conferido |
|---|---|---|
| **Correspondência de nomes** entre os bairros do IBGE e os da Prefeitura (`crosswalk_bairros.csv`); não aparece no mapa | na época, o Filipeia não era acessível | — (pode ser trocado pelo `bairros.zip` oficial do Filipeia, de 2026) |
| **Contornos das 214 praças** (área verde da página de serviços) | o Filipeia oferece só a tabela das praças, sem o shapefile | o pipeline exige nome e área idênticos aos da tabela oficial, senão para; 160 das 162 praças com código de quadra ficam na quadra indicada pelo cadastro de 2026 |
| **Coordenadas de 3 escolas** que o INEP publica sem localização | o INEP atual não tem a coordenada | só coordenadas que não se repetem em outras escolas (o geodata-jp põe 12 escolas num mesmo ponto genérico, descartado) |

Os parques, que antes também vinham do geodata-jp, agora vêm do shapefile oficial do Filipeia, idêntico ao anterior.

---

## 1. Bairros e população

População dos 64 bairros nos Censos 2010 e 2022, variação 2010→2022 e densidade. O site tem mapa
coroplético (população, densidade ou variação), painel de detalhe do bairro com a origem de cada
número, ranking dos bairros que mais cresceram e mais perderam população e tabela completa com
download em CSV. Gerado por `python -m src.process.build`.

### Fontes

Arquivos baixados em 14/10/2026.

| Dado | Origem | Arquivo | Uso |
|---|---|---|---|
| População e área por bairro, 2022 | IBGE, Censo 2022, Agregados por Setores Censitários | `Agregados_por_bairros_basico_BR_20260520.zip` | `v0001` (total de pessoas), `v0002` (domicílios), `AREA_KM2` |
| População do município, 2022 | IBGE, idem | `Agregados_por_municipios_basico_BR_20260520.zip` | `v0001`, só para validação |
| Limites dos bairros, 2022 | IBGE, malha de bairros com atributos | `PB_bairros_CD2022.gpkg` | geometria do mapa |
| Dicionário de dados 2022 | IBGE | `dicionario_de_dados_agregados_por_setores_censitarios_20260520.xlsx` | referência |
| População por setor, 2010 | IBGE, Censo 2010, Resultados do Universo por setor | `PB_20260615.zip` | `Domicilio02` V001 somado por `Cod_bairro` do `Basico` |
| Setores censitários, 2010 | IBGE, malha de setores 2010 | `pb_setores_censitarios.zip` | limites de 2010, para medir mudanças de limite |
| Limites dos bairros (Prefeitura) | Filipeia, via geodata-jp (commit `76f128b`) | `bairros.geojson` | só para a tabela de correspondência de nomes |

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
- É o território exato em que a população foi contada; por isso é a malha do mapa em todo o site.
- Cobre 167,8 km² dos 210,0 km² do município (soma de `AREA_KM2` dos setores de 2022). A diferença são
  áreas fora de bairros.
- Para o mapa, a geometria foi simplificada com tolerância de 5 m, mantendo os bairros encaixados
  (sem buracos nem sobreposições). A densidade usa a área publicada pelo IBGE (`AREA_KM2`), não a
  área da geometria simplificada.

**Bairros da Prefeitura (geodata-jp)**
- Os limites de vários bairros diferem dos do IBGE (ver *Correspondência de nomes*). O campo
  `densidade` do arquivo está quase todo vazio ou inválido e não é usado.

### Metodologia

| Indicador | Cálculo |
|---|---|
| População 2022 | `v0001` da tabela por bairro do IBGE |
| População 2010 | soma de `Domicilio02` V001 dos setores com o mesmo `Cod_bairro` |
| Variação absoluta | `pop_2022 − pop_2010` |
| Variação percentual | `100 × (pop_2022 − pop_2010) / pop_2010` |
| Densidade 2022 | `pop_2022 / AREA_KM2` (hab/km²) |

A origem de cada coluna também está em `data/processed/metadados.json`.

#### Comparabilidade 2010 → 2022

Os códigos de bairro do IBGE são os mesmos nos dois censos (001 a 063; o 064, Mussuré, só existe em
2022), mas alguns limites mudaram. Para cada bairro, comparamos o polígono de 2010 (setores de 2010
dissolvidos por bairro) com o de 2022 usando IoU (área da interseção ÷ área da união; 1 = idênticos):

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

#### Correspondência de nomes e casos ambíguos

A chave do projeto é o código IBGE do bairro (`cd_bairro`, 10 dígitos), igual em 2010 e 2022.
`data/processed/crosswalk_bairros.csv` liga cada bairro IBGE ao bairro da Prefeitura de maior
sobreposição (os 64 se correspondem um a um) e registra as divergências na coluna `observacoes`:

- **Nomes diferentes:** Estados × BAIRRO DOS ESTADOS; Indústrias × BAIRRO DAS INDUSTRIAS;
  Ipês × BAIRRO DOS IPÊS; Roger × RÓGER; Ernani Sátiro × ERNANI SATIRO.
- **Grafia de 2010:** o IBGE 2010 grafa "Mucumago"; em 2022, "Muçumagro" (mesmo código, 041).
- **Códigos:** os códigos da Prefeitura não são os do IBGE a partir do 33 (a Prefeitura pula o 33), e os
  cinco bairros do sul (Barra de Gramame, Costa do Sol, Gramame, Mumbaba, Mussuré) têm código "XX" nela.
- **Limites IBGE × Prefeitura muito diferentes:** Mussuré (IoU 0,17; 2,6 × 14,9 km²),
  Mumbaba (0,21; 3,0 × 14,0 km²), Alto do Céu (0,41), Muçumagro (0,48), Indústrias (0,69).
  Ao cruzar dados da Prefeitura com a população do IBGE, esses bairros exigem cuidado.

### Decisões de visualização

- **Mapa:** Plotly (`Choroplethmap`, base CARTO/OpenStreetMap, sem token). População e densidade usam
  uma escala sequencial de um só tom (azul, claro → escuro). A variação usa uma escala divergente
  vermelho (perda) ↔ cinza (zero) ↔ azul (ganho), que satura em ±60% para que as perdas, que vão até
  −34%, não fiquem apagadas ao lado de ganhos de até +173%; o valor exato aparece no tooltip.
  Bairros não comparáveis ficam sem cor e com contorno escuro.
- **Ranking:** exclui bairros não comparáveis e, por padrão, bairros com menos de 1.000 habitantes em
  2010 (ajustável no app de 0 a 5.000). Sem esse corte, Barra de Gramame (347 → 802 pessoas, +131%)
  entraria no topo do ranking percentual. Bairros comparáveis com ressalva aparecem marcados com †.
- As cores foram checadas com um validador de paleta (contraste e separação para daltonismo).

### Dados processados (`data/processed/`)

| Arquivo | Conteúdo |
|---|---|
| `indicadores_bairros.csv` | uma linha por bairro: `cd_bairro`, `nm_bairro`, `area_km2`, `pop_2022`, `domicilios_2022`, `densidade_2022`, `nm_bairro_2010`, `pop_2010`, `setores_2010`, `var_abs`, `var_pct`, `iou_limites_2010_2022`, `area_km2_2010_calc`, `comparabilidade` |
| `bairros_jp.geojson` | polígonos dos bairros (EPSG:4326) com `cd_bairro` e `nm_bairro` |
| `crosswalk_bairros.csv` | nomes IBGE 2022, IBGE 2010 e Prefeitura, IoUs e observações |
| `totais_municipio.csv` | total do município × soma dos bairros, por ano |
| `metadados.json` | origem de cada coluna, parâmetros e manifesto dos arquivos brutos |

---

## 2. Serviços públicos e acesso

Escolas públicas, unidades de saúde do SUS, praças e parques por bairro, com distância até a
escola e a UBS/USF mais próximas, área verde por habitante e um índice simples de acesso. Matas e
áreas protegidas aparecem no mapa, fora do índice. Gerado por `python -m src.process.servicos`.

### No dashboard

- **Mapa:** a cor dos bairros mostra o índice de acesso, a distância até a escola ou a UBS/USF, a área
  verde por morador ou os moradores por equipamento. As camadas se ligam e desligam:
  - pontos: escolas, escolas de atividade complementar/AEE, UBS/USF e outras unidades de saúde;
  - áreas: praças e parques; matas e áreas protegidas (OpenStreetMap, só informativa).
- **Detalhe do bairro:** índice e seus três componentes, distâncias e serviços por 10 mil habitantes,
  com a comparação com a média da cidade em palavras ("30% mais perto", "13% abaixo"), e a lista dos
  serviços que ficam no bairro.
- **Comparar dois bairros:** em "Comparar com", escolha um segundo bairro; os dois aparecem lado a lado,
  com a média da cidade como referência, e o segundo ganha contorno cinza no mapa.
- **Link de um bairro:** a URL acompanha o bairro escolhido e a comparação, para compartilhar
  (ex.: `.../servicos?bairro=mangabeira&comparar=bessa`; na página de bairros, que é a página inicial,
  `.../?bairro=mangabeira`).
  Acento e maiúsculas não importam; um nome que não existe abre o bairro padrão.
- **Ranking:** bairros com mais moradores por escola ou UBS/USF, e a lista dos que não têm nenhum dos dois.
- **Índice:** fórmula, explicação e tabela com os componentes de todos os bairros (com download em CSV).
- **Gasto em saúde e educação:** valor empenhado nas funções Saúde e Educação (TCE-PB, corrigido pelo
  IPCA, sem transferências entre órgãos) no último ano completo e por habitante desde 2009, com link para a
  página de despesas. É o gasto da cidade toda: os empenhos não dizem o bairro, e nada é dividido por bairro.
- **Fontes e limitações:** seção aberta no fim da página, com a tabela de fontes, os filtros de cada uma,
  as limitações, os pontos não atribuídos a bairro e os arquivos de origem (com SHA-256).
- **Cores das camadas:** amarelo, violeta e vermelho para os pontos; verde-água para praças e parques;
  verde-escuro para matas. Foram validadas com o validador de paleta, todos os pares. A escola de
  atividade complementar é um ponto vazado, para não depender só da cor.

### Fontes

| Dado | Origem | Arquivo bruto | Atualização da fonte | Obtido em |
|---|---|---|---|---|
| Escolas | INEP, [Catálogo de Escolas](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/inep-data/catalogo-de-escolas) (UF = PB) | `inep/catalogo_escolas_PB.csv` | situação do Censo Escolar 2024 (o catálogo não traz data; conferido uma vez com os [microdados do Censo Escolar 2024](https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2024.zip)) | 22/10/2026 |
| Unidades de saúde | Ministério da Saúde, CNES, [API de dados abertos](https://apidadosabertos.saude.gov.br/) (município 250750) | `cnes/estabelecimentos_250750.json`, `cnes/tipounidades.json` | cadastros atualizados até 16/10/2026 | 16/10/2026 |
| Parques | Prefeitura, [Filipeia](https://filipeia.joaopessoa.pb.gov.br/) (shapefile exportado à mão) | `filipeia/Parques_Municipais.zip` (+ `.csv`) | arquivo de 08/02/2021 | 23/10/2026 |
| Praças | Tabela do Filipeia; contornos da Prefeitura na cópia do geodata-jp (commit `76f128b`), conferidos com a tabela e as quadras | `filipeia/pracas.csv`, `geodata_jp/pracas.geojson` | intervenções registradas até 2018 | 23/10/2026 |
| Quadras e bairros da Prefeitura (só conferência) | Filipeia | `filipeia/quadras_gerais.zip`, `filipeia/bairros.zip` | quadras de 02/10/2026; bairros de 13/04/2026 | 23/10/2026 |
| Ruas e caminhos (distância pelas ruas) | OpenStreetMap, Overpass API, © colaboradores do OpenStreetMap (ODbL) | `osm/ruas.json` | base do OSM de 15/07/2026 (carimbo do servidor) | 24/10/2026 |
| Matas e áreas protegidas (só no mapa) | [OpenStreetMap](https://www.openstreetmap.org/), Overpass API, © colaboradores do OpenStreetMap (ODbL) | `osm/matas.json`, `osm/parques.json` | consulta de 23/10/2026 | 23/10/2026 |
| Coordenadas de apoio (escolas) | Catálogo do INEP de 2022 (via geodata-jp) e OpenStreetMap (API, 2 elementos fixos) | `geodata_jp/escolas_publicas.geojson`, `osm/escolas.json` | fev/2022; OSM de 23/10/2026 | 22–23/10/2026 |
| População por setor censitário | IBGE, Censo 2022, malha de setores com atributos (`v0001`) | `ibge_censo2022/PB_setores_CD2022.gpkg` | 2022 | 22/10/2026 |
| Matrículas por escola e etapa | INEP, [microdados do Censo Escolar 2024](https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2024.zip) (`QT_MAT_INF_CRE`, `QT_MAT_INF_PRE`, `QT_MAT_FUND`, `QT_MAT_MED`) | `inep/microdados_censo_escolar_2024.zip` | Censo Escolar 2024 (arquivo de 07/2026) | 24/10/2026 |
| Renda e saneamento por bairro | IBGE, Censo 2022: [rendimento do responsável](https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios_Rendimento_do_Responsavel/) (divulgação de 05/2026) e características dos domicílios, partes 1 e 2, por bairro | `ibge_censo2022/Agregados_por_bairros_renda_responsavel_BR_20260508_csv.zip`, `..._caracteristicas_domicilio1_...zip`, `..._caracteristicas_domicilio2_...zip` | 2022 | 24/10/2026 |
| Equipes de Saúde da Família | Ministério da Saúde, DATASUS, [base completa do CNES](https://cnes.datasus.gov.br/pages/downloads/arquivosBaseDados.jsp) (`tbEquipe`, `tbTipoEquipe`) | `cnes/BASE_DE_DADOS_CNES_202609.ZIP` | competência 09/2026 | 24/10/2026 |

**Escolas: INEP em vez do geodata-jp.** A camada de escolas do geodata-jp é de fevereiro de 2022.
Comparada com o catálogo atual do INEP, faltam 12 escolas abertas depois, e 8 das que ela traz estão
hoje paralisadas. Por isso a fonte é o INEP, e o geodata-jp só completa coordenadas.

**Coleta do INEP.** O catálogo não tem download direto: é um painel do Oracle Analytics, e
`src/collect/inep_catalogo.py` o opera com Playwright + Chromium (filtro UF = PB, Aplicar, Exportar).
A exportação é conferida: o painel precisa dizer que selecionou entre 1.000 e 20.000 escolas, e todas
as linhas precisam ser da PB, porque, se o filtro falha, o painel exporta 100 mil linhas de várias UFs.
O servidor do INEP não envia o certificado intermediário da RNP (*RNP ICPEdu GR46 OV TLS CA 2025*).
O certificado público está em `certs/` e é registrado no banco de certificados do Chromium; a
verificação TLS não é desligada.

**Filipeia.** O portal da Prefeitura fica atrás de um firewall anti-robô que bloqueia acesso
automatizado (inclusive de navegador automatizado). Por isso as camadas foram exportadas à mão pelo
navegador em 23/10/2026 e registradas no manifesto com `python -m src.collect.filipeia --registrar`.
O portal oferece o shapefile dos parques, mas só a tabela das praças. A versão atual é igual à copiada
pelo geodata-jp em 2022: o cadastro de praças e parques da Prefeitura não foi atualizado desde então.

**OpenStreetMap.** Matas, áreas protegidas e parques vêm de consultas ao Overpass
(`src/collect/osm.py`). O servidor principal recusa consultas grandes daqui, por isso há servidores
alternativos. As duas escolas vêm da API principal do OSM, por elemento fixo, conferido à mão: mesmo
nome e ponto no bairro do endereço do INEP.

**CNES.** A API devolve 20 registros por página. Em 22/10/2026 ela estava fora do ar; a cópia usada
foi baixada e conferida em 16/10/2026 (data registrada no manifesto).

### O que entra

- **Escolas:** públicas (municipais, estaduais e federais) de João Pessoa, exceto as paralisadas
  ou extintas: **301**. Dessas, 5 são de **atividade complementar ou AEE** exclusiva (sem turmas
  regulares) e aparecem no mapa numa categoria própria, mas ficam fora das distâncias e do índice.
- **Saúde (rede SUS):** estabelecimentos ativos dos tipos UBS/USF (centro de saúde, posto),
  policlínica, UPA/pronto atendimento e hospital (geral, especializado e misto) que são públicos
  (natureza jurídica do grupo 1) ou atendem pelo SUS. Cadastros de regulação (ex.: "... REGULACAO
  SESPB") são excluídos. Ficam **145** unidades: 106 UBS/USF, 9 policlínicas, 4 UPAs e 26 hospitais.
  Usamos a natureza jurídica porque a "esfera administrativa" do CNES indica quem faz a gestão, não
  quem é dono.
- **Equipes de Saúde da Família (eSF):** equipes ativas na base completa do CNES de setembro de 2026,
  de todo tipo cuja descrição começa por "ESF": **227**, todas em UBS/USF do mapa (98 UBS/USF têm pelo menos
  uma; 8 não têm nenhuma). A API do CNES não traz equipes; a base completa (cerca de 750 MB) é baixada por
  `python -m src.collect.cnes_base` e lida direto do ZIP. 4 equipes ficam em UBS/USF fora dos bairros do IBGE.
- **Praças e parques:** 214 praças (61,8 ha) e 11 parques (270,8 ha) do cadastro da Prefeitura. Onde
  uma praça e um parque se sobrepõem (1,4 ha), a área conta uma vez. As praças são conferidas a cada
  execução: as 214 precisam ter nome e área idênticos aos da tabela oficial (senão o pipeline para), e
  160 das 162 com código cartográfico ficam dentro ou encostadas na quadra indicada nas quadras do
  Filipeia de 2026.
- **Matas e áreas protegidas (OpenStreetMap):** 4.109 ha no município, entre elas a Mata do Buraquinho
  (516 ha), o Refúgio de Vida Silvestre Mata do Buraquinho (512 ha) e o Parque Estadual Mata do Aratu
  (340 ha). Aparecem **só no mapa**: não entram na área verde por morador nem no índice, porque não são
  do mesmo cadastro nem do mesmo critério (praça e parque).

O funil completo de cada fonte está em `data/processed/servicos/metadados.json` (`funil`).

### Pontos sem coordenada ou fora dos bairros

Cada ponto recebe um status, e os que não caem num bairro ficam em `pontos_nao_atribuidos.csv`:

| Status | Escolas | Saúde | O que acontece |
|---|---|---|---|
| no bairro | 286 | 144 | contado no bairro |
| sem coordenada | 14 | 0 | fora do mapa e das distâncias; listado |
| no município, fora de bairro | 1 | 0 | no mapa e nas distâncias; não contado em bairro |
| fora do município | 0 | 1 | fora das distâncias e das contagens; listado |

- **Escolas sem coordenada no INEP (19):**
  - 9 estão no geodata-jp, mas 6 delas têm lá o mesmo ponto (−7,145192; −34,859117), repetido em 12
    escolas de endereços diferentes. É um marcador genérico, não uma localização, então só 3
    coordenadas são usadas, marcadas como "geodata-jp (Catálogo de Escolas do INEP, versão de 2022)";
  - mais 2 (CEEEA Sesquicentenário e ECI Liliosa de Paiva Leite) usam o ponto do OpenStreetMap,
    marcado como tal;
  - as outras 14 não estão em nenhuma fonte acessível. A posição não é estimada pelo endereço.
- **USF Integrada Boa Esperança:** a coordenada do CNES fica 36 km fora do município (o endereço é em
  Gramame), e a base completa do CNES de junho de 2025 (OpenDataSUS) tem o mesmo erro. Não é corrigida à mão.
- **Bairro pela malha da Prefeitura:** `pontos_nao_atribuidos.csv` traz essa informação para quem tem
  coordenada. A escola do Porto do Capim, fora dos bairros do IBGE, fica no Varadouro pela malha da Prefeitura.
- **Limite do município:** é a união dos setores censitários de 2022. 14 setores (3.143 moradores) não
  pertencem a nenhum bairro do IBGE.
- **Divisa:** um ponto exatamente na divisa entre dois bairros fica com o de menor código (o número de
  casos está em `metadados.json`).

### Metodologia

Distâncias e áreas são calculadas em **SIRGAS 2000 / UTM 25S (EPSG:31985)**, em metros, nunca em graus.

- **Distância até o serviço mais próximo:** linha reta até a escola
  regular ou a UBS/USF mais próxima no município, inclusive de outro bairro. Duas versões:
  - **ponderada pela população (a principal):** distância de cada setor censitário com moradores
    (centroide do setor) até o serviço mais próximo, com média ponderada pelo número de moradores
    do setor no Censo 2022;
  - **do centroide do bairro:** um ponto só. É mais simples, mas o centro geométrico pode ser um
    mangue, um parque ou uma área vazia. A diferença entre as duas mostra onde as pessoas moram de
    fato em relação ao centro do bairro. No Planalto da Boa Esperança, por exemplo, a escola está a
    29 m do centroide, mas o morador médio está a 366 m de uma escola.
- **Distância pelas ruas:** caminho mais curto pela malha de ruas e caminhos do OpenStreetMap
  (`osm/ruas.json`: 100.679 nós e 116.552 trechos; ruas e avenidas, vias de serviço, calçadões, caminhos de pedestre, escadas, trilhas e ciclovias; sentido único é ignorado, porque o trajeto é a pé), do
  centroide de cada setor ao serviço mais próximo, com média ponderada pelos moradores, como na linha
  reta. Setor, escola e UBS são ligados ao nó de rua mais próximo, e a distância é a soma dos trechos em
  metros (EPSG:31985). Na mediana dos setores, o caminho é 1,56 vez a linha reta até a escola e 1,46 vez
  até a UBS/USF. Em 5 setores (2.047 moradores) não há caminho na malha até nenhum serviço; eles ficam
  fora da média pelas ruas, e a lista está em `metadados.json` (`distancia_rede`). O índice de acesso
  continua usando a linha reta.
- **Serviços por 10 mil habitantes:** contagem no bairro ÷ população 2022 × 10.000. Vale também para as
  equipes de Saúde da Família (soma das equipes das UBS/USF do bairro). Não é cobertura: cada equipe atende uma
  área de abrangência, que não está nos dados e pode incluir outros bairros, por isso não há percentual de cobertura.
- **Área verde por habitante (m²/hab):** área de praças e parques dentro do bairro ÷ população 2022.
- **Ranking "mais gente e menos serviços":** habitantes por equipamento (escolas regulares +
  UBS/USF no bairro). Bairros sem nenhum dos dois aparecem à parte. Só entram bairros com pelo menos
  1.000 moradores, porque em bairros quase vazios a razão não diz muito.
- **Índice de acesso (0 a 100):** média simples de três posições percentuais entre os 64 bairros:

  `índice = (P_escola + P_ubs + P_verde) / 3`

  - `P_escola`: posição pela distância ponderada até a escola, invertida (mais perto = mais alto);
  - `P_ubs`: o mesmo para a UBS/USF;
  - `P_verde`: posição pela área verde por habitante (mais área = mais alto).

  Cada posição é o percentil do bairro (de 1/64 × 100 a 100; empates recebem a posição média). O
  índice é **relativo**: 100 seria o melhor bairro de João Pessoa nos três itens, não um padrão ideal.
  Os três componentes têm o mesmo peso, e a escolha é deliberadamente simples para que o número
  possa ser refeito à mão.
- **Sensibilidade aos pesos:** o índice é recalculado com outros pesos (cada item com peso dobrado, sem
  área verde, só escola, só UBS/USF), e o site mostra quanto o ranking muda: correlação de Spearman com o
  ranking publicado, mudança média e máxima de posição, e quantos dos primeiros colocados continuam. Com
  um item de peso dobrado, a correlação fica entre 0,93 e 0,98; tirar um item muda bem mais. A posição de
  cada bairro em cada cenário está em `sensibilidade_indice.csv`.

### Limitações

- **Só serviços públicos ou do SUS.** Escolas, clínicas e hospitais privados não estão contados. Um
  bairro "sem escola pública nem UBS" (Aeroclube, Portal do Sol, Tambaú, Cabo Branco, Brisamar e outros)
  pode ter serviços privados.
- **A distância não indica a unidade de referência.** Cada família é atendida pela UBS da sua área de
  abrangência, e essas áreas não estão nos dados. A distância mostra só a unidade mais próxima.
- **Linha reta** subestima o caminho real, ainda mais onde há rios, mangues ou vias expressas no meio.
- **Distância pelas ruas é aproximada.** Depende de a malha do OpenStreetMap estar completa (vielas e
  atalhos podem faltar), não considera calçadas, travessias, relevo nem segurança, e liga cada setor ao
  nó de rua mais próximo do seu centroide.
- **Efeito de borda:** o serviço mais próximo pode estar em outro bairro (isso é contado); serviços
  em municípios vizinhos não estão nos dados.
- **Área verde só do cadastro da Prefeitura:** a Mata do Buraquinho e outras matas não são praça nem
  parque no cadastro; aparecem na camada de matas do mapa, mas não na área verde por morador nem no
  índice. Bairros vizinhos a elas aparecem com menos área verde do que de fato têm.
- **Parque em mais de um bairro:** é contado em cada bairro que toca (por isso a soma dos parques por
  bairro passa de 11), mas a área é dividida entre eles.
- **Cadastro desatualizado:** os parques são de um arquivo de 2021 e as praças registram intervenções
  até 2018. O OpenStreetMap tem parques que o cadastro não tem: Parque Socioambiental do Roger (em
  construção, 24,6 ha), Parque Linear das Três Ruas (7,7 ha), Parque Jardim do Norte (4,9 ha), Horto de
  Santo Antônio (4,2 ha) e Ecobosque (1,1 ha). Não foram somados, para não misturar fontes.
- **Bairros IBGE × Prefeitura:** o mapa usa os bairros do IBGE, onde a população do Censo é contada. A
  malha da Prefeitura (abril de 2026) cobre 194 km² do município, contra 168 km² do IBGE; alguns bairros
  de borda (Mussuré, Mumbaba, Alto do Céu, Muçumagro) são bem maiores nela.
- **14 escolas sem coordenada** (lista em `pontos_nao_atribuidos.csv`) não entram nas distâncias;
  a distância até a escola pode estar superestimada nos bairros delas.
- **Coordenadas declaradas:** são as informadas ao INEP e ao CNES e não foram conferidas uma a uma.

### Matrículas e crianças do bairro

- **Matrículas:** microdados do Censo Escolar 2024 do INEP, por escola e etapa (creche, pré-escola,
  fundamental, médio), baixados por `python -m src.collect.inep_microdados`. As 301 escolas do site estão
  todas nos microdados, e suas matrículas são exatamente as das escolas públicas em funcionamento da cidade
  (as 5 de atividade complementar/AEE não têm turmas regulares). Na cidade, de 54% (pré-escola) a 71% (creche)
  das matrículas são em escola pública.
- **Crianças e jovens:** população por idade do Censo 2022, por bairro (`V01031` a `V01034`).
- **Indicadores:** matrículas públicas no bairro por 100 crianças que moram nele: educação infantil ÷ 0 a 4
  anos; fundamental ÷ 5 a 14 anos; médio ÷ 15 a 19 anos. As faixas do IBGE são de 5 em 5 anos e não coincidem
  com as idades das etapas (creche 0–3, pré-escola 4–5, fundamental 6–14, médio 15–17), e muitos alunos estudam
  fora do bairro onde moram: bairros com escolas grandes e poucos moradores passam de 100. É uma comparação,
  não uma medida de falta ou sobra de vagas. No mapa, a cor satura no percentil 90.

### Renda e saneamento (Censo 2022)

Gerado por `python -m src.process.censo_bairros` em `data/processed/censo_bairros.csv`, usado nas páginas de
bairros (cor do mapa e painel) e de serviços (gráfico "Renda e acesso").

- **Tabelas por bairro do IBGE**, não soma de setores: nas tabelas por setor há valores sigilosos ("X") em
  setores pequenos de João Pessoa, e somá-los deixaria pessoas de fora. Nas tabelas por bairro não há nenhum.
  Um "X" vira vazio e é contado em `censo_bairros_meta.json`, nunca estimado.
- **Renda:** rendimento nominal mensal médio e mediano das pessoas responsáveis pelo domicílio **com**
  rendimento (o IBGE não inclui responsáveis sem rendimento), em R$ de 2022. Mussuré (3 moradores) não tem o
  dado. Em 27 bairros a mediana é exatamente R$ 1.212, o salário mínimo de 2022. Os números do arquivo usam
  vírgula decimal, mas uma mediana vem com ponto ("6598.5"); o leitor aceita os dois e rejeita um texto com
  os dois separadores.
- **Saneamento:** parte dos domicílios particulares permanentes ocupados (`V00001`) com água pela rede geral
  (`V00111`), esgoto ligado à rede (`V00309`, rede geral ou pluvial, + `V00310`, fossa séptica ou
  fossa filtro ligada à rede) e lixo coletado no domicílio ou em caçamba (`V00397` +
  `V00398`).
- **Renda e acesso:** o gráfico mostra cada bairro e a correlação de Spearman entre a renda mediana e o
  indicador escolhido. É uma descrição; correlação não indica causa, e serviços privados não estão contados.

### Dados processados (`data/processed/servicos/`)

| Arquivo | Conteúdo |
|---|---|
| `indicadores_servicos.csv` | por bairro: contagens por tipo, por 10 mil hab., área verde (m² e m²/hab), distâncias (ponderada, do centroide e pelas ruas), habitantes por equipamento, marcação do ranking e índice de acesso |
| `pontos_servicos.geojson` | escolas e unidades de saúde com coordenada: tipo, rede/natureza, endereço, origem da coordenada, status, bairro e arquivo de origem |
| `pontos_nao_atribuidos.csv` | pontos sem coordenada ou fora dos bairros, com o motivo e o bairro pela malha da Prefeitura |
| `areas_verdes.geojson` | praças e parques (simplificados em 1 m para o mapa), com área |
| `matas_osm.geojson` | matas e áreas protegidas do OpenStreetMap recortadas pelo município (simplificadas em 2 m), com tipo, nome, área e id do OSM |
| `sensibilidade_indice.csv` | posição de cada bairro no índice em cada cenário de pesos |
| `metadados.json` | funil de filtros, pontos por status, conferência das praças, áreas verdes, matas, médias da cidade, setores e manifesto dos arquivos brutos |

---

## 3. Para onde vai o dinheiro de João Pessoa

Como os órgãos municipais de João Pessoa gastam seus recursos, a partir dos **empenhos** declarados
ao Tribunal de Contas do Estado da Paraíba (TCE-PB) pelo sistema SAGRES. Gerado por
`python -m src.process.despesas`.

> **Os valores são os declarados pela Prefeitura e pelos demais órgãos municipais ao TCE-PB.
> Podem mudar depois da análise e auditoria do Tribunal.** O dashboard mostra para onde vai o
> dinheiro; não faz juízo sobre a regularidade de nenhuma despesa.

### No dashboard

- **Opções no topo:** valor empenhado ou pago; nominal ou corrigido pelo IPCA; todos os órgãos, só
  Executivo ou só Legislativo; com ou sem transferências entre órgãos do município (sem, por padrão).
  Todo gráfico diz se o valor é nominal ou corrigido.
- **Visão geral:** total por ano, gasto por habitante e mês a mês. 2016 e o ano em andamento
  aparecem em tom claro e ficam fora das variações anuais.
- **Por área:** treemap por função e subfunção de governo, tabela com participação e variação, e a
  série histórica de uma área.
- **Fornecedores:** ranking de empresas (CNPJ) num período e busca por nome ou CNPJ, com o valor
  por ano, por órgão pagador e os arquivos de origem. Entidades públicas ficam ocultas por padrão.
- **Licitação:** participação de cada modalidade por ano (sem folha de pagamento, por padrão).
- **Mapa (experimental):** valor dos empenhos que citam um bairro, com a cobertura em destaque.
- **Sobre os dados:** aviso, metodologia resumida, conferência com o SICONFI e arquivos de origem.

### Fontes

| Dado | Origem | Arquivos | Gerado pela fonte em | Baixado em |
|---|---|---|---|---|
| Empenhos (despesas) | TCE-PB, [Dados Abertos do SAGRES](https://dados-abertos.tce.pb.gov.br/), município 095 | `despesas-2009.zip` … `despesas-2026.zip` | 06/02/2026 (2009–2025); 14/10/2026 (2026) | 14/10/2026 |
| Conferência dos totais | Tesouro Nacional, SICONFI, DCA Anexo I-D (despesa por natureza) | `dca-anexo-I-D-AAAA.json` | — | 14/10/2026 |
| IPCA | IBGE, SIDRA tabela 1737 (número-índice, dez/1993 = 100) | `ipca_tabela1737.json` | até set/2026 | 14/10/2026 |
| População por ano | IBGE, SIDRA tabela 6579 (estimativas) e Censos 2010 e 2022 | `populacao_estimada_tabela6579.json` | — | 14/10/2026 |

As datas e os hashes de cada arquivo ficam em `data/raw/manifest.json` (download) e
`data/raw/tce_pb/listagem.xml` (data de geração no servidor do TCE-PB).

O portal do TCE-PB publica um `.zip` por município, conjunto de dados e ano, com um CSV em UTF-8.
Os antigos arquivos estaduais `.txt.gz` não estão mais disponíveis. O Sagres Online e a API do
Sagres Captura não puderam ser usados para conferência: o primeiro bloqueia acesso automatizado e
a documentação da API exige login. Por isso os totais são conferidos com o SICONFI.

### Unidades gestoras incluídas

Todas as 19 que aparecem para João Pessoa, o que permite conferir com o total oficial:

- **Executivo:** Prefeitura; fundos municipais de Saúde, Assistência Social, Urbanização,
  Cultura, Meio Ambiente, Direitos Difusos, Empreender-JP, Criança e Adolescente, Procuradoria
  (Funderm), Idoso e Trabalho; IPM (previdência), Emlur, Semob/STTrans, Funjope e Instituto
  Cândida Vargas.
- **Legislativo:** Câmara Municipal e Fundo da Câmara.

Vários fundos deixam de aparecer a partir de 2024; o Fundo de Assistência Social, em 2026. As
despesas passam a ser empenhadas pela Prefeitura, o que muda a distribuição entre órgãos, mas
não o total.

### Metodologia

- **Série:** de 2009 a 2026. 2003–2008 ficam de fora: até 2006 só há Prefeitura e Câmara, e até
  2008 o valor liquidado não foi preenchido.
- **Valor principal:** valor **empenhado** (o compromisso de gasto). Liquidado e pago também
  estão disponíveis.
- **Anulações:** o TCE-PB publica o empenhado já líquido das anulações. A soma bate centavo a
  centavo com o total declarado ao Tesouro em 2015, 2018, 2023 e 2024, e empenhos totalmente
  anulados aparecem com valor zero. Por isso nada é subtraído de novo.
- **Transferências entre órgãos do município** (modalidade de aplicação 91, intraorçamentária;
  por exemplo, a contribuição patronal da Prefeitura ao IPM): fazem parte do total oficial, mas
  contam o mesmo dinheiro duas vezes. Ficam marcadas (`intra`), e o dashboard permite excluí-las.
- **Folha de pagamento:** nesses empenhos o "credor" é o próprio órgão pagador (ex.: Secretaria
  de Finanças, Fundo de Saúde) ou o INSS/IPM. Por isso o grupo "Pessoal e Encargos Sociais" não
  entra no ranking de fornecedores (continua nos totais).
- **Correção pela inflação:** cada mês é corrigido pelo IPCA até o último mês publicado (set/2026):
  `valor corrigido = valor × IPCA(set/2026) / IPCA(mês do empenho)`. Empenhos de meses ainda sem
  IPCA publicado (out/2026) ficam com fator 1. O dashboard sempre indica se o valor é nominal ou
  corrigido.
- **Gasto por habitante:** população das estimativas do IBGE e, em 2010 e 2022, dos Censos. O
  IBGE não publicou estimativa para 2023: o gasto por habitante desse ano fica em branco.
- **Função de governo:** códigos padronizados (o TCE-PB publica "4" e "04") e nomes oficiais da
  Portaria 42/1999 (o arquivo traz grafias como "Encargos Especias").
- **Modalidade de licitação:** os nomes mudam com a Lei 14.133/2021 ("Pregão Eletrônico" →
  "Pregão (Lei 14.133/21)"). Foram agrupados em categorias estáveis (pregão, concorrência,
  dispensa, inexigibilidade, adesão a ata etc.), e um nome novo interrompe o pipeline até ser
  mapeado. "Sem licitação" inclui despesas que não passam por licitação, como folha, tributos e
  transferências.

### Privacidade

- Credores pessoa física: o CPF é mascarado (`***.123.456-**`, só os 6 dígitos centrais) e o nome
  não segue para os dados processados. Não há ranking nem busca de pessoas físicas; o valor pago a
  elas aparece só no total.
- O TCE-PB publica o CPF com 14 dígitos ("000" + CPF). Como alguns CNPJs também começam com "000"
  (agências do Banco do Brasil), o tipo é decidido pelos dígitos verificadores; se o documento é
  válido como CPF e como CNPJ, o nome desempata (S/A, LTDA, BANCO...). Na dúvida, é tratado como
  pessoa física.
- Microempreendedores individuais (MEI) costumam ter o CPF do titular no nome da empresa: esse
  CPF também é mascarado.

### Mapa por bairro (experimental)

O histórico de cada empenho é um texto livre. Procuramos nele os nomes dos 64 bairros oficiais.
Nomes que também são palavras comuns ou nomes de pessoas (Centro, Torre, Treze de Maio, José
Américo...) só contam depois da palavra "bairro", e nomes precedidos de rua, avenida, praça ou
escola não contam. Empenhos que citam mais de um bairro não são divididos entre eles.

**É uma estimativa parcial:** só 0,7% a 5% do valor empenhado de cada ano cita um único bairro
(`bairros_cobertura.csv`). A maior parte do gasto (folha, saúde, educação em rede) não é
atribuível a um bairro pelo texto.

### Limitações

- **2016 incompleto no TCE-PB:** só Prefeitura e Câmara (R$ 1,03 bi, contra R$ 1,78 bi declarados
  ao Tesouro, −42%). Receitas e servidores de 2016 também estão incompletos na fonte. O ano aparece
  com aviso e fica fora das comparações entre anos.
- **2020:** os arquivos do TCE-PB somam 3,1% a mais que o declarado ao Tesouro (cerca de R$ 70 mi),
  e as fontes disponíveis não explicam a diferença.
- **2026 é parcial:** os dados vão até 09/10/2026 (outubro incompleto), e o TCE-PB regenera o
  arquivo com frequência.
- O histórico de 2021 em diante vem repetido duas vezes no arquivo (corrigido no processamento).
  Em cerca de 3.900 históricos, travessões e aspas aparecem como "¿" na fonte; não foram
  alterados.
- Empenho não é pagamento: um valor empenhado pode ser liquidado e pago depois, ou cancelado.

### Conferência com o Tesouro (SICONFI)

| Ano | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Diferença TCE-PB × SICONFI | +0,06% | 0,00% | −42,25% | 0,00% | 0,00% | 0,00% | +3,12% | 0,00% | 0,00% | 0,00% | 0,00% | +0,13% |

O teste aceita até **0,2%** de diferença; 2016 e 2020 são exceções documentadas em `src/config.py`.
O SICONFI não tem a DCA de João Pessoa antes de 2014. Detalhes em
`data/processed/despesas/validacao_siconfi.csv`.

### Dados processados (`data/processed/despesas/`)

| Arquivo | Conteúdo |
|---|---|
| `despesas_cubo.parquet` | valores empenhado/liquidado/pago (nominais e corrigidos) por ano, mês, unidade gestora, função, subfunção, grupo de natureza da despesa, modalidade de licitação, tipo de credor e transferência interna; com o arquivo de origem e o fator do IPCA |
| `credores_pj.parquet` | valores por CNPJ, ano e unidade gestora (sem pessoas físicas e sem folha), nominais e corrigidos, com marca de entidade pública |
| `bairros_citados.csv` / `bairros_cobertura.csv` | valor por bairro citado (nominal e corrigido) e cobertura por ano |
| `validacao_siconfi.csv` | total anual TCE-PB × SICONFI |
| `ipca.csv` / `populacao.csv` | séries usadas na correção e no gasto por habitante |
| `metadados.json` | mês de referência do IPCA, última data de empenho, checagens, aviso e manifesto dos arquivos brutos |

Cada linha do cubo e da tabela de credores traz o `arquivo_origem` (ex.: `despesas-2025.zip`), e o
manifesto liga esse arquivo à URL, à data de download e ao SHA-256.

---

## Testes

`pytest` roda os testes do pipeline e das funções do app. Os que recalculam a partir dos dados
brutos só rodam quando `data/raw/` está presente; os demais usam só `data/processed/`.

- **Bairros e população:**
  - soma dos bairros a até 1% do total do município (2010 e 2022);
  - nenhum bairro sem geometria, e geometrias válidas, sem sobreposição;
  - nenhuma população negativa, e variação e densidade consistentes;
  - valores sigilosos do IBGE ("X") interrompem o pipeline em vez de serem estimados.
- **Serviços:**
  - todo ponto num bairro tem exatamente um bairro válido e cai dentro dele; ids únicos;
  - pontos fora de bairro ou sem coordenada listados com o motivo;
  - contagens iguais ao total da fonte filtrada por João Pessoa (recalculado dos arquivos brutos quando
    presentes), e contagens por bairro iguais aos pontos;
  - nenhuma distância negativa ou ausente; área verde menor que a área do bairro; índice entre 0 e 100;
  - praças conferidas com a tabela oficial e as quadras do Filipeia; escolas com coordenada do OSM
    caem num bairro; matas fora do índice e dentro do município.
- **Dinheiro:**
  - total anual igual ao do SICONFI (tolerância de 0,2%, com 2016 e 2020 como exceções documentadas);
  - campos essenciais sem nulos e datas dentro do ano do arquivo;
  - nenhum CPF exposto nos dados processados, e ranking só com CNPJs válidos;
  - regras de limpeza, de bairros e de busca do dashboard.

## Créditos e licenças das fontes

- **IBGE, INEP, Ministério da Saúde (CNES), TCE-PB e Tesouro Nacional (SICONFI):** dados públicos
  oficiais, citados em cada página com link e data.
- **Prefeitura de João Pessoa, Filipeia:** dados públicos do portal da Prefeitura.
- **OpenStreetMap:** © colaboradores do OpenStreetMap, sob a licença
  [ODbL](https://opendatacommons.org/licenses/odbl/). O crédito aparece no mapa sempre que a camada de
  matas está ligada. O mapa de fundo também usa dados do OpenStreetMap, com base da CARTO.
- **geodata-jp:** cópia de camadas da Prefeitura e do INEP. O repositório não declara licença; o
  uso e as conferências estão em [Onde o geodata-jp ainda é usado](#onde-o-geodata-jp-ainda-é-usado).

## Melhorias planejadas

As próximas melhorias estão nas [issues do repositório](https://github.com/davialves1820/RaioX-Joao-Pessoa/issues):
testes automáticos no GitHub, vagas na escola × crianças por bairro, equipes de Saúde da Família,
renda e saneamento do Censo 2022, distância pelas ruas (feitas), população de 2025 da Prefeitura, entre outras.
