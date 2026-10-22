# -*- coding: utf-8 -*-
"""Conferência com a planilha antiga (arquivo com "conferencia" no nome).

Cada linha da planilha (matrícula + data do corte) é procurada na base de cortes do painel e cada campo é comparado:
religação, mês da religação, pós-corte, régua e situação. Para cada diferença o painel diz o motivo — olhando as
atividades lidas (status da OS, próximo corte da matrícula, planilhas LISC, cadastro e a data de hoje usada na régua).
"""
import pandas as pd

from . import base
from .config import REGRAS
from .leitura import normaliza

CAT, ST, TXT, RG = REGRAS["categorias"], REGRAS["status"], REGRAS["textos"], REGRAS["regua"]
LIMITE = 60000                                   # linhas mandadas ao site (o resumo conta todas)
# analítico comparativo: uma linha por corte, cada campo lado a lado (planilha × painel)
CAMPOS_COMP = ["resultado", "matricula", "data", "diferencas", "motivos", "rel_x", "rel_p", "mesrel_x", "mesrel_p", "pos_x", "pos_p",
               "regua_x", "regua_p", "sit_x", "sit_p", "dias_x", "dias_p", "perm_x", "perm_p", "tipo_corte", "cidade", "sit_fonte", "os_corte", "arquivo"]


def _d(v):
    return "" if v is None or pd.isna(v) else pd.Timestamp(v).strftime("%d/%m/%Y")


