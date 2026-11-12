# Padrão dos painéis: leitura da pasta + layout e cores

Guia para montar um painel novo igual ao **Análise de Corte e Religação**.
Ele mostra como o painel lê uma pasta do OneDrive/SharePoint sincronizada no computador e qual é o padrão visual
("Águas do Rio · Relatório Executivo"). Tudo roda no navegador: nenhum arquivo é enviado para servidor.

---

## 1. Leitura da pasta

### 1.1 Como funciona
1. O usuário clica em **📁 Conectar pasta** e escolhe a pasta sincronizada (ex.: `OneDrive - Águas do Rio/...`).
2. O navegador lista os arquivos (`.xlsx`, `.xlsm`, `.xls`, `.csv`), inclusive das subpastas. Ficam de fora:
   - arquivos temporários do Excel (`~$...`);
   - as bases que o próprio painel gera.
3. Os arquivos vão para um **Web Worker** com **Pyodide** (Python no navegador): pandas, xlrd e openpyxl.
4. O Python lê, classifica e calcula, e devolve um JSON para a página desenhar.
5. A pasta escolhida fica guardada no **IndexedDB**, e o botão **↻ Atualizar** lê de novo sem perguntar.
6. Ao reabrir a página, ela faz duas coisas:
   - mostra na hora a última leitura guardada;
   - lê a pasta de novo. Se o navegador pedir permissão, a leitura começa no primeiro clique.

| Navegador | Como escolhe a pasta | Atualizar sem escolher de novo |
|---|---|---|
| Chrome / Edge | `showDirectoryPicker` (File System Access API) | Sim (handle guardado no IndexedDB) |
| Firefox / Safari | `<input type="file" webkitdirectory>` | Não (escolhe a pasta toda vez) |

### 1.2 Código base (página)

```html
<button id="btnConectar" class="btn-top">📁 Conectar pasta</button>
<button id="btnAtualizar" class="btn-top" disabled>↻ Atualizar</button>
<input type="file" id="inputPasta" webkitdirectory directory multiple hidden>
```

```js
const EXT = /\.(xlsx|xlsm|xls|csv)$/i;
let pastaHandle = null;

// lista os arquivos da pasta e subpastas
async function arquivosDaPasta(handle, prefixo = "") {
  const lista = [];
  for await (const [nome, item] of handle.entries()) {
    if (item.kind === "directory") lista.push(...await arquivosDaPasta(item, prefixo + nome + "/"));
    else if (EXT.test(nome) && !nome.startsWith("~$")) {
      const f = await item.getFile();
      lista.push({ nome: prefixo + nome, arquivo: f, tamanho: f.size, modificado: f.lastModified });
    }
  }
  return lista;
}

// guarda a pasta (e a última leitura) no IndexedDB
function bancoPasta() {
  return new Promise((ok, erro) => {
    const r = indexedDB.open("MEU_PAINEL_pasta", 1);           // troque o nome por painel
    r.onupgradeneeded = () => r.result.createObjectStore("pasta");
    r.onsuccess = () => ok(r.result); r.onerror = () => erro(r.error);
  });
}
async function guardaPasta(h) { try { (await bancoPasta()).transaction("pasta", "readwrite").objectStore("pasta").put(h, "atual"); } catch (e) {} }
async function pastaGuardada() {
  try { const db = await bancoPasta(); return await new Promise((ok) => { const r = db.transaction("pasta").objectStore("pasta").get("atual"); r.onsuccess = () => ok(r.result || null); r.onerror = () => ok(null); }); }
  catch (e) { return null; }
}

async function lePasta() {
  if ((await pastaHandle.queryPermission({ mode: "read" })) !== "granted"
      && (await pastaHandle.requestPermission({ mode: "read" })) !== "granted") return;
  analisa(await arquivosDaPasta(pastaHandle));
}
async function conecta() {
  if ("showDirectoryPicker" in window) {
    try { pastaHandle = await showDirectoryPicker({ id: "meu_painel", mode: "read" }); } catch (e) { return; }  // cancelou
    guardaPasta(pastaHandle); lePasta();
  } else document.getElementById("inputPasta").click();       // Firefox/Safari
}
document.getElementById("btnConectar").onclick = conecta;
document.getElementById("btnAtualizar").onclick = () => pastaHandle && lePasta();
document.getElementById("inputPasta").onchange = (e) => {
  const arquivos = [...e.target.files].filter((f) => EXT.test(f.name) && !f.name.startsWith("~$"))
    .map((f) => ({ nome: (f.webkitRelativePath || f.name).split("/").slice(1).join("/") || f.name, arquivo: f, tamanho: f.size, modificado: f.lastModified }));
  analisa(arquivos); e.target.value = "";
};

// ao abrir: recupera a pasta e lê sozinho se a permissão já estiver dada; senão, no primeiro clique
(async () => {
  worker.postMessage({ fase: "preparar" });                   // o Python começa a baixar já
  if (!("showDirectoryPicker" in window)) return;
  pastaHandle = await pastaGuardada(); if (!pastaHandle) return;
  if ((await pastaHandle.queryPermission({ mode: "read" })) === "granted") return lePasta();
  const umClique = () => { document.removeEventListener("pointerdown", umClique, true); lePasta(); };
  document.addEventListener("pointerdown", umClique, true);
})();
```

