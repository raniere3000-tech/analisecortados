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
