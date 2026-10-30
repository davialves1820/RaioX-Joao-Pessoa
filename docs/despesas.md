# Para onde vai o dinheiro de João Pessoa

[← Voltar ao README](../README.md)

Como os órgãos municipais de João Pessoa gastam seus recursos, a partir dos **empenhos** declarados
ao Tribunal de Contas do Estado da Paraíba (TCE-PB) pelo sistema SAGRES. Gerado por
`python -m src.process.despesas`.

> **Os valores são os declarados pela Prefeitura e pelos demais órgãos municipais ao TCE-PB.
> Podem mudar depois da análise e auditoria do Tribunal.** O dashboard mostra para onde vai o
> dinheiro; não faz juízo sobre a regularidade de nenhuma despesa.

## No dashboard

- **Opções no topo:** valor empenhado ou pago; nominal ou corrigido pelo IPCA; todos os órgãos, só
  Executivo ou só Legislativo; com ou sem transferências entre órgãos do município (sem, por padrão).
  Todo gráfico diz se o valor é nominal ou corrigido.
- **Visão geral:** total por ano, gasto por habitante e mês a mês. 2016 e o ano em andamento
  aparecem em tom claro e ficam fora das variações anuais.
- **Por órgão (2022 em diante):** treemap órgão → unidade orçamentária, tabela com valor, participação,
  variação e a área em que cada órgão mais gasta, quanto de cada área sai de cada órgão e a série de um
  órgão. Nomes oficiais dos órgãos, com a fonte de cada um.
- **Por área:** treemap por função e subfunção de governo, tabela com participação e variação, e a
  série histórica de uma área.
- **Fornecedores:** ranking de empresas (CNPJ) num período e busca por nome ou CNPJ, com o valor
  por ano, por órgão pagador e os arquivos de origem. Entidades públicas ficam ocultas por padrão.
- **Licitação:** participação de cada modalidade por ano (sem folha de pagamento, por padrão).
- **Mapa (experimental):** valor dos empenhos que citam um bairro, com a cobertura em destaque.
- **Sobre os dados:** aviso, metodologia resumida, conferência com o SICONFI e arquivos de origem.

## Fontes

