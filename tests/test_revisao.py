"""Casos apontados na revisão de código (cada teste reproduz o cenário que dava resultado errado)."""
import gzip
import json
import os

import pandas as pd

from cortes import Analise, base, cache_arquivos, leitura

COLS = ["Recurso", "ID da Atividade", "Matrícula", "Código/Descrição", "Data", "Status da Atividade", "Cidade"]
CORTE = "109001-CORTE DE ÁGUA NO CAVALETE - DÉBITO"
RELIG = "111001-RELIGAÇÃO DE ÁGUA NO CAVALETE - DÉBITO"


def _ativ(pasta, linhas, nome="Atividades-teste.xlsx"):
    pd.DataFrame(linhas, columns=COLS).to_excel(os.path.join(pasta, nome), index=False)


def _cad(pasta, linhas):
    pd.DataFrame(linhas, columns=["REFERENCIA", "NUM_LIGACAO", "NOM_CLIENTE", "SIT_LIG", "SUB_CATEGORIA", "TOTAL_ECO", "CIDADE"]) \
        .to_excel(os.path.join(pasta, "Cadastro.xlsx"), index=False)


def test_situacao_de_cadastro_anterior_ao_corte_nao_vale(tmp_path):
    _ativ(tmp_path, [["R", "1", "100", CORTE, "05/04/26", "Finalizada", "A"],      # cadastro de março: ATIVA antes do corte
                     ["R", "2", "200", CORTE, "05/02/26", "Finalizada", "A"]])     # cadastro de março: ATIVA depois do corte
    _cad(tmp_path, [["01/03/2026", "100", "X", "ATIVA", "RES", "1", "A"], ["01/03/2026", "200", "Y", "ATIVA", "RES", "1", "A"]])
    a = Analise(str(tmp_path)); a.executar("2026-04-20")
    c = a.cortes.set_index("matricula")
    assert c.loc["100", "situacao"] == "CORTADA" and c.loc["100", "mes_religacao"] == "Sem Religação"
    assert c.loc["100", "situacao_fonte"].startswith("calculada")
    assert c.loc["200", "situacao"] == "ATIVA" and c.loc["200", "mes_religacao"] == "Ativa"


def test_religacao_e_novo_corte_no_mesmo_dia(tmp_path):
    _ativ(tmp_path, [["R", "1", "100", CORTE, "01/03/26", "Finalizada", "A"], ["R", "2", "100", RELIG, "10/03/26", "Finalizada", "A"],
                     ["R", "3", "100", CORTE, "10/03/26", "Finalizada", "A"]])
    a = Analise(str(tmp_path)); a.executar("2026-04-20")
    c = a.cortes.sort_values("data")
    assert c.iloc[0]["data_religacao"] == pd.Timestamp("2026-03-10") and c.iloc[0]["dias"] == 9
    assert pd.isna(c.iloc[1]["data_religacao"]) and c.iloc[1]["regua"] == "Sem pós corte + 15 dias"


def test_matricula_com_zero_a_esquerda_cruza_com_o_cadastro():
    assert base.matricula(pd.Series(["0101877734", "101877734", "101877734.0", "000"])).tolist()[:3] == ["101877734"] * 3


def test_valor_sem_centavos():
    v = base.valor_br(pd.Series(["R$ 1.234", "R$ 1.234,50", "R$ 12.345.678", "R$ 78,84", "1234.56"]))
    assert v.tolist() == [1234, 1234.5, 12345678, 78.84, 1234.56]



def test_xlsx_plano_com_celula_vazia_no_cabecalho(tmp_path):
    import zipfile
    sheet = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
             '<row r="1"><c r="A1" t="str"><v>ID da Atividade</v></c><c r="B1" s="1"/><c r="C1" t="str"><v>Matrícula</v></c><c r="D1" t="str"><v>Data</v></c></row>'
             '<row r="2"><c r="A2" t="str"><v>1</v></c><c r="B2" t="str"><v>lixo</v></c><c r="C2" t="str"><v>100</v></c><c r="D2" t="str"><v>01/04/26</v></c></row>'
             '</sheetData></worksheet>')
    with zipfile.ZipFile(tmp_path / "Atividades-plano.xlsx", "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>"); z.writestr("_rels/.rels", "<Relationships/>")
        z.writestr("workbook.xml", "<workbook/>"); z.writestr("sheet1.xml", sheet)
    df = leitura.le_atividades(str(tmp_path / "Atividades-plano.xlsx"))
    assert df["matricula"].tolist() == ["100"] and df["data"].tolist() == ["01/04/26"]


