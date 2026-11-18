# -*- coding: utf-8 -*-
"""Executa tudo: lê a pasta, calcula as bases e devolve o pacote de dados do painel."""
from datetime import date

import pandas as pd

from . import base, cache_arquivos, conferencia, leitura, saida
from .config import REGRAS

CAT = REGRAS["categorias"]
SUSPEITOS = r"CORTE|RELIGA|POS CORTE|IMPLANTACAO DE LIGACAO DE AGUA"


def _info_lisc(ativ, fora_cidade=0, cidades_fora=""):
    """Quanto as planilhas de religação LISC trouxeram (para conferir na aba Dados)."""
    if "fonte" not in ativ or not ativ["fonte"].eq("religacao_lisc").any():
        return {"Planilhas de religação LISC": "nenhuma na pasta" if not fora_cidade else f"todas as {fora_cidade} linhas são de cidades fora das atividades"}
    lisc = ativ[ativ["fonte"].eq("religacao_lisc")]
    religa = lisc["categoria"].eq(CAT["religacao"])
    fin = lisc["status"].eq(REGRAS["status"]["finalizada"]).fillna(False)
    auto = lisc["tipo"].eq("AUTORELIGAÇÃO")
    info = {
        "Religações das planilhas LISC (com Dt. Execução)": int((religa & fin).sum()),
        "… dessas, autoreligações": int((religa & fin & auto).sum()),
        "Linhas das planilhas LISC sem Dt. Execução (não contam)": int((religa & ~fin).sum()),
        "Linhas das planilhas LISC que não são religação (não contam)": int((~religa).sum()),
        "Linhas das planilhas LISC de cidades que não estão nas atividades (não contam)": int(fora_cidade),
    }
    if cidades_fora:
        info["Cidades tiradas das planilhas LISC"] = cidades_fora
    return info