| Dado | Origem | Arquivos | Gerado pela fonte em | Baixado em |
|---|---|---|---|---|
| Empenhos (despesas) | TCE-PB, [Dados Abertos do SAGRES](https://dados-abertos.tce.pb.gov.br/), município 095 | `despesas-2009.zip` … `despesas-2026.zip` | 06/02/2026 (2009–2025); 14/10/2026 (2026) | 14/10/2026 |
| Conferência dos totais | Tesouro Nacional, SICONFI, DCA Anexo I-D (despesa por natureza) | `dca-anexo-I-D-AAAA.json` | — | 14/10/2026 |
| IPCA | IBGE, SIDRA tabela 1737 (número-índice, dez/1993 = 100) | `ipca_tabela1737.json` | até set/2026 | 14/10/2026 |
| População por ano | IBGE, SIDRA tabela 6579 (estimativas) e Censos 2010 e 2022 | `populacao_estimada_tabela6579.json` | — | 14/10/2026 |
| Nomes oficiais dos órgãos | Câmara Municipal, [SAPL](https://sapl.joaopessoa.pb.leg.br/): LOA 2024 (Lei 15.066/2024) e Leis 15.399/2024, 15.467, 15.468 e 15.469/2025 | `camara_jp/*.pdf` | leis de 2024 e 2025 | 25/10/2026 |

As datas e os hashes de cada arquivo ficam em `data/raw/manifest.json` (download) e
`data/raw/tce_pb/listagem.xml` (data de geração no servidor do TCE-PB).

O portal do TCE-PB publica um `.zip` por município, conjunto de dados e ano, com um CSV em UTF-8.
Os antigos arquivos estaduais `.txt.gz` não estão mais disponíveis. O Sagres Online e a API do
Sagres Captura não puderam ser usados para conferência: o primeiro bloqueia acesso automatizado e
a documentação da API exige login. Por isso os totais são conferidos com o SICONFI.

## Unidades gestoras incluídas

Todas as 19 que aparecem para João Pessoa, o que permite conferir com o total oficial:

- **Executivo:** Prefeitura; fundos municipais de Saúde, Assistência Social, Urbanização,
  Cultura, Meio Ambiente, Direitos Difusos, Empreender-JP, Criança e Adolescente, Procuradoria
  (Funderm), Idoso e Trabalho; IPM (previdência), Emlur, Semob/STTrans, Funjope e Instituto
  Cândida Vargas.
- **Legislativo:** Câmara Municipal e Fundo da Câmara.

Vários fundos deixam de aparecer a partir de 2024; o Fundo de Assistência Social, em 2026. As
despesas passam a ser empenhadas pela Prefeitura, o que muda a distribuição entre órgãos, mas
não o total.

## Metodologia

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

## Privacidade

- Credores pessoa física: o CPF é mascarado (`***.123.456-**`, só os 6 dígitos centrais) e o nome
  não segue para os dados processados. Não há ranking nem busca de pessoas físicas; o valor pago a
  elas aparece só no total.
- O TCE-PB publica o CPF com 14 dígitos ("000" + CPF). Como alguns CNPJs também começam com "000"
  (agências do Banco do Brasil), o tipo é decidido pelos dígitos verificadores; se o documento é
  válido como CPF e como CNPJ, o nome desempata (S/A, LTDA, BANCO...). Na dúvida, é tratado como
  pessoa física.
- Microempreendedores individuais (MEI) costumam ter o CPF do titular no nome da empresa: esse
  CPF também é mascarado.

## Por órgão (2022 em diante)

`orgaos.parquet` divide o gasto por **órgão** e **unidade orçamentária** (a secretaria, fundo ou
autarquia que tem o orçamento), por ano e função, de 2022 em diante. A soma por ano é a mesma do cubo.

- **Órgão** = os dois primeiros dígitos do código da unidade orçamentária (10101 → órgão 10). Cada
  órgão agrupa as unidades ligadas a ele no orçamento, por exemplo:
  - órgão 06 (SEAD) inclui o IPM (previdência);
  - órgão 71 (SEGGOV) inclui a Emlur e a Semob;
  - órgão 10 (SEDEC) inclui a Funjope e o Fundo Municipal de Cultura.
- **Nome da unidade:** o do ano mais recente em que o código aparece. O mesmo código muda de nome
  entre 2022–2023 ("10101-GABINETE DO SECRETÁRIO") e 2024 em diante ("SEDEC - AÇÕES DE GOVERNO"). O
  nome de cada ano fica em `nome_no_arquivo`.
- **Sigla do órgão:** a da unidade "SIGLA - AÇÕES DE GOVERNO" (SEDEC, SEINFRA, SEMUSB…). Os órgãos 01
  (Câmara), 13 (Saúde) e 16 (Encargos Gerais) não têm sigla no arquivo.
- **Nome oficial do órgão:** o arquivo do TCE-PB não traz o nome por extenso. Ele vem de leis
  publicadas no [SAPL da Câmara Municipal](https://sapl.joaopessoa.pb.leg.br/), baixadas por
  `src/collect/camara_jp.py` e listadas com a página em `NOMES_ORGAOS`
  (`src/process/despesas_regras.py`):
  - **LOA 2024** (Lei 15.066/2024), quadro por órgão ("ÓRGÃO : 10000 SECRETARIA MUNICIPAL DE EDUCAÇÃO
    E CULTURA"), para 26 órgãos. É a última LOA publicada no SAPL com os anexos; as de 2025 e 2026 têm
    só o texto da lei, digitalizado.
  - **Leis de criação de 2025:** 15.467 (Preservação, Revitalização e Inovação do Centro Histórico,
    INOVACENTRO), 15.468 (Serviços Urbanos e Zeladoria, SESUZ) e 15.469 (Cuidado e Proteção Animal). A
    15.469 não dá sigla; o TCE-PB usa SMCPA, e os empenhos do órgão 35 citam a secretaria pelo nome.
  - **Lei 15.399/2024:** novo nome da secretaria das mulheres (órgão 28), antes "Secretaria
    Extraordinária".
  - A grafia foi ajustada só em maiúsculas, acentos e abreviações ("SEC. MUNIC." → "Secretaria
    Municipal"); a da lei fica guardada. A LOA escreve "Coordenadora" no órgão 30 (Defesa Civil,
    COMPDEC); o site usa "Coordenadoria".
  - O nome vale para 2022–2026. Um órgão novo, que não esteja na lista, interrompe o pipeline até ser
    incluído com a fonte.
- **Órgão 16, Encargos Gerais do Município:** reúne os recursos sob a supervisão das secretarias da
  Administração e das Finanças, empenhados nas funções Administração e Encargos Especiais.
- **Nomes cortados:** o TCE-PB corta a descrição em 50 caracteres; esses nomes terminam em "…".
- **Por que só desde 2022:** a estrutura de órgãos mudou em 2022 (Emlur e Semob passaram do órgão 02
  para o 71). Antes disso o arquivo traz só o nome da diretoria ("DIRETORIA DE ADMINISTRAÇÃO E
  FINANÇAS"), repetido em vários órgãos. Nomear esses órgãos exigiria outra fonte (as LOAs de cada
  ano), com ganho pequeno de precisão.

## Mapa por bairro (experimental)

O histórico de cada empenho é um texto livre. Procuramos nele os nomes dos 64 bairros oficiais.
Nomes que também são palavras comuns ou nomes de pessoas (Centro, Torre, Treze de Maio, José
Américo...) só contam depois da palavra "bairro", e nomes precedidos de rua, avenida, praça ou
escola não contam. Empenhos que citam mais de um bairro não são divididos entre eles.

**É uma estimativa parcial:** só 0,7% a 5% do valor empenhado de cada ano cita um único bairro
(`bairros_cobertura.csv`). A maior parte do gasto (folha, saúde, educação em rede) não é
atribuível a um bairro pelo texto.

## Limitações

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

## Conferência com o Tesouro (SICONFI)

| Ano | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Diferença TCE-PB × SICONFI | +0,06% | 0,00% | −42,25% | 0,00% | 0,00% | 0,00% | +3,12% | 0,00% | 0,00% | 0,00% | 0,00% | +0,13% |

O teste aceita até **0,2%** de diferença; 2016 e 2020 são exceções documentadas em `src/config.py`.
O SICONFI não tem a DCA de João Pessoa antes de 2014. Detalhes em
`data/processed/despesas/validacao_siconfi.csv`.

## Dados processados (`data/processed/despesas/`)

| Arquivo | Conteúdo |
|---|---|
| `despesas_cubo.parquet` | valores empenhado/liquidado/pago (nominais e corrigidos) por ano, mês, unidade gestora, função, subfunção, grupo de natureza da despesa, modalidade de licitação, tipo de credor e transferência interna; com o arquivo de origem e o fator do IPCA |
| `credores_pj.parquet` | valores por CNPJ, ano e unidade gestora (sem pessoas físicas e sem folha), nominais e corrigidos, com marca de entidade pública |
| `bairros_citados.csv` / `bairros_cobertura.csv` | valor por bairro citado (nominal e corrigido) e cobertura por ano |
| `validacao_siconfi.csv` | total anual TCE-PB × SICONFI |
| `ipca.csv` / `populacao.csv` | séries usadas na correção e no gasto por habitante |
| `orgaos.parquet` | 2022 em diante: valor por ano, unidade gestora, órgão, unidade orçamentária (com o nome de cada ano em `nome_no_arquivo`), função e repasse interno (`intra`), empenhado, liquidado, pago e corrigidos pelo IPCA |
| `metadados.json` | mês de referência do IPCA, última data de empenho, checagens, aviso e manifesto dos arquivos brutos |

Cada linha do cubo e da tabela de credores traz o `arquivo_origem` (ex.: `despesas-2025.zip`), e o
manifesto liga esse arquivo à URL, à data de download e ao SHA-256.
