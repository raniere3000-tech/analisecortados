import json
import os

from cortes import leitura


def test_le_pasta_com_subpastas(pasta):
    lido = leitura.le_pasta(pasta)
    tipos = {a["arquivo"]: a["tipo"] for a in lido["arquivos"]}
    assert tipos["marco/Atividades-CENTRALIZADA - IN 06_03_26.xlsx"] == "atividades"
    assert tipos["Cadastro ligacoes.xlsx"] == "cadastro"
    assert tipos["outra coisa.xlsx"] == "não usado"
    assert len(lido["atividades"]) == 19          # 17 + 2 (a repetida sai depois, na preparação)
    assert len(lido["cadastro"]) == 8


def test_atividade_repetida_entre_arquivos_conta_uma_vez(resultado):
    _, dados = resultado
    assert dados["info"]["Atividades repetidas entre arquivos (contadas uma vez)"] == 1
    assert dados["info"]["Atividades lidas"] == 18


def test_json_do_site(resultado):
    _, dados = resultado
    texto = json.dumps(dados, ensure_ascii=False)
    assert "NaN" not in texto and "NaT" not in texto
    n = len(dados["cortes"]["matricula"])
    assert all(len(v) == n for v in dados["cortes"].values())
    assert dados["cortes"]["data"][0].count("-") == 2


def test_excel_de_conferencia(resultado, tmp_path):
    analise, _ = resultado
    destino = tmp_path / "Base.xlsx"
    destino.write_bytes(analise.excel())
    import pandas as pd
    abas = pd.read_excel(destino, sheet_name=None)
    assert set(abas) == {"Base cortes", "Eventos saldo", "Arquivos lidos", "Parâmetros"}
    assert len(abas["Base cortes"]) == len(analise.cortes)


def test_cache_reaproveita_leitura(pasta, tmp_path, monkeypatch):
    from cortes import cache_arquivos
    monkeypatch.setattr(cache_arquivos, "CACHE_DIR", str(tmp_path))
    rel = "marco/Atividades-CENTRALIZADA - IN 06_03_26.xlsx"
    meta = {"versao": cache_arquivos.VERSAO, "arquivos": {rel: {"id": "abc", "em_cache": False}}}
    (tmp_path / "meta.json").write_text(json.dumps(meta))
    leitura.le_pasta(pasta)
    assert (tmp_path / "saida" / "abc.pkl.gz").exists()
    os.makedirs(tmp_path / "entrada")
    os.replace(tmp_path / "saida" / "abc.pkl.gz", tmp_path / "entrada" / "abc.pkl.gz")
    meta["arquivos"][rel]["em_cache"] = True
    (tmp_path / "meta.json").write_text(json.dumps(meta))
    lido = leitura.le_pasta(pasta)
    linha = [a for a in lido["arquivos"] if a["arquivo"] == rel][0]
    assert linha["obs"] == "já lido antes" and linha["linhas"] == 2
