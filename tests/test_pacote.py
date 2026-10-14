import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_worker_carrega_todos_os_arquivos_do_pacote():
    worker = open(os.path.join(RAIZ, "analisador.worker.js"), encoding="utf-8").read()
    listados = set(re.findall(r'"(cortes/[^"]+)"', worker))
    no_pacote = {f"cortes/{n}" for n in os.listdir(os.path.join(RAIZ, "cortes")) if n.endswith((".py", ".json"))}
    assert no_pacote == listados, "inclua/retire o arquivo em ARQUIVOS_PY no analisador.worker.js"


def test_versao_do_site_igual_no_cabecalho():
    html = open(os.path.join(RAIZ, "index.html"), encoding="utf-8").read()
    versao = re.search(r'const VERSAO_SITE = "([^"]+)"', html).group(1)
    assert f'<span id="versao">{versao}</span>' in html
