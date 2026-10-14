# -*- coding: utf-8 -*-
"""Executa tudo: lê a pasta, calcula as bases e devolve o pacote de dados do painel."""
from datetime import date

import pandas as pd

from . import base, leitura, saida
from .config import REGRAS

CAT = REGRAS["categorias"]
SUSPEITOS = r"CORTE|RELIGA|POS CORTE|IMPLANTACAO DE LIGACAO DE AGUA"


class Analise:
    def __init__(self, pasta, progresso=None):
        self.pasta = pasta
        self.progresso = progresso or (lambda pct, texto: None)
        self.cortes = self.eventos = None
        self.arquivos, self.info = [], {}

    def executar(self, hoje=None):
        hoje = pd.Timestamp(hoje or date.today()).normalize()
        lido = leitura.le_pasta(self.pasta, self.progresso)
        self.arquivos = lido["arquivos"]
        if lido["atividades"] is None:
            raise ValueError("Nenhum arquivo de atividades encontrado: o nome precisa começar com "
                             f"\"{REGRAS['arquivos']['prefixo_atividades']}\".")
        self.progresso(70, "Classificando as atividades…")
        cat, origem_cat = base.catalogo(lido["catalogo"])
        ativ, duplicadas = base.prepara_atividades(lido["atividades"], cat)
        cad = base.prepara_cadastro(lido["cadastro"])

        self.progresso(80, "Cruzando cortes, religações e pós-corte…")
        self.cortes = base.monta_cortes(ativ, cad, hoje)
        self.progresso(90, "Calculando o saldo de economias…")
        self.eventos = base.monta_saldo(ativ, cad)

        sem_cat = ativ[ativ["categoria"].isna()]
        suspeitos = sem_cat[sem_cat["servico"].fillna("").map(leitura.normaliza).str.contains(SUSPEITOS)]
        nao_class = suspeitos["servico"].value_counts().head(30)
        datas_ok = ativ["data"].dropna()
        self.info = {
            "Data usada na régua (hoje)": hoje.strftime("%d/%m/%Y"),
            "Período das atividades": (f"{datas_ok.min():%d/%m/%Y} a {datas_ok.max():%d/%m/%Y}" if len(datas_ok) else "-"),
            "Atividades lidas": int(len(ativ)),
            "Atividades repetidas entre arquivos (contadas uma vez)": int(duplicadas),
            "Atividades sem data ou matrícula": int((ativ["data"].isna() | ativ["matricula"].isna()).sum()),
            "Catálogo de serviços": origem_cat,
            "Cadastro": (f"{len(cad):,} linhas; referência mais recente {cad['ref'].max():%m/%Y}".replace(",", ".")
                         if cad is not None and cad["ref"].notna().any() else ("sem planilha de cadastro na pasta" if cad is None else f"{len(cad)} linhas")),
            "Cortes (matrícula + data)": int(len(self.cortes)),
            "Cortes sem cadastro": int((self.cortes["situacao"] == REGRAS["textos"]["sem_cadastro"]).sum()),
            "Eventos do saldo sem cadastro (contam 1 economia)": int(self.eventos["sem_cadastro"].sum()),
        }
        self.progresso(97, "Montando o painel…")
        status = ativ[ativ["categoria"].notna()].groupby(["categoria", "status"]).size().reset_index(name="qtd")
        return {
            "cortes": saida.colunar(self.cortes, saida.COLUNAS_CORTES),
            "saldo": saida.saldo_agrupado(self.eventos),
            "status": saida.colunar(status, {c: c for c in status.columns}),
            "arquivos": self.arquivos,
            "info": self.info,
            "nao_classificados": [{"servico": k, "qtd": int(v)} for k, v in nao_class.items()],
            "regras": {k: REGRAS[k] for k in ("regua", "permanencia", "textos", "categorias", "status", "tipos")},
            "hoje": hoje.strftime("%Y-%m-%d"),
        }

    def excel(self):
        return saida.excel(self.cortes, self.eventos, self.arquivos, self.info)
