# -*- coding: utf-8 -*-
"""Leitura da pasta: acha os arquivos de atividades, o cadastro e (se houver) o catálogo de serviços.

- Atividades: todo arquivo cujo nome começa com "Atividades-" (em qualquer subpasta).
- Cadastro: planilha com as colunas NUM_LIGACAO, SIT_LIG e TOTAL_ECO.
- Catálogo: planilha com as colunas SERVICO e CATEGORIA (a "Descrição serviço"); sem ela vale a cópia do site.
Cada arquivo é reduzido às colunas usadas; o resultado pode vir guardado de uma análise anterior (cache_arquivos).
"""
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


def _le_csv(caminho, **kw):
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(caminho, sep=None, engine="python", dtype=str, encoding=enc, **kw)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Não foi possível ler o CSV {os.path.basename(caminho)}")


def _cabecalho(caminho, max_linhas=30):
    """(linha do cabeçalho, nomes das colunas) — o cabeçalho pode estar abaixo de um título."""
    if caminho.lower().endswith(".csv"):
        df = _le_csv(caminho, header=None, nrows=max_linhas)
    else:
        df = pd.read_excel(_fonte(caminho), header=None, dtype=str, nrows=max_linhas)
    melhor, cheias = 0, -1
    for i in range(len(df)):
        n = int(df.iloc[i].notna().sum())
        if n > cheias:
            melhor, cheias = i, n
    return melhor, [str(c).strip() for c in df.iloc[melhor].tolist()] if len(df) else []


def _le_colunas(caminho, linha, colunas):
    """Lê só as colunas pedidas (pelo nome normalizado) e devolve com os nomes de `colunas`."""
    alvo = {normaliza(c): c for c in colunas}
    usar = lambda c: normaliza(c) in alvo  # noqa: E731
    if caminho.lower().endswith(".csv"):
        df = _le_csv(caminho, header=linha, usecols=usar)
    else:
        df = pd.read_excel(_fonte(caminho), header=linha, dtype=str, usecols=usar)
    df.columns = [alvo[normaliza(c)] for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    for c in colunas:
        if c not in df.columns:
            df[c] = None
    return df[colunas]


def tipo_arquivo(caminho):
    """'atividades', 'cadastro', 'catalogo' ou None (arquivo que não é usado)."""
    arq = REGRAS["arquivos"]
    if os.path.basename(caminho).lower().startswith(arq["prefixo_atividades"].lower()):
        return "atividades"
    _, nomes = _cabecalho(caminho)
    nomes = {normaliza(n) for n in nomes}
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
    return df


def le_cadastro(caminho):
    linha, _ = _cabecalho(caminho)
    return _le_colunas(caminho, linha, COLUNAS_CADASTRO).dropna(subset=["NUM_LIGACAO"])


def le_catalogo(caminho):
    linha, _ = _cabecalho(caminho)
    return _le_colunas(caminho, linha, COLUNAS_CATALOGO).dropna(subset=["SERVICO"])


LEITORES = {"atividades": le_atividades, "cadastro": le_cadastro, "catalogo": le_catalogo}


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
            else:
                tipo = tipo_arquivo(caminho)
                df = LEITORES[tipo](caminho) if tipo else None
                cache_arquivos.guarda(caminho, (tipo, df))
        except Exception as erro:  # um arquivo com problema não para a análise
            relatorio.append({"arquivo": rel, "tipo": "erro", "linhas": 0,
                              "obs": f"{str(erro)[:150]} | {diagnostico(caminho)}"[:400]})
            continue
        if tipo is None:
            relatorio.append({"arquivo": rel, "tipo": "não usado", "linhas": 0, "obs": "não é atividades, cadastro nem catálogo"})
            continue
        df = df.assign(arquivo=rel)
        partes[tipo].append(df)
        relatorio.append({"arquivo": rel, "tipo": tipo, "linhas": int(len(df)),
                          "obs": "já lido antes" if cache_arquivos.em_cache(caminho) else ""})
    junta = lambda lista: pd.concat(lista, ignore_index=True) if lista else None  # noqa: E731
    return {"atividades": junta(partes["atividades"]), "cadastro": junta(partes["cadastro"]),
            "catalogo": junta(partes["catalogo"]), "arquivos": relatorio}
