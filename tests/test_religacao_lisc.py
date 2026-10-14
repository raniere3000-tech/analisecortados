import pandas as pd

from cortes import Analise, base, leitura

COLS_LISC = ["Nº da O.S", "Ano da O.S", "Matrícula", "Dt. Emissão", "Setor Comercial", "Serviço Executado", "Nome Cliente",
             "Nome Requerente", "Telefone", "Endereço do Requerente", "Nome Logradouro", "Número da Porta", "Desc. Complemento",
             "Nome do Bairro", "Nome da Localidade", "Dt Agendamento", "Dt. Impressão", "Prev. Conclusão", "Dt. Execução",
             "Executor", "Entrada no Setor", "Data Pedido", "Atendente", "Solicitação Associada", "Tipo de Solicitação"]
COLS_ATIV = ["Recurso", "ID da Atividade", "Matrícula", "Código/Descrição", "Data", "Status da Atividade", "Cidade"]


def _lisc(destino, linhas):
    df = pd.DataFrame([{**{c: None for c in COLS_LISC}, **l} for l in linhas], columns=COLS_LISC)
    with pd.ExcelWriter(destino) as w:                       # título "AGUAS DO RIO 1 SPE S.A" acima do cabeçalho
        pd.DataFrame([["AGUAS DO RIO 1 SPE S.A"]]).to_excel(w, index=False, header=False)
        df.to_excel(w, index=False, startrow=1)


def _pasta(tmp_path):
    ativ = [["R1", "1", "1000", "109002-CORTE DE ÁGUA NO CAVALETE - DÉBITO (LISC)", "01/04/26", "Finalizada", "APERIBE"],
            ["R1", "2", "2000", "109001-CORTE DE ÁGUA NO CAVALETE - DÉBITO", "01/04/26", "Finalizada", "APERIBE"],
            ["R1", "3", "2000", "111001-RELIGAÇÃO DE ÁGUA NO CAVALETE - DÉBITO", "05/04/26", "Finalizada", "APERIBE"],
            ["R1", "4", "3000", "109001-CORTE DE ÁGUA NO CAVALETE - DÉBITO", "02/04/26", "Finalizada", "CAMBUCI"]]
    pd.DataFrame(ativ, columns=COLS_ATIV).to_excel(tmp_path / "Atividades-IN_01_04_26.xlsx", index=False)
    (tmp_path / "LISC").mkdir()
    _lisc(tmp_path / "LISC" / "Religacao LISC abril.xlsx", [
        {"Nº da O.S": "5001", "Ano da O.S": "2026", "Matrícula": "1000", "Serviço Executado": "RELIGAÇÃO DE ÁGUA NO CAVALETE - DÉBITO (LISC)",
         "Dt. Execução": "03/04/2026 10:15", "Nome da Localidade": "APERIBE", "Executor": "EQUIPE LISC 1"},
        {"Nº da O.S": "5002", "Ano da O.S": "2026", "Matrícula": "2000", "Serviço Executado": "RELIGACAO LISC",       # repete a religação das atividades
         "Dt. Execução": "05/04/2026", "Nome da Localidade": "APERIBE", "Executor": "EQUIPE LISC 1"},
        {"Nº da O.S": "5003", "Ano da O.S": "2026", "Matrícula": "3000", "Serviço Executado": "RELIGAÇÃO LISC",
         "Dt. Execução": None, "Nome da Localidade": "CAMBUCI", "Executor": "EQUIPE LISC 2"},                    # sem execução: não conta
        {"Nº da O.S": "5004", "Ano da O.S": "2026", "Matrícula": "3000", "Serviço Executado": "VISTORIA DE CONSUMO",
         "Dt. Execução": "04/04/2026", "Nome da Localidade": "CAMBUCI", "Executor": "EQUIPE LISC 2"},            # não é religação
        {"Nº da O.S": "5005", "Ano da O.S": "2026", "Matrícula": "3000", "Serviço Executado": "AUTORELIGAÇÃO LISC",
         "Dt. Execução": "06/04/2026", "Nome da Localidade": "Cambuci", "Executor": "EQUIPE LISC 2"},            # cidade com outra grafia: vale
        {"Nº da O.S": "5006", "Ano da O.S": "2026", "Matrícula": "4000", "Serviço Executado": "AUTORELIGAÇÃO LISC",
         "Dt. Execução": "06/04/2026", "Nome da Localidade": "NITERÓI", "Executor": "EQUIPE LISC 3"},            # cidade fora das atividades
    ])
    _lisc(tmp_path / "LISC" / "Religacao LISC abril (copia).xlsx", [                                        # mesma O.S. em outro arquivo
        {"Nº da O.S": "5001", "Ano da O.S": "2026", "Matrícula": "1000", "Serviço Executado": "RELIGAÇÃO DE ÁGUA NO CAVALETE - DÉBITO (LISC)",
         "Dt. Execução": "03/04/2026 10:15", "Nome da Localidade": "APERIBE", "Executor": "EQUIPE LISC 1"}])
    return tmp_path


