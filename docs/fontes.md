# Fontes dos dados

[← Voltar ao README](../README.md)

Todas as fontes usadas, como são obtidas e onde entram. Os detalhes e as limitações de cada uma estão na página que a usa: [bairros](bairros.md), [serviços](servicos.md) e [despesas](despesas.md).

As datas exatas (UTC), as URLs e os SHA-256 de cada arquivo estão em
[`data/raw/manifest.json`](../data/raw/manifest.json).

| Fonte | Usada em | Como é obtida | Data dos dados |
|---|---|---|---|
| IBGE, Censo 2022 (bairros, setores e malhas) | as três páginas | download do FTP do IBGE | 2022 |
| IBGE, Censo 2010 (setores) | Bairros | download do FTP do IBGE | 2010 |
| IBGE, SIDRA (IPCA e estimativas de população do município) | Dinheiro | API do SIDRA | IPCA até set/2026 |
| INEP, Catálogo de Escolas | Serviços | exportação do painel por navegador automatizado | situação do Censo Escolar 2024 |
| INEP, microdados do Censo Escolar (matrículas) | Serviços | download do portal do INEP | Censo Escolar 2024 |
| Ministério da Saúde, CNES | Serviços | API de dados abertos | cadastros até 16/10/2026 |
| Ministério da Saúde, DATASUS, base completa do CNES (equipes de Saúde da Família) | Serviços | download do DATASUS | competência 09/2026 |
| Prefeitura, Filipeia (parques, praças, quadras, bairros) | Serviços | exportação manual pelo navegador | parques: 2021; praças: intervenções até 2018 |
| OpenStreetMap (matas, áreas protegidas, 2 escolas) | Serviços (só no mapa e em 2 coordenadas) | Overpass API e API do OSM | consulta de 23/10/2026 |
| OpenStreetMap (ruas e caminhos) | Serviços (distância pelas ruas) | Overpass API | base de 15/07/2026 |
| geodata-jp (cópia de camadas da Prefeitura e do INEP) | Bairros e Serviços, como apoio | download do GitHub (commit fixo) | fev/2022 |
| TCE-PB, SAGRES (empenhos) | Dinheiro | download do portal de dados abertos | 2009 a 09/10/2026 |
| Tesouro Nacional, SICONFI | Dinheiro (conferência dos totais) | API do SICONFI | 2014–2025 |
| Câmara Municipal, SAPL (LOA 2024 e leis de 2024–2025) | Dinheiro (nomes oficiais dos órgãos) | download do SAPL | leis de 2024 e 2025 |

## Onde o geodata-jp ainda é usado

O [geodata-jp](https://github.com/paulovitorweb/geodata-jp) é um repositório que copiou, em fevereiro
de 2022, camadas do Filipeia (Prefeitura) e do Catálogo de Escolas do INEP. O repositório **não declara
licença**, por isso ele só entra onde não há alternativa oficial acessível, e sempre conferido:

| Uso | Por que não a fonte oficial | Como é conferido |
|---|---|---|
| **Correspondência de nomes** entre os bairros do IBGE e os da Prefeitura (`crosswalk_bairros.csv`); não aparece no mapa | na época, o Filipeia não era acessível | — (pode ser trocado pelo `bairros.zip` oficial do Filipeia, de 2026) |
| **Contornos das 214 praças** (área verde da página de serviços) | o Filipeia oferece só a tabela das praças, sem o shapefile | o pipeline exige nome e área idênticos aos da tabela oficial, senão para; 160 das 162 praças com código de quadra ficam na quadra indicada pelo cadastro de 2026 |
| **Coordenadas de 3 escolas** que o INEP publica sem localização | o INEP atual não tem a coordenada | só coordenadas que não se repetem em outras escolas (o geodata-jp põe 12 escolas num mesmo ponto genérico, descartado) |

Os parques, que antes também vinham do geodata-jp, agora vêm do shapefile oficial do Filipeia, idêntico ao anterior.
