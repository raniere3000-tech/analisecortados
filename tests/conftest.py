import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dados_sinteticos  # noqa: E402


@pytest.fixture(scope="session")
def pasta(tmp_path_factory):
    return dados_sinteticos.cria_pasta(str(tmp_path_factory.mktemp("dados")))


@pytest.fixture(scope="session")
def resultado(pasta):
    from cortes import Analise
    analise = Analise(pasta)
    dados = analise.executar(dados_sinteticos.HOJE)
    return analise, dados