def test_cabecalho_com_colunas_sem_nome(tmp_path):
    linhas = [["R", "1", "100", CORTE, "01/04/26", "Finalizada", "A", "x", "y"]]
    pd.DataFrame(linhas, columns=COLS + ["Unnamed: 1", "Unnamed: 2"]).rename(columns={"Unnamed: 1": None, "Unnamed: 2": None}) \
        .to_excel(tmp_path / "Atividades-x.xlsx", index=False)
    df = leitura.le_atividades(str(tmp_path / "Atividades-x.xlsx"))
    assert df["matricula"].tolist() == ["100"]


def test_csv_com_titulo_acima_do_cabecalho(tmp_path):
    (tmp_path / "cadastro.csv").write_text("Relatorio de cadastro\nREFERENCIA;NUM_LIGACAO;SIT_LIG;TOTAL_ECO\n01/03/2026;100;ATIVA;2\n", encoding="utf-8")
    assert leitura.tipo_arquivo(str(tmp_path / "cadastro.csv")) == "cadastro"
    assert leitura.le_cadastro(str(tmp_path / "cadastro.csv"))["NUM_LIGACAO"].tolist() == ["100"]


def test_cidade_do_saldo_vem_do_cadastro(tmp_path):
    _ativ(tmp_path, [["R", "1", "100", CORTE, "01/04/26", "Finalizada", None]])
    _cad(tmp_path, [["01/04/2026", "100", "X", "CORTADA", "RES", "1", "CAMBUCI"]])
    a = Analise(str(tmp_path)); a.executar("2026-04-20")
    assert a.cortes["cidade"].tolist() == ["CAMBUCI"] and a.eventos["cidade"].tolist() == ["CAMBUCI"]


def test_corte_na_planilha_lisc_nao_conta(tmp_path):
    from test_religacao_lisc import _lisc
    _ativ(tmp_path, [["R", "1", "100", CORTE, "01/04/26", "Finalizada", "APERIBE"]])
    _lisc(tmp_path / "lisc.xlsx", [{"Nº da O.S": "1", "Ano da O.S": "2026", "Matrícula": "200", "Serviço Executado": "109002 - CORTE DE ÁGUA NO CAVALETE - DÉBITO (LISC)",
                                   "Dt. Execução": "05/04/2026", "Nome da Localidade": "APERIBE", "Executor": "E"}])
    a = Analise(str(tmp_path)); d = a.executar("2026-04-20")
    assert a.cortes["matricula"].tolist() == ["100"]
    assert d["info"]["Linhas das planilhas LISC que não são religação (não contam)"] == 1


def test_leitura_guardada_corrompida_e_descartada(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_arquivos, "CACHE_DIR", str(tmp_path / "cache"))
    (tmp_path / "dados").mkdir(); (tmp_path / "cache" / "entrada").mkdir(parents=True)
    (tmp_path / "dados" / "Atividades-a.xlsx").write_bytes(b"")              # o site grava vazio o que veio do cache
    (tmp_path / "cache" / "entrada" / "abc.pkl.gz").write_bytes(gzip.compress(b"nao e pickle"))
    (tmp_path / "cache" / "meta.json").write_text(json.dumps({"versao": cache_arquivos.VERSAO, "arquivos": {"Atividades-a.xlsx": {"id": "abc", "em_cache": True}}}))
    lido = leitura.le_pasta(str(tmp_path / "dados"))
    assert lido["arquivos"][0]["tipo"] == "erro" and "Atualizar" in lido["arquivos"][0]["obs"]
    assert cache_arquivos.invalidos() == ["abc"]


def test_versao_do_cache_depende_das_regras_de_leitura():
    assert cache_arquivos.VERSAO.startswith(cache_arquivos.BASE + "-") and len(cache_arquivos.VERSAO.split("-")[1]) == 8


def test_religou_sem_os_inclui_corte_seguido_de_outro_corte(tmp_path):
    _ativ(tmp_path, [["R", "1", "100", CORTE, "05/02/26", "Finalizada", "A"],      # cortada de novo em maio: religou no meio sem OS
                     ["R", "2", "100", CORTE, "05/05/26", "Finalizada", "A"],
                     ["R", "3", "200", CORTE, "05/02/26", "Finalizada", "A"],      # ATIVA no cadastro, único corte
                     ["R", "4", "300", CORTE, "05/02/26", "Finalizada", "A"]])     # CORTADA: segue sem religação
    _cad(tmp_path, [["01/06/2026", "100", "X", "CORTADA", "RES", "1", "A"], ["01/06/2026", "200", "Y", "ATIVA", "RES", "1", "A"],
                    ["01/06/2026", "300", "Z", "CORTADA", "RES", "1", "A"]])
    a = Analise(str(tmp_path)); d = a.executar("2026-06-10")
    c = a.cortes.sort_values(["matricula", "data"])
    assert c["religou_sem_os"].tolist() == [True, False, True, False]
    assert "religou_sem_os" in d["cortes"]