`analisa(arquivos)` manda os arquivos para o worker. Os `File` passam direto no `postMessage`, sem copiar.

### 1.3 Worker com Pyodide (`analisador.worker.js`)

```js
const PYODIDE_VERSAO = "0.29.5";
const PYODIDE_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSAO}/full/`;
const ARQUIVOS_PY = ["pacote/__init__.py", "pacote/leitura.py", "pacote/regras.json" /* todo arquivo do pacote */];
importScripts(PYODIDE_URL + "pyodide.js");

async function prepara() {
  const py = await loadPyodide({ indexURL: PYODIDE_URL });
  await py.loadPackage(["pandas", "micropip", "xlrd"]);
  await py.pyimport("micropip").install("openpyxl");
  for (const caminho of ARQUIVOS_PY) {                         // copia o código Python para o disco virtual
    const txt = await (await fetch(caminho + "?v=" + VERSAO)).text();
    py.FS.mkdirTree(caminho.split("/").slice(0, -1).join("/") || "."); py.FS.writeFile(caminho, txt);
  }
  return py;
}
self.onmessage = async (e) => { /* fase "preparar" | "analisar": grava os File em /dados, roda o Python, devolve { tipo:"resultado", dados } */ };
```

### 1.4 Regras que valem para todo painel
- **Reconhecer pelo nome ou pelas colunas:** cada arquivo é identificado pelo nome (ex.: `Atividades-*`) ou pelas colunas do cabeçalho. Aceite variações de nome, acento e espaço. O que não for reconhecido aparece na aba Dados como "não usado", com o motivo.
- **Cache por arquivo:** guarde no IndexedDB a leitura de cada arquivo, com a chave `nome + tamanho + data de modificação + VERSÃO`. Se mudar o código de leitura, aumente a versão (`BASE`).
- **Regras de negócio** ficam em `regras.json`, nunca espalhadas no código.
- **Planilhas de clientes** (`*.xlsx`, `*.csv`) ficam no `.gitignore`; nunca vão para o repositório.
- **Pacote Python novo:** todo arquivo novo do pacote precisa entrar em `ARQUIVOS_PY`.

---

## 2. Layout padrão

Ordem da tela, de cima para baixo:

1. **Cabeçalho** em degradê marinho, com duas linhas:
   - Linha 1: selo `ÁGUAS DO RIO • RELATÓRIO EXECUTIVO` com a versão (`v52`), o título com o período e os botões à direita (Conectar pasta, Atualizar, Menu).
   - Linha 2: filtros, cada um com o rótulo pequeno em maiúsculas acima do campo. Ordem: Mês inicial, Mês final, Superintendência, Cidade (vários), Tipo (vários), checkbox e o link **Limpar filtros** à direita.
2. **Abas** brancas, com sublinhado ciano na ativa. A aba **Dados** fica sempre por último.
3. Em cada aba, nesta ordem: filtros da aba (se houver), depois **KPIs em faixa única**, depois **tabelas**, depois **gráficos**.
4. **Cartões brancos** com título à esquerda, um **?** ao lado do título e as ações à direita (seletores, ⬇ CSV).
   - O **?** guarda a explicação: aparece ao passar o mouse e não ocupa espaço na tela.
5. **Aba Dados:** no topo, o **Reporte semanal** com botão de copiar imagem. Abaixo, tópicos em sanfona: avisos, conferência, bases carregadas, parâmetros, downloads e, para cada página, "como foi calculado".
6. **Toast** no canto inferior direito para as mensagens ("Painel atualizado — N arquivo(s) lidos").
7. **Painel lateral** que abre ao clicar num número, com a lista dos clientes, e fecha ao clicar fora ou com Esc.

### Valores
- **Números:** em pt-BR (`1.234`, `12,5%`, `R$ 1.234,56`). Zero aparece como "-".
- **Datas e meses:** datas em `dd/mm/aaaa`; meses como `Janeiro/2026` nas tabelas e `Jan/26` nos gráficos.
- **Versão:** toda atualização aumenta a versão do cabeçalho (`VERSAO_SITE = "vNN-AAAAMMDD"` e o selo `vNN`).

---

## 3. Cores

### 3.1 Tokens (CSS)

```css
:root {
  --navy:#102840;  --blue:#176b9c;  --cyan:#16a5b8;
  --ink:#1f2d3d;   --muted:#64748b; --line:#dbe4ec; --bg:#f3f6f9;
  --marinho:#1A2740; --azul:#394D73; --azul-claro:#49668C;
  --tint:#e7f0f6;  --zebra:#f7fafc;
  --laranja:#E8710A; --laranja-texto:#C2560C;
  --fonte:'IBM Plex Sans','Segoe UI',Arial,sans-serif;
  --fonte-cond:'IBM Plex Sans Condensed','Segoe UI',Arial,sans-serif;
}
```

| Uso | Cor |
|---|---|
| Fundo da página | `#f3f6f9` |
| Cabeçalho (degradê) | `linear-gradient(120deg,#102840,#174f70)` |
| Selo / textos claros no cabeçalho | `#9fe1e7` |
| Cabeçalho das tabelas, títulos | marinho `#1A2740` |
| Aba ativa (texto / sublinhado) | `#176b9c` / ciano `#16a5b8` |
| Bordas e linhas | `#dbe4ec` |
| Zebra das tabelas | `#f7fafc` |
| Negativo / corte / alerta | laranja `#E8710A` (texto `#C2560C`) |
| Positivo / meta batida | verde `#166534` (selo `#dcfce7`) |