def _txt(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NaT:
        return ""
    if hasattr(v, "strftime"):                       # datetime do Excel ou Timestamp
        return v.strftime("%d/%m/%Y")
    t = str(v).strip()
    return "" if t.lower() in ("nan", "nat", "none") else t


def _mes_br(v):
    """Mês para o comparativo: '2026-04' ou data do 1º dia -> '04/2026'; textos ficam como estão."""
    t = _txt(v)
    if len(t) == 7 and t[4] == "-":
        return f"{t[5:]}/{t[:4]}"
    if len(t) == 10 and t[2] == "/" and t.startswith("01/"):
        return t[3:]
    return t


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    try:
        return str(int(float(v)))
    except (TypeError, ValueError):
        return _txt(v)


def _data_ou_texto(serie):
    """Coluna que tem data ou um texto ('Sem Religação', 'Sem Pós Corte'): devolve só as datas (texto vira NaT)."""
    return base.datas(serie)


def _regua_padrao(txt):
    """Rótulo da régua da planilha -> rótulo do painel."""
    t = normaliza(txt)
    if not t:
        return ""
    if "RELIGADO APOS" in t:
        return RG["religado_apos_pos"]
    if t.startswith("RELIGADO"):
        return RG["religado"]
    if "REALIZADO" in t:
        return RG["com_pos"]
    fx = RG["faixas"]
    if "- 7" in t or "-7" in t:
        return fx[0]["nome"]
    if "15" in t and ("+ 7" in t or "7 A 15" in t or "7 E" in t):
        return fx[1]["nome"]
    if "+ 15" in t or "+15" in t:
        return fx[2]["nome"]
    return str(txt)


def _mes_txt(v):
    """Mês da religação da planilha (data do 1º dia, 'Ativa' ou 'Sem Religação') no formato do painel."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    t = normaliza(v)
    if t == normaliza(TXT["ativa"]):
        return TXT["ativa"]
    if "SEM RELIG" in t:
        return TXT["sem_religacao"]
    d = base.datas(pd.Series([v])).iloc[0]
    return d.strftime("%Y-%m") if pd.notna(d) else str(v)


def compara(conf, cortes, ativ, hoje):
    """Devolve o pacote da conferência para o site: resumo por tipo de diferença e as linhas com o motivo."""
    if conf is None or conf.empty:
        return None
    arquivo = conf["arquivo"].iloc[0] if "arquivo" in conf.columns else ""
    aba = conf["aba"].iloc[0] if "aba" in conf.columns else ""
    df = conf.copy()
    df["matricula"] = base.matricula(df["matricula"])
    df["data"] = base.datas(df["data"])
    df = df.dropna(subset=["matricula", "data"])
    total = len(df)
    df = df.drop_duplicates(subset=["matricula", "data"])
    duplicadas = total - len(df)

    painel = {(c["matricula"], c["data"]): c for c in cortes.to_dict("records")}
    arq_por_id = dict(zip(ativ["id"].astype(str), ativ["arquivo"])) if "arquivo" in ativ.columns else {}
    por_mat = {m: g for m, g in ativ[ativ["matricula"].notna()].groupby("matricula")}
    cortes_por_mat = {m: g for m, g in cortes.groupby("matricula")}

    def arquivo_os(os_id):
        if os_id is None or pd.isna(os_id):
            return ""
        a = arq_por_id.get(str(os_id))
        return f" (OS {os_id}, arquivo {a})" if a else f" (OS {os_id})"

    def por_que_nao(mat, dia, categoria, aceitos, c, campo):
        """Por que a OS (religação/pós) da planilha naquele dia não foi usada pelo painel."""
        g = por_mat.get(mat)
        if g is None:
            return "matrícula não aparece nas atividades lidas"
        no_dia = g[g["data"] == dia]
        if no_dia.empty:
            return f"não há OS de {categoria.lower()} dessa matrícula em {_d(dia)} nos arquivos lidos"
        da_cat = no_dia[no_dia["categoria"] == categoria]
        if da_cat.empty:
            servs = ", ".join(sorted(set(no_dia["servico"].astype(str)))[:2])
            return f"a OS de {_d(dia)} ({servs}) não está classificada como {categoria} no catálogo"
        if not da_cat["status"].isin(aceitos).any():
            return f"a OS de {categoria.lower()} de {_d(dia)} está com status “{da_cat['status'].iloc[0]}” (só {' ou '.join(aceitos)} conta)"
        prox = c.get("prox_corte")
        if prox is not None and pd.notna(prox) and (dia > prox if campo == "data_religacao" else dia >= prox):
            return f"a OS de {_d(dia)} é depois do próximo corte da matrícula ({_d(prox)}): no painel ela fica com o corte seguinte"
        outros = cortes_por_mat.get(mat)
        if outros is not None and campo in outros and (outros[campo] == dia).any():
            return f"a OS de {_d(dia)} já está ligada a outro corte da matrícula (cada OS vale para um corte só)"
        return f"a OS de {_d(dia)} está nos arquivos, mas não foi a 1ª depois do corte"

    linhas, cont, comp, atual = [], {}, [], {"difs": [], "motivos": []}

    def add(tipo, mat, dia, campo, v_excel, v_painel, motivo, c=None):
        cont[tipo] = cont.get(tipo, 0) + 1
        atual["difs"].append(campo if campo != "corte" else tipo)
        atual["motivos"].append(f"{campo if campo != 'corte' else tipo}: {motivo}")
        if len(linhas) < LIMITE:
            linhas.append({"tipo": tipo, "matricula": mat, "data": dia.strftime("%Y-%m-%d"), "campo": campo,
                           "excel": _txt(v_excel), "painel": _txt(v_painel), "motivo": motivo,
                           "cidade": (c or {}).get("cidade"), "tipo_corte": (c or {}).get("tipo")})

    sem_rel, sem_pos = TXT["sem_religacao"], TXT["sem_pos"]

    def linha_comp(resultado, mat, dia, r=None, c=None):
        x = (lambda k: getattr(r, k, None)) if r is not None else (lambda k: None)
        c = c or {}
        p_rel, p_pos = c.get("data_religacao"), c.get("data_pos")
        if len(comp) < LIMITE:
            comp.append({
                "resultado": resultado, "matricula": mat, "data": dia.strftime("%Y-%m-%d"),
                "diferencas": ", ".join(atual["difs"]), "motivos": " | ".join(atual["motivos"]),
                "rel_x": _txt(x("data_religacao")), "rel_p": (_d(p_rel) or sem_rel) if c else "",
                "mesrel_x": _mes_br(x("mes_religacao")), "mesrel_p": _mes_br(c.get("mes_religacao")) if c else "",
                "pos_x": _txt(x("data_pos")), "pos_p": (_d(p_pos) or sem_pos) if c else "",
                "regua_x": _txt(x("regua")), "regua_p": _txt(c.get("regua")),
                "sit_x": _txt(x("situacao")), "sit_p": _txt(c.get("situacao")),
                "dias_x": _num(x("dias")), "dias_p": (_num(c.get("dias")) or sem_rel) if c else "",
                "perm_x": _txt(x("permanencia")), "perm_p": _txt(c.get("permanencia")),
                "tipo_corte": _txt(c.get("tipo")) or _txt(x("descricao")), "cidade": _txt(c.get("cidade")),
                "sit_fonte": _txt(c.get("situacao_fonte")), "os_corte": _txt(c.get("id")), "arquivo": _txt(c.get("arquivo")),
            })

    for r in df.itertuples(index=False):
        mat, dia = r.matricula, r.data
        atual["difs"], atual["motivos"] = [], []
        c = painel.get((mat, dia))
        if c is None:
            g = por_mat.get(mat)
            outros = cortes_por_mat.get(mat)
            if g is None:
                motivo = "a matrícula não aparece nos arquivos de atividades lidos (falta o arquivo desse período na pasta?)"
            else:
                no_dia = g[g["data"] == dia]
                corte_dia = no_dia[no_dia["categoria"] == CAT["corte"]]
                if not corte_dia.empty and not corte_dia["status"].eq(ST["finalizada"]).any():
                    motivo = f"a OS de corte de {_d(dia)} está com status “{corte_dia['status'].iloc[0]}” (só {ST['finalizada']} conta)"
                elif not no_dia.empty and corte_dia.empty:
                    servs = ", ".join(sorted(set(no_dia["servico"].astype(str)))[:2])
                    motivo = f"a OS de {_d(dia)} ({servs}) não está classificada como corte no catálogo"
                elif outros is not None:
                    perto = outros.iloc[(outros["data"] - dia).abs().argsort()[:1]]["data"].iloc[0]
                    motivo = f"no painel os cortes desta matrícula estão em outras datas (o mais perto: {_d(perto)})"
                else:
                    motivo = "não há OS de corte Finalizada desta matrícula nos arquivos lidos"
            add("Corte não encontrado no painel", mat, dia, "corte", _d(dia), "", motivo)
            linha_comp("Corte não encontrado no painel", mat, dia, r)
            continue

        dif = False
        # religação
        x_rel = _data_ou_texto(pd.Series([getattr(r, "data_religacao", None)])).iloc[0]
        p_rel = c.get("data_religacao")
        p_rel = None if p_rel is None or pd.isna(p_rel) else pd.Timestamp(p_rel)
        x_rel = None if pd.isna(x_rel) else pd.Timestamp(x_rel)
        if x_rel != p_rel:
            dif = True
            if x_rel is not None and p_rel is None:
                motivo = por_que_nao(mat, x_rel, CAT["religacao"], [ST["finalizada"]], c, "data_religacao")
            elif x_rel is None:
                motivo = f"o painel achou a religação de {_d(p_rel)}{arquivo_os(c.get('id_religacao'))}, que a planilha não tem"
            elif p_rel < x_rel:
                motivo = f"o painel achou uma religação anterior, em {_d(p_rel)}{arquivo_os(c.get('id_religacao'))}, que a planilha não tem"
            else:
                motivo = por_que_nao(mat, x_rel, CAT["religacao"], [ST["finalizada"]], c, "data_religacao") + f"; o painel usou a de {_d(p_rel)}"
            add("Religação diferente", mat, dia, "Data Religação", _d(x_rel) or sem_rel, _d(p_rel) or sem_rel, motivo, c)
        else:
            x_mes = _mes_txt(getattr(r, "mes_religacao", None))
            p_mes = c.get("mes_religacao") or ""
            if x_mes and p_mes and x_mes != p_mes:
                dif = True
                if x_mes == TXT["ativa"] and pd.notna(c.get("prox_corte")):
                    motivo = f"a planilha marca Ativa pela situação do cadastro em qualquer corte; o painel só no último corte da matrícula (este teve outro corte em {_d(c.get('prox_corte'))})"
                elif TXT["ativa"] in (x_mes, p_mes):
                    motivo = f"a situação no cadastro é diferente (planilha: {_txt(getattr(r, 'situacao', ''))}; painel: {c.get('situacao')} — {c.get('situacao_fonte') or 'cadastro'})"
                else:
                    motivo = "mês calculado de forma diferente"
                add("Mês da religação diferente", mat, dia, "Mês Religação", x_mes, p_mes, motivo, c)
        # pós-corte
        x_pos = _data_ou_texto(pd.Series([getattr(r, "data_pos", None)])).iloc[0]
        p_pos = c.get("data_pos")
        p_pos = None if p_pos is None or pd.isna(p_pos) else pd.Timestamp(p_pos)
        x_pos = None if pd.isna(x_pos) else pd.Timestamp(x_pos)
        if x_pos != p_pos:
            dif = True
            if x_pos is not None and p_pos is None:
                motivo = por_que_nao(mat, x_pos, CAT["pos_corte"], ST["pos_corte_aceitos"], c, "data_pos")
            elif x_pos is None:
                motivo = f"o painel achou a vistoria pós-corte de {_d(p_pos)}{arquivo_os(c.get('id_pos'))} (status {c.get('status_pos')}), que a planilha não tem"
            elif p_pos < x_pos:
                motivo = f"o painel achou uma vistoria anterior, em {_d(p_pos)}{arquivo_os(c.get('id_pos'))} (status {c.get('status_pos')})"
            else:
                motivo = por_que_nao(mat, x_pos, CAT["pos_corte"], ST["pos_corte_aceitos"], c, "data_pos") + f"; o painel usou a de {_d(p_pos)}"
            add("Pós-corte diferente", mat, dia, "Data Pós Corte", _d(x_pos) or sem_pos, _d(p_pos) or sem_pos, motivo, c)
        # régua (só quando religação e pós batem: senão a diferença vem deles)
        x_reg = _regua_padrao(getattr(r, "regua", ""))
        p_reg = c.get("regua") or ""
        if x_rel == p_rel and x_pos == p_pos and x_reg and p_reg and x_reg != p_reg:
            dif = True
            faixas = [f["nome"] for f in RG["faixas"]]
            if x_reg in faixas and p_reg in faixas:
                dc = c.get("dias_cortado")
                motivo = (f"a régua conta os dias cortado até hoje: no painel {int(dc) if pd.notna(dc) else '?'} dias em {_d(hoje)}; "
                          "a planilha foi calculada em outro dia (e a fórmula dela não tem a faixa de exatamente 7 dias)")
                add("Régua diferente (dias até hoje)", mat, dia, "Regua de Cobrança", getattr(r, "regua", ""), p_reg, motivo, c)
            else:
                add("Régua diferente", mat, dia, "Regua de Cobrança", getattr(r, "regua", ""), p_reg, "classificação diferente com as mesmas datas", c)
        # situação
        x_sit = normaliza(getattr(r, "situacao", "") or "")
        p_sit = normaliza(c.get("situacao") or "")
        if x_sit and p_sit and x_sit != p_sit and x_sit not in ("#N/A", "#N/D", "NAN"):
            dif = True
            fonte = c.get("situacao_fonte") or ""
            if fonte.startswith("calculada"):
                motivo = "no painel a situação foi calculada (o cadastro da pasta é de mês anterior ao corte): ATIVA se religou, senão CORTADA"
            elif p_sit == normaliza(TXT["sem_cadastro"]):
                motivo = "a matrícula não está na planilha de cadastro da pasta"
            else:
                motivo = "o cadastro da pasta (referência mais recente) tem outra situação que a Base da planilha"
            add("Situação diferente", mat, dia, "Situação", getattr(r, "situacao", ""), c.get("situacao"), motivo, c)
        if not dif:
            cont["Bate em tudo"] = cont.get("Bate em tudo", 0) + 1
        linha_comp("Diferente" if dif else "Bate em tudo", mat, dia, r, c)

    # cortes do painel que a planilha não tem (no mesmo período da planilha)
    ini, fim = df["data"].min(), df["data"].max()
    chaves = set(zip(df["matricula"], df["data"]))
    so_painel = cortes[(cortes["data"] >= ini) & (cortes["data"] <= fim)]
    so_painel = so_painel[[k not in chaves for k in zip(so_painel["matricula"], so_painel["data"])]]
    for c in so_painel.to_dict("records"):
        atual["difs"], atual["motivos"] = [], []
        add("Corte só no painel", c["matricula"], c["data"], "corte", "", _d(c["data"]),
            f"OS de corte Finalizada{arquivo_os(c.get('id'))} que não está na planilha (a Base dela pode ter sido extraída antes ou com outro filtro)", c)
        linha_comp("Corte só no painel", c["matricula"], c["data"], None, c)

    ordem = ["Bate em tudo", "Corte não encontrado no painel", "Corte só no painel", "Religação diferente", "Mês da religação diferente",
             "Pós-corte diferente", "Régua diferente (dias até hoje)", "Régua diferente", "Situação diferente"]
    resumo = [{"tipo": t, "qtd": int(cont[t])} for t in ordem if cont.get(t)]
    return {
        "arquivo": arquivo, "aba": aba, "linhas_planilha": int(total), "duplicadas": int(duplicadas),
        "periodo": f"{_d(ini)} a {_d(fim)}", "comparadas": int(len(df)), "resumo": resumo,
        "linhas": {k: [l[k] for l in linhas] for k in ("tipo", "matricula", "data", "campo", "excel", "painel", "motivo", "cidade", "tipo_corte")},
        "cortadas": len(linhas) < sum(cont.values()) - cont.get("Bate em tudo", 0),
        "comparativo": {k: [l[k] for l in comp] for k in CAMPOS_COMP},
    }
