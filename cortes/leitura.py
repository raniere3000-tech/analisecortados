# -*- coding: utf-8 -*-
"""Leitura da pasta: acha os arquivos de atividades, o cadastro e (se houver) o catálogo de serviços.

- Atividades: todo arquivo cujo nome começa com "Atividades-" (em qualquer subpasta).
- Cadastro: planilha com as colunas NUM_LIGACAO, SIT_LIG e TOTAL_ECO.
- Catálogo: planilha com as colunas SERVICO e CATEGORIA (a "Descrição serviço"); sem ela vale a cópia do site.
- Religação LISC: relatório de O.S. com as colunas Matrícula, Serviço Executado e Dt. Execução (vem em arquivos separados).
Cada arquivo é reduzido às colunas usadas; o resultado pode vir guardado de uma análise anterior (cache_arquivos).
"""
import html
import io
import os
import re
import unicodedata
import zipfile

import pandas as pd

from . import cache_arquivos
from .config import REGRAS

EXTENSOES = (".xlsx", ".xlsm", ".xls", ".csv")
COLUNAS_CADASTRO = ["REFERENCIA", "NUM_LIGACAO", "NOM_CLIENTE", "SIT_LIG", "SUB_CATEGORIA", "TOTAL_ECO",
                    "CIDADE", "NOM_BAIRRO"]
COLUNAS_CATALOGO = ["CODIGO/DESCRICAO", "SERVICO", "CATEGORIA", "Abertura"]


def normaliza(texto):
    """Maiúsculas, sem acento e com espaços simples (para comparar nomes de colunas e descrições)."""
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().upper()


def lista_arquivos(pasta):
    """Todos os arquivos de planilha da pasta e subpastas (ignora temporários do Excel '~$')."""
    achados = []
    for raiz, _, nomes in os.walk(pasta):
        for nome in nomes:
            if nome.startswith("~$") or not nome.lower().endswith(EXTENSOES):
                continue
            achados.append(os.path.join(raiz, nome))
    return sorted(achados)


def _fonte(caminho):
    """Caminho do arquivo — ou, se for um .xlsx com nomes internos fora do padrão (começando com "/" ou usando "\\",
    comum em arquivos gravados por certos sistemas), uma cópia em memória com os nomes corrigidos."""
    if not caminho.lower().endswith((".xlsx", ".xlsm")):
        return caminho
    try:
        with zipfile.ZipFile(caminho) as z:
            nomes = z.namelist()
            limpos = [n.replace("\\", "/").lstrip("/") for n in nomes]
            if limpos == nomes:
                return caminho
            saida = io.BytesIO()
            with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as nova:
                for original, limpo in zip(nomes, limpos):
                    if limpo and not limpo.endswith("/"):
                        nova.writestr(limpo, z.read(original))
    except zipfile.BadZipFile:
        return caminho                                   # o pandas dá a mensagem; o diagnóstico explica
    saida.seek(0)
    return saida


def _motor(caminho):
    """Motor de leitura explícito: o pandas adivinha o formato procurando "xl/workbook.xml" e falha em .xlsx gravados
    por alguns sistemas, que guardam workbook.xml e sheet1.xml soltos na raiz do zip (sem a pasta "xl/")."""
    c = caminho.lower() if isinstance(caminho, str) else ""
    if c.endswith((".xlsx", ".xlsm")):
        return "openpyxl"
    return "xlrd" if c.endswith(".xls") else None


# ===== leitura rápida de .xlsx "plano" =====
# Alguns sistemas gravam o .xlsx com workbook.xml e sheet1.xml soltos na raiz do zip (sem a pasta "xl/") e todas as
# células como texto (t="str"). São arquivos de ~20 MB de XML (centenas de colunas) dos quais só usamos algumas colunas:
# ler só elas é muito mais rápido que carregar tudo no pandas. Qualquer coisa fora do padrão volta para a leitura normal.
_CEL_CAB = re.compile(rb'<c r="([A-Z]+)1"[^>]*?(?:/>|>(.*?)</c>)', re.S)       # aceita célula vazia <c r="B1" s="1"/>
_VALOR = re.compile(rb"<v>(.*?)</v>|<t[^>]*>(.*?)</t>", re.S)


def _texto_celula(interno):
    m = _VALOR.search(interno or b"")
    if not m:
        return None
    v = (m.group(1) if m.group(1) is not None else m.group(2)).decode("utf-8", "replace")
    v = html.unescape(v) if "&" in v else v
    return v if v != "" else None


