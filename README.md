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
- **Corte × Religação**: mês do corte × mês da religação, com *Ativa* e *Sem Religação*, em quantidade ou %.
- **Pós-corte**: clientes cortados sem a 1ª visita pela régua (−7, 7 a 15, +15 dias cortado até hoje), régua completa,
  1ª visita sem sucesso (*Encerrada com Ocorrência*) e a lista para baixar.
- **Permanência**: tipo de corte × faixa de dias até a religação e a eficácia de cada tipo com × sem pós-corte.
- **Dados**: parâmetros, arquivos lidos, explicação de cada cálculo e downloads (base calculada em Excel, CSV de cada tabela).

Filtros no topo: mês inicial/final (mês do corte), cidade, recurso e tipo de corte.

## Recursos do painel

- **Gráficos** (Chart.js) em cada aba, com as tabelas logo abaixo como apoio: saldo mensal e por tipo, destino dos cortes e velocidade de religação, cortados sem a 1ª visita por mês e por cidade, régua de cobrança, permanência por tipo e eficácia do pós-corte. Clicar numa barra filtra o mês, a cidade ou o tipo.
- **Clicar num número** (de qualquer tabela) abre, num painel lateral, as matrículas por trás dele, com ⬇ para baixar em CSV; clicar numa matrícula mostra o histórico do cliente.
- Lista de clientes com **busca** (matrículas ou texto), ordenação pelo cabeçalho e "Mostrar todos"; qualquer tabela ordena pelo cabeçalho; tabelas largas arrastam para o lado.
- **Ativas = religadas** (filtro no cabeçalho, vale para todas as abas): quando ligado, o corte sem OS de religação cuja ligação está ATIVA no cadastro passa a contar como religado — sai de "sem religação" e de "sem a 1ª visita", entra no % religado, na régua ("Ativa sem OS de religação"), na permanência ("Ativa sem OS") e, no saldo, como religação no mês do corte. Sem data de religação, esses casos não entram nos cálculos de dias. A escolha fica lembrada e vai no link.
- **Atalhos:** `1`…`5` trocam de aba, `/` vai para a busca, `Esc` fecha o painel lateral ou o modo apresentação.
- O endereço da página guarda a **aba e os filtros** (copie e envie o link); as escolhas dos botões ficam lembradas no navegador.
- **🖥 Apresentar** (esconde o cabeçalho e aumenta gráficos e fontes) e **📄 Executivo** (abre a impressão em A4 paisagem; escolha "Salvar como PDF").

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
