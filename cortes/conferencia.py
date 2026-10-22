# -*- coding: utf-8 -*-
"""Conferência com a planilha antiga (arquivo com "conferencia" no nome).

Cada linha da planilha (matrícula + data do corte) é procurada na base de cortes do painel e cada campo é comparado:
religação, mês da religação, pós-corte, régua e situação. Para cada diferença o painel diz o motivo — olhando as
atividades lidas (status da OS, próximo corte da matrícula, planilhas LISC, cadastro e a data de hoje usada na régua).

Desempenho: no navegador o Python é várias vezes mais lento, então nada de pandas dentro do laço por linha. As datas
viram números (dias desde 1970) uma vez por coluna, as OS de cada matrícula viram listas simples e os textos repetidos
(régua, situação, mês) são convertidos uma vez por valor diferente.
"""
import datetime as _dt
from functools import lru_cache

import pandas as pd

from . import base
from .config import REGRAS
from .leitura import normaliza

CAT, ST, TXT, RG = REGRAS["categorias"], REGRAS["status"], REGRAS["textos"], REGRAS["regua"]
LIMITE = 60000                                   # linhas mandadas ao site (o resumo conta todas)
# analítico comparativo: uma linha por corte, cada campo lado a lado (planilha × painel)
CAMPOS_COMP = ["resultado", "matricula", "data", "diferencas", "motivos", "rel_x", "rel_p", "mesrel_x", "mesrel_p", "pos_x", "pos_p",
               "regua_x", "regua_p", "sit_x", "sit_p", "dias_x", "dias_p", "perm_x", "perm_p", "tipo_corte", "cidade", "sit_fonte", "os_corte", "arquivo",
               # diagnóstico: o que há nos arquivos para entender por que conta ou não conta
               "na_atividade", "os_no_dia", "corte_anterior", "proximo_corte", "religacoes_arq", "vistorias_arq",
               "cad_sit", "cad_ref", "economias", "dias_cortado", "conta_saldo", "conta_pos", "por_que_pos", "arquivos_mat"]
MAX_OS = 6                                       # OS listadas por célula no diagnóstico
_EPOCA = _dt.date(1970, 1, 1)


# ===== conversões rápidas =====
def _dias(serie):
    """Coluna de datas -> lista de inteiros (dias desde 1970) ou None."""
    s = pd.to_datetime(serie, errors="coerce")
    v = s.to_numpy(dtype="datetime64[D]").astype("int64")
    vazio = s.isna().to_numpy()
    return [None if n else int(x) for x, n in zip(v.tolist(), vazio.tolist())]


@lru_cache(maxsize=None)
def _fd(d):
    """Dias desde 1970 -> 'dd/mm/aaaa'."""
    return "" if d is None else (_EPOCA + _dt.timedelta(days=d)).strftime("%d/%m/%Y")


@lru_cache(maxsize=None)
def _norm(t):
    return normaliza(t)


def _txt(v):
    if v is None or (isinstance(v, float) and v != v) or v is pd.NaT:
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
    if v is None or (isinstance(v, float) and v != v):
        return ""
    try:
        return str(int(float(v)))
    except (TypeError, ValueError):
        return _txt(v)


def _lista(serie):
    return [None if (v is None or (isinstance(v, float) and v != v) or v is pd.NaT) else v for v in serie.tolist()]


@lru_cache(maxsize=None)
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


def _mes_txt_serie(serie):
    """Mês da religação da planilha (data do 1º dia, 'Ativa' ou 'Sem Religação') no formato do painel — por valor distinto."""
    texto = serie.map(_txt)
    datas = base.datas(texto)
    saida = []
    ativa, sem = _norm(TXT["ativa"]), TXT["sem_religacao"]
    for t, d in zip(texto.tolist(), datas.tolist()):
        if not t:
            saida.append("")
        elif _norm(t) == ativa:
            saida.append(TXT["ativa"])
        elif "SEM RELIG" in _norm(t):
            saida.append(sem)
        elif d is not pd.NaT and d == d:
            saida.append(d.strftime("%Y-%m"))
        else:
            saida.append(t)
    return saida