_ULTIMO_PLANO = {"chave": None, "xml": None}


def _planilha_plana(caminho):
    """XML (bytes) da 1ª planilha de um .xlsx plano, ou None se o arquivo não for desse formato.
    Guarda o último lido: o mesmo arquivo é aberto para achar o tipo, o cabeçalho e os dados."""
    if not caminho.lower().endswith((".xlsx", ".xlsm")):
        return None
    try:
        st = os.stat(caminho)
        chave = (os.path.abspath(caminho), st.st_size, st.st_mtime)
    except OSError:
        return None
    if _ULTIMO_PLANO["chave"] == chave:
        return _ULTIMO_PLANO["xml"]
    xml = _abre_plana(caminho)
    _ULTIMO_PLANO.update(chave=chave, xml=xml)
    return xml


def _abre_plana(caminho):
    try:
        with zipfile.ZipFile(caminho) as z:
            nomes = {n.replace("\\", "/").lstrip("/").lower(): n for n in z.namelist()}
            if "xl/workbook.xml" in nomes or "workbook.xml" not in nomes or "sharedstrings.xml" in nomes:
                return None
            folhas = sorted(n for n in nomes if re.fullmatch(r"sheet\d+\.xml", n))
            if not folhas:
                return None
            return z.read(nomes[folhas[0]])
    except (zipfile.BadZipFile, KeyError, OSError):
        return None


def _cabecalho_plano(xml):
    """{letra da coluna: nome} da linha 1."""
    ini = xml.find(b'<row r="1"')
    fim = xml.find(b"</row>", ini) if ini >= 0 else -1
    if fim < 0:
        return {}
    return {letra.decode(): (_texto_celula(interno) or "").strip() for letra, interno in _CEL_CAB.findall(xml[ini:fim])}


def _le_colunas_plano(caminho, colunas):
    """DataFrame (texto) só com `colunas` — ou None se o arquivo não é plano ou não tem o cabeçalho esperado."""
    xml = _planilha_plana(caminho)
    if xml is None:
        return None
    cab = _cabecalho_plano(xml)
    por_nome = {}
    for letra, nome in cab.items():
        por_nome.setdefault(normaliza(nome), letra)
    alvo = {c: por_nome.get(normaliza(c)) for c in colunas}
    if not any(alvo.values()):
        return None
    letras = sorted({l for l in alvo.values() if l}, key=lambda l: (len(l), l))
    celula = re.compile(rb'<c r="(' + "|".join(letras).encode() + rb')(\d+)"[^>]*?(?:/>|>(.*?)</c>)', re.S)
    linhas = {}
    for letra, numero, interno in celula.findall(xml):
        if numero != b"1":
            linhas.setdefault(int(numero), {})[letra.decode()] = _texto_celula(interno)
    ordem = sorted(linhas)
    dados = {c: [linhas[n].get(alvo[c]) if alvo[c] else None for n in ordem] for c in colunas}
    return pd.DataFrame(dados, columns=list(colunas), dtype=object)


def diagnostico(caminho):
    """Texto curto para entender um arquivo que não abriu: tamanho, início e nomes internos."""
    try:
        tamanho = os.path.getsize(caminho)
        with open(caminho, "rb") as f:
            inicio = f.read(8)
        partes = [f"{tamanho} bytes", "início " + inicio.hex()]
        if zipfile.is_zipfile(caminho):
            with zipfile.ZipFile(caminho) as z:
                nomes = z.namelist()
            partes.append(f"{len(nomes)} partes: " + ", ".join(nomes[:6]))
        else:
            partes.append("não é um arquivo zip/.xlsx válido (vazio, cortado ou ainda não baixado do OneDrive?)")
        return "; ".join(partes)
    except OSError as erro:
        return f"não foi possível abrir: {erro}"


def _separador(caminho, enc):
    """; , ou tab: o que aparece em mais linhas entre as 30 primeiras (a 1ª pode ser um título)."""
    with open(caminho, encoding=enc) as f:
        linhas = [f.readline() for _ in range(30)]
    return max([";", ",", "\t"], key=lambda sep: (sum(1 for l in linhas if sep in l), sum(l.count(sep) for l in linhas)))


