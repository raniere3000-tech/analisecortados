import pandas as pd

from cortes import base


def _corte(resultado, mat, data=None):
    analise, _ = resultado
    c = analise.cortes[analise.cortes["matricula"] == str(mat)]
    if data:
        c = c[c["data"] == pd.Timestamp(data)]
    assert len(c) == 1, c
    return c.iloc[0]


def test_corte_duplicado_no_mesmo_dia_conta_uma_vez(resultado):
    c = _corte(resultado, 100)
    assert c["tipo"] == "CAVALETE"
    assert c["data_religacao"] == pd.Timestamp("2026-01-07")
    assert c["dias"] == 2 and c["permanencia"] == "Menor que 15"
    assert c["regua"] == "Religado" and c["mes_religacao"] == "2026-01"


def test_pos_corte_sem_sucesso_e_religacao_apos_pos(resultado):
    c = _corte(resultado, 200)
    assert c["tipo"] == "RAMAL"
    assert c["data_pos"] == pd.Timestamp("2026-01-12")
    assert c["status_pos"] == "Encerrada com Ocorrência"
    assert "sem sucesso" in c["obs_pos"]
    assert c["data_pos_finalizada"] == pd.Timestamp("2026-01-15")
    assert c["regua"] == "Religado após pós corte"
    assert c["dias"] == 41 and c["permanencia"] == "30 a 45 dias"


def test_sem_religacao_mas_ativa_no_cadastro(resultado):
    c = _corte(resultado, 300)
    assert pd.isna(c["data_religacao"])
    assert c["mes_religacao"] == "Ativa" and c["situacao"] == "ATIVA"
    assert c["dias_cortado"] == 37 and c["regua"] == "Sem pós corte + 15 dias"
    assert c["permanencia"] == "Sem Religação"


def test_religacao_so_vale_antes_do_proximo_corte(resultado):
    primeiro = _corte(resultado, 400, "2026-01-01")
    segundo = _corte(resultado, 400, "2026-03-01")
    assert pd.isna(primeiro["data_religacao"])
    assert primeiro["mes_religacao"] == "Sem Religação"      # ATIVA hoje, mas foi cortada de novo depois
    assert segundo["data_religacao"] == pd.Timestamp("2026-03-05")
    assert segundo["tipo_religacao"] == "AUTORELIGAÇÃO" and segundo["dias"] == 4


def test_regua_conta_dias_ate_hoje(resultado):
    c = _corte(resultado, 500)
    assert c["tipo"] == "LISC"
    assert c["dias_cortado"] == 2 and c["regua"] == "Sem pós corte - 7 dias"
    c9 = _corte(resultado, 900)
    assert c9["dias_cortado"] == 4 and c9["cidade"] == "ITAOCARA"


def test_cancelada_nao_conta(resultado):
    analise, _ = resultado
    assert "501" not in set(analise.cortes["matricula"])


def test_sem_cadastro_e_religacao_no_mesmo_dia(resultado):
    c = _corte(resultado, 700)
    assert c["situacao"] == "Sem cadastro" and c["economias"] == 1
    assert c["dias"] == 0 and c["permanencia"] == "Menor que 15"


def test_saldo_de_economias(resultado):
    analise, _ = resultado
    ev = analise.eventos.copy()
    ev["mes"] = ev["mes"].dt.strftime("%Y-%m")
    jan = ev[ev["mes"] == "2026-01"]
    # sem cadastro de jan, vale o mais recente: 100 tem 2 economias
    cortes = jan[jan["categoria"] == "CORTE"]
    assert sorted(cortes["matricula"]) == ["100", "200", "400"]
    assert cortes.loc[cortes["matricula"] == "100", "economias"].iloc[0] == 2
    lna = jan[jan["categoria"] == "IMPLANTAÇÃO DE LIGAÇÃO DE ÁGUA"]
    assert lna["economias"].sum() == 3 and (lna["tipo"] == "LNA").all()
    saldo = (jan["economias"] * jan["sinal"]).sum()
    assert saldo == -(2 + 1 + 1) + 2 + 3       # −cortes (100, 200, 400) + religação (100) + implantação (600)
    fev = ev[(ev["mes"] == "2026-02") & (ev["matricula"] == "100")]
    assert fev.empty


def test_economias_do_mes_de_referencia():
    eventos = pd.DataFrame({"matricula": ["1", "1"], "data": pd.to_datetime(["2026-02-10", "2026-04-01"])})
    cad = base.prepara_cadastro(pd.DataFrame({
        "REFERENCIA": ["01/02/2026", "01/03/2026"], "NUM_LIGACAO": ["1", "1"], "SIT_LIG": ["ATIVA", "ATIVA"],
        "TOTAL_ECO": ["4", "5"], "NOM_CLIENTE": None, "SUB_CATEGORIA": None, "CIDADE": None}))
    eco, sem = base.economias(eventos, cad)
    assert list(eco) == [4, 5] and not sem.any()


def test_datas_e_valores():
    d = base.datas(pd.Series(["01/10/26", "5/1/2026", "2026-02-03 00:00:00", "46296", None, "x"]))
    assert list(d[:4]) == [pd.Timestamp(x) for x in ("2026-10-01", "2026-01-05", "2026-02-03", "2026-10-01")]
    assert d[4:].isna().all()
    v = base.valor_br(pd.Series(["R$ 1.234,56", "R$", "R$ 78,84", None]))
    assert v[0] == 1234.56 and pd.isna(v[1]) and v[2] == 78.84 and pd.isna(v[3])
    assert list(base.matricula(pd.Series(["101877734.0", " 1018 ", None]))[:2]) == ["101877734", "1018"]
