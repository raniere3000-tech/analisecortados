# -*- coding: utf-8 -*-
"""O que vai para o site (JSON colunar, leve) e o Excel para conferir os cálculos (aba Dados)."""
import io

import numpy as np
import pandas as pd

# coluna no JSON -> coluna da base de cortes
COLUNAS_CORTES = {
    "matricula": "matricula", "data": "data", "mes_corte": "mes_corte", "tipo": "tipo", "servico": "servico",
    "recurso": "recurso", "cidade": "cidade", "sup": "sup", "cliente": "cliente", "sub_categoria": "sub_categoria",
    "economias": "economias", "valor_debito": "valor_debito", "negociou": "negociou", "motivo": "motivo",
    "data_religacao": "data_religacao", "mes_religacao": "mes_religacao", "tipo_religacao": "tipo_religacao",
    "data_pos": "data_pos", "mes_pos": "mes_pos", "status_pos": "status_pos", "obs_pos": "obs_pos",
    "data_pos_finalizada": "data_pos_finalizada", "regua": "regua", "dias": "dias", "dias_cortado": "dias_cortado",
    "permanencia": "permanencia", "situacao": "situacao", "situacao_fonte": "situacao_fonte", "religou_sem_os": "religou_sem_os", "id": "id", "arquivo": "arquivo",
}

# eventos do saldo (corte, religação, implantação) para abrir os clientes por trás de cada número
COLUNAS_EVENTOS = {
    "matricula": "matricula", "data": "data", "categoria": "categoria", "tipo": "tipo", "economias": "economias",
    "cidade": "cidade", "sup": "sup", "recurso": "recurso", "servico": "servico", "id": "id",
}

# nomes das colunas no Excel (como nas planilhas antigas, quando havia equivalente)
NOMES_EXCEL = {
    "matricula": "NUM_LIGACAO", "data": "DATA_CONCLUSAO", "mes_corte": "Mês Corte", "tipo": "Tipo de corte",
    "servico": "Código/Descrição", "recurso": "Recurso", "cidade": "Cidade", "sup": "Sup", "cliente": "Cliente",
    "sub_categoria": "Subcategoria", "economias": "Economias", "valor_debito": "Valor Total dos Débitos",
    "negociou": "Negociou O Débito?", "motivo": "Motivo de Não Execução - Normal",
    "data_religacao": "Data Religação", "mes_religacao": "Mês Religação", "tipo_religacao": "Tipo de religação",
    "data_pos": "Data Pós Corte", "mes_pos": "Mês Pós Corte", "status_pos": "Status 1ª visita pós corte",
    "obs_pos": "Observação pós corte", "data_pos_finalizada": "Data 1º pós corte Finalizado",
    "regua": "Regua de Cobrança", "dias": "Dias", "dias_cortado": "Dias cortado (até hoje)",
    "permanencia": "Permanencia", "situacao": "Situação", "situacao_fonte": "Origem da situação", "religou_sem_os": "Religou sem OS (ativa ou cortada de novo)", "id": "ID da Atividade", "arquivo": "Arquivo",
}


def _lista(serie):
    if pd.api.types.is_datetime64_any_dtype(serie):
        return [None if pd.isna(v) else v.strftime("%Y-%m-%d") for v in serie]
    if pd.api.types.is_numeric_dtype(serie):
        return [None if pd.isna(v) else (int(v) if float(v).is_integer() else round(float(v), 2)) for v in serie]
    return [None if (v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA) else str(v) for v in serie]


def colunar(df, colunas):
    return {k: _lista(df[v]) if v in df.columns else [None] * len(df) for k, v in colunas.items()}


def saldo_agrupado(ev):
    """Saldo por mês, categoria, tipo, cidade e recurso (o site soma conforme os filtros)."""
    if ev.empty:
        return {k: [] for k in ("mes", "categoria", "tipo", "sup", "cidade", "recurso", "qtd", "economias", "sem_cadastro")}
    g = (ev.assign(cidade=ev["cidade"].fillna(""), recurso=ev["recurso"].fillna(""),
                   sup=ev["sup"].fillna("") if "sup" in ev.columns else "")
         .groupby(["mes", "categoria", "tipo", "sup", "cidade", "recurso"], dropna=False)
         .agg(qtd=("matricula", "size"), economias=("economias", "sum"), sem_cadastro=("sem_cadastro", "sum"))
         .reset_index())
    g["mes"] = g["mes"].dt.strftime("%Y-%m")
    return colunar(g, {c: c for c in g.columns})


def excel(cortes, eventos, arquivos, info):
    """Planilha para conferir: base de cortes, eventos do saldo, arquivos lidos e parâmetros."""
    buf = io.BytesIO()
    try:
        import xlsxwriter  # noqa: F401
        motor = "xlsxwriter"
    except ImportError:
        motor = "openpyxl"
    base = cortes[[c for c in COLUNAS_CORTES.values() if c in cortes.columns]].rename(columns=NOMES_EXCEL)
    ev = eventos[["categoria", "tipo", "matricula", "data", "mes", "status", "economias", "sem_cadastro", "sinal",
                  "servico", "recurso", "cidade", "sup", "id", "arquivo"]].copy()
    ev["economias com sinal"] = ev["economias"] * ev["sinal"]
    with pd.ExcelWriter(buf, engine=motor) as w:
        base.to_excel(w, sheet_name="Base cortes", index=False)
        ev.to_excel(w, sheet_name="Eventos saldo", index=False)
        pd.DataFrame(arquivos).to_excel(w, sheet_name="Arquivos lidos", index=False)
        pd.DataFrame(list(info.items()), columns=["Parâmetro", "Valor"]).to_excel(w, sheet_name="Parâmetros", index=False)
    return buf.getvalue()