def test_planilha_lisc_e_reconhecida(tmp_path):
    lido = leitura.le_pasta(str(_pasta(tmp_path)))
    tipos = {a["arquivo"]: a["tipo"] for a in lido["arquivos"]}
    assert tipos["LISC/Religacao LISC abril.xlsx"] == "religacao_lisc"
    df = lido["atividades"]
    lisc = df[df["fonte"] == "religacao_lisc"]
    assert len(lisc) == 7 and lisc["id"].iloc[0] == "OS 5001/2026"
    assert lisc["status"].isna().sum() == 1                  # a linha sem Dt. Execução não vira Finalizada


def test_religacao_lisc_entra_nos_cortes_e_no_saldo(tmp_path):
    analise = Analise(str(_pasta(tmp_path)))
    dados = analise.executar("2026-04-10")
    c = analise.cortes.set_index("matricula")
    assert c.loc["1000", "data_religacao"] == pd.Timestamp("2026-04-03")
    assert c.loc["1000", "tipo_religacao"] == "LISC" and c.loc["1000", "dias"] == 2
    assert c.loc["3000", "data_religacao"] == pd.Timestamp("2026-04-06")   # sem execução e vistoria não religam; a autoreligação de 06/04 sim
    assert "4000" not in set(analise.eventos["matricula"])  # NITERÓI não está nas atividades
    ev = analise.eventos
    rel = ev[ev["categoria"] == "RELIGAÇÃO"]
    assert sorted(rel["matricula"]) == ["1000", "2000", "3000"]      # a religação de 2000 (atividades + LISC no mesmo dia) conta uma vez
    assert dados["info"]["Religações das planilhas LISC (com Dt. Execução)"] == 3
    assert dados["info"]["Linhas das planilhas LISC de cidades que não estão nas atividades (não contam)"] == 1
    assert dados["info"]["Linhas das planilhas LISC sem Dt. Execução (não contam)"] == 1
    assert dados["info"]["Linhas das planilhas LISC que não são religação (não contam)"] == 1
    assert dados["info"]["Atividades repetidas entre arquivos (contadas uma vez)"] == 1


def test_os_repetida_vale_a_finalizada():
    cat, _ = base.catalogo(None)
    ativ = pd.DataFrame({c: [None, None] for c in ["id", "recurso", "conta", "matricula", "servico", "data", "status", "cidade", "parecer", "motivo", "valor_debito", "negociou"]})
    ativ["id"] = ["9", "9"]; ativ["matricula"] = ["1", "1"]; ativ["servico"] = ["109001-CORTE DE ÁGUA NO CAVALETE - DÉBITO"] * 2
    ativ["data"] = ["01/04/26", "02/04/26"]; ativ["status"] = ["Pendente", "Finalizada"]
    df, dup = base.prepara_atividades(ativ, cat)
    assert dup == 1 and df["status"].tolist() == ["Finalizada"]


def test_referencia_do_cadastro_em_outros_formatos():
    d = base.datas(pd.Series(["09/2026", "202609", "2026-09-01", "01/09/2026"]))
    assert (d == pd.Timestamp("2026-09-01")).all()
