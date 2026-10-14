# -*- coding: utf-8 -*-
"""Pasta de exemplo com atividades, cadastro e situações que testam cada regra."""
import os

import pandas as pd

COLUNAS = ["Recurso", "Cód. Protocolo Origem", "ID da Atividade", "Número da Conta", "Matrícula", "Código/Descrição",
           "Data", "Status da Atividade", "Cidade", "Parecer De Campo", "Motivo de Não Execução - Normal",
           "Valor Total dos Débitos", "Negociou O Débito?"]

C_CAV = "109001-CORTE DE ÁGUA NO CAVALETE - DÉBITO"
C_LISC = "109002 - CORTE DE ÁGUA NO CAVALETE - DÉBITO (LISC)"
C_RAMAL = "109004-CORTE DE ÁGUA NO RAMAL - DÉBITO"
R_CAV = "111001-RELIGAÇÃO DE ÁGUA NO CAVALETE - DÉBITO"
AUTO = "Autoreligação"
POS = "110010-VISTORIA PÓS CORTE"
LNA = "117007-IMPLANTAÇÃO DE LIGAÇÃO DE ÁGUA 3/4 - TERRA"
OUTRO = "146004-VERIFICAÇÃO DE FALTA DE ÁGUA"


def _linha(id_, mat, serv, data, status="Finalizada", cidade="APERIBE", recurso="RIOOPEIN-006", valor="R$ 78,84"):
    return {"Recurso": recurso, "Cód. Protocolo Origem": "x", "ID da Atividade": str(id_), "Número da Conta": "92",
            "Matrícula": str(mat), "Código/Descrição": serv, "Data": data, "Status da Atividade": status,
            "Cidade": cidade, "Parecer De Campo": "ok", "Motivo de Não Execução - Normal": None,
            "Valor Total dos Débitos": valor, "Negociou O Débito?": None}


ATIVIDADES_1 = [
    # 100: corte no cavalete + LISC no mesmo dia (vale 1 corte, CAVALETE); religação 2 dias depois
    _linha(1, 100, C_CAV, "05/01/26"), _linha(2, 100, C_LISC, "05/01/26"), _linha(3, 100, R_CAV, "07/01/26"),
    # 200: 1ª visita pós-corte sem sucesso, depois uma Finalizada; religa 41 dias após o corte
    _linha(4, 200, C_RAMAL, "10/01/26"), _linha(5, 200, POS, "12/01/26", "Encerrada com Ocorrência"),
    _linha(6, 200, POS, "15/01/26"), _linha(7, 200, R_CAV, "20/02/26"),
    # 300: cortado sem religação, mas ATIVA no cadastro (religou sem OS)
    _linha(8, 300, C_CAV, "01/02/26"),
    # 400: dois cortes; a religação vem depois do 2º corte -> só o 2º religou
    _linha(9, 400, C_CAV, "01/01/26"), _linha(10, 400, C_CAV, "01/03/26"), _linha(11, 400, AUTO, "05/03/26"),
    # 500: corte recente sem pós-corte; corte cancelado não conta
    _linha(12, 500, C_LISC, "08/03/26"), _linha(13, 501, C_CAV, "08/03/26", "Cancelada"),
    # 600: implantação de ligação de água (3 economias no cadastro)
    _linha(14, 600, LNA, "03/01/26"),
    # 700: sem cadastro; religação no mesmo dia do corte
    _linha(15, 700, C_CAV, "2026-02-02 00:00:00"), _linha(16, 700, R_CAV, "02/02/26"),
    # serviço fora do painel
    _linha(17, 800, OUTRO, "02/02/26"),
]
# arquivo numa subpasta repetindo a atividade 1 (conta uma vez) e trazendo uma nova
ATIVIDADES_2 = [_linha(1, 100, C_CAV, "05/01/26"), _linha(18, 900, C_CAV, "06/03/26", cidade="ITAOCARA")]

CADASTRO = [
    {"REFERENCIA": "01/02/2026", "NUM_LIGACAO": "100", "NOM_CLIENTE": "A", "SIT_LIG": "CORTADA", "SUB_CATEGORIA": "RESIDENCIAL", "TOTAL_ECO": "1", "CIDADE": "APERIBE"},
    {"REFERENCIA": "01/03/2026", "NUM_LIGACAO": "100", "NOM_CLIENTE": "A", "SIT_LIG": "ATIVA", "SUB_CATEGORIA": "RESIDENCIAL", "TOTAL_ECO": "2", "CIDADE": "APERIBE"},
    {"REFERENCIA": "01/03/2026", "NUM_LIGACAO": "200", "NOM_CLIENTE": "B", "SIT_LIG": "ATIVA", "SUB_CATEGORIA": "RESIDENCIAL", "TOTAL_ECO": "1", "CIDADE": "APERIBE"},
    {"REFERENCIA": "01/03/2026", "NUM_LIGACAO": "300", "NOM_CLIENTE": "C", "SIT_LIG": "ATIVA", "SUB_CATEGORIA": "COMERCIAL", "TOTAL_ECO": "1", "CIDADE": "APERIBE"},
    {"REFERENCIA": "01/03/2026", "NUM_LIGACAO": "400", "NOM_CLIENTE": "D", "SIT_LIG": "ATIVA", "SUB_CATEGORIA": "RESIDENCIAL", "TOTAL_ECO": "1", "CIDADE": "APERIBE"},
    {"REFERENCIA": "01/03/2026", "NUM_LIGACAO": "500", "NOM_CLIENTE": "E", "SIT_LIG": "CORTADA", "SUB_CATEGORIA": "RESIDENCIAL", "TOTAL_ECO": "1", "CIDADE": "APERIBE"},
    {"REFERENCIA": "01/03/2026", "NUM_LIGACAO": "600", "NOM_CLIENTE": "F", "SIT_LIG": "ATIVA", "SUB_CATEGORIA": "RESIDENCIAL", "TOTAL_ECO": "3", "CIDADE": "APERIBE"},
    {"REFERENCIA": "01/03/2026", "NUM_LIGACAO": "900", "NOM_CLIENTE": "G", "SIT_LIG": "CORTADA", "SUB_CATEGORIA": "RESIDENCIAL", "TOTAL_ECO": "1", "CIDADE": "ITAOCARA"},
]

HOJE = "2026-03-10"


def cria_pasta(pasta):
    os.makedirs(os.path.join(pasta, "marco"), exist_ok=True)
    pd.DataFrame(ATIVIDADES_1, columns=COLUNAS).to_excel(os.path.join(pasta, "Atividades-CENTRALIZADA - IN 01_01_26.xlsx"), index=False)
    pd.DataFrame(ATIVIDADES_2, columns=COLUNAS).to_excel(os.path.join(pasta, "marco", "Atividades-CENTRALIZADA - IN 06_03_26.xlsx"), index=False)
    cad = pd.DataFrame(CADASTRO)
    with pd.ExcelWriter(os.path.join(pasta, "Cadastro ligacoes.xlsx")) as w:   # cabeçalho abaixo de um título
        pd.DataFrame([["Relatório de cadastro"]]).to_excel(w, index=False, header=False)
        cad.to_excel(w, index=False, startrow=2)
    pd.DataFrame({"x": [1]}).to_excel(os.path.join(pasta, "outra coisa.xlsx"), index=False)
    return pasta
