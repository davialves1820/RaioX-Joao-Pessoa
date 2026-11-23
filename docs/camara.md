# Câmara Municipal: fontes, regras e limitações

Dados da Câmara Municipal de João Pessoa: vereadores, produção legislativa, situação dos projetos
de lei, subsídio e folha de pessoal. A investigação das fontes está na
[issue #45](https://github.com/davialves1820/RaioX-Joao-Pessoa/issues/45).

A página "Câmara Municipal" do painel (`src/app/camara.py`) usa estes arquivos; as funções de apoio,
sem Streamlit, estão em `src/app/dados_camara.py`.

## Fontes

| Fonte | O que traz | Coleta |
|---|---|---|
| [SAPL da Câmara](https://sapl.joaopessoa.pb.leg.br/api/) (API aberta) | matérias, autoria, normas jurídicas, tramitações, parlamentares, mandatos, filiações, sessões e presença | `python -m src.collect.camara_sapl` |
| SAPL: atas, ordem do dia, votos nominais e comissões | atas das sessões ordinárias e extraordinárias (PDF), lista de presentes e ausentes, votos nas comissões | `python -m src.collect.camara_sessoes` |
| TCE-PB, dados abertos do SAGRES (`servidores-AAAA.zip`) | folha de pessoal mensal: cargo, vínculo e valor bruto; o CPF já vem mascarado | `python -m src.collect.tce_pb` |
| TCE-PB, empenhos (`data/interim/empenhos.parquet`) | despesas e diárias da Câmara, por elemento de despesa | `python -m src.process.despesas` (antes do processamento da Câmara) |
| Tesouro Nacional, SICONFI (RGF Anexo 01, Poder Legislativo) | despesa com pessoal da Câmara e limites da LRF, por quadrimestre | `python -m src.collect.siconfi` |
| [Lei 14.702/2022](https://sapl.joaopessoa.pb.leg.br/media/sapl/public/normajuridica/2022/19248/lei_no_14702-2022.pdf) | subsídio da legislatura 2025–2028: R$ 26.000 por vereador e R$ 32.000 para o presidente, mais 13º | referência para os testes |

O SAPL derruba conexões com frequência e responde 503 quando sobrecarregado. O coletor usa no
máximo 2 conexões simultâneas e tenta cada página até 8 vezes. A coleta completa leva dezenas de minutos.

## Recorte

18ª e 19ª legislaturas (2021 em diante). Desde 2021, a autoria das matérias e as atas das sessões
ordinárias estão completas no SAPL; antes disso há lacunas (presença e atas não existem
antes de 2019).

## Arquivos gerados (`data/processed/camara/`)

| Arquivo | Conteúdo |
|---|---|
| `vereadores.csv` | um mandato por linha, com período de exercício, titular ou suplente, partido atual, foto e link do SAPL |
| `producao.csv` | matérias por vereador, ano e grupo de tipo |
| `projetos.parquet` | projetos de lei ordinária e complementar, com autores, situação, lei gerada e links |
| `subsidio.csv` | valor bruto mensal pago a cada vereador |
| `materias.parquet` | demais matérias (indicações, requerimentos, votos de aplauso e pesar, resoluções, emendas...), com autores e link |
| `normas.parquet` | leis, resoluções e decretos legislativos, com link para o texto oficial |
| `sessoes.csv` | sessões e reuniões, com links da pauta e da ata |
| `folha_cargos.csv` | folha da Câmara por mês, vínculo e cargo: pessoas e total, sem nomes |
| `despesas_por_elemento.csv` | despesas da Câmara e do fundo da Câmara (FEJP) por ano e elemento de despesa |
| `diarias.csv` | diárias por mês, só totais (quem recebe são pessoas físicas) |
| `rgf.csv` | despesa com pessoal da Câmara frente à Receita Corrente Líquida e aos limites da LRF, por quadrimestre |
| `metadados.json` | regras, checagens e arquivos brutos usados (URL, data e SHA-256) |

## Regras

**Grupos de tipo.** Os tipos de matéria do SAPL são agrupados em projetos de lei (ordinária e
complementar), propostas de emenda à Lei Orgânica, projetos de resolução, projetos de decreto
legislativo, indicações, requerimentos de obras e serviços, votos de aplauso, pesar e similares,
emendas impositivas ao orçamento, outros requerimentos, emendas e substitutivos, e outros.
O SAPL de João Pessoa não tem o tipo "moção": os votos de aplauso e pesar são requerimentos
(art. 171, X, do Regimento Interno).

**Produção.** Cada matéria conta uma vez para cada vereador autor ou coautor.

**Situação dos projetos de lei.**
- *Virou lei*: uma norma jurídica do SAPL aponta para o projeto (521 das 524 normas de 2025 têm essa ligação).
- *Em tramitação*: o SAPL marca o projeto como em tramitação.
- Nos demais casos, pelo status e pelo texto da última tramitação:
  - *Vetado*: o veto aparece no status ou no texto;
  - *Rejeitado em plenário*;
  - *Retirado pelo autor*;
  - *Arquivado*: em geral, depois de parecer contrário na Comissão de Constituição e Justiça e fim do prazo de recurso;
  - *Sem conclusão registrada*: nenhum dos anteriores.

O campo `resultado` do SAPL vem sempre vazio e não é usado. A rejeição em votação no plenário é rara: a maior parte dos projetos que não viram lei é arquivada na comissão.

**Subsídio.** Campo `valor_vantagem` da folha do TCE-PB: o total bruto do mês. Inclui o 13º e os meses
proporcionais (posse ou saída no meio do mês). A folha é ligada ao SAPL pelo nome completo. Quando o SAPL
abrevia ou grafa diferente, a ligação vem de uma tabela conferida pelo período de mandato
(`CORRESPONDENCIA_FOLHA` em `src/process/camara.py`). Os meses pagos fora do período de mandato
registrado no SAPL ficam listados em `metadados.json` (`subsidio_fora_do_periodo_no_sapl`): 13º pago
depois da saída, ou exercício que o SAPL não registra (Marcelo da Torre recebeu de junho a setembro de
2022, mas o SAPL só tem a suplência de 2024).

**Folha.** Pessoas distintas (matrícula) e total bruto por mês, vínculo e grupo de cargo. Os grupos de
cargo saem do nome do cargo: gabinetes dos vereadores, Mesa Diretora e Presidência, comissões,
lideranças, comunicação e cerimonial, administração e apoio, e cedidos por outros órgãos. A Câmara
tem cerca de 470 cargos de gabinete por mês.

## Pedidos de obras por bairro

`python -m src.process.camara_pedidos` (depois de `src.process.camara`) gera
`requerimentos_bairros.parquet`: uma linha por requerimento de obras, serviços e melhoramentos e bairro
citado, com tema(s), órgão destinatário, ano e autores. O resumo fica em `metadados_pedidos.json`.

- **Bairro:** os 64 nomes oficiais (sem acento e sem diferenciar maiúsculas) e variações do próprio
  nome ("Cristo", "Geisel", "Valentina de Figueiredo"...; lista em `VARIACOES`). Nomes que também são
  palavras comuns (Centro, Torre, Estados, Penha, Cuiá, Roger, Ipês) só contam com contexto de endereço
  ("bairro do Centro", ", Centro"), para não pegar "Centro de Vigilância" ou "torre de telefonia".
- **Resultado (2021 a 11/2026):** 82,2% dos 83.603 requerimentos citam exatamente um bairro, 1,5%
  citam mais de um e 16,3% nenhum reconhecível. Numa amostra de 60 conferida à mão, 59 estavam
  certos (o outro cita um ponto de referência, a falésia do Cabo Branco). Trechos da amostra viraram
  testes.
- **Sem bairro:** pedidos para a cidade toda ou por região, e pedidos que citam só a comunidade ou o
  loteamento (Rangel, Novais, Colinas do Sul, Quadramares...). Esses nomes não são ligados a um bairro
  porque não há fonte oficial no projeto que diga onde fica cada um.
- **Tema** (palavras-chave, um pedido pode ter mais de um) e **órgão** (primeira sigla citada) servem
  para filtrar.
- **No painel** (seção *Pedidos por bairro* da página da Câmara): mapa e tabela por bairro, em total ou
  por mil moradores, com filtros de ano, tema e vereador; e a lista dos pedidos de um bairro, com link para o SAPL. A taxa por mil moradores não é
  calculada em bairros com menos de 1.000 moradores (Mussuré, área industrial, tem 3), onde ela não diz
  nada. Pedido não é problema confirmado: mostra o que os vereadores pediram, não o estado da cidade.

## Emendas impositivas e sua execução

`python -m src.collect.camara_emendas` baixa o texto original das emendas impositivas ao orçamento
(tipos ELO-I e EI-CO do SAPL). `python -m src.process.camara_emendas` (depois de `src.process.camara`;
requer o `pdftotext`, do pacote poppler-utils) gera:

- `emendas.parquet`: uma linha por emenda, com autor, valor, órgão, unidade orçamentária, natureza da
  despesa, beneficiário (meta e CNPJ), valores empenhado e pago nos empenhos ligados e a melhor
  conferência da ligação;
- `emendas_empenhos.parquet`: os empenhos do TCE-PB que citam o número de uma emenda;
- `metadados_emendas.json`.

**Valor e beneficiário.** A ementa no SAPL é incompleta (um terço traz o valor ou o CNPJ). O texto
original é um formulário padrão (PDF ou Word) com "Valor acrescido", dotação e meta, de onde saem os
campos. Das 401 emendas de 2025 ao orçamento de 2026, 383 têm o valor lido; 16 são PDFs digitalizados,
sem texto, e 2 trazem o valor mal digitado ("30.0000,00" e "70.0000,00", nº 261 e 262/2025: 30 ou 300
mil?). Essas 18 ficam com o valor vazio; o texto mal digitado fica em `valor_no_texto`.

**Execução.** O empenho cita a emenda no histórico ("EMENDA IMPOSITIVA Nº 393/2025"); a ligação é pelo
número e ano (o mesmo número do SAPL), lendo todas as citações de cada histórico. Emendas federais
(numeração de 11 dígitos) não entram. A ligação é conferida: CNPJ igual ao da emenda; mesma raiz de
CNPJ (matriz e filial); nome parecido, quando a emenda não traz CNPJ; "a conferir" (por exemplo, um
fornecedor comprando equipamento para a entidade); ou CNPJ diferente. Nada é descartado: as
divergências aparecem marcadas.

**No painel** (seção *Emendas impositivas* da página da Câmara): totais, uma tabela por vereador em
ordem alfabética (emendas, valor, empenhado e pago) e a lista de emendas com busca e filtros de
vereador, situação e conferência; cada emenda mostra beneficiário, dotação, valor, links para o SAPL e
para o texto original, e os empenhos que a citam.

**Número repetido.** A emenda corrigida (EI-CO) tem numeração própria e pode repetir o número de uma
ELO-I. O SAPL não indica qual emenda a corrigida substitui, então ela entra na soma por vereador (a de
Tarcísio Jardim passa da cota em R$ 80 mil por isso). Com mais de uma candidata, a ligação fica com a de melhor conferência; se nenhuma confere pelo
CNPJ ou pelo nome, fica "a conferir".

**Avisos.** "Sem empenho encontrado" não quer dizer "não executada": o empenho pode não citar o número,
ou ainda não ter saído. Emenda não executada também não é irregularidade (a lei prevê impedimento
técnico). Credor pessoa física aparece sem nome nem histórico, com o CPF mascarado.

## Presença nas sessões e votos nas comissões

`python -m src.collect.camara_sessoes` baixa as atas das sessões ordinárias e extraordinárias (2021 em
diante), a ordem do dia, os votos nominais e as comissões. `python -m src.process.camara_sessoes` (depois
de `src.process.camara`; requer o `pdftotext`) gera:

- `presencas.parquet`: uma linha por sessão e vereador, com a situação na ata (presente, presente de forma
  virtual, ausente com justificativa, ausente);
- `atas_presenca.csv`: cada ata lida, quantos vereadores ela lista, as cadeiras e se foi conferida (com o motivo, se não);
- `votos_comissoes.parquet`: os votos nominais nas reuniões de comissão, com matéria, comissão e resultado;
- `sessoes_video.csv`: o link do vídeo da sessão, quando o SAPL tem;
- `metadados_sessoes.json`.

**Presença.** A ata de cada sessão traz, antes da abertura, a composição da mesa e as listas de
presentes em plenário, presentes de forma virtual, ausentes com justificativa e ausentes, com nome
completo e partido. Cada nome é ligado a um vereador do SAPL da mesma legislatura (nome completo, nome
parlamentar ou a maior parte das palavras do nome). Uma ata só entra quando é **conferida**: todo nome
foi ligado, cada vereador aparece numa só situação e o total listado é igual ao número de cadeiras
(titulares que tomaram posse no primeiro dia da legislatura, no SAPL: 27 na 18ª e 29 na 19ª). As demais
ficam em `atas_presenca.csv` com o motivo; em geral, a própria ata lista um vereador a menos ou a mais.

A lista é a da **abertura dos trabalhos**: quem chega depois aparece como ausente. A ata é o documento
oficial; o registro de presença do SAPL serviu de conferência (11/2026, sessões com registro): 97% dos
presentes na ata estão no registro, e 6% dos ausentes também (chegaram depois da abertura). Resultado:
403 das 442 atas de 2021 a 11/2026 conferidas; das 39 restantes, 7 não têm o bloco de presença no
formato padrão (posse e eleição da mesa, por exemplo) e a maioria lista um vereador a mais ou a menos.

**Votos nas comissões.** O SAPL registra o voto de cada membro nas reuniões de comissão (CCJRLP, CPP,
CFOOAP e CCDHDC), quase sempre sobre o parecer do relator. São votos sobre pareceres, não a votação final
em plenário.

**No painel:** seção *Presença* (tabela por vereador em ordem alfabética, por legislatura e ano, com as
atas não conferidas e o motivo), seção *Votações nas comissões* (cada votação com os nomes por voto,
filtros de comissão, ano, vereador e "só com voto contrário ou abstenção"), a presença e o vídeo em cada
sessão de *Pautas e atas*, e, no perfil do vereador, a presença e os votos contrários e abstenções.

**Cadastro duplicado.** O SAPL tem um cadastro antigo de Marcos Vinícius (id 45, mandato de 2001–2004)
em que foram registrados 34 votos na CCJRLP em abril de 2025; eles são atribuídos ao cadastro atual (id
382), que não vota nessas mesmas votações (`CADASTRO_DUPLICADO`).

**Paginação da API.** Sem ordenação explícita, algumas listas do SAPL (a ordem do dia, por exemplo) mudam
de ordem entre as páginas: registros vêm repetidos e outros somem, com o total certo. A coleta pede
`o=id` em todas as consultas e para se algum id se repetir.

## Limitações

- **Custo por vereador não é calculado.** A folha não informa de qual gabinete é cada assessor. Dividir
  o custo dos gabinetes entre os vereadores seria uma estimativa, então só o total da Câmara é mostrado.
- **Votos no plenário.** O plenário vota de forma simbólica: o SAPL guarda só o resultado. Votos nominais
  existem apenas nas comissões.
- **Pautas** estão incompletas no SAPL em 2025 e 2026.
- **Quantidade não mede trabalho.** Em 2025–2026, os requerimentos de obras por vereador vão de cerca
  de 2.800 a zero, e os projetos de lei de 180 a zero. Os vereadores aparecem em ordem alfabética, sem ranking.
- **Série por tipo.** O tipo "requerimento de obras e serviços" só existe desde 2019; antes, esses
  pedidos eram requerimentos genéricos.
