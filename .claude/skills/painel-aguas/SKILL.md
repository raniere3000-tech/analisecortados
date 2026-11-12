---
name: painel-aguas
description: Padrão para criar ou ajustar painéis HTML da Águas do Rio que leem uma pasta do OneDrive/SharePoint no navegador (botão Conectar pasta, Atualizar, File System Access API, IndexedDB, Web Worker com Pyodide/pandas) e seguem o layout "Relatório Executivo" (cabeçalho em degradê marinho com filtros, abas com sublinhado ciano, KPIs em faixa, cartões brancos, tabelas com cabeçalho marinho, ? com balão, aba Dados por último, cores marinho/ciano/laranja). Use sempre que o usuário pedir um painel novo, ler planilhas de uma pasta, "padrão do painel", "mesmo layout", "cores padrão" ou ajustar a tela de um painel existente.
---

# Painel Águas do Rio — leitura da pasta + layout padrão

Siga `referencia.md` (nesta pasta). Ele traz o código pronto e as cores. Resumo do que é obrigatório:

## Leitura da pasta
- Use os botões **📁 Conectar pasta** e **↻ Atualizar**:
  - Chrome/Edge: `showDirectoryPicker`, com a pasta guardada no IndexedDB.
  - Firefox/Safari: `<input webkitdirectory>`.
- Leia as subpastas e ignore os arquivos `~$`. Extensões aceitas: `.xlsx`, `.xlsm`, `.xls` e `.csv`.
- Ao abrir a página:
  - mostre a última leitura guardada;
  - leia a pasta sozinho se a permissão já estiver dada; senão, no primeiro clique.
- Processe num Web Worker com Pyodide (pandas, xlrd, openpyxl). Todo arquivo Python do pacote entra em `ARQUIVOS_PY`.
- Guarde a leitura de cada arquivo com a chave nome + tamanho + modificação + versão. Mudou a leitura, aumente a versão.
- Reconheça cada arquivo pelo nome ou pelas colunas, aceitando variações. O que não for usado aparece na aba Dados com o motivo.
- Regras de negócio ficam em `regras.json`. Planilhas de clientes nunca vão para o repositório (`.gitignore`).

## Layout
- **Cabeçalho:**
  - Fundo `linear-gradient(120deg,#102840,#174f70)`.
  - Linha 1: selo "ÁGUAS DO RIO • RELATÓRIO EXECUTIVO" com a versão `vNN`, o título com o período e os botões à direita.
  - Linha 2: filtros, com o rótulo pequeno em maiúsculas acima do campo e o link "Limpar filtros" à direita.
  - Filtros de vários itens (Cidade, Tipo) com lista, busca, Todos e Limpar.
- **Abas:** brancas, com sublinhado ciano na ativa. A **Dados** fica por último e traz:
  - o Reporte semanal, com botão para copiar a imagem;
  - os tópicos em sanfona, com o "como foi calculado" e os ⬇ CSV analíticos.
- **Em cada aba:** filtros da aba, depois KPIs em faixa única, depois tabelas, depois gráficos.
- **Textos explicativos** ficam no **?** ao lado do título, que abre um balão marinho ao passar o mouse. Não ponha parágrafos na tela.
- **Tabelas:** cabeçalho marinho `#1A2740`, zebra, números alinhados à direita, linha de total em destaque. Clicar num número abre o painel lateral com os clientes.
- **Gráficos (Chart.js 4.4.1):** sem grade e sem eixo Y, com o rótulo do valor na barra e a dica ao passar o mouse na coluna.
- **Valores** em pt-BR (`1.234`, `12,5%`, `dd/mm/aaaa`, `Janeiro/2026`). Zero aparece como "-".
- **Versão:** toda atualização aumenta `VERSAO_SITE = "vNN-AAAAMMDD"` e o selo `vNN`.

## Cores
| Uso | Cor |
|---|---|
| Fundo | `#f3f6f9` |
| Marinho (títulos, cabeçalho de tabela, religação) | `#1A2740` |
| Azul / azul médio | `#394D73` / `#176b9c` |
| Ciano (aba ativa, implantação, destaque) | `#16a5b8` |
| Laranja (corte, negativo, alerta) | `#E8710A` (texto `#C2560C`) |
| Cinza de comparação | `#A7B5CB` |
| Verde (meta batida) | `#166534` |
| Linhas | `#dbe4ec` |

Fontes: IBM Plex Sans e IBM Plex Sans Condensed (números das tabelas e KPIs).