def _amostra_csv(caminho, max_linhas):
    """Primeiras linhas do CSV como tabela, mesmo com um título de uma coluna só acima do cabeçalho."""
    import csv
    for enc in ("utf-8-sig", "latin-1"):
        try:
            sep = _separador(caminho, enc)
            with open(caminho, encoding=enc, newline="") as f:
                linhas = [l for _, l in zip(range(max_linhas), csv.reader(f, delimiter=sep))]
            largura = max((len(l) for l in linhas), default=0)
            return pd.DataFrame([[(c if c.strip() else None) for c in l] + [None] * (largura - len(l)) for l in linhas])
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Não foi possível ler o CSV {os.path.basename(caminho)}")


def _le_csv(caminho, **kw):
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(caminho, sep=_separador(caminho, enc), engine="python", dtype=str, encoding=enc, **kw)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Não foi possível ler o CSV {os.path.basename(caminho)}")


def _cabecalho(caminho, max_linhas=30):
    """(linha do cabeçalho, nomes das colunas) — o cabeçalho pode estar abaixo de um título."""
    xml = None if caminho.lower().endswith(".csv") else _planilha_plana(caminho)
    if xml is not None and sum(1 for n in _cabecalho_plano(xml).values() if n) >= 3:   # cabeçalho na linha 1 (sem título acima)
        return 0, [n for _, n in sorted(_cabecalho_plano(xml).items(), key=lambda kv: (len(kv[0]), kv[0]))]
    if caminho.lower().endswith(".csv"):
        df = _amostra_csv(caminho, max_linhas)
    else:
        df = pd.read_excel(_fonte(caminho), header=None, dtype=str, nrows=max_linhas, engine=_motor(caminho))
    conhecidos = _nomes_conhecidos()
    melhor, nota = 0, (-1, -1)
    for i in range(len(df)):
        valores = df.iloc[i]
        n = (sum(1 for v in valores.dropna() if normaliza(v) in conhecidos), int(valores.notna().sum()))
        if n > nota:
            melhor, nota = i, n
    return melhor, [str(c).strip() for c in df.iloc[melhor].tolist()] if len(df) else []


