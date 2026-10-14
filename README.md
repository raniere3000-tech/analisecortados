# Análise de Corte e Religação

Painel que lê os arquivos de atividades de campo (`Atividades-*.xlsx`) e o cadastro de ligações direto da pasta do
SharePoint e mostra o saldo de economias, os cortes × religações, o pós-corte e a permanência no corte.

## Como usar

Abra o site (GitHub Pages deste repositório) no **Chrome ou Edge**, clique em **📁 Conectar pasta** e escolha a pasta do
SharePoint sincronizada no computador pelo OneDrive. As subpastas também são lidas. Depois de colocar arquivos novos
na pasta, clique em **↻ Atualizar**: arquivos que não mudaram não são lidos de novo (a leitura fica guardada no navegador).

O processamento roda no navegador: o site executa o pacote Python `cortes/` com o [Pyodide](https://pyodide.org)
(`analisador.worker.js` + `executor_web.py`). Os arquivos não são enviados para nenhum servidor. Na primeira vez, o
navegador baixa o Python (cerca de 30 MB), que depois fica em cache.

### Arquivos da pasta

| Arquivo | Como é reconhecido | Usado para |
|---|---|---|
| Atividades | nome começa com `Atividades-` (vários arquivos, em qualquer subpasta) | cortes, religações, implantações e vistorias pós-corte |
| Cadastro | colunas `NUM_LIGACAO`, `SIT_LIG`, `TOTAL_ECO` (cabeçalho pode estar abaixo de um título) | situação atual (ATIVA/CORTADA), economias, cliente |
| Descrição serviço (opcional) | colunas `SERVICO` e `CATEGORIA` | código do serviço → categoria; sem ela vale `cortes/catalogo_servicos.json` |

Colunas usadas das atividades: Recurso, ID da Atividade, Número da Conta, Matrícula, Código/Descrição, Data, Status da
Atividade, Cidade, Parecer De Campo, Motivo de Não Execução - Normal, Valor Total dos Débitos, Negociou O Débito?.
A mesma atividade (mesmo *ID da Atividade*) em mais de um arquivo conta uma vez.

## Abas

- **Saldo de economias**: por mês, −corte (por tipo) + religação (por tipo) + implantação de ligação de água, em
  economias (`TOTAL_ECO`) ou em ligações, com o saldo do mês e o acumulado.
- **Corte × Religação**: mês do corte × mês da religação, com *Ativa* e *Sem Religação*, em quantidade ou %.
- **Pós-corte**: clientes cortados sem a 1ª visita pela régua (−7, 7 a 15, +15 dias cortado até hoje), régua completa,
  1ª visita sem sucesso (*Encerrada com Ocorrência*) e a lista para baixar.
- **Permanência**: tipo de corte × faixa de dias até a religação e a eficácia de cada tipo com × sem pós-corte.
- **Dados**: parâmetros, arquivos lidos, explicação de cada cálculo e downloads (base calculada em Excel, CSV de cada tabela).

Filtros no topo: mês inicial/final (mês do corte), cidade, recurso e tipo de corte.

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
