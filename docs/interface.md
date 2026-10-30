# Interface do site

[← Voltar ao README](../README.md)

Como as páginas estão organizadas, o tema claro e escuro e o uso no celular.

## Organização das páginas

Nas três páginas, o mapa (ou as opções, na de despesas) fica na primeira tela, e o resto fica em abas
logo abaixo, em vez de uma página longa:

- **Bairros e população:** cor do mapa numa lista; painel do bairro em três cartões (população,
  território, renda e saneamento); abas *Quem cresceu e quem perdeu*, *Tabela completa* e *Sobre os dados*.
- **Serviços e acesso:** indicadores agrupados na lista "Cor do mapa" (distância, saúde, educação);
  painel do bairro em cartões (índice e área verde, distâncias, serviços por 10 mil moradores); abas
  *Mais gente, menos serviços*, *Índice de acesso*, *Matrículas*, *Renda e acesso*, *Gasto em saúde e
  educação* e *Fontes e limitações*.
- **Para onde vai o dinheiro:** as opções que valem para todas as abas ficam num quadro próprio.
- **Mapas:** a escala de cor mostra os números no padrão brasileiro (60.000, e não 60,000), com a unidade
  no topo e "≥" na última marca quando a cor satura; o zoom e a posição se mantêm ao trocar de indicador;
  um clique na legenda esconde ou mostra uma camada.

## Modo claro e escuro

O site abre no tema do sistema (claro ou escuro), e o botão do canto superior direito (lua ou sol)
troca entre **Claro** e **Escuro**. É o único botão do topo: o menu ⋮ do Streamlit e os botões do
Streamlit Cloud (Share, estrela, editar, que só o dono do app vê) ficam escondidos por CSS. Mapas e gráficos trocam de cor junto: no escuro, o mapa de fundo é o
CARTO *Dark Matter* e as cores vêm da mesma paleta, em tons escolhidos para o fundo escuro
(`src/app/tema.py`), e não de uma inversão automática.

- **Escala sequencial (azul):** no claro vai do azul-claro (pouco) ao azul-escuro (muito); no escuro, ao
  contrário, para o tom de "pouco" se confundir com o fundo. As legendas que falam de tom ("mais escuro =
  mais longe") trocam junto.
- **Camadas de pontos no escuro:** amarelo `#e09a00`, violeta `#9085e9` e vermelho `#e66767`, com anel da
  cor do fundo. O amarelo da paleta escura (`#c98500`) ficava parecido demais com o vermelho (validador:
  ΔE 13,0, abaixo do mínimo de 15); `#e09a00` dá 15,7. Ele sai um pouco da faixa de luminosidade da
  paleta escura, o que foi aceito porque são pontos sobre o mapa, com legenda e contagem.
- **Treemap de despesas:** mesma rampa nos dois temas, só nos tons em que o texto branco é legível.
- **Como o botão funciona:** o Streamlit não deixa o Python trocar o tema, então o botão usa a opção
  Claro/Escuro do menu ⋮, que continua na página, invisível. O Streamlit só informa o novo tema ao Python
  na próxima atualização (issue [#11920](https://github.com/streamlit/streamlit/issues/11920)); um
  observador na página percebe a troca e pede essa atualização (atalho "R"), no máximo duas vezes a cada
  10 segundos, para nunca entrar em ciclo.
- **O que não dá para esconder:** no Streamlit Cloud, os selos do canto inferior direito (a foto do dono e
  o logo do Streamlit, e o "Manage app" que só o dono vê) ficam fora do app e não podem ser tirados pelo
  código.

## No celular

O Streamlit não informa a largura da tela, então o app usa o navegador (User-Agent) para reconhecer
celulares. Neles, os mapas ficam mais baixos (460 px), com zoom menor para a cidade inteira caber na
largura, e a escala de cor fica deitada no rodapé do mapa. As colunas empilham sozinhas, e a página não
rola na horizontal (conferido a 390 px de largura); só as tabelas largas rolam dentro delas.
