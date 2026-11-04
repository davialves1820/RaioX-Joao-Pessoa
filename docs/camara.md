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
| TCE-PB, dados abertos do SAGRES (`servidores-AAAA.zip`) | folha de pessoal mensal: cargo, vínculo e valor bruto; o CPF já vem mascarado | `python -m src.collect.tce_pb` |
| [Lei 14.702/2022](https://sapl.joaopessoa.pb.leg.br/media/sapl/public/normajuridica/2022/19248/lei_no_14702-2022.pdf) | subsídio da legislatura 2025–2028: R$ 26.000 por vereador e R$ 32.000 para o presidente, mais 13º | referência para os testes |

O SAPL derruba conexões com frequência e responde 503 quando sobrecarregado. O coletor usa no
máximo 2 conexões simultâneas e tenta cada página até 8 vezes. A coleta completa leva dezenas de minutos.

## Recorte

18ª e 19ª legislaturas (2021 em diante). Desde 2021, a autoria das matérias, a presença nas sessões
ordinárias e as atas estão completas no SAPL; antes disso há lacunas (presença e atas não existem
antes de 2019).

## Arquivos gerados (`data/processed/camara/`)

| Arquivo | Conteúdo |
|---|---|
| `vereadores.csv` | um mandato por linha, com período de exercício, titular ou suplente, partido atual, foto e link do SAPL |
| `producao.csv` | matérias por vereador, ano e grupo de tipo |
| `producao_origem.csv` | matérias por ano, grupo e origem (vereador, Executivo, Mesa, comissão...) |
| `projetos.parquet` | projetos de lei ordinária e complementar, com autores, situação, lei gerada e links |
| `subsidio.csv` | valor bruto mensal pago a cada vereador |
| `folha.csv` | folha da Câmara por mês, vínculo e grupo de cargo: pessoas e total, sem nomes |
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

## Limitações

- **Custo por vereador não é calculado.** A folha não informa de qual gabinete é cada assessor. Dividir
  o custo dos gabinetes entre os vereadores seria uma estimativa, então só o total da Câmara é mostrado.
- **Presença nas sessões não é publicada.** O registro de presença do SAPL existe para quase todas as
  sessões ordinárias desde 2021, mas é incompleto. A ata da 7ª sessão ordinária (06/03/2025), por
  exemplo, lista entre os presentes vereadores que o registro do SAPL não tem. O presidente, que conduz
  a sessão, também quase nunca aparece no registro. Além disso, o SAPL não registra afastamentos (licença para assumir secretaria, por
  exemplo): há titulares com mandato "ativo" que não recebem subsídio por meses. Um número de presença
  por vereador seria enganoso. A alternativa é extrair a lista de presentes das atas oficiais
  (issue #51).
- **Votos no plenário.** O SAPL guarda só o placar (sim, não e abstenções). Votos nominais existem
  apenas nas comissões.
- **Pautas** estão incompletas no SAPL em 2025 e 2026.
- **Quantidade não mede trabalho.** Em 2025–2026, os requerimentos de obras por vereador vão de cerca
  de 2.800 a zero, e os projetos de lei de 180 a zero. Os vereadores aparecem em ordem alfabética, sem ranking.
- **Série por tipo.** O tipo "requerimento de obras e serviços" só existe desde 2019; antes, esses
  pedidos eram requerimentos genéricos.
