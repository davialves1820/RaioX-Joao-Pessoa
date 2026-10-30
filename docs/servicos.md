# Serviços públicos e acesso

[← Voltar ao README](../README.md)

Escolas públicas, unidades de saúde do SUS, praças e parques por bairro, com distância até a
escola e a UBS/USF mais próximas, área verde por habitante e um índice simples de acesso. Matas e
áreas protegidas aparecem no mapa, fora do índice. Gerado por `python -m src.process.servicos`.

## No dashboard

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
- **Fontes e limitações:** aba logo abaixo do mapa, com a tabela de fontes, os filtros de cada uma,
  as limitações, os pontos não atribuídos a bairro e os arquivos de origem (com SHA-256).
- **Cores das camadas:** amarelo, violeta e vermelho para os pontos; verde-água para praças e parques;
  verde-escuro para matas. Foram validadas com o validador de paleta, todos os pares. A escola de
  atividade complementar é um ponto vazado, para não depender só da cor.

## Fontes

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

## O que entra

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

## Pontos sem coordenada ou fora dos bairros

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

## Metodologia

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

## Limitações

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

## Matrículas e crianças do bairro

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

## Renda e saneamento (Censo 2022)

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

## Dados processados (`data/processed/servicos/`)

| Arquivo | Conteúdo |
|---|---|
| `indicadores_servicos.csv` | por bairro: contagens por tipo, por 10 mil hab., área verde (m² e m²/hab), distâncias (ponderada, do centroide e pelas ruas), habitantes por equipamento, marcação do ranking e índice de acesso |
| `pontos_servicos.geojson` | escolas e unidades de saúde com coordenada: tipo, rede/natureza, endereço, origem da coordenada, status, bairro e arquivo de origem |
| `pontos_nao_atribuidos.csv` | pontos sem coordenada ou fora dos bairros, com o motivo e o bairro pela malha da Prefeitura |
| `areas_verdes.geojson` | praças e parques (simplificados em 1 m para o mapa), com área |
| `matas_osm.geojson` | matas e áreas protegidas do OpenStreetMap recortadas pelo município (simplificadas em 2 m), com tipo, nome, área e id do OSM |
| `sensibilidade_indice.csv` | posição de cada bairro no índice em cada cenário de pesos |
| `metadados.json` | funil de filtros, pontos por status, conferência das praças, áreas verdes, matas, médias da cidade, setores e manifesto dos arquivos brutos |
