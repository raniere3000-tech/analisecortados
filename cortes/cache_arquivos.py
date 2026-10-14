# -*- coding: utf-8 -*-
"""Arquivos já lidos em análises anteriores (guardados no navegador) não são lidos de novo.

O site (analisador.worker.js) compara cada arquivo da pasta pelo caminho, tamanho e data de alteração:
  - igual ao de uma análise anterior: grava um arquivo vazio no lugar e entrega o resultado guardado em
    CACHE_DIR/entrada/<id>.pkl.gz — a leitura é pulada;
  - novo ou alterado: é lido normalmente e o resultado vai para CACHE_DIR/saida/<id>.pkl.gz, que o site guarda.
CACHE_DIR/meta.json diz, para cada arquivo (caminho relativo à pasta), o id e se veio do cache.
Sem meta.json (linha de comando, testes) tudo é lido do arquivo.
"""
import gzip
import hashlib
import json
import os
import pickle

from .config import REGRAS

# mude BASE quando a leitura dos arquivos mudar; a parte de regras.json que define a leitura entra sozinha na versão
BASE = "3"
_LEITURA = {k: REGRAS.get(k) for k in ("arquivos", "colunas_atividades", "religacao_lisc")}
VERSAO = BASE + "-" + hashlib.sha1(json.dumps(_LEITURA, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:8]
CACHE_DIR = os.environ.get("CORTES_CACHE", "/cache")

_estado = {"pasta": None, "meta": {}, "invalidos": []}


def configura(pasta):
    meta = {}
    caminho = os.path.join(CACHE_DIR, "meta.json")
    if os.path.exists(caminho):
        try:
            with open(caminho, encoding="utf-8") as f:
                dados = json.load(f)
            if str(dados.get("versao")) == VERSAO:
                meta = dados.get("arquivos") or {}
        except (OSError, ValueError):
            meta = {}
    _estado.update(pasta=os.path.abspath(pasta), meta=meta, invalidos=[])


def _rel(caminho):
    return os.path.relpath(os.path.abspath(caminho), _estado["pasta"] or "").replace(os.sep, "/")


def _info(caminho):
    return _estado["meta"].get(_rel(caminho))


def em_cache(caminho):
    i = _info(caminho)
    return bool(i and i.get("em_cache"))


def carrega(caminho):
    """Resultado guardado da leitura deste arquivo, ou None."""
    i = _info(caminho)
    if not (i and i.get("em_cache")):
        return None
    arq = os.path.join(CACHE_DIR, "entrada", f"{i['id']}.pkl.gz")
    if not os.path.exists(arq):
        i["em_cache"] = False
        return None
    try:
        with gzip.open(arq, "rb") as f:
            return pickle.load(f)
    except Exception:                                       # arquivo guardado corrompido ou de outra versão do pandas
        _estado["invalidos"].append(i["id"])
        return None


def invalidos():
    """ids das leituras guardadas que não abriram: o site apaga do navegador."""
    return list(_estado["invalidos"])


def _js():
    try:
        import js  # noqa: F401  (só existe no navegador, Pyodide)
        return js if hasattr(js, "materializa") else None
    except ImportError:
        return None


def materializa(caminho):
    """No navegador o arquivo só é copiado para a memória do Python na hora de ser lido (o site deixa um vazio no lugar)."""
    js = _js()
    if js is not None:
        js.materializa(_rel(caminho))


def libera(caminho):
    """Depois de lido, o arquivo volta a ocupar 0 bytes (com ~250 arquivos a memória do navegador acabaria)."""
    js = _js()
    if js is not None:
        js.libera(_rel(caminho))


def guarda(caminho, resultado):
    """Grava o resultado da leitura para o site guardar (só quando o site mandou o meta.json)."""
    i = _info(caminho)
    if not i:
        return
    pasta = os.path.join(CACHE_DIR, "saida")
    os.makedirs(pasta, exist_ok=True)
    with gzip.open(os.path.join(pasta, f"{i['id']}.pkl.gz"), "wb", compresslevel=3) as f:
        pickle.dump(resultado, f, protocol=pickle.HIGHEST_PROTOCOL)