def compara(conf, cortes, ativ, hoje, cad=None):
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
    df = df.drop_duplicates(subset=["matricula", "data"]).reset_index(drop=True)
    duplicadas = total - len(df)
    for col in ("data_religacao", "mes_religacao", "data_pos", "regua", "situacao", "dias", "permanencia", "descricao"):
        if col not in df.columns:
            df[col] = None

    # --- planilha: colunas convertidas uma vez ---
    x_mat = df["matricula"].tolist()
    x_dia = _dias(df["data"])
    x_rel = _dias(base.datas(df["data_religacao"].map(_txt)))
    x_pos = _dias(base.datas(df["data_pos"].map(_txt)))
    x_mes = _mes_txt_serie(df["mes_religacao"])
    x_reg_raw = [_txt(v) for v in df["regua"].tolist()]
    x_reg = [_regua_padrao(t) for t in x_reg_raw]
    x_sit_raw = [_txt(v) for v in df["situacao"].tolist()]
    x_rel_raw = [_txt(v) for v in df["data_religacao"].tolist()]
    x_pos_raw = [_txt(v) for v in df["data_pos"].tolist()]
    x_mes_raw = [_mes_br(v) for v in df["mes_religacao"].tolist()]
    x_dias_raw = [_num(v) for v in df["dias"].tolist()]
    x_perm_raw = [_txt(v) for v in df["permanencia"].tolist()]
    x_desc = [_txt(v) for v in df["descricao"].tolist()]
    mats = set(x_mat)

    # --- painel: cortes como dicionários, com as datas em dias ---
    pc = cortes.copy()
    for col, novo in (("data", "_d"), ("data_religacao", "_rel"), ("data_pos", "_pos"), ("prox_corte", "_prox")):
        pc[novo] = _dias(pc[col]) if col in pc.columns else None
    usar = [c for c in ("matricula", "_d", "_rel", "_pos", "_prox", "id", "id_religacao", "id_pos", "status_pos", "regua", "situacao",
                        "situacao_fonte", "mes_religacao", "dias", "permanencia", "tipo", "cidade", "arquivo", "dias_cortado") if c in pc.columns]
    registros = pc[usar].astype(object).where(pc[usar].notna(), None).to_dict("records")
    painel = {(c["matricula"], c["_d"]): c for c in registros}
    cortes_por_mat = {}
    for c in registros:
        cortes_por_mat.setdefault(c["matricula"], []).append(c)

    # --- atividades: só das matrículas que interessam, como listas (data, serviço, status, categoria, arquivo) ---
    ini, fim = min(x_dia), max(x_dia)
    mats_todas = mats | {c["matricula"] for c in registros if ini <= c["_d"] <= fim}
    sub = ativ[ativ["matricula"].isin(mats_todas)]
    sub = sub.sort_values(["matricula", "data"], kind="stable")
    por_mat = {}
    arq_por_id = {}
    sub_arq = sub["arquivo"].astype(str).tolist() if "arquivo" in sub.columns else [""] * len(sub)
    for m, d, sv, stt, ct, ar, i in zip(sub["matricula"].tolist(), _dias(sub["data"]), sub["servico"].astype(str).tolist(),
                                         _lista(sub["status"]), _lista(sub["categoria"]), sub_arq, sub["id"].astype(str).tolist()):
        por_mat.setdefault(m, []).append((d, sv, stt, ct, ar))
        arq_por_id[i] = ar

    # --- cadastro: última referência de cada matrícula ---
    cad_info = {}
    ult = base.ultimo_cadastro(cad) if cad is not None else None
    if ult is not None:
        u = ult[ult.index.isin(mats_todas)]
        refs = u["ref"].dt.strftime("%m/%Y").fillna("") if "ref" in u.columns else pd.Series("", index=u.index)
        for m, sit, ref, eco in zip(u.index.tolist(), u["SIT_LIG"].tolist(), refs.tolist(), u["economias"].tolist()):
            cad_info[m] = (_txt(sit), ref, _num(eco))

    def arquivo_os(os_id):
        if os_id is None:
            return ""
        a = arq_por_id.get(str(os_id))
        return f" (OS {os_id}, arquivo {a})" if a else f" (OS {os_id})"

    def por_que_nao(mat, dia, categoria, aceitos, c, campo):
        """Por que a OS (religação/pós) da planilha naquele dia não foi usada pelo painel."""
        g = por_mat.get(mat)
        if g is None:
            return "matrícula não aparece nas atividades lidas"
        no_dia = [o for o in g if o[0] == dia]
        if not no_dia:
            return f"não há OS de {categoria.lower()} dessa matrícula em {_fd(dia)} nos arquivos lidos"
        da_cat = [o for o in no_dia if o[3] == categoria]
        if not da_cat:
            servs = ", ".join(sorted({o[1] for o in no_dia})[:2])
            return f"a OS de {_fd(dia)} ({servs}) não está classificada como {categoria} no catálogo"
        if not any(o[2] in aceitos for o in da_cat):
            return f"a OS de {categoria.lower()} de {_fd(dia)} está com status “{da_cat[0][2]}” (só {' ou '.join(aceitos)} conta)"
        prox = c.get("_prox")
        if prox is not None and (dia > prox if campo == "_rel" else dia >= prox):
            return f"a OS de {_fd(dia)} é depois do próximo corte da matrícula ({_fd(prox)}): no painel ela fica com o corte seguinte"
        if any(o.get(campo) == dia for o in cortes_por_mat.get(mat, [])):
            return f"a OS de {_fd(dia)} já está ligada a outro corte da matrícula (cada OS vale para um corte só)"
        return f"a OS de {_fd(dia)} está nos arquivos, mas não foi a 1ª depois do corte"

    def lista_os(g, categoria, desde, ate=None):
        """'dd/mm/aaaa serviço (status) [arquivo]' das OS da matrícula, em ordem de data."""
        if g is None:
            return ""
        h = [o for o in g if o[0] is not None and o[0] >= desde and (ate is None or o[0] <= ate) and (categoria is None or o[3] == categoria)]
        itens = [f"{_fd(o[0])} {o[1][:60]} ({o[2] or 'sem status'}) [{o[4]}]" for o in h[:MAX_OS]]
        return " ; ".join(itens) + (f" ; … +{len(h) - MAX_OS}" if len(h) > MAX_OS else "")

    def diagnostico(mat, dia, c):
        g = por_mat.get(mat)
        outros = cortes_por_mat.get(mat, [])
        antes = [o["_d"] for o in outros if o["_d"] < dia]
        depois = [o["_d"] for o in outros if o["_d"] > dia]
        d = {
            "na_atividade": "Sim" if g is not None else "Não",
            "os_no_dia": lista_os(g, None, dia, dia),
            "corte_anterior": _fd(max(antes)) if antes else "", "proximo_corte": _fd(min(depois)) if depois else "",
            "religacoes_arq": lista_os(g, CAT["religacao"], dia),
            "vistorias_arq": lista_os(g, CAT["pos_corte"], dia),
            "arquivos_mat": ", ".join(sorted({o[4] for o in g})[:5]) if g is not None else "",
        }
        if mat in cad_info:
            d["cad_sit"], d["cad_ref"], d["economias"] = cad_info[mat]
        else:
            d.update(cad_sit="fora do cadastro" if cad is not None else "sem cadastro na pasta", cad_ref="", economias="")
        if c:
            d["dias_cortado"] = _num(c.get("dias_cortado"))
            d["conta_saldo"] = "Sim (corte Finalizado)"
            motivos = []
            if c.get("_pos") is not None:
                motivos.append(f"teve pós-corte em {_fd(c['_pos'])}")
            if c.get("_rel") is not None:
                motivos.append(f"religou em {_fd(c['_rel'])}")
            if _norm(c.get("situacao") or "") != "CORTADA":
                motivos.append(f"situação {c.get('situacao')}" + (f" ({c.get('situacao_fonte')})" if c.get("situacao_fonte") else ""))
            d["conta_pos"] = "Não" if motivos else "Sim"
            d["por_que_pos"] = "; ".join(motivos) if motivos else "sem pós-corte, sem religação e CORTADA"
        else:
            d.update(dias_cortado="", conta_saldo="Não (não virou corte no painel)", conta_pos="Não", por_que_pos="não virou corte no painel")
        return d

    linhas, cont, comp, atual = [], {}, [], {"difs": [], "motivos": []}
    sem_rel, sem_pos = TXT["sem_religacao"], TXT["sem_pos"]

    def add(tipo, mat, dia, campo, v_excel, v_painel, motivo, c=None):
        cont[tipo] = cont.get(tipo, 0) + 1
        rot = campo if campo != "corte" else tipo
        atual["difs"].append(rot)
        atual["motivos"].append(f"{rot}: {motivo}")
        if len(linhas) < LIMITE:
            linhas.append({"tipo": tipo, "matricula": mat, "data": (_EPOCA + _dt.timedelta(days=dia)).isoformat(),
                           "campo": campo, "excel": _txt(v_excel), "painel": _txt(v_painel), "motivo": motivo,
                           "cidade": (c or {}).get("cidade"), "tipo_corte": (c or {}).get("tipo")})

    def linha_comp(resultado, mat, dia, i=None, c=None):
        if len(comp) >= LIMITE:
            return
        c = c or {}
        tem = bool(c)
        comp.append({
            "resultado": resultado, "matricula": mat, "data": (_EPOCA + _dt.timedelta(days=dia)).isoformat(),
            "diferencas": ", ".join(atual["difs"]), "motivos": " | ".join(atual["motivos"]),
            "rel_x": x_rel_raw[i] if i is not None else "", "rel_p": (_fd(c.get("_rel")) or sem_rel) if tem else "",
            "mesrel_x": x_mes_raw[i] if i is not None else "", "mesrel_p": _mes_br(c.get("mes_religacao")) if tem else "",
            "pos_x": x_pos_raw[i] if i is not None else "", "pos_p": (_fd(c.get("_pos")) or sem_pos) if tem else "",
            "regua_x": x_reg_raw[i] if i is not None else "", "regua_p": _txt(c.get("regua")),
            "sit_x": x_sit_raw[i] if i is not None else "", "sit_p": _txt(c.get("situacao")),
            "dias_x": x_dias_raw[i] if i is not None else "", "dias_p": (_num(c.get("dias")) or sem_rel) if tem else "",
            "perm_x": x_perm_raw[i] if i is not None else "", "perm_p": _txt(c.get("permanencia")),
            "tipo_corte": _txt(c.get("tipo")) or (x_desc[i] if i is not None else ""), "cidade": _txt(c.get("cidade")),
            "sit_fonte": _txt(c.get("situacao_fonte")), "os_corte": _txt(c.get("id")), "arquivo": _txt(c.get("arquivo")),
            **diagnostico(mat, dia, c),
        })

    ativa_txt, sem_cad = TXT["ativa"], _norm(TXT["sem_cadastro"])
    faixas = [f["nome"] for f in RG["faixas"]]
    for i, (mat, dia) in enumerate(zip(x_mat, x_dia)):
        atual["difs"], atual["motivos"] = [], []
        c = painel.get((mat, dia))
        if c is None:
            g = por_mat.get(mat)
            outros = cortes_por_mat.get(mat)
            if g is None:
                motivo = "a matrícula não aparece nos arquivos de atividades lidos (falta o arquivo desse período na pasta?)"
            else:
                no_dia = [o for o in g if o[0] == dia]
                corte_dia = [o for o in no_dia if o[3] == CAT["corte"]]
                if corte_dia and not any(o[2] == ST["finalizada"] for o in corte_dia):
                    motivo = f"a OS de corte de {_fd(dia)} está com status “{corte_dia[0][2]}” (só {ST['finalizada']} conta)"
                elif no_dia and not corte_dia:
                    servs = ", ".join(sorted({o[1] for o in no_dia})[:2])
                    motivo = f"a OS de {_fd(dia)} ({servs}) não está classificada como corte no catálogo"
                elif outros:
                    perto = min((o["_d"] for o in outros), key=lambda d: abs(d - dia))
                    motivo = f"no painel os cortes desta matrícula estão em outras datas (o mais perto: {_fd(perto)})"
                else:
                    motivo = "não há OS de corte Finalizada desta matrícula nos arquivos lidos"
            add("Corte não encontrado no painel", mat, dia, "corte", _fd(dia), "", motivo)
            linha_comp("Corte não encontrado no painel", mat, dia, i)
            continue

        dif = False
        # religação
        xr, pr = x_rel[i], c.get("_rel")
        if xr != pr:
            dif = True
            if xr is not None and pr is None:
                motivo = por_que_nao(mat, xr, CAT["religacao"], [ST["finalizada"]], c, "_rel")
            elif xr is None:
                motivo = f"o painel achou a religação de {_fd(pr)}{arquivo_os(c.get('id_religacao'))}, que a planilha não tem"
            elif pr < xr:
                motivo = f"o painel achou uma religação anterior, em {_fd(pr)}{arquivo_os(c.get('id_religacao'))}, que a planilha não tem"
            else:
                motivo = por_que_nao(mat, xr, CAT["religacao"], [ST["finalizada"]], c, "_rel") + f"; o painel usou a de {_fd(pr)}"
            add("Religação diferente", mat, dia, "Data Religação", _fd(xr) or sem_rel, _fd(pr) or sem_rel, motivo, c)
        else:
            xm, pm = x_mes[i], c.get("mes_religacao") or ""
            if xm and pm and xm != pm:
                dif = True
                if xm == ativa_txt and c.get("_prox") is not None:
                    motivo = f"a planilha marca Ativa pela situação do cadastro em qualquer corte; o painel só no último corte da matrícula (este teve outro corte em {_fd(c['_prox'])})"
                elif ativa_txt in (xm, pm):
                    motivo = f"a situação no cadastro é diferente (planilha: {x_sit_raw[i]}; painel: {c.get('situacao')} — {c.get('situacao_fonte') or 'cadastro'})"
                else:
                    motivo = "mês calculado de forma diferente"
                add("Mês da religação diferente", mat, dia, "Mês Religação", xm, pm, motivo, c)
        # pós-corte
        xp, pp = x_pos[i], c.get("_pos")
        if xp != pp:
            dif = True
            if xp is not None and pp is None:
                motivo = por_que_nao(mat, xp, CAT["pos_corte"], ST["pos_corte_aceitos"], c, "_pos")
            elif xp is None:
                motivo = f"o painel achou a vistoria pós-corte de {_fd(pp)}{arquivo_os(c.get('id_pos'))} (status {c.get('status_pos')}), que a planilha não tem"
            elif pp < xp:
                motivo = f"o painel achou uma vistoria anterior, em {_fd(pp)}{arquivo_os(c.get('id_pos'))} (status {c.get('status_pos')})"
            else:
                motivo = por_que_nao(mat, xp, CAT["pos_corte"], ST["pos_corte_aceitos"], c, "_pos") + f"; o painel usou a de {_fd(pp)}"
            add("Pós-corte diferente", mat, dia, "Data Pós Corte", _fd(xp) or sem_pos, _fd(pp) or sem_pos, motivo, c)
        # régua (só quando religação e pós batem: senão a diferença vem deles)
        xg, pg = x_reg[i], c.get("regua") or ""
        if xr == pr and xp == pp and xg and pg and xg != pg:
            dif = True
            if xg in faixas and pg in faixas:
                dc = c.get("dias_cortado")
                motivo = (f"a régua conta os dias cortado até hoje: no painel {_num(dc) or '?'} dias em {hoje.strftime('%d/%m/%Y')}; "
                          "a planilha foi calculada em outro dia (e a fórmula dela não tem a faixa de exatamente 7 dias)")
                add("Régua diferente (dias até hoje)", mat, dia, "Regua de Cobrança", x_reg_raw[i], pg, motivo, c)
            else:
                add("Régua diferente", mat, dia, "Regua de Cobrança", x_reg_raw[i], pg, "classificação diferente com as mesmas datas", c)
        # situação
        xs, ps = _norm(x_sit_raw[i]), _norm(c.get("situacao") or "")
        if xs and ps and xs != ps and xs not in ("#N/A", "#N/D", "NAN"):
            dif = True
            fonte = c.get("situacao_fonte") or ""
            if fonte.startswith("calculada"):
                motivo = "no painel a situação foi calculada (o cadastro da pasta é de mês anterior ao corte): ATIVA se religou, senão CORTADA"
            elif ps == sem_cad:
                motivo = "a matrícula não está na planilha de cadastro da pasta"
            else:
                motivo = "o cadastro da pasta (referência mais recente) tem outra situação que a Base da planilha"
            add("Situação diferente", mat, dia, "Situação", x_sit_raw[i], c.get("situacao"), motivo, c)
        if not dif:
            cont["Bate em tudo"] = cont.get("Bate em tudo", 0) + 1
        linha_comp("Diferente" if dif else "Bate em tudo", mat, dia, i, c)

    # cortes do painel que a planilha não tem (no mesmo período da planilha)
    chaves = set(zip(x_mat, x_dia))
    for c in registros:
        if ini <= c["_d"] <= fim and (c["matricula"], c["_d"]) not in chaves:
            atual["difs"], atual["motivos"] = [], []
            add("Corte só no painel", c["matricula"], c["_d"], "corte", "", _fd(c["_d"]),
                f"OS de corte Finalizada{arquivo_os(c.get('id'))} que não está na planilha (a Base dela pode ter sido extraída antes ou com outro filtro)", c)
            linha_comp("Corte só no painel", c["matricula"], c["_d"], None, c)

    ordem = ["Bate em tudo", "Corte não encontrado no painel", "Corte só no painel", "Religação diferente", "Mês da religação diferente",
             "Pós-corte diferente", "Régua diferente (dias até hoje)", "Régua diferente", "Situação diferente"]
    resumo = [{"tipo": t, "qtd": int(cont[t])} for t in ordem if cont.get(t)]
    return {
        "arquivo": arquivo, "aba": aba, "linhas_planilha": int(total), "duplicadas": int(duplicadas),
        "periodo": f"{_fd(ini)} a {_fd(fim)}", "comparadas": int(len(df)), "resumo": resumo,
        "linhas": {k: [l[k] for l in linhas] for k in ("tipo", "matricula", "data", "campo", "excel", "painel", "motivo", "cidade", "tipo_corte")},
        "cortadas": len(linhas) < sum(cont.values()) - cont.get("Bate em tudo", 0),
        "comparativo": {k: [l[k] for l in comp] for k in CAMPOS_COMP},
    }