def _le_colunas(caminho, linha, colunas):
    """Lê só as colunas pedidas (pelo nome normalizado) e devolve com os nomes de `colunas`."""
    if linha == 0:
        rapido = _le_colunas_plano(caminho, colunas)
        if rapido is not None:
            return rapido
    alvo = {normaliza(c): c for c in colunas}
    usar = lambda c: normaliza(c) in alvo  # noqa: E731
    if caminho.lower().endswith(".csv"):
        df = _le_csv(caminho, skiprows=linha, header=0, usecols=usar)     # pula o título acima do cabeçalho
    else:
        df = pd.read_excel(_fonte(caminho), header=linha, dtype=str, usecols=usar, engine=_motor(caminho))
    df.columns = [alvo[normaliza(c)] for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    for c in colunas:
        if c not in df.columns:
            df[c] = None
    return df[colunas]


def _nomes_conhecidos():
    """Nomes de coluna que o painel procura (para achar a linha do cabeçalho)."""
    arq = REGRAS["arquivos"]
    nomes = list(REGRAS["colunas_atividades"].values()) + list(REGRAS["religacao_lisc"]["colunas"].values())
    nomes += arq["colunas_cadastro"] + arq["colunas_catalogo"] + COLUNAS_CADASTRO + COLUNAS_CATALOGO
    return {normaliza(n) for n in nomes}


def tipo_arquivo(caminho):
    """'atividades', 'religacao_lisc', 'cadastro', 'catalogo' ou None (arquivo que não é usado)."""
    arq = REGRAS["arquivos"]
    if os.path.basename(caminho).lower().startswith(arq["prefixo_atividades"].lower()):
        return "atividades"
    _, nomes = _cabecalho(caminho)
    nomes = {normaliza(n) for n in nomes}
    if all(normaliza(c) in nomes for c in arq["colunas_religacao_lisc"]):
        return "religacao_lisc"
    if all(normaliza(c) in nomes for c in arq["colunas_cadastro"]):
        return "cadastro"
    if all(normaliza(c) in nomes for c in arq["colunas_catalogo"]):
        return "catalogo"
    return None


def le_atividades(caminho):
    linha, _ = _cabecalho(caminho)
    colunas = list(REGRAS["colunas_atividades"].values())
    df = _le_colunas(caminho, linha, colunas)
    df.columns = list(REGRAS["colunas_atividades"].keys())
    df = df.dropna(how="all")
    df["fonte"] = "atividades"
    return df


def le_religacao_lisc(caminho):
    """Relatório de religação LISC no mesmo formato das atividades: cada O.S. com Dt. Execução é uma religação Finalizada."""
    linha, _ = _cabecalho(caminho)
    col = REGRAS["religacao_lisc"]["colunas"]
    df = _le_colunas(caminho, linha, list(col.values()))
    df.columns = list(col.keys())
    df = df.dropna(subset=["matricula"])
    os_ = df["os"].astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    ano = df["ano"].astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    data_ok = df["data"].notna() & (df["data"].astype("string").str.strip() != "")
    saida = pd.DataFrame({c: None for c in REGRAS["colunas_atividades"]}, index=df.index)
    saida["id"] = ("OS " + os_ + "/" + ano.fillna("")).where(os_.notna() & (os_ != ""))
    for c in ("recurso", "matricula", "servico", "data", "cidade"):
        saida[c] = df[c]
    saida["status"] = pd.Series("Finalizada", index=df.index).where(data_ok)
    saida["fonte"] = "religacao_lisc"
    return saida.reset_index(drop=True)


def le_cadastro(caminho):
    linha, _ = _cabecalho(caminho)
    return _le_colunas(caminho, linha, COLUNAS_CADASTRO).dropna(subset=["NUM_LIGACAO"])


def le_catalogo(caminho):
    linha, _ = _cabecalho(caminho)
    return _le_colunas(caminho, linha, COLUNAS_CATALOGO).dropna(subset=["SERVICO"])


LEITORES = {"atividades": le_atividades, "religacao_lisc": le_religacao_lisc, "cadastro": le_cadastro, "catalogo": le_catalogo}
DESTINO = {"atividades": "atividades", "religacao_lisc": "atividades", "cadastro": "cadastro", "catalogo": "catalogo"}


def le_pasta(pasta, progresso=None):
    """Lê a pasta inteira. Devolve {'atividades': df, 'cadastro': df|None, 'catalogo': df|None, 'arquivos': [...]}."""
    cache_arquivos.configura(pasta)
    arquivos = lista_arquivos(pasta)
    partes = {"atividades": [], "cadastro": [], "catalogo": []}
    relatorio = []
    for i, caminho in enumerate(arquivos):
        rel = os.path.relpath(caminho, pasta).replace(os.sep, "/")
        if progresso:
            progresso(5 + int(60 * i / max(len(arquivos), 1)), f"Lendo {rel} ({i + 1} de {len(arquivos)})")
        try:
            guardado = cache_arquivos.carrega(caminho)
            if guardado is not None:
                tipo, df = guardado
            elif cache_arquivos.em_cache(caminho):           # a leitura guardada não abriu e o arquivo não veio
                raise ValueError("a leitura guardada deste arquivo não abriu; ela foi descartada — clique em ↻ Atualizar")
            else:
                cache_arquivos.materializa(caminho)
                tipo = tipo_arquivo(caminho)
                df = LEITORES[tipo](caminho) if tipo else None
                cache_arquivos.guarda(caminho, (tipo, df))
        except Exception as erro:  # um arquivo com problema não para a análise
            relatorio.append({"arquivo": rel, "tipo": "erro", "linhas": 0,
                              "obs": f"{str(erro)[:150]} | {diagnostico(caminho)}"[:400]})
            continue
        finally:
            cache_arquivos.libera(caminho)
            _ULTIMO_PLANO.update(chave=None, xml=None)
        if tipo is None:
            relatorio.append({"arquivo": rel, "tipo": "não usado", "linhas": 0, "obs": "não é atividades, religação LISC, cadastro nem catálogo"})
            continue
        df = df.assign(arquivo=rel)
        partes[DESTINO[tipo]].append(df)
        relatorio.append({"arquivo": rel, "tipo": tipo, "linhas": int(len(df)),
                          "obs": "já lido antes" if cache_arquivos.em_cache(caminho) else ""})
    junta = lambda lista: pd.concat(lista, ignore_index=True) if lista else None  # noqa: E731
    return {"atividades": junta(partes["atividades"]), "cadastro": junta(partes["cadastro"]),
            "catalogo": junta(partes["catalogo"]), "arquivos": relatorio}
