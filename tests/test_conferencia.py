import datetime as dt

import pandas as pd

from cortes import Analise

COLS_ATIV = ["Recurso", "ID da Atividade", "Matrícula", "Código/Descrição", "Data", "Status da Atividade", "Cidade"]
CORTE, RELIG = "109001-CORTE DE ÁGUA NO CAVALETE - DÉBITO", "111001-RELIGAÇÃO DE ÁGUA NO CAVALETE - DÉBITO"


def _pasta(tmp_path):
    ativ = [["R1", "1", "1000", CORTE, "05/04/26", "Finalizada", "APERIBE"],          # bate em tudo
            ["R1", "2", "2000", CORTE, "05/04/26", "Finalizada", "APERIBE"],          # religação Pendente: planilha conta, painel não
            ["R1", "3", "2000", RELIG, "08/04/26", "Pendente", "APERIBE"],
            ["R1", "4", "3000", CORTE, "06/04/26", "Finalizada", "APERIBE"],          # painel acha religação que a planilha não tem
            ["R1", "5", "3000", RELIG, "09/04/26", "Finalizada", "APERIBE"],
            ["R1", "6", "4000", CORTE, "07/04/26", "Cancelada", "APERIBE"],           # corte não Finalizado: não está no painel
            ["R1", "7", "5000", CORTE, "07/04/26", "Finalizada", "APERIBE"]]          # só no painel
    pd.DataFrame(ativ, columns=COLS_ATIV).to_excel(tmp_path / "Atividades-IN.xlsx", index=False)
    cab = ["NUM_LIGACAO", "DATA_CONCLUSAO", "DESCRICAO", "Mês Corte", "Data Religação", "Mês Religação", "Data Pós Corte", "Mês Pós Corte",
           "Regua de Cobrança", "Dias", "Permanencia", "Situação"]
    d = lambda s: dt.datetime.strptime(s, "%d/%m/%Y")  # noqa: E731
    linhas = [[1000, d("05/04/2026"), "CAVALETE", d("01/04/2026"), "Sem Religação", "Sem Religação", "Sem Pós Corte", "Sem Pós Corte", "Sem pós corte + 15 dias", "Sem Religação", "Sem Religação", None],
              [2000, d("05/04/2026"), "CAVALETE", d("01/04/2026"), d("08/04/2026"), d("01/04/2026"), "Sem Pós Corte", "Sem Pós Corte", "Religado", 3, "Menos de 15 dias", None],
              [3000, d("06/04/2026"), "CAVALETE", d("01/04/2026"), "Sem Religação", "Sem Religação", "Sem Pós Corte", "Sem Pós Corte", "Sem pós corte + 15 dias", "Sem Religação", "Sem Religação", None],
              [4000, d("07/04/2026"), "CAVALETE", d("01/04/2026"), "Sem Religação", "Sem Religação", "Sem Pós Corte", "Sem Pós Corte", "Sem pós corte + 15 dias", "Sem Religação", "Sem Religação", None]]
    with pd.ExcelWriter(tmp_path / "Conferência abril.xlsx") as w:          # título acima do cabeçalho, como nas abas de detalhe
        pd.DataFrame([["Detalhes do Contagem de NUM_LIGACAO"]]).to_excel(w, sheet_name="Detalhe", index=False, header=False)
        pd.DataFrame(linhas, columns=cab).to_excel(w, sheet_name="Detalhe", index=False, startrow=2)
        pd.DataFrame([[1]], columns=["x"]).to_excel(w, sheet_name="Outra", index=False)
    return tmp_path


def test_conferencia_compara_e_explica(tmp_path):
    dados = Analise(str(_pasta(tmp_path))).executar("2026-05-10")
    conf = dados["conferencia"]
    assert {a["arquivo"]: a["tipo"] for a in dados["arquivos"]}["Conferência abril.xlsx"] == "conferencia"
    resumo = {r["tipo"]: r["qtd"] for r in conf["resumo"]}
    assert resumo["Bate em tudo"] == 1
    assert resumo["Religação diferente"] == 2 and resumo["Corte não encontrado no painel"] == 1 and resumo["Corte só no painel"] == 1
    linhas = pd.DataFrame(conf["linhas"])
    m = lambda mat, tipo: linhas[(linhas["matricula"] == mat) & (linhas["tipo"] == tipo)]["motivo"].iloc[0]  # noqa: E731
    assert "Pendente" in m("2000", "Religação diferente")
    assert "09/04/2026" in m("3000", "Religação diferente")
    assert "Cancelada" in m("4000", "Corte não encontrado no painel")
    assert conf["comparadas"] == 4


def test_analitico_comparativo_lado_a_lado(tmp_path):
    conf = Analise(str(_pasta(tmp_path))).executar("2026-05-10")["conferencia"]
    cp = pd.DataFrame(conf["comparativo"]).set_index("matricula")
    assert len(cp) == 5                                            # 4 linhas da planilha + 1 corte só no painel
    assert cp.loc["1000", "resultado"] == "Bate em tudo"
    assert cp.loc["2000", "resultado"] == "Diferente" and cp.loc["2000", "rel_x"] == "08/04/2026" and cp.loc["2000", "rel_p"] == "Sem Religação"
    assert "Pendente" in cp.loc["2000", "motivos"] and cp.loc["2000", "diferencas"] == "Data Religação"
    assert cp.loc["3000", "rel_p"] == "09/04/2026" and cp.loc["4000", "resultado"] == "Corte não encontrado no painel"
    assert cp.loc["5000", "resultado"] == "Corte só no painel"


def test_comparativo_traz_diagnostico(tmp_path):
    cp = pd.DataFrame(Analise(str(_pasta(tmp_path))).executar("2026-05-10")["conferencia"]["comparativo"]).set_index("matricula")
    assert "Pendente" in cp.loc["2000", "religacoes_arq"] and "Atividades-IN.xlsx" in cp.loc["2000", "religacoes_arq"]
    assert cp.loc["4000", "conta_saldo"].startswith("Não") and "Cancelada" in cp.loc["4000", "os_no_dia"]
    assert cp.loc["1000", "conta_pos"] == "Sim" or "situação" in cp.loc["1000", "por_que_pos"]
    assert cp.loc["3000", "conta_pos"] == "Não" and "religou em 09/04/2026" in cp.loc["3000", "por_que_pos"]
