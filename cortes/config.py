# -*- coding: utf-8 -*-
"""Regras de negócio (regras.json) e catálogo padrão de serviços (catalogo_servicos.json)."""
import json
import os

_PASTA = os.path.dirname(os.path.abspath(__file__))


def _carrega(nome):
    with open(os.path.join(_PASTA, nome), encoding="utf-8") as f:
        return json.load(f)


REGRAS = _carrega("regras.json")
CATALOGO_PADRAO = _carrega("catalogo_servicos.json")["servicos"]
