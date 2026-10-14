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


def _regrava_zip(origem, destino, renomeia):
    import zipfile
    with zipfile.ZipFile(origem) as zin, zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            zout.writestr(renomeia(info.filename), zin.read(info.filename))


def test_xlsx_com_nomes_internos_fora_do_padrao_e_lido(pasta, tmp_path):
    import shutil
    origem = os.path.join(pasta, "Atividades-CENTRALIZADA - IN 01_01_26.xlsx")
    for nome, renomeia in (("barra", lambda n: "/" + n), ("contrabarra", lambda n: n.replace("/", "\\"))):
        sub = tmp_path / nome
        sub.mkdir()
        _regrava_zip(origem, sub / "Atividades-teste.xlsx", renomeia)
        lido = leitura.le_pasta(str(sub))
        assert lido["arquivos"][0]["tipo"] == "atividades", lido["arquivos"]
        assert lido["arquivos"][0]["linhas"] == 17
    shutil.rmtree(tmp_path / "barra")


def test_arquivo_invalido_mostra_diagnostico(tmp_path):
    (tmp_path / "Atividades-vazio.xlsx").write_bytes(b"")
    (tmp_path / "Atividades-texto.xlsx").write_bytes(b"isto nao e um xlsx")
    lido = leitura.le_pasta(str(tmp_path))
    obs = {a["arquivo"]: a for a in lido["arquivos"]}
    assert all(a["tipo"] == "erro" for a in obs.values())
    assert "0 bytes" in obs["Atividades-vazio.xlsx"]["obs"]
    assert "não é um arquivo zip" in obs["Atividades-texto.xlsx"]["obs"]


def _xlsx_plano(destino, linhas, cabecalho):
    """.xlsx como o de alguns sistemas: workbook.xml e sheet1.xml soltos na raiz do zip, células t="str"."""
    import zipfile
    from xml.sax.saxutils import escape

    def letra(i):
        return chr(ord("A") + i)

    def celula(i, n, v):
        return f'<c r="{letra(i)}{n}" t="str" s="0"><v>{escape(v)}</v></c>'

    linhas_xml = ['<row r="1">' + "".join(celula(i, 1, c) for i, c in enumerate(cabecalho)) + "</row>"]
    for n, linha in enumerate(linhas, start=2):
        linhas_xml.append(f'<row r="{n}">' + "".join(celula(i, n, v) for i, v in enumerate(linha)) + "</row>")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("_rels/", "")
        z.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="workbook.xml"/></Relationships>')
        z.writestr("_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="sheet1.xml"/></Relationships>')
        z.writestr("workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Page 1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("styles.xml", '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>')
        z.writestr("sheet1.xml", '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                   + "".join(linhas_xml) + "</sheetData></worksheet>")


def test_xlsx_plano_sem_pasta_xl_e_lido(tmp_path):
    from cortes.config import REGRAS
    cab = ["Recurso", "ID da Atividade", "Matrícula", "Código/Descrição", "Data", "Status da Atividade", "Cidade", "Coluna extra"]
    linhas = [["D11 - A & B", "1", "100", "109001-CORTE DE ÁGUA NO CAVALETE - DÉBITO", "01/04/26", "Finalizada", "APERIBE", "x"],
              ["D11", "2", "200", "111001-RELIGAÇÃO DE ÁGUA NO CAVALETE - DÉBITO", "02/04/26", "Finalizada", "", "y"]]
    _xlsx_plano(tmp_path / "Atividades-plano.xlsx", linhas, cab)
    lido = leitura.le_pasta(str(tmp_path))
    assert lido["arquivos"][0]["tipo"] == "atividades" and lido["arquivos"][0]["linhas"] == 2, lido["arquivos"]
    df = lido["atividades"]
    assert df["recurso"].tolist() == ["D11 - A & B", "D11"]          # &amp; volta a "&"
    assert df["matricula"].tolist() == ["100", "200"]
    assert df["cidade"].isna().tolist() == [False, True]             # célula vazia vira vazio
    assert df["valor_debito"].isna().all()                           # coluna que não existe no arquivo
    assert list(df.columns[:12]) == list(REGRAS["colunas_atividades"].keys())


def test_xlsx_plano_alimenta_o_painel(tmp_path):
    from cortes import Analise
    cab = ["Recurso", "ID da Atividade", "Matrícula", "Código/Descrição", "Data", "Status da Atividade", "Cidade"]
    linhas = [["R", "1", "100", "109001-CORTE DE ÁGUA NO CAVALETE - DÉBITO", "01/04/26", "Finalizada", "APERIBE"],
              ["R", "2", "100", "111001-RELIGAÇÃO DE ÁGUA NO CAVALETE - DÉBITO", "03/04/26", "Finalizada", "APERIBE"]]
    _xlsx_plano(tmp_path / "Atividades-plano.xlsx", linhas, cab)
    analise = Analise(str(tmp_path))
    analise.executar("2026-04-10")
    c = analise.cortes.iloc[0]
    assert len(analise.cortes) == 1 and c["dias"] == 2 and c["regua"] == "Religado" and c["tipo"] == "CAVALETE"
