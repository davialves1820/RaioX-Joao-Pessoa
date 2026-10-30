# Manutenção: coleta, atualização, testes e deploy

[← Voltar ao README](../README.md)

Como baixar e atualizar os dados, rodar os testes, atualizar as bibliotecas e publicar o site.

## Estrutura do código

```
streamlit_app.py   entrada do Streamlit: liga as três páginas
src/collect/       um script de coleta por fonte (+ download.py, que mantém o manifesto);
                   python -m src.collect roda todos
src/process/       build.py (bairros e população), censo_bairros.py (renda e saneamento),
                   despesas.py + despesas_regras.py + despesas_bairros.py, servicos.py
src/app/           app.py + dados.py (bairros), servicos.py + dados_servicos.py,
                   despesas.py + dados_despesas.py; tema.py (cores claro/escuro, mapa, estilo)
data/raw/          dados brutos, uma pasta por fonte (só o manifest.json é versionado)
data/interim/      tabela de empenhos linha a linha (não versionada; cerca de 40 MB)
data/processed/    dados prontos para o painel (versionados)
tests/             testes do pipeline, dos dados e das funções do painel
```

Ordem do processamento: `build` → `despesas` e `censo_bairros` → `servicos`.

## Coleta

- **Arquivo já baixado não é baixado de novo** (`--force` rebaixa tudo). Downloads interrompidos não
  deixam arquivos pela metade.
- **Dados que mudam com o tempo:** nada se atualiza sozinho; ver [Atualizar os dados](#atualizar-os-dados).
- **INEP:** o Catálogo de Escolas é exportado por um navegador automatizado (Playwright + Chromium);
  para atualizar, use `python -m src.collect.inep_catalogo --force`. Se o painel mudar, o docstring do
  script explica a exportação manual.
- **Filipeia (Prefeitura):** o portal bloqueia acesso automatizado. As camadas são exportadas à mão para
  `data/raw/filipeia/` e registradas com `python -m src.collect.filipeia --registrar`; o docstring do
  script lista os arquivos.

Os dados brutos não ficam no git (são grandes e reprodutíveis); os processados ficam, porque o app usa só eles.

## Atualizar os dados

**Nada se atualiza sozinho.** O site lê os arquivos de `data/processed/` que estão no repositório; o
único fluxo automático do GitHub é o de testes. Para atualizar, rode a coleta e o processamento, confira
com os testes e faça commit dos arquivos processados (o manifesto, `data/raw/manifest.json`, vai junto).
O Streamlit Cloud publica a nova versão a cada push na `main`.

| O que muda | Com que frequência | Como atualizar |
|---|---|---|
| Despesas do ano corrente (TCE-PB) | o TCE-PB regera o arquivo com frequência | receita abaixo |
| IPCA e estimativas de população (IBGE) | IPCA todo mês; população uma vez por ano | `python -m src.collect.ibge_sidra --atualizar` |
| Conferência com o Tesouro (SICONFI) | uma vez por ano, após a prestação de contas | `python -m src.collect.siconfi` (baixa até o ano anterior os arquivos que ainda não estão em `data/raw/siconfi/`) |
| Unidades de saúde e equipes (CNES) | todo mês | `python -m src.collect.cnes --atualizar` e `python -m src.collect.cnes_base --force`, depois `python -m src.process.servicos` |
| Escolas e matrículas (INEP) | uma vez por ano | `python -m src.collect.inep_catalogo --force`; para os microdados de outro ano, mude `ANO` em `src/collect/inep_microdados.py` (o processamento usa esse ano) e rode `python -m src.collect.inep_microdados` |
| Praças, parques e bairros da Prefeitura (Filipeia) | quando a Prefeitura atualizar | exportação manual (ver acima) |
| Censos do IBGE, OpenStreetMap, leis da Câmara | raramente | `--force` no script da fonte |

`python -m src.collect --atualizar` rebaixa de uma vez tudo o que muda com o tempo (despesas do ano
corrente, IPCA, população e CNES).

**Receita dos gastos:**

```bash
python -m src.collect.tce_pb --atualizar     # ano corrente do TCE-PB e a listagem com as datas de geração
python -m src.collect.ibge_sidra --atualizar # IPCA e população mais recentes
python -m src.collect.siconfi                # anos que ainda não foram baixados para a conferência com o Tesouro
python -m src.process.despesas               # refaz data/processed/despesas/
pytest                                       # confere, entre outras coisas, os totais com o SICONFI
git add data/raw/manifest.json data/processed/despesas && git commit -m "dados: despesas até DD/MM/AAAA"
```

- **Virada do ano:** o `--atualizar` passa a baixar o arquivo do ano novo. O ano que terminou deixa de
  ser marcado "em andamento" na próxima vez que o processamento rodar. Para pegar a versão final dele,
  apague `data/raw/tce_pb/despesas-AAAA.zip` e rode o coletor de novo (`--force` rebaixa todos os anos).
- **O pipeline para em vez de adivinhar.** Uma modalidade de licitação nova (`MODALIDADES`), um órgão
  novo sem nome oficial (`NOMES_ORGAOS`, com a fonte), ambas em `src/process/despesas_regras.py`, ou um
  código de função desconhecido (`FUNCOES`, em `src/process/despesas.py`) interrompem o processamento,
  com a mensagem do que falta.
- **Teste que falha depois da atualização** (ex.: um ano novo fora da tolerância do SICONFI) é sinal de
  conferir a fonte antes de publicar, não de ajustar o teste.

## Testes automáticos (CI)

O workflow [`.github/workflows/testes.yml`](../.github/workflows/testes.yml) roda o `pytest` em todo PR e em
todo push na `main`, com Python 3.12 e 3.13. Ele instala só `requirements.txt` e o pytest; os testes que
dependem de `data/raw/` (não versionado) são pulados, e os demais usam `data/processed/`. Um PR com teste
quebrado aparece com o check **Testes** em vermelho.

## O que os testes conferem

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

## Atualizar as bibliotecas

`requirements.txt` fixa as versões exatas, porque o Streamlit Community Cloud instala esse arquivo a cada
deploy e uma versão nova pode quebrar o site sem mudança no código. Para atualizar:

1. Num ambiente limpo, instale as versões novas (`pip install -U` das bibliotecas listadas).
2. Rode o pipeline e `pytest`, e abra o app para conferir as três páginas.
3. Copie as versões de `pip freeze` para `requirements.txt` e abra um PR: o CI testa nas duas versões
   do Python.

## Deploy no Streamlit Community Cloud

1. Em [share.streamlit.io](https://share.streamlit.io), clique em **Create app** e escolha este
   repositório e a branch `main`.
2. Em *Main file path*, use `streamlit_app.py` (é o padrão).
3. Em *Advanced settings*, escolha Python 3.12 ou 3.13 (as versões testadas no CI). Não há segredos a configurar.

O app lê apenas `data/processed/`; não é preciso rodar a coleta no deploy. Cada push na `main`
atualiza o site.
