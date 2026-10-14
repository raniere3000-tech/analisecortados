# Regras do repositório

- **Toda atualização muda a versão do cabeçalho do site.** Em `index.html`, aumente `VERSAO_SITE`
  (ex.: `"v1-20261014"` → `"v2-AAAAMMDD"`, com a data do dia) e o texto do `<span id="versao">`
  para o mesmo número. A mensagem do commit começa com essa versão (ex.: `v2: ...`).
- Rode `python -m pytest tests -q` antes de enviar.
- Arquivo novo no pacote `cortes/` precisa entrar em `ARQUIVOS_PY` no `analisador.worker.js` (um teste confere).
- Mudou a leitura dos arquivos (colunas lidas, tipos)? Aumente `VERSAO` em `cortes/cache_arquivos.py`, senão o
  navegador reaproveita leituras antigas guardadas.
- Regras de negócio (faixas da régua e da permanência, status, prioridade de tipos) ficam em `cortes/regras.json`.
- Nunca suba planilhas com dados de clientes (`*.xlsx`, `*.csv` estão no `.gitignore`).
- **Publicação autorizada:** o dono do repositório autorizou atualizar a `main` sempre. Depois de rodar os testes,
  envie o commit para a branch de trabalho e avance a `main` para o mesmo commit
  (`git push origin HEAD:main`) — a `main` é o que o GitHub Pages publica. Confira se a publicação terminou com sucesso.