### 3.2 Cores dos gráficos (Chart.js)

```js
const COR = { marinho: "#1A2740", azul: "#394D73", azulMed: "#176b9c", ciano: "#16a5b8", cianCl: "#8fd3dc",
              ant: "#A7B5CB", laranja: "#E8710A", laranjaEsc: "#9a3412", laranjaCl: "#F3B27A", grade: "#dbe4ec" };
```

- **Significado das cores:** religação ou valor bom em marinho/azul; corte ou valor ruim em laranja; base de comparação ("sem", período anterior) em cinza `#A7B5CB`; implantação em ciano.
- **Gráficos limpos:** sem linhas de grade, sem eixo Y e com o rótulo do valor na própria barra.
- **Interação:** a dica aparece ao passar o mouse na coluna, e clicar numa barra filtra o mês, a cidade ou o tipo.

### 3.3 Componentes (CSS essencial)

```css
body { margin:0; background:var(--bg); color:var(--ink); font-family:"Segoe UI",Arial,sans-serif; font-size:14px; }
.top { background:linear-gradient(120deg,#102840,#174f70); color:#fff; padding:8px 14px 8px 20px; }
.eyebrow { color:#9fe1e7; font-size:10px; letter-spacing:1.2px; font-weight:700; text-transform:uppercase; }
.fsel { display:flex; flex-direction:column; gap:3px; font-size:9.5px; font-weight:700; text-transform:uppercase; color:#9fb6cc; }
.fsel select { border:1px solid rgba(255,255,255,.28); border-radius:7px; background:rgba(255,255,255,.08); color:#fff; padding:5px 8px; }
.tab { border:0; background:none; padding:7px 14px; color:var(--muted); font-weight:650; border-bottom:3px solid transparent; }
.tab.active { color:var(--blue); border-bottom-color:var(--cyan); }
.card { background:#fff; margin:10px auto; padding:14px 18px; max-width:1800px; border:1px solid var(--line); border-radius:12px; box-shadow:0 3px 12px rgba(17,42,66,.045); }
.card h2 { font-size:14px; font-weight:600; margin:0; color:var(--marinho); }
.kpis { display:grid; grid-template-columns:repeat(var(--n,5),minmax(0,1fr)); gap:1px; background:var(--line); border:1px solid var(--line); border-radius:8px; overflow:hidden; }
.kpi { background:#fff; padding:7px 12px; border-top:3px solid var(--marinho); }
.kpi.neg { border-top-color:var(--laranja); }
.kpi-rot { font-size:10.5px; color:var(--azul-claro); }
.kpi-val { font-family:var(--fonte-cond); font-size:15px; font-weight:600; font-variant-numeric:tabular-nums; }
table { border-collapse:collapse; width:100%; font-family:var(--fonte-cond); font-size:12px; font-variant-numeric:tabular-nums; }
th, td { border:1px solid var(--line); padding:5px 7px; white-space:nowrap; background:#fff; }
th { background:var(--marinho); color:#fff; font-weight:600; font-size:11.5px; position:sticky; top:0; }
tbody tr:nth-child(even) td { background:var(--zebra); }
td.num { text-align:right; }
tr.linha-total td { font-weight:700; background:var(--tint); }
.selo { display:inline-block; padding:1px 8px; border-radius:10px; font:700 11px var(--fonte); }
.selo-ok { background:#dcfce7; color:#166534; } .selo-atencao { background:#ffedd5; color:#9a3412; } .selo-info { background:#e0e7ff; color:#3730a3; }
.info { display:inline-flex; align-items:center; justify-content:center; width:15px; height:15px; margin-left:6px; border-radius:50%;
        border:1px solid var(--azul-claro); color:var(--azul-claro); font:700 10px/1 var(--fonte); cursor:help; }
.info:hover { background:var(--cyan); border-color:var(--cyan); color:#fff; }
#balao { position:fixed; z-index:9999; max-width:400px; background:var(--marinho); color:#fff; font-size:12px; line-height:1.5; padding:10px 13px; border-radius:8px; }
```

### 3.4 Ícone da aba
O ícone é o `favicon.svg`: uma gota azul cercada por duas setas, laranja (corte) e ciano (religação), sem fundo.
Em outro painel, troque a gota por um símbolo do tema e mantenha as setas grossas, para continuar legível em 16 px.

### 3.5 Bibliotecas (CDN)
- Chart.js `4.4.1`: `https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js`
- Pyodide `0.29.5`: `https://cdn.jsdelivr.net/pyodide/v0.29.5/full/`
- html2canvas `1.4.1`, para copiar uma tabela como imagem: carregado só no primeiro uso.
- Fontes: IBM Plex Sans e IBM Plex Sans Condensed, do Google Fonts.
