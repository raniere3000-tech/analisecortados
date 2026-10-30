# Análise de Corte e Religação

Painel que lê os arquivos de atividades de campo (`Atividades-*.xlsx`) e o cadastro de ligações direto da pasta do
SharePoint e mostra o saldo de economias, os cortes × religações, o pós-corte e a permanência no corte.

## Como usar

Abra o site (GitHub Pages deste repositório) no **Chrome ou Edge**, clique em **📁 Conectar pasta** e escolha a pasta do
SharePoint sincronizada no computador pelo OneDrive. As subpastas também são lidas. Depois de colocar arquivos novos
na pasta, clique em **↻ Atualizar**: arquivos que não mudaram não são lidos de novo (a leitura fica guardada no navegador).

**Ao abrir ou atualizar a página**, o painel mostra na hora a última leitura e já começa a ler a pasta de novo (o Python
começa a baixar assim que a página abre). Se o navegador guardou a permissão da pasta (no Chrome/Edge, escolha
"Permitir em todas as visitas" quando ele perguntar), a leitura começa sozinha; senão, basta um clique em qualquer
lugar da página.

O processamento roda no navegador: o site executa o pacote Python `cortes/` com o [Pyodide](https://pyodide.org)
(`analisador.worker.js` + `executor_web.py`). Os arquivos não são enviados para nenhum servidor. Na primeira vez, o
navegador baixa o Python (cerca de 30 MB), que depois fica em cache.

### Arquivos da pasta

| Arquivo | Como é reconhecido | Usado para |
|---|---|---|
| Atividades | nome começa com `Atividades-` (vários arquivos, em qualquer subpasta) | cortes, religações, implantações e vistorias pós-corte |
| Religação LISC / autoreligação | colunas `Matrícula`, `Serviço Executado`, `Dt. Execução` — aceitam variações (`Matricula`, `Serviço`, `Dt Execução`, `Data de Execução`…; ver `religacao_lisc.colunas` no `regras.json`); título acima do cabeçalho é ignorado | cada O.S. com data de execução vira religação Finalizada. `AUTO RELIGAÇÃO`/`AUTO-RELIGAÇÃO` = AUTORELIGAÇÃO; serviço sem tipo usa o nome do arquivo (`Autoreligação.xlsx` → AUTORELIGAÇÃO), senão LISC. Só valem as cidades das atividades (`Nome da Localidade`/`Localidade`/`Município`, comparando sem acento, pontuação e com abreviações: `S.FCO.DO ITABAPOANA` = `São Francisco de Itabapoana`) ou matrículas que têm atividade. Planilha vazia ou sem as colunas aparece na aba Dados com o motivo |
| Cadastro | colunas `NUM_LIGACAO`, `SIT_LIG`, `TOTAL_ECO` (cabeçalho pode estar abaixo de um título) | situação atual (ATIVA/CORTADA), economias, cliente |
| Descrição serviço (opcional) | colunas `SERVICO` e `CATEGORIA` | código do serviço → categoria; sem ela vale `cortes/catalogo_servicos.json` |

Colunas usadas das atividades: Recurso, ID da Atividade, Número da Conta, Matrícula, Código/Descrição, Data, Status da
Atividade, Cidade, Parecer De Campo, Motivo de Não Execução - Normal, Valor Total dos Débitos, Negociou O Débito?.
A mesma atividade (mesmo *ID da Atividade*) em mais de um arquivo conta uma vez.

## Abas

- **Saldo de economias**: por mês, −corte (por tipo) + religação (por tipo) + implantação de ligação de água, em
  economias (`TOTAL_ECO`) ou em ligações, com o saldo do mês e o acumulado.
- **Corte × Religação**: destino dos cortes de cada mês em barras de 100% deitadas (Sem religação sempre na ponta direita, quantidade
  de cortes ao lado do mês, meses em aberto mais claros), mapa de calor da velocidade de religação (% acumulado religado até
  cada mês depois do corte; clique numa célula para ver os clientes) e duas tabelas mês do corte × mês da religação — uma em
  quantidade e outra em % da linha (na linha Total Geral, cada mês de religação mostra 100% = religações feitas no mês; Sem religação e % religado são sobre todos os cortes). A **Medida** (Matrículas = contagem de cortes, igual à “Contagem de Matrícula” da tabela
  dinâmica; ou Economias = soma do TOTAL_ECO) é uma só: trocar numa tabela troca na outra.
  **Período vale para**: “Corte e religação” (padrão) — o mês inicial/final filtra o mês do corte e também o mês da religação, como
  filtrar as duas colunas na tabela dinâmica (religação depois do mês final tira o corte da conta, com aviso e lista); “Só corte” — como antes.
  Linhas da base sem data do corte não entram (no Excel aparecem como “(vazio)”).
- **Pós-corte**: como a tabela dinâmica “clientes sem a 1ª visita” — filtros na aba: **Pós-corte** (Sem/Com/Todos), **Religação**
  (Sem/Com/Todos), **Situação no cadastro**, 1ª visita sem sucesso, meses do corte (vários) e colunas por régua, tipo, cidade ou recurso.
  Padrão: sem pós-corte, sem religação e CORTADA (“Voltar ao padrão” restaura). Um gráfico e uma tabela mês do corte × colunas;
  “Ver clientes” abre a lista do filtro; o ⬇ baixa o analítico.
  Embaixo, **A visita pós-corte faz o cliente religar?**: frase-resumo (“de cada 100 visitados, X religam em até 15 dias; sem visita, Y”),
  indicadores (visitados, religaram depois, tempo até religar, visita sem necessidade), barras em até 7/15/30 dias com × sem visita
  e a curva acumulada de religação a partir da visita. Comparação com clientes sem visita no mesmo tempo de corte; filtro Todas/Finalizadas/Sem sucesso.
  Mais: “Quando visitar?” (efeito por tempo de corte no dia da visita: 0–3, 4–7, 8–15, 16–30, +30 dias, com a diferença em p.p. acima
  das barras), evolução mês a mês, tabela de detalhamento (por tempo até a visita, tipo, cidade, Sup, mês ou resultado da visita, com
  % em 7/15/30 dias com × sem visita, efeito, mediana e visitas sem necessidade; números clicáveis) e ⬇ analítico das visitas.
- **Permanência**: tipo de corte × faixa de dias até a religação e a eficácia de cada tipo com × sem pós-corte.
- **Dados**: tópicos que abrem e fecham — Avisos, Conferência rápida (números principais com os filtros atuais e como chegar
  neles pelo analítico), Bases carregadas (pasta, hora da leitura, arquivos e detalhes técnicos), Parâmetros, Classificação dos
  serviços, Bases para download e, de 1 a 4, cada página com o que mostra, bases e colunas, cálculo passo a passo, como conferir
  e o ⬇ do analítico. Os tópicos abertos ficam guardados no navegador.

Filtros no topo (linha abaixo do título): mês inicial/final (mês do corte), Sup, cidade, tipo de corte e Ativas = religadas.
Cidade e tipo de corte aceitam vários itens: a lista abre com busca, caixas de seleção, `Todos` e `Limpar`; fecha ao clicar fora ou com Esc.
O link compartilhável guarda os itens escolhidos separados por `|`.

## Recursos do painel

- **Explicações no `?`**: os textos de como ler e como foi calculado ficam no `?` ao lado do título de cada cartão, gráfico e KPI. Aparecem ao passar o mouse, no foco do teclado ou ao tocar no celular.
- **Reporte semanal** (topo da aba Dados): as três tabelas do reporte semanal com os filtros atuais.
  - Corte × Religação em quantidade e em %, sem a coluna Ativa, com a medida e o período da aba.
  - Evolução do pós-corte com Data A × Data B, com os filtros e as datas da aba Pós-corte. As datas também mudam ali.
  - **📋 Copiar imagem** (ou **Copiar as três**) copia a tabela como figura para colar com Ctrl+V. Se o navegador não deixar copiar, a imagem é baixada em PNG. Usa o html2canvas, carregado do jsDelivr no primeiro uso.

- **Ícone da aba** (`favicon.svg`): sem fundo, gota azul e setas grossas laranja (corte) e ciano (religação); `apple-touch-icon.png` é o atalho no celular.

- **Gráficos** (Chart.js) em cada aba, com as tabelas logo abaixo como apoio: saldo mensal e por tipo, destino dos cortes e velocidade de religação, cortados sem a 1ª visita por mês e por cidade, régua de cobrança, permanência por tipo e eficácia do pós-corte. Clicar numa barra filtra o mês, a cidade ou o tipo.
- **Clicar num número** (de qualquer tabela) abre, num painel lateral, as matrículas por trás dele, com ⬇ para baixar em CSV; clicar numa matrícula mostra o histórico do cliente.
- Lista de clientes com **busca** (matrículas ou texto), ordenação pelo cabeçalho e "Mostrar todos"; qualquer tabela ordena pelo cabeçalho; tabelas largas arrastam para o lado.
- **Ativas = religadas** (filtro no cabeçalho, vale para todas as abas): quando ligado, o corte sem OS de religação cuja ligação está ATIVA no cadastro passa a contar como religado — sai de "sem religação" e de "sem a 1ª visita", entra no % religado, na régua ("Ativa sem OS de religação"), na permanência ("Ativa sem OS") e, no saldo, como religação no mês do corte. Sem data de religação, esses casos não entram nos cálculos de dias. A escolha fica lembrada e vai no link.
- **Atalhos:** `1`…`5` trocam de aba, `/` vai para a busca, `Esc` fecha o painel lateral.
- O endereço da página guarda a **aba e os filtros** (copie e envie o link); as escolhas dos botões ficam lembradas no navegador.
- **📄 Executivo** (abre a impressão em A4 paisagem; escolha "Salvar como PDF").

## Regras de cálculo

- Só OS **Finalizadas** para corte, religação e implantação; pós-corte aceita *Finalizada* e *Encerrada com Ocorrência*.
- Um corte por matrícula e data (OS principal + LISC no mesmo dia contam um).
- Religação e pós-corte: o 1º evento no dia do corte ou depois e **antes do próximo corte** da mesma matrícula.
- Régua: dias cortado contados até **hoje**. Permanência: dias entre corte e religação (0 = mesmo dia).
- Os limites das faixas, os textos e os status ficam em `cortes/regras.json`.

## Linha de comando e testes

```bash
pip install -r requirements-dev.txt
python analise_cortes.py --pasta DADOS        # grava DADOS/Base_Cortes.xlsx
python -m pytest tests -q
```

Os testes usam dados sintéticos (`tests/dados_sinteticos.py`) e rodam no GitHub Actions a cada push.

## Sup e cidades

- O filtro **Sup** (Leste / Interior) fica no cabeçalho e vale em todas as abas; a lista de cidades mostra só as da Sup escolhida.
- A Sup de cada cidade está em `cortes/regras.json` → `supervisao.cidades` (nome como em `Nome da Localidade`).
- Nomes parecidos da mesma cidade (atividades, LISC, cadastro) viram um só: sem acento, pontuação, “de/do/São”, com abreviações
  (`S.FCO.DO ITABAPOANA` = `São Francisco de Itabapoana`) e sufixos (`RIO DE JANEIRO - A` = `RIO DE JANEIRO`). Cidade fora da lista fica em “Sem Sup”.

## Downloads (⬇) — analítico

- O ⬇ de cada tabela de apoio baixa o **analítico** em CSV (separador `;`, abre direto no Excel): uma linha por corte ou OS usada
  na tabela, já com os filtros da tela. As primeiras colunas dizem onde cada linha foi contada (“Linha: mês do corte”,
  “Coluna: mês da religação”, “Coluna: régua”, “Sinal no saldo”, “Economias com sinal”…), então uma tabela dinâmica refaz o número da tela.
- Depois vêm as colunas comuns: matrícula, cliente, Sup, cidade, recurso, tipo e serviço do corte, datas e meses do corte e da religação,
  dias e meses até religar, religou no mesmo mês, pós-corte (data, status, dias do corte ao pós, religou depois do pós), régua, permanência,
  situação e origem, economias, débitos, motivo e arquivo de origem.
- O ⬇ da lista lateral (ao clicar num número) e o “Cortes filtrados (CSV)” da aba Dados usam as mesmas colunas.
- Depois que a pasta termina de carregar, o cabeçalho fica limpo (sem a linha “Pasta… lidos às” nem “Detalhes da leitura”); essas informações ficam na aba Dados → Bases carregadas.
- Painel lateral (ao clicar num número): entra deslizando sobre um fundo escurecido — clicar fora ou `Esc` fecha. Tem resumo (cortes e economias),
  busca, chips por tipo/categoria para filtrar, ordenação clicando no cabeçalho e “Mostrar mais”; o ⬇ baixa as linhas filtradas.

## Conferência com a planilha antiga

- Coloque na pasta um arquivo com **“conferencia”** no nome (ex.: `conferencia.xlsx`) com as colunas da planilha antiga:
  `NUM_LIGACAO`, `DATA_CONCLUSAO`, `Data Religação`, `Mês Religação`, `Data Pós Corte`, `Regua de Cobrança`, `Situação` (as que tiver;
  o cabeçalho pode estar abaixo de um título). Com várias abas, vale a que tem mais dessas colunas e, empatando, mais linhas.
- Cada linha é comparada com o painel por **matrícula + data do corte**. Na aba Dados → “Conferência com a planilha” aparece o resumo
  (bate em tudo, corte não encontrado, corte só no painel, religação/mês da religação/pós-corte/régua/situação diferentes), os motivos
  mais comuns, a lista de diferenças (clique na matrícula para o histórico) e os downloads: **⬇ Analítico comparativo (CSV)** — uma linha
  por corte com cada campo lado a lado (planilha × painel) — inclusive o mês do corte —, o resultado e os motivos; também no topo da aba Dados — e ⬇ Só as diferenças.
- O comparativo traz no fim um **diagnóstico** por corte: se conta no painel e no Pós-corte padrão (e por quê), dias cortado até hoje,
  corte anterior e próximo da matrícula, todas as OS da matrícula no dia do corte, as religações e vistorias pós-corte encontradas nos
  arquivos desde o corte (com status e arquivo), o cadastro (SIT_LIG, referência, economias) e em quais arquivos a matrícula aparece.
- Para cada diferença o painel diz **por quê**: OS com status que não conta (ex.: Pendente, Cancelada), serviço fora do catálogo,
  OS depois do próximo corte da matrícula, OS já usada por outro corte, religação/vistoria que só o painel achou (com a OS e o arquivo),
  régua calculada em outro dia, situação do cadastro, matrícula fora dos arquivos lidos.

## Desempenho

- A conferência compara sem pandas dentro do laço: datas viram números uma vez por coluna e as OS de cada matrícula viram listas
  (5 mil linhas: de 97 s para menos de 1 s; 50 mil linhas: cerca de 7 s no computador, um pouco mais no navegador).
- O arquivo de conferência escolhe a aba pelo cabeçalho e pelo tamanho gravado, e lê só essa aba e só as colunas usadas.
- No navegador, pandas e xlrd vêm do próprio Pyodide e o openpyxl é instalado direto do PyPI (sem o aviso “No known package”);
  o xlsxwriter não é mais instalado (a planilha calculada é gravada com o openpyxl).
- Ordem das abas: Corte × Religação começa pelas tabelas (quantidade e %) e depois os gráficos — o destino e a velocidade também
  seguem a Medida (Matrículas ou Economias), que é uma só para as tabelas e os gráficos. Pós-corte: filtros → indicadores → tabela →
  gráfico → análise da visita (indicadores em cima e o resumo em quadros: com visita, sem visita, resultado, melhor momento, atenção).
- **Evolução — comparar duas datas** (aba Pós-corte, logo abaixo da tabela): dois quadros “Meses | Total Geral” como estavam na
  Data A e na Data B (calendários), com a coluna Dif. Cada quadro é reconstruído pelas datas das OS (já cortado, sem pós-corte e sem
  religação até a data, conforme os filtros da aba; quem religou depois conta como CORTADA naquela data). Embaixo: quantos saíram
  (religaram, tiveram a 1ª visita, outros) e quantos entraram (cortes novos), com clique para ver os clientes. A Data B em hoje bate com a tabela da aba.
- **Religações do mês** (aba Dados → Bases para download): escolha o mês e baixe em CSV todas as OS de religação Finalizadas do mês
  (atividades e planilhas LISC/autoreligação; respeita Sup e cidade), com o corte que cada uma religou no painel (data e mês do corte,
  tipo, dias até religar, se teve pós-corte antes, situação) ou o aviso “sem corte ligado”.
