# Raio-X dos Bairros de João Pessoa

Dashboard aberto com indicadores por bairro de João Pessoa (PB), feito a partir de dados públicos.
Esta primeira fase trata de **população** (Censos 2010 e 2022), **variação populacional** e
**densidade demográfica** nos 64 bairros do município.

O dashboard tem: mapa coroplético dos bairros (população, densidade ou variação 2010→2022),
painel de detalhe ao clicar num bairro (com a origem de cada número), ranking dos bairros que mais
cresceram e mais perderam população, tabela completa com download em CSV e uma seção sobre fontes
e limitações.

A segunda página, **"Para onde vai o dinheiro de João Pessoa"**, mostra as despesas dos órgãos
municipais declaradas ao TCE-PB: visão geral, gasto por área, fornecedores, modalidades de licitação
e um mapa experimental. Ver a seção [Para onde vai o dinheiro](#para-onde-vai-o-dinheiro-de-joão-pessoa).

A página **"Serviços e acesso"** mostra escolas públicas (INEP), unidades de saúde do SUS (CNES),
praças e parques num mapa com camadas que se ligam e desligam; distâncias até a escola e a UBS/USF
mais próximas, área verde por morador, o ranking "mais gente e menos serviços" e um índice de acesso
com a fórmula explicada. Ver [Serviços públicos e acesso](#serviços-públicos-e-acesso).

## Como rodar

Requer Python 3.11+.

```bash
pip install -r requirements-dev.txt
python -m src.collect          # baixa os dados brutos para data/raw/ (reexecutável; --force rebaixa)
python -m src.process.build    # gera data/processed/ (bairros e população)
python -m src.process.despesas # gera data/processed/despesas/ (depende do passo anterior)
python -m src.process.servicos # gera data/processed/servicos/ (depende do build)
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

Para atualizar os dados que mudam com o tempo (despesas do ano corrente, IPCA e estimativas de
população, estabelecimentos do CNES), rode `python -m src.collect --atualizar` e depois os passos
de processamento. O Catálogo de Escolas do INEP é exportado por navegador automatizado (ver
[Serviços públicos e acesso](#serviços-públicos-e-acesso)); para atualizá-lo, use
`python -m src.collect.inep_catalogo --force`.

## Estrutura

```
data/raw/          dados baixados, sem alteração (só o manifest.json é versionado)
data/interim/      tabela de empenhos limpa, um por linha (não versionada; ~40 MB)
data/processed/    dados limpos e prontos para o app
src/collect/       um script de download por fonte
src/process/       leitura, junções e cálculo dos indicadores (build.py orquestra)
src/app/           código do Streamlit: app.py e dados.py (bairros), servicos.py e dados_servicos.py
                   (serviços), despesas.py e dados_despesas.py (dinheiro); streamlit_app.py liga as páginas
certs/             certificado intermediário público usado na coleta do INEP
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
  Por isso os **bairros** do geodata-jp não são usados no mapa, só na tabela de correspondência, e os
  arquivos brutos do geodata-jp não são versionados aqui.
- **Exceção: os contornos das praças** (página de serviços). O Filipeia oferece só a tabela das praças, sem
  o shapefile. Os contornos vêm do geodata-jp, mas são os da Prefeitura: o pipeline exige que as 214 praças
  tenham nome e área idênticos aos da tabela oficial do Filipeia e confere a posição com as quadras do
  Filipeia (ver [Serviços públicos e acesso](#serviços-públicos-e-acesso)). A cópia é do geodata-jp; o
  dado é público, da Prefeitura. Os contornos simplificados ficam em
  `data/processed/servicos/areas_verdes.geojson`, com a Prefeitura citada como fonte.
- Os limites de vários bairros diferem dos do IBGE (ver abaixo). O campo `densidade` do arquivo está
  quase todo vazio ou inválido e não é usado.
- O portal Filipeia respondeu 403 ao acesso automatizado em 14/10/2026 e em 23/10/2026 (firewall
  anti-robô). Em 23/10/2026 as camadas de parques, praças (tabela), quadras e bairros foram exportadas à
  mão (ver Serviços públicos e acesso).

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

`pytest` verifica, no módulo de despesas: total anual igual ao do SICONFI (tolerância de 0,2%, com
2016 e 2020 como exceções documentadas), campos essenciais sem nulos, datas dentro do ano do
arquivo, nenhum CPF exposto nos dados processados, ranking só com CNPJs válidos e as regras de
limpeza, de bairros e de busca do dashboard.

No módulo de bairros, verifica entre outras coisas: soma dos bairros a até 1% do total do município (2010 e 2022),
nenhum bairro sem geometria (e geometrias válidas, sem sobreposição), nenhuma população negativa,
consistência da variação e da densidade, e que valores sigilosos do IBGE ("X") interrompem o pipeline
em vez de serem estimados.

No módulo de serviços, verifica: todo ponto num bairro tem exatamente um bairro válido (e cai
dentro dele), ids únicos, pontos fora de bairro ou sem coordenada listados com o motivo, contagens
iguais ao total da fonte filtrada por João Pessoa (recalculado dos arquivos brutos quando estão
presentes), contagens por bairro iguais aos pontos, nenhuma distância negativa ou ausente, área verde
menor que a área do bairro e índice entre 0 e 100.

## Para onde vai o dinheiro de João Pessoa

Módulo sobre como os órgãos municipais de João Pessoa gastam seus recursos, a partir dos
**empenhos** declarados ao Tribunal de Contas do Estado da Paraíba (TCE-PB) pelo sistema SAGRES.

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

## Serviços públicos e acesso

Escolas públicas, unidades de saúde do SUS, praças e parques por bairro, com distância até a
escola e a UBS/USF mais próximas, área verde por habitante e um índice simples de acesso.
Gerado por `python -m src.process.servicos`.

### Fontes

| Dado | Origem | Arquivo bruto | Atualização da fonte | Obtido em |
|---|---|---|---|---|
| Escolas | INEP, [Catálogo de Escolas](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/inep-data/catalogo-de-escolas) (UF = PB) | `inep/catalogo_escolas_PB.csv` | situação do Censo Escolar 2024 (o catálogo não traz data; conferido uma vez com os [microdados do Censo Escolar 2024](https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2024.zip)) | 22/10/2026 |
| Unidades de saúde | Ministério da Saúde, CNES, [API de dados abertos](https://apidadosabertos.saude.gov.br/) (município 250750) | `cnes/estabelecimentos_250750.json`, `cnes/tipounidades.json` | cadastros atualizados até 16/10/2026 | 16/10/2026 |
| Parques | Prefeitura, [Filipeia](https://filipeia.joaopessoa.pb.gov.br/) (shapefile exportado à mão) | `filipeia/Parques_Municipais.zip` (+ `.csv`) | arquivo de 08/02/2021 | 23/10/2026 |
| Praças | Tabela do Filipeia; contornos do [geodata-jp](https://github.com/paulovitorweb/geodata-jp) (commit `76f128b`), conferidos com a tabela e as quadras do Filipeia | `filipeia/pracas.csv`, `geodata_jp/pracas.geojson` | intervenções registradas até 2018 | 23/10/2026 |
| Quadras e bairros da Prefeitura (só conferência) | Filipeia | `filipeia/quadras_gerais.zip`, `filipeia/bairros.zip` | quadras de 02/10/2026; bairros de 13/04/2026 | 23/10/2026 |
| Matas e áreas protegidas (só no mapa) | [OpenStreetMap](https://www.openstreetmap.org/), Overpass API, © colaboradores do OpenStreetMap (ODbL) | `osm/matas.json`, `osm/parques.json` | consulta de 23/10/2026 | 23/10/2026 |
| Coordenadas de apoio (escolas) | Catálogo do INEP de 2022 (via geodata-jp) e OpenStreetMap (API, 2 elementos fixos) | `geodata_jp/escolas_publicas.geojson`, `osm/escolas.json` | fev/2022; OSM de 23/10/2026 | 22–23/10/2026 |
| População por setor censitário | IBGE, Censo 2022, malha de setores com atributos (`v0001`) | `ibge_censo2022/PB_setores_CD2022.gpkg` | 2022 | 22/10/2026 |

**Por que não só o geodata-jp:** a camada de escolas do geodata-jp é de fevereiro de 2022. Comparada
com o catálogo atual do INEP, faltam 12 escolas abertas depois e 8 das que ela traz estão hoje
paralisadas. Por isso a fonte é o INEP, e o geodata-jp só completa coordenadas. O geodata-jp não tem
unidades de saúde: elas vêm do CNES.

**Coleta do INEP:** o catálogo não tem download direto. É um painel do Oracle Analytics, e
`src/collect/inep_catalogo.py` o opera com Playwright + Chromium (filtro UF = PB, Aplicar, Exportar).
A exportação é conferida: o painel precisa dizer que selecionou entre 1.000 e 20.000 escolas, e todas
as linhas precisam ser da PB, porque, se o filtro falha, o painel exporta 100 mil linhas de várias UFs.
O servidor do INEP não envia o certificado intermediário da RNP (*RNP ICPEdu GR46 OV TLS CA 2025*).
O certificado público está em `certs/` e é registrado no banco de certificados do Chromium; a
verificação TLS não é desligada. Se o painel mudar, o docstring do script explica a exportação manual.

**Filipeia:** o portal da Prefeitura fica atrás de um firewall anti-robô que bloqueia acesso automatizado
(inclusive de navegador automatizado), então as camadas foram exportadas à mão pelo navegador e são
registradas com `python -m src.collect.filipeia --registrar` (ver o docstring do script). O portal oferece o
shapefile dos parques, mas só a tabela das praças. Por isso os contornos das praças vêm do geodata-jp, e o
pipeline confere: as 214 praças precisam ter nome e área idênticos aos da tabela oficial (senão ele para), e
160 das 162 praças com código cartográfico ficam dentro ou encostadas na quadra indicada pelo código nas
quadras do Filipeia de 2026. A versão atual do Filipeia é igual à copiada pelo geodata-jp em 2022: o cadastro
de praças e parques da Prefeitura não foi atualizado desde então.

**OpenStreetMap:** matas e áreas protegidas, e parques, vêm de consultas ao Overpass (`src/collect/osm.py`;
o servidor principal recusa consultas grandes daqui, por isso há servidores alternativos). As duas escolas
vêm da API principal do OSM, por elemento fixo, conferido à mão (mesmo nome, ponto no bairro do endereço do INEP).

**CNES:** a API devolve 20 registros por página. Em 22/10/2026 ela estava fora do ar; a cópia usada
foi baixada e conferida em 16/10/2026 (data registrada no manifesto).

### O que entra

- **Escolas:** públicas (municipais, estaduais e federais) de João Pessoa, exceto as paralisadas
  ou extintas: **301**. Dessas, 5 são de **atividade complementar ou AEE** exclusiva (sem turmas
  regulares) e aparecem no mapa numa categoria própria, mas ficam fora das distâncias e do índice.
- **Saúde (rede SUS):** estabelecimentos ativos dos tipos UBS/USF (centro de saúde, posto),
  policlínica, UPA/pronto atendimento e hospital (geral, especializado e misto) que são públicos
  (natureza jurídica do grupo 1) ou atendem pelo SUS. Cadastros de regulação (ex.: "... REGULACAO
  SESPB") são excluídos: **145** unidades (106 UBS/USF, 9 policlínicas, 4 UPAs, 26 hospitais).
  "Esfera administrativa" do CNES indica a gestão, não quem é dono, por isso a natureza jurídica.
- **Áreas verdes:** 214 praças (61,8 ha) e 11 parques (270,8 ha) do cadastro da Prefeitura. Onde
  uma praça e um parque se sobrepõem (1,4 ha), a área conta uma vez.
- **Matas e áreas protegidas (OpenStreetMap):** 4.109 ha no município, entre elas a Mata do Buraquinho
  (516 ha), o Refúgio de Vida Silvestre Mata do Buraquinho (512 ha) e o Parque Estadual Mata do Aratu
  (340 ha). Aparecem **só no mapa**: não entram na área verde por morador nem no índice, porque não são do
  mesmo cadastro nem do mesmo critério (praça e parque).

Funil completo em `data/processed/servicos/metadados.json` (`funil`).

### Pontos sem coordenada ou fora dos bairros

Nenhum ponto é descartado em silêncio. Cada um recebe um status, e os que não caem num bairro
ficam em `pontos_nao_atribuidos.csv`:

| Status | Escolas | Saúde | O que acontece |
|---|---|---|---|
| no bairro | 286 | 144 | contado no bairro |
| sem coordenada | 14 | 0 | fora do mapa e das distâncias; listado |
| no município, fora de bairro | 1 | 0 | no mapa e nas distâncias; não contado em bairro |
| fora do município | 0 | 1 | fora das distâncias e das contagens; listado |

- Das 19 escolas sem coordenada no catálogo, 9 estão no geodata-jp, mas 6 delas têm lá o mesmo
  ponto (−7,145192; −34,859117), repetido em 12 escolas de endereços diferentes. É um marcador
  genérico, não uma localização, então só as 3 coordenadas restantes são usadas (marcadas como
  "geodata-jp (Catálogo de Escolas do INEP, versão de 2022)").
- Mais 2 escolas (CEEEA Sesquicentenário e ECI Liliosa de Paiva Leite) usam o ponto do OpenStreetMap,
  marcado como tal. As outras 14 não estão em nenhuma fonte acessível; a posição não é estimada pelo endereço.
- A USF Integrada Boa Esperança tem a mesma coordenada errada também na base completa do CNES de junho
  de 2025 (OpenDataSUS).
- `pontos_nao_atribuidos.csv` traz, para quem tem coordenada, o bairro pela malha da Prefeitura (a escola
  do Porto do Capim, fora dos bairros do IBGE, fica no Varadouro pela malha da Prefeitura).
- A USF Integrada Boa Esperança tem no CNES uma coordenada a 36 km do limite do município (o endereço
  é em Gramame). Não é corrigida à mão.
- A malha de bairros do IBGE cobre 167,8 km² dos 210,0 km² do município (soma do campo `AREA_KM2`
  dos setores censitários de 2022). O limite do município é a
  união dos setores censitários de 2022; 14 setores (3.143 moradores) não pertencem a nenhum bairro.
- Um ponto exatamente na divisa entre dois bairros fica com o de menor código (o número de casos
  está em `metadados.json`).

### Metodologia

Distâncias e áreas são calculadas em **SIRGAS 2000 / UTM 25S (EPSG:31985)**, em metros, nunca em graus.

- **Distância até o serviço mais próximo:** linha reta (não é o caminho pelas ruas) até a escola
  regular ou a UBS/USF mais próxima no município, inclusive de outro bairro. Duas versões:
  - **ponderada pela população (a principal):** distância de cada setor censitário com moradores
    (centroide do setor) até o serviço mais próximo, com média ponderada pelo número de moradores
    do setor no Censo 2022;
  - **do centroide do bairro:** um ponto só. É mais simples, mas o centro geométrico pode ser um
    mangue, um parque ou uma área vazia. A diferença entre as duas mostra onde as pessoas moram de
    fato em relação ao centro do bairro (no Planalto da Boa Esperança, por exemplo, a escola está a
    29 m do centroide, mas o morador médio está a 366 m de uma escola).
- **Serviços por 10 mil habitantes:** contagem no bairro ÷ população 2022 × 10.000.
- **Área verde por habitante (m²/hab):** área de praças e parques dentro do bairro ÷ população 2022.
- **Ranking "mais gente e menos serviços":** habitantes por equipamento (escolas regulares +
  UBS/USF no bairro). Bairros sem nenhum dos dois aparecem à parte, no topo. Só entram bairros com
  pelo menos 1.000 moradores, porque em bairros quase vazios a razão não diz muito.
- **Índice de acesso (0 a 100):** média simples de três posições percentuais entre os 64 bairros:

  `índice = (P_escola + P_ubs + P_verde) / 3`

  - `P_escola`: posição pela distância ponderada até a escola, invertida (mais perto = mais alto);
  - `P_ubs`: o mesmo para a UBS/USF;
  - `P_verde`: posição pela área verde por habitante (mais área = mais alto).

  Cada posição é o percentil do bairro (de 1/64 × 100 a 100; empates recebem a posição média). O
  índice é **relativo**: 100 seria o melhor bairro de João Pessoa nos três, não um padrão ideal.
  Os três componentes têm o mesmo peso, e a escolha é deliberadamente simples para que o número
  possa ser refeito à mão.

### Limitações

- **Só serviços públicos ou do SUS.** Escolas, clínicas e hospitais privados não estão contados. Um
  bairro "sem escola pública nem UBS" (Aeroclube, Portal do Sol, Tambaú, Cabo Branco, Brisamar e outros)
  pode ter serviços privados.
- **A distância não indica a unidade de referência.** Cada família é atendida pela UBS da sua área de
  abrangência, e essas áreas não estão nos dados. A distância mostra só a unidade mais próxima.
- **Linha reta** subestima o caminho real, ainda mais onde há rios, mangues ou vias expressas no meio.
- **Efeito de borda:** o serviço mais próximo pode estar em outro bairro (isso é contado); serviços
  em municípios vizinhos não estão nos dados.
- **Área verde só do cadastro da Prefeitura:** a **Mata do Buraquinho** e outras matas não são praça nem
  parque no cadastro; aparecem na camada de matas do mapa, mas não na área verde por morador nem no índice.
  Bairros vizinhos a elas aparecem com menos área verde do que de fato têm.
- **Cadastro desatualizado:** os parques são de um arquivo de 2021 e as praças registram intervenções até
  2018. O OpenStreetMap tem parques que o cadastro não tem: Parque Socioambiental do Roger (em construção,
  24,6 ha), Parque Linear das Três Ruas (7,7 ha), Parque Jardim do Norte (4,9 ha), Horto de Santo Antônio
  (4,2 ha) e Ecobosque (1,1 ha). Não foram somados, para não misturar fontes.
- **Bairros IBGE × Prefeitura:** o mapa usa os bairros do IBGE, onde a população do Censo é contada. A malha
  da Prefeitura (abril de 2026) cobre 194 km² do município, contra 168 km² do IBGE; alguns bairros de borda
  (Mussuré, Mumbaba, Alto do Céu, Muçumagro) são bem maiores nela.
  Um parque que atravessa mais de um bairro é contado em cada um (por isso a soma dos parques por
  bairro passa de 11), mas a área é dividida entre eles.
- **14 escolas sem coordenada** (lista em `pontos_nao_atribuidos.csv`) não entram nas distâncias;
  a distância até a escola pode estar superestimada nos bairros delas.
- As coordenadas são as declaradas ao INEP e ao CNES e não foram conferidas uma a uma.

### No dashboard

- **Mapa:** a cor dos bairros mostra o índice de acesso, a distância até a escola ou a UBS/USF, a área
  verde por morador ou os moradores por equipamento. As camadas de pontos (escolas, escolas de atividade
  complementar/AEE, UBS/USF, outras unidades de saúde), de praças e parques e de matas e áreas protegidas
  (OpenStreetMap, só informativa) se ligam e desligam.
- **Detalhe do bairro:** índice e seus três componentes, distâncias e serviços por 10 mil habitantes com a
  diferença em relação à média da cidade, e a lista dos serviços que ficam no bairro.
- **Ranking:** bairros com mais moradores por escola ou UBS/USF, e a lista dos que não têm nenhum dos dois.
- **Índice:** fórmula, explicação e tabela com os componentes de todos os bairros (com download em CSV).
- **Fontes e limitações:** seção aberta no fim da página, com a tabela de fontes, os filtros de cada uma,
  as limitações, os pontos não atribuídos a bairro e os arquivos de origem (com SHA-256).
- Cores das camadas (amarelo, violeta, vermelho; verde-água para praças e parques; verde-escuro para matas) validadas com o
  validador de paleta, todos os pares; a escola de atividade complementar é um ponto vazado, para não
  depender só da cor.

### Dados processados (`data/processed/servicos/`)

| Arquivo | Conteúdo |
|---|---|
| `indicadores_servicos.csv` | por bairro: contagens por tipo, por 10 mil hab., área verde (m² e m²/hab), distâncias (ponderada e do centroide), habitantes por equipamento, marcação do ranking e índice de acesso |
| `pontos_servicos.geojson` | escolas e unidades de saúde com coordenada: tipo, rede/natureza, endereço, origem da coordenada, status, bairro e arquivo de origem |
| `pontos_nao_atribuidos.csv` | pontos sem coordenada ou fora dos bairros, com o motivo |
| `areas_verdes.geojson` | praças e parques (simplificados em 1 m para o mapa), com área |
| `matas_osm.geojson` | matas e áreas protegidas do OpenStreetMap recortadas pelo município (simplificadas em 2 m), com tipo, nome, área e id do OSM |
| `metadados.json` | funil de filtros, pontos por status, áreas verdes, médias da cidade, setores e manifesto dos arquivos brutos |

## Próximas fases

Ciclovias e comunidades, outros indicadores do Censo 2022 (renda, saneamento, faixa etária) e
distâncias pela rede de ruas.
