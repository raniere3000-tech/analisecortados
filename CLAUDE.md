# Regras do repositório

- **Toda atualização muda a versão do cabeçalho do site.** Em `index.html`, aumente `VERSAO_SITE`
  (ex.: `"v4-20261014"` → `"v5-AAAAMMDD"`, com a data do dia) e o selo `<span id="versao">`
  para o mesmo número (só o `v5`). A mensagem do commit começa com essa versão (ex.: `v2: ...`).
- Rode `python -m pytest tests -q` antes de enviar.
- Arquivo novo no pacote `cortes/` precisa entrar em `ARQUIVOS_PY` no `analisador.worker.js` (um teste confere).
- Mudou o código da leitura dos arquivos (colunas lidas, tipos)? Aumente `BASE` em `cortes/cache_arquivos.py`, senão o
  navegador reaproveita leituras antigas guardadas. Mudanças nas partes de leitura do `regras.json` (`arquivos`,
  `colunas_atividades`, `religacao_lisc`) já mudam a versão sozinhas.
- Regras de negócio (faixas da régua e da permanência, status, prioridade de tipos) ficam em `cortes/regras.json`.
- Nunca suba planilhas com dados de clientes (`*.xlsx`, `*.csv` estão no `.gitignore`).
- **Publicação autorizada:** o dono do repositório autorizou atualizar a `main` sempre. Depois de rodar os testes,
  envie o commit para a branch de trabalho e avance a `main` para o mesmo commit
  (`git push origin HEAD:main`) — a `main` é o que o GitHub Pages publica. Confira se a publicação terminou com sucesso.
- **Padrão visual:** o site segue o guia "Padrão visual dos painéis — Águas do Rio · Relatório Executivo"
  (cabeçalho em degradê marinho com filtros, abas brancas com sublinhado ciano, cartões brancos, KPIs em faixa única,
  tabelas com cabeçalho marinho e zebra, selos, toast, valores em pt-BR, aba Dados por último). Siga-o em toda mudança de tela.
