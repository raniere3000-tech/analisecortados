# -*- coding: utf-8 -*-
"""Ponte entre o site (Pyodide) e o pacote `cortes`.

analisar(pasta, progresso) -> JSON com as bases do painel
excel()                    -> grava /dados/Base_Cortes.xlsx (aba Dados, botão de baixar)
"""
import json
import sys

sys.path.insert(0, "/app")

try:
    from cortes import Analise  # noqa: E402
except ModuleNotFoundError as erro:  # worker antigo guardado no cache do navegador
    raise ModuleNotFoundError(
        "Os arquivos do programa não foram carregados (versão antiga em cache no navegador). "
        "Pressione Ctrl+F5 para recarregar a página e tente de novo.") from erro

_estado = {}


def analisar(pasta, progresso):
    analise = Analise(pasta, progresso=progresso)
    _estado["analise"] = analise
    return json.dumps(analise.executar(), ensure_ascii=False)


def excel(destino):
    with open(destino, "wb") as f:
        f.write(_estado["analise"].excel())
