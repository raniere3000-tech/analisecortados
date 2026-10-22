// Roda a análise em Python dentro do navegador (Pyodide), fora da thread da página.
// Nada é enviado para servidor: os arquivos ficam numa pasta virtual na memória.

const PYODIDE_VERSAO = "0.29.5";
const PYODIDE_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSAO}/full/`;
const PASTA = "/dados";
// Arquivos do pacote Python que o site copia para o Pyodide (caminho no site -> pasta virtual /app)
const ARQUIVOS_PY = [
  "cortes/__init__.py", "cortes/base.py", "cortes/cache_arquivos.py", "cortes/conferencia.py", "cortes/config.py", "cortes/leitura.py",
  "cortes/pipeline.py", "cortes/saida.py", "cortes/regras.json", "cortes/catalogo_servicos.json",
];
const SAIDA_EXCEL = `${PASTA}/Base_Cortes.xlsx`;

importScripts(PYODIDE_URL + "pyodide.js");

let pyodidePronto = null;

function avisa(tipo, dados, transferir = []) {
  self.postMessage({ tipo, ...dados }, transferir);
}

async function preparaPython() {
  avisa("etapa", { texto: "Carregando o Python no navegador…" });
  const pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
  pyodide.setStdout({ batched: (linha) => avisa("log", { linha }) });
  pyodide.setStderr({ batched: (linha) => avisa("log", { linha }) });

  avisa("etapa", { texto: "Instalando pandas e leitores de Excel…" });
  // pandas, micropip e xlrd (.xls) vêm do próprio Pyodide, numa só chamada
  await pyodide.loadPackage(["pandas", "micropip", "xlrd"]);
  // openpyxl (.xlsx) não está no Pyodide: vem do PyPI direto (sem a tentativa que falhava e gerava o aviso).
  // xlsxwriter não é instalado: a planilha calculada (Excel) é gravada com o openpyxl.
  const micropip = pyodide.pyimport("micropip");
  if (!pyodide.runPython(`import importlib.util; importlib.util.find_spec("openpyxl") is not None`)) {
    try { await micropip.install("openpyxl"); }
    catch (e) { avisa("log", { linha: `Aviso: não foi possível instalar openpyxl (${String(e.message || e).split("\n").pop()}).` }); }
  }

  avisa("etapa", { texto: "Carregando o programa de análise…" });
  const FS = pyodide.FS;
  for (const caminho of ARQUIVOS_PY) {
    const resp = await fetch(caminho, { cache: "no-cache" });
    if (!resp.ok) throw new Error(`Não foi possível baixar ${caminho} (HTTP ${resp.status}).`);
    const destino = `/app/${caminho}`;
    FS.mkdirTree(destino.substring(0, destino.lastIndexOf("/")));
    FS.writeFile(destino, new Uint8Array(await resp.arrayBuffer()));
  }
  const executor = await (await fetch("executor_web.py", { cache: "no-cache" })).text();
  pyodide.runPython(executor);
  return pyodide;
}

async function iniciaPyodide() {
  if (!pyodidePronto) pyodidePronto = preparaPython().catch((e) => { pyodidePronto = null; throw e; });
  return pyodidePronto;
}

function apagaTudo(FS, caminho) {
  for (const nome of FS.readdir(caminho)) {
    if (nome === "." || nome === "..") continue;
    const c = `${caminho}/${nome}`;
    if (FS.isDir(FS.stat(c).mode)) { apagaTudo(FS, c); FS.rmdir(c); } else FS.unlink(c);
  }
}

function limpaDir(FS, caminho) {
  try { apagaTudo(FS, caminho); } catch (e) { /* não existia */ }
  FS.mkdirTree(caminho);
}

function mensagemAmigavel(erro) {
  const texto = String(erro && erro.message ? erro.message : erro);
  const linhas = texto.trim().split("\n").filter(Boolean);
  const ultima = linhas[linhas.length - 1] || texto;
  return { resumo: ultima.replace(/^\w+(Error|Exception|Exit):\s*/, ""), detalhe: texto };
}

// ===== Arquivos já lidos (guardados no navegador, IndexedDB) =====
// Arquivo com o mesmo caminho, tamanho e data de alteração não é lido de novo: o Python recebe a leitura guardada.
const CACHE = "/cache";
const BANCO = "cortes_cache";
const LIMITE_MB = 1500;                            // acima disso, apaga o que não é da pasta atual

function req(r) { return new Promise((ok, erro) => { r.onsuccess = () => ok(r.result); r.onerror = () => erro(r.error); }); }
function abreBanco() {
  return new Promise((ok, erro) => {
    const r = indexedDB.open(BANCO, 1);
    r.onupgradeneeded = () => r.result.createObjectStore("arquivos", { keyPath: "id" });
    r.onsuccess = () => ok(r.result);
    r.onerror = () => erro(r.error);
  });
}
function bancoLe(db, id) { return req(db.transaction("arquivos").objectStore("arquivos").get(id)); }
function bancoTransacao(db, acao) {
  return new Promise((ok, erro) => {
    const t = db.transaction("arquivos", "readwrite");
    acao(t.objectStore("arquivos"));
    t.oncomplete = ok; t.onerror = () => erro(t.error); t.onabort = () => erro(t.error);
  });
}
function bancoResumo(db) {                          // [{id, rel, versao, bytes}] sem carregar os dados guardados
  return new Promise((ok, erro) => {
    const itens = [], r = db.transaction("arquivos").objectStore("arquivos").openCursor();
    r.onsuccess = () => { const c = r.result; if (!c) return ok(itens); const v = c.value; itens.push({ id: v.id, rel: v.rel, versao: v.versao, bytes: v.bytes || 0 }); c.continue(); };
    r.onerror = () => erro(r.error);
  });
}

async function idArquivo(chave) {                   // id curto e seguro para nome de arquivo
  try {
    const h = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(chave));
    return Array.from(new Uint8Array(h)).map((b) => b.toString(16).padStart(2, "0")).join("");
  } catch (e) {                                     // sem crypto.subtle (página aberta como arquivo): hash simples
    let h1 = 0x811c9dc5, h2 = 0x01000193;
    for (let i = 0; i < chave.length; i++) { h1 = Math.imul(h1 ^ chave.charCodeAt(i), 16777619); h2 = Math.imul(h2 + chave.charCodeAt(i), 2246822519); }
    return (h1 >>> 0).toString(16) + (h2 >>> 0).toString(16) + chave.length.toString(16);
  }
}

async function faseAnalisar(arquivos) {
  const pyodide = await iniciaPyodide();
  const FS = pyodide.FS;
  avisa("etapa", { texto: "Copiando os arquivos para análise…" });
  limpaDir(FS, PASTA);
  limpaDir(FS, CACHE);
  FS.mkdirTree(`${CACHE}/entrada`);
  const versao = pyodide.runPython("from cortes.cache_arquivos import VERSAO\nVERSAO");
  let db = null;
  try { db = await abreBanco(); } catch (e) { avisa("log", { linha: "Aviso: sem acesso ao armazenamento do navegador; todos os arquivos serão lidos." }); }
  const meta = {}, atuais = new Set();
  let reaproveitados = 0;
  // Cada arquivo só é copiado para a memória do Python na hora de ser lido (cortes/cache_arquivos.py chama
  // materializa/libera): com ~250 arquivos, copiar tudo antes estourava a memória do navegador.
  const pendentes = new Map();
  self.materializa = (rel) => { const f = pendentes.get(rel); if (f) FS.writeFile(`${PASTA}/${rel}`, new Uint8Array(new FileReaderSync().readAsArrayBuffer(f))); };
  self.libera = (rel) => { if (pendentes.has(rel)) FS.writeFile(`${PASTA}/${rel}`, new Uint8Array(0)); };
  for (const arq of arquivos) {
    const partes = arq.nome.split("/").filter((p) => p && p !== "." && p !== "..");   // mantém as subpastas
    const rel = partes.join("/");
    if (partes.length > 1) FS.mkdirTree(`${PASTA}/${partes.slice(0, -1).join("/")}`);
    const id = await idArquivo(`${versao}|${PYODIDE_VERSAO}|${rel}|${arq.tamanho}|${arq.modificado || 0}`);   // outra versão do Python não reaproveita
    atuais.add(id);
    let guardado = null;
    if (db && arq.modificado) { try { guardado = await bancoLe(db, id); } catch (e) { guardado = null; } }
    if (guardado && guardado.versao === versao && guardado.dados) {
      FS.writeFile(`${PASTA}/${rel}`, new Uint8Array(0));        // o arquivo nem é lido: o Python usa a leitura guardada
      FS.writeFile(`${CACHE}/entrada/${id}.pkl.gz`, guardado.dados);
      meta[rel] = { id, em_cache: true };
      reaproveitados++;
    } else {
      FS.writeFile(`${PASTA}/${rel}`, new Uint8Array(0));        // vazio por enquanto: o conteúdo vem em materializa()
      pendentes.set(rel, arq.arquivo);
      meta[rel] = { id, em_cache: false };
    }
  }
  FS.writeFile(`${CACHE}/meta.json`, JSON.stringify({ versao, arquivos: meta }));
  avisa("etapa", { texto: reaproveitados ? `Lendo os arquivos novos (${reaproveitados} já lidos antes)…` : "Lendo os arquivos…" });
  const analisar = pyodide.globals.get("analisar");
  const json = analisar(PASTA, (pct, texto) => avisa("progresso", { pct, texto }));
  analisar.destroy();
  const dados = JSON.parse(json);
  pendentes.clear();
  if (db && dados.cache_invalido && dados.cache_invalido.length) {            // leituras guardadas que não abriram: apaga
    try { await bancoTransacao(db, (st) => dados.cache_invalido.forEach((id) => st.delete(id))); } catch (e) { /* tenta na próxima */ }
  }
  if (db) {
    try { dados.cacheMB = await guardaLeituras(FS, db, meta, versao, atuais); }
    catch (e) { avisa("log", { linha: "Aviso: não foi possível guardar os arquivos lidos para a próxima vez (" + e.message + ")." }); }
  }
  avisa("resultado", { dados });
}

// Guarda no navegador o que o Python leu agora (CACHE/saida/<id>.pkl.gz) e tira o que ficou velho
async function guardaLeituras(FS, db, meta, versao, atuais) {
  const saida = `${CACHE}/saida`;
  const porId = {};
  Object.entries(meta).forEach(([rel, m]) => { porId[m.id] = rel; });
  if (FS.analyzePath(saida).exists) {
    for (const nome of FS.readdir(saida)) {
      const id = nome.replace(/\.pkl\.gz$/, "");
      if (!porId[id]) continue;
      const dados = FS.readFile(`${saida}/${nome}`);
      await bancoTransacao(db, (st) => st.put({ id, rel: porId[id], versao, dados, bytes: dados.byteLength, guardado: Date.now() }));
    }
  }
  // tira: outra versão do programa; mesmo arquivo (caminho) com outro conteúdo; e, acima do limite, o que não é desta pasta
  const itens = await bancoResumo(db);
  const relsAtuais = new Set(Object.keys(meta));
  let apagar = itens.filter((i) => i.versao !== versao || (relsAtuais.has(i.rel) && !atuais.has(i.id))).map((i) => i.id);
  const restantes = itens.filter((i) => !apagar.includes(i.id));
  let total = restantes.reduce((a, i) => a + i.bytes, 0);
  if (total > LIMITE_MB * 1e6) {
    const fora = restantes.filter((i) => !atuais.has(i.id));
    apagar = apagar.concat(fora.map((i) => i.id));
    total -= fora.reduce((a, i) => a + i.bytes, 0);
  }
  if (apagar.length) await bancoTransacao(db, (st) => apagar.forEach((id) => st.delete(id)));
  return Math.round(total / 1e5) / 10;
}

async function faseExcel() {
  const pyodide = await iniciaPyodide();
  avisa("etapa", { texto: "Gerando a planilha…" });
  const excel = pyodide.globals.get("excel");
  excel(SAIDA_EXCEL);
  excel.destroy();
  const bytes = pyodide.FS.readFile(SAIDA_EXCEL);
  avisa("excel", { conteudo: bytes.buffer }, [bytes.buffer]);
}

async function limpaCache() {
  await new Promise((ok) => { const r = indexedDB.deleteDatabase(BANCO); r.onsuccess = r.onerror = r.onblocked = () => ok(); });
  avisa("cacheLimpo", {});
}

self.onmessage = async (evento) => {
  const { fase, arquivos } = evento.data;
  if (fase === "preparar") {                         // ao abrir a página: adianta o download do Python enquanto a pasta não vem
    try { await iniciaPyodide(); avisa("pronto", {}); } catch (e) { avisa("log", { linha: "Aviso: " + (e.message || e) }); }
    return;
  }
  try {
    if (fase === "limparCache") await limpaCache();
    else if (fase === "excel") await faseExcel();
    else await faseAnalisar(arquivos);
  } catch (erro) {
    avisa("erro", mensagemAmigavel(erro));
  }
};