class Analise:
    def __init__(self, pasta, progresso=None):
        self.pasta = pasta
        self.progresso = progresso or (lambda pct, texto: None)
        self.cortes = self.eventos = None
        self.conferencia = None
        self.arquivos, self.info = [], {}

    def procura(self, mat):
        """Todas as linhas lidas de uma matrícula (antes de tirar repetidas), com a classificação e o que o painel fez."""
        mat = base.matricula(pd.Series([mat])).iloc[0]
        bruto = self._bruto
        if mat is None or bruto is None:
            return {"matricula": mat, "linhas": [], "cortes": []}
        sub = bruto[base.matricula(bruto["matricula"]).eq(mat).fillna(False).to_numpy(dtype=bool)].copy()
        orig_mat, orig_data = sub["matricula"].astype(str).tolist(), sub["data"].astype(str).tolist()
        sub["matricula"] = mat
        sub["data"] = base.datas(sub["data"])
        sub["status"] = sub["status"].astype("string").str.strip()
        cls = base.classifica(sub, self._cat)
        usados = set(self._ativ["id"].dropna().astype(str)) if "id" in self._ativ.columns else set()
        linhas = []
        for i, (_, r) in enumerate(cls.iterrows()):
            data = r["data"]
            if pd.isna(data):
                obs = "data não reconhecida — a OS fica de fora"
            elif r["categoria"] is None or pd.isna(r["categoria"]):
                obs = "serviço fora do catálogo (sem categoria) — fica de fora"
            elif pd.notna(r.get("id")) and str(r.get("id")) not in usados:
                obs = "não entrou: mesma OS repetida em outro arquivo (vale a outra cópia) ou fora das cidades"
            else:
                obs = ""
            linhas.append({"arquivo": r.get("arquivo"), "id": None if pd.isna(r.get("id")) else str(r.get("id")),
                           "matricula_lida": orig_mat[i], "data_lida": orig_data[i],
                           "data": None if pd.isna(data) else data.date().isoformat(), "servico": r.get("servico"),
                           "status": None if pd.isna(r["status"]) else str(r["status"]), "categoria": r["categoria"], "obs": obs})
        linhas.sort(key=lambda x: (x["data"] or "", x["arquivo"] or ""))
        cs = self.cortes[self.cortes["matricula"].eq(mat)] if self.cortes is not None else self.cortes
        f = lambda v: None if pd.isna(v) else pd.Timestamp(v).date().isoformat()  # noqa: E731
        cortes = [{"data": f(c["data"]), "data_pos": f(c.get("data_pos")), "status_pos": None if pd.isna(c.get("status_pos")) else c.get("status_pos"),
                   "data_religacao": f(c.get("data_religacao")), "prox_corte": f(c.get("prox_corte")), "regua": c.get("regua")}
                  for _, c in (cs.iterrows() if cs is not None else [])]
        return {"matricula": mat, "linhas": linhas, "cortes": cortes}

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
        # nomes parecidos da mesma cidade (atividades, LISC, cadastro) viram um só — o da lista de Sup
        mapa_cid = base.padroniza_cidades(ativ["cidade"], None if cad is None else cad.get("CIDADE"))
        base.aplica_cidades(ativ, mapa_cid)
        base.aplica_cidades(cad, mapa_cid, "CIDADE")
        ativ, lisc_fora, lisc_cidades_fora = base.filtra_lisc_por_cidade(ativ)
        self._bruto, self._cat, self._ativ = lido["atividades"], cat, ativ      # para procurar uma matrícula depois

        self.progresso(80, "Cruzando cortes, religações e pós-corte…")
        self.cortes = base.monta_cortes(ativ, cad, hoje)
        self.progresso(90, "Calculando o saldo de economias…")
        self.eventos = base.monta_saldo(ativ, cad)
        if lido.get("conferencia") is not None:                 # planilha antiga: compara linha a linha (matrícula + data do corte)
            self.progresso(95, "Conferindo com a planilha de conferência…")
        self.conferencia = conferencia.compara(lido.get("conferencia"), self.cortes, ativ, hoje, cad)
        for df in (self.cortes, self.eventos):
            df["sup"] = base.sup(df["cidade"])
        sem_sup = pd.concat([self.cortes.loc[self.cortes["sup"].eq(REGRAS["supervisao"]["sem_sup"]), "cidade"],
                             self.eventos.loc[self.eventos["sup"].eq(REGRAS["supervisao"]["sem_sup"]), "cidade"]])
        sem_sup = sem_sup.fillna("(sem cidade)").value_counts().head(15)
        juntados = {}
        for orig, novo in mapa_cid.items():
            if orig != novo:
                juntados.setdefault(novo, []).append(orig)

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
            **_info_lisc(ativ, lisc_fora, lisc_cidades_fora),
            "Cidades com nomes diferentes juntadas": "; ".join(f"{n} ← {', '.join(v[:5])}" for n, v in juntados.items())[:600] or "nenhuma",
            "Cidades fora da lista de Sup (ficam em \"" + REGRAS["supervisao"]["sem_sup"] + "\")": ", ".join(f"{n} ({q})" for n, q in sem_sup.items()) or "nenhuma",
            "Arquivos que não puderam ser lidos": sum(1 for a in self.arquivos if a["tipo"] == "erro"),
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
            "eventos": saida.colunar(self.eventos, saida.COLUNAS_EVENTOS),
            "status": saida.colunar(status, {c: c for c in status.columns}),
            "arquivos": self.arquivos,
            "info": self.info,
            "nao_classificados": [{"servico": k, "qtd": int(v)} for k, v in nao_class.items()],
            "regras": {k: REGRAS[k] for k in ("regua", "permanencia", "textos", "categorias", "status", "tipos")},
            "hoje": hoje.strftime("%Y-%m-%d"),
            "cache_invalido": cache_arquivos.invalidos(),
            "conferencia": self.conferencia,
        }

    def excel(self):
        return saida.excel(self.cortes, self.eventos, self.arquivos, self.info)
