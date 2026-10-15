# -*- coding: utf-8 -*-
"""Cálculos: classifica as atividades, monta a base de cortes e o saldo de economias.

Base de cortes — uma linha por corte (matrícula + data), só OS Finalizadas:
  - religação: a 1ª religação Finalizada no dia do corte ou depois, e antes do próximo corte da mesma matrícula;
  - pós-corte: a 1ª vistoria pós-corte (Finalizada ou Encerrada com Ocorrência) na mesma janela;
    se essa 1ª visita foi Encerrada com Ocorrência, a observação diz que foi sem sucesso;
  - régua: religado (antes/depois do pós-corte), realizado pós-corte ou, sem nenhum dos dois,
    a faixa de dias cortado contada até hoje;
  - permanência: dias entre o corte e a religação, em faixas;
  - situação: SIT_LIG do cadastro (referência mais recente da matrícula).
"""
import re
from datetime import date

import numpy as np
import pandas as pd

from .config import CATALOGO_PADRAO, REGRAS
from .leitura import normaliza

CAT = REGRAS["categorias"]
TXT = REGRAS["textos"]


# ===== Limpeza dos campos =====
def matricula(serie):
    """Só os dígitos, sem zeros à esquerda (101877734.0 e 0101877734 -> 101877734); vazio vira NaN."""
    s = serie.astype("string").str.strip().str.replace(r"\.0+$", "", regex=True).str.replace(r"\D", "", regex=True).str.lstrip("0")
    return s.where(s.str.len() > 0).astype(object)


def datas(serie):
    """Datas das planilhas: '01/01/26', '01/01/2026', '2026-01-01 00:00:00' ou número de série do Excel."""
    s = serie.astype("string").str.strip()
    saida = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    iso = s.str.match(r"^\d{4}-\d{2}-\d{2}", na=False)
    saida[iso] = pd.to_datetime(s[iso].str[:10], format="%Y-%m-%d", errors="coerce")
    br = s.str.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", na=False)
    if br.any():
        partes = s[br].str.extract(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})")
        ano = partes[2].astype(int)
        ano = ano.where(ano >= 100, ano + 2000)
        saida[br] = pd.to_datetime(dict(year=ano, month=partes[1].astype(int), day=partes[0].astype(int)), errors="coerce")
    mm_aaaa = s.str.fullmatch(r"\d{1,2}/\d{4}", na=False)           # 09/2026 (referência do cadastro)
    if mm_aaaa.any():
        p = s[mm_aaaa].str.extract(r"(\d{1,2})/(\d{4})")
        saida[mm_aaaa] = pd.to_datetime(dict(year=p[1].astype(int), month=p[0].astype(int), day=1), errors="coerce")
    aaaamm = s.str.fullmatch(r"20\d{2}(0[1-9]|1[0-2])", na=False)      # 202609
    if aaaamm.any():
        saida[aaaamm] = pd.to_datetime(s[aaaamm] + "01", format="%Y%m%d", errors="coerce")
    num = s.str.fullmatch(r"\d{5}(\.\d+)?", na=False)
    if num.any():
        saida[num] = pd.to_datetime("1899-12-30") + pd.to_timedelta(s[num].astype(float).astype(int), unit="D")
    return saida.dt.normalize()


def valor_br(serie):
    """'R$ 1.234,56' -> 1234.56; 'R$' sozinho ou vazio -> NaN."""
    s = serie.astype("string").str.replace(r"[^\d,.\-]", "", regex=True)
    milhar = s.str.fullmatch(r"-?\d{1,3}(\.\d{3})+", na=False)          # "R$ 1.234" (sem centavos)
    s = s.where(~(s.str.contains(",", na=False) | milhar), s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(s, errors="coerce")


def mes(serie):
    return serie.dt.to_period("M").dt.to_timestamp()


# ===== Catálogo e classificação =====
def catalogo(df_pasta=None):
    """{código: {categoria, descricao, abertura}} — da planilha da pasta, se houver; senão a cópia do site."""
    if df_pasta is None or df_pasta.empty:
        return dict(CATALOGO_PADRAO), "padrão do site"
    cat = {}
    for _, r in df_pasta.iterrows():
        cod = re.sub(r"\D", "", str(r["SERVICO"]))
        if not cod or cod in cat:
            continue
        desc = str(r.get("CODIGO/DESCRICAO") or "")
        cat[cod] = {"categoria": str(r["CATEGORIA"]).strip(),
                    "descricao": re.sub(r"^\s*\d+\s*-\s*", "", desc).strip(),
                    "abertura": str(r.get("Abertura") or "").strip()}
    return cat, "planilha da pasta"


def tipo_servico(texto):
    t = re.sub(r"AUTO[\s\-_.]*RELIG", "AUTORELIG", normaliza(texto))   # 'AUTO RELIGAÇÃO', 'AUTO-RELIGAÇÃO' = AUTORELIGAÇÃO
    for termo, nome in REGRAS["tipos"]["ordem"]:
        if termo in t:
            return nome
    return REGRAS["tipos"]["outros"]


def classifica(ativ, cat):
    """Acrescenta codigo, categoria e tipo a cada atividade (pelo código do serviço; sem código, pela descrição)."""
    df = ativ.copy()
    texto = df["servico"].astype("string").fillna("")
    df["codigo"] = texto.str.extract(r"^\s*(\d{4,})", expand=False)
    por_desc = {normaliza(v["descricao"]): k for k, v in cat.items()}
    sem_cod = df["codigo"].isna()
    df.loc[sem_cod, "codigo"] = texto[sem_cod].map(lambda t: por_desc.get(normaliza(t)))
    info = df["codigo"].map(cat)
    df["categoria"] = info.map(lambda i: i["categoria"] if isinstance(i, dict) else None)
    descricao = info.map(lambda i: f"{i['abertura']} {i['descricao']}" if isinstance(i, dict) else None)
    df["tipo"] = descricao.fillna(texto).map(tipo_servico)
    if "fonte" in df.columns:                      # planilha de religação LISC: só entra como religação
        lisc = df["fonte"].eq("religacao_lisc").to_numpy(dtype=bool)
        religa = texto.map(normaliza).str.contains("RELIG", na=False).to_numpy(dtype=bool)
        df.loc[lisc & df["categoria"].isna().to_numpy() & religa, "categoria"] = CAT["religacao"]
        padrao = lisc & df["categoria"].eq(CAT["religacao"]).to_numpy(dtype=bool) & df["tipo"].eq(REGRAS["tipos"]["outros"]).to_numpy(dtype=bool)
        # sem tipo no nome do serviço: vale o tipo do nome do arquivo ('Autoreligação.xlsx' → AUTORELIGAÇÃO) ou LISC
        arquivo = df["arquivo"] if "arquivo" in df.columns else pd.Series("", index=df.index)
        do_arquivo = arquivo.fillna("").astype(str).map(lambda a: tipo_servico(a.rsplit("/", 1)[-1]))
        do_arquivo = do_arquivo.where(do_arquivo.ne(REGRAS["tipos"]["outros"]), REGRAS["religacao_lisc"]["tipo_padrao"])
        df.loc[padrao, "tipo"] = do_arquivo[padrao]
        df.loc[lisc & df["categoria"].ne(CAT["religacao"]).fillna(True).to_numpy(dtype=bool), "categoria"] = None   # corte/vistoria na LISC não conta
    return df


def prepara_atividades(ativ, cat):
    """Limpa, tira duplicadas (mesmo ID da Atividade em mais de um arquivo) e classifica."""
    df = ativ.copy()
    df["matricula"] = matricula(df["matricula"])
    df["data"] = datas(df["data"])
    df["status"] = df["status"].astype("string").str.strip()
    df["valor_debito"] = valor_br(df["valor_debito"])
    antes = len(df)
    # a mesma O.S. pode vir em mais de um arquivo (reprogramada, exportada de novo): vale a Finalizada e, depois, a mais recente
    df = df.assign(_nao_fin=df["status"].ne(REGRAS["status"]["finalizada"]).fillna(True).astype(bool))
    df = df.sort_values(["_nao_fin", "data"], ascending=[True, False], na_position="last", kind="stable").drop(columns="_nao_fin")
    com_id = df["id"].notna() & (df["id"].astype("string").str.strip() != "")
    df = pd.concat([df[com_id].drop_duplicates(subset="id"), df[~com_id].drop_duplicates(subset=[c for c in df.columns if c != "arquivo"])])
    duplicadas = antes - len(df)
    df = classifica(df, cat)
    return df.reset_index(drop=True), duplicadas


_ABREV_CIDADE = {"FCO": "FRANCISCO", "B": "BOM", "N": "NOVA", "STA": "SANTA", "STO": "SANTO", "PTO": "PORTO",
                 "CONC": "CONCEICAO", "J": "JOSE", "MAL": "MARECHAL", "PRES": "PRESIDENTE", "GOV": "GOVERNADOR"}
_TIRA_CIDADE = {"DE", "DA", "DO", "DAS", "DOS", "E", "S", "SAO", "SANTO", "SANTA", "MUNICIPIO", "CIDADE"}


def chave_cidade(nome):
    """Nome da cidade para comparar entre sistemas: 'S.FCO.DO ITABAPOANA' = 'São Francisco de Itabapoana'."""
    if not isinstance(nome, str) or not nome.strip():
        return None
    partes = re.sub(r"[^A-Z0-9]+", " ", normaliza(nome)).split()
    partes = [_ABREV_CIDADE.get(p, p) for p in partes]
    return "".join(p for p in partes if p not in _TIRA_CIDADE) or None


def _cidade_parecida(c, validas):
    if c in validas:
        return True
    from difflib import SequenceMatcher
    return any(v.startswith(c) or c.startswith(v) or SequenceMatcher(None, c, v).ratio() >= 0.88
               for v in validas if min(len(c), len(v)) >= 5)


def filtra_lisc_por_cidade(ativ):
    """Planilhas de religação LISC/autoreligação: só valem as cidades que aparecem nos arquivos de atividades.
    O nome da cidade é comparado sem acento, pontuação, 'de/do/São' e com as abreviações comuns
    ('S.FCO.DO ITABAPOANA' = 'SAO FRANCISCO DE ITABAPOANA'); também vale a matrícula que tem atividade
    (localidade/distrito com outro nome). Devolve (atividades, linhas tiradas, cidades tiradas)."""
    if "fonte" not in ativ.columns:
        return ativ, 0, ""
    lisc = ativ["fonte"].eq("religacao_lisc").fillna(False).astype(bool)
    if not lisc.any():
        return ativ, 0, ""
    cidade = ativ["cidade"].map(chave_cidade)
    validas = set(cidade[~lisc].dropna())
    ok = {c: _cidade_parecida(c, validas) for c in set(cidade[lisc].dropna())}
    cidade_ok = cidade.map(lambda c: ok.get(c, False) if c else False).astype(bool)
    matricula_ok = ativ["matricula"].isin(set(ativ.loc[~lisc, "matricula"].dropna()))
    fora = lisc & ~cidade_ok & ~matricula_ok
    nomes = ativ.loc[fora, "cidade"].fillna("(sem cidade)").astype(str).str.strip().value_counts().head(15)
    resumo = ", ".join(f"{n} ({q})" for n, q in nomes.items())
    return ativ[~fora].reset_index(drop=True), int(fora.sum()), resumo


# ===== Cadastro =====
def prepara_cadastro(cad):
    """Cadastro com a matrícula limpa, o mês de referência e as economias (mínimo 1)."""
    if cad is None or cad.empty:
        return None
    df = cad.copy()
    df["matricula"] = matricula(df["NUM_LIGACAO"])
    df["ref"] = mes(datas(df["REFERENCIA"]))
    df["economias"] = pd.to_numeric(df["TOTAL_ECO"].astype("string").str.replace(",", ".", regex=False), errors="coerce")
    df["economias"] = df["economias"].where(df["economias"] > 0, 1)
    df["SIT_LIG"] = df["SIT_LIG"].astype("string").str.strip().str.upper()
    df = df.dropna(subset=["matricula"]).sort_values(["matricula", "ref"], na_position="first")
    return df.drop_duplicates(subset=["matricula", "ref"], keep="last")


def ultimo_cadastro(cad):
    return None if cad is None else cad.drop_duplicates(subset="matricula", keep="last").set_index("matricula")


def economias(eventos, cad):
    """Economias de cada evento: TOTAL_ECO do cadastro do mesmo mês; sem esse mês, o mais recente; sem cadastro, 1."""
    if cad is None:
        return pd.Series(1.0, index=eventos.index), pd.Series(True, index=eventos.index)
    chave = eventos[["matricula"]].assign(ref=mes(eventos["data"]))
    mesmo_mes = chave.merge(cad[["matricula", "ref", "economias"]], on=["matricula", "ref"], how="left")["economias"]
    mesmo_mes.index = eventos.index
    ultimo = eventos["matricula"].map(ultimo_cadastro(cad)["economias"])
    eco = mesmo_mes.fillna(ultimo)
    return eco.fillna(1.0), eco.isna()


# ===== Base de cortes =====
def _igual(serie, valor):
    """serie == valor sem quebrar com vazios (NA conta como diferente)."""
    return serie.astype(object).eq(valor).to_numpy(dtype=bool)


def _faixa(valor, faixas):
    for f in faixas:
        if f["ate"] is None or valor <= f["ate"]:
            return f["nome"]
    return faixas[-1]["nome"]


def _proximo(cortes, eventos, sufixo):
    """Para cada corte, o 1º evento da mesma matrícula no dia do corte ou depois (merge_asof para frente)."""
    if eventos.empty:
        colunas = [f"data_{sufixo}" if c == "data" else c for c in eventos.columns if c != "matricula"]
        return pd.DataFrame(index=cortes.index, columns=colunas)
    esq = cortes[["matricula", "data"]].reset_index().sort_values("data")
    dir_ = eventos.rename(columns={"data": f"data_{sufixo}"}).sort_values(f"data_{sufixo}")
    dir_["data"] = dir_[f"data_{sufixo}"]
    junto = pd.merge_asof(esq, dir_, on="data", by="matricula", direction="forward", allow_exact_matches=True)
    return junto.set_index("index").drop(columns=["matricula", "data"]).reindex(cortes.index)


def monta_cortes(ativ, cad, hoje=None):
    """Base de cortes (uma linha por matrícula + data do corte)."""
    hoje = pd.Timestamp(hoje or date.today()).normalize()
    fin = ativ["status"] == REGRAS["status"]["finalizada"]
    ok = ativ["matricula"].notna() & ativ["data"].notna()

    cortes = ativ[fin & ok & (ativ["categoria"] == CAT["corte"])].copy()
    prioridade = {t: i for i, t in enumerate(REGRAS["tipos"]["prioridade_mesmo_dia"])}
    cortes["_p"] = cortes["tipo"].map(prioridade).fillna(len(prioridade))
    cortes = cortes.sort_values(["matricula", "data", "_p"]).drop_duplicates(subset=["matricula", "data"]).drop(columns="_p")
    cortes = cortes.reset_index(drop=True)
    cortes["prox_corte"] = cortes.groupby("matricula")["data"].shift(-1)

    relig = ativ[fin & ok & (ativ["categoria"] == CAT["religacao"])][["matricula", "data", "tipo", "id"]]
    relig = relig.rename(columns={"tipo": "tipo_religacao", "id": "id_religacao"}).drop_duplicates(subset=["matricula", "data"])
    r = _proximo(cortes, relig, "religacao")
    pos_ok = ativ["status"].isin(REGRAS["status"]["pos_corte_aceitos"])
    pos = ativ[pos_ok & ok & (ativ["categoria"] == CAT["pos_corte"])][["matricula", "data", "status", "id", "parecer"]]
    pos = pos.rename(columns={"status": "status_pos", "id": "id_pos", "parecer": "parecer_pos"})
    pos = pos.sort_values(["matricula", "data", "status_pos"], ascending=[True, True, False]).drop_duplicates(subset=["matricula", "data"])
    p = _proximo(cortes, pos, "pos")
    pos_fin = pos[pos["status_pos"] == REGRAS["status"]["finalizada"]][["matricula", "data"]]
    pf = _proximo(cortes, pos_fin, "pos_finalizada")

    df = pd.concat([cortes, r, p, pf], axis=1)
    janela = df["prox_corte"]
    for col, extras in (("data_religacao", ["tipo_religacao", "id_religacao"]),
                        ("data_pos", ["status_pos", "id_pos", "parecer_pos"]),
                        ("data_pos_finalizada", [])):
        # religação no mesmo dia do próximo corte fica com o corte anterior (o novo corte veio depois dela)
        fora = janela.notna() & df[col].notna() & ((df[col] > janela) if col == "data_religacao" else (df[col] >= janela))
        df.loc[fora, [col] + extras] = None
        df[col] = pd.to_datetime(df[col])
    usada = df["data_religacao"].notna() & df.duplicated(subset=["matricula", "data_religacao"], keep="first")
    df.loc[usada, ["data_religacao", "tipo_religacao", "id_religacao"]] = None   # uma religação vale para um corte só
    df["data_religacao"] = pd.to_datetime(df["data_religacao"])

    religado = df["data_religacao"].notna()
    com_pos = df["data_pos"].notna()
    df["mes_corte"] = mes(df["data"])
    df["dias"] = (df["data_religacao"] - df["data"]).dt.days
    df["dias_cortado"] = np.where(religado, np.nan, (hoje - df["data"]).dt.days)
    perm = REGRAS["permanencia"]
    df["permanencia"] = [(_faixa(d, perm["faixas"]) if pd.notna(d) else perm["sem_religacao"]) for d in df["dias"]]

    rg = REGRAS["regua"]
    regua = []
    for rel, pos_, dr, dp, dc in zip(religado, com_pos, df["data_religacao"], df["data_pos"], df["dias_cortado"]):
        if rel:
            regua.append(rg["religado_apos_pos"] if pos_ and dr >= dp else rg["religado"])
        elif pos_:
            regua.append(rg["com_pos"])
        else:
            regua.append(_faixa(dc, rg["faixas"]))
    df["regua"] = regua
    df["obs_pos"] = np.where(_igual(df["status_pos"], REGRAS["status"]["pos_corte_sem_sucesso"]), TXT["pos_sem_sucesso"], "")

    ult = ultimo_cadastro(cad)
    if ult is not None:
        # a situação do cadastro só vale se a referência dele for do mês do corte ou depois; com cadastro mais antigo
        # que o corte, a situação é calculada: ATIVA se houve religação, senão CORTADA
        no_cad = df["matricula"].isin(ult.index)
        ref = df["matricula"].map(ult["ref"])
        vale = no_cad & (ref.isna() | (ref >= df["mes_corte"]))
        calculada = np.where(df["data_religacao"].notna(), "ATIVA", "CORTADA")
        df["situacao"] = np.where(vale, df["matricula"].map(ult["SIT_LIG"]).astype(object), np.where(no_cad, calculada, TXT["sem_cadastro"]))
        df["situacao_fonte"] = np.where(vale, "cadastro", np.where(no_cad, "calculada (cadastro anterior ao corte)", ""))
        df["cliente"] = df["matricula"].map(ult["NOM_CLIENTE"])
        df["sub_categoria"] = df["matricula"].map(ult["SUB_CATEGORIA"])
        df["cidade"] = df["cidade"].fillna(df["matricula"].map(ult["CIDADE"]))
    else:
        df["situacao"] = TXT["sem_cadastro"]
        df["situacao_fonte"] = ""
        df["cliente"] = None
        df["sub_categoria"] = None
    df["economias"], _ = economias(df, cad)
    mes_rel = mes(df["data_religacao"]).dt.strftime("%Y-%m")
    # "Ativa" (religou sem OS) só vale para o último corte da matrícula: os anteriores foram seguidos de outro corte
    ativa = _igual(df["situacao"], "ATIVA") & df["prox_corte"].isna().to_numpy()
    df["mes_religacao"] = np.where(religado, mes_rel, np.where(ativa, TXT["ativa"], TXT["sem_religacao"]))
    df["mes_pos"] = np.where(com_pos, mes(df["data_pos"]).dt.strftime("%Y-%m"), TXT["sem_pos"])
    # Religou sem OS (usado pelo filtro "Ativas = religadas"): sem OS de religação, mas a ligação está ATIVA no cadastro
    # ou a matrícula foi cortada de novo depois (para ser cortada de novo, foi religada no meio)
    df["religou_sem_os"] = (~religado) & (_igual(df["situacao"], "ATIVA") | df["prox_corte"].notna().to_numpy())
    return df


# ===== Saldo de economias =====
def monta_saldo(ativ, cad):
    """Eventos Finalizados de corte, religação e implantação (uma vez por matrícula + data + categoria),
    com as economias. O saldo do mês é −corte + religação + implantação."""
    usar = [CAT["corte"], CAT["religacao"], CAT["implantacao"]]
    ev = ativ[(ativ["status"] == REGRAS["status"]["finalizada"]) & ativ["categoria"].isin(usar)
              & ativ["matricula"].notna() & ativ["data"].notna()].copy()
    prioridade = {t: i for i, t in enumerate(REGRAS["tipos"]["prioridade_mesmo_dia"])}
    ev["_p"] = ev["tipo"].map(prioridade).fillna(len(prioridade))
    ev = ev.sort_values(["matricula", "data", "categoria", "_p"]).drop_duplicates(subset=["matricula", "data", "categoria"])
    ev = ev.drop(columns="_p").reset_index(drop=True)
    ev["economias"], ev["sem_cadastro"] = economias(ev, cad)
    if cad is not None:                            # cidade vazia vem do cadastro, como nos cortes
        ev["cidade"] = ev["cidade"].fillna(ev["matricula"].map(ultimo_cadastro(cad)["CIDADE"]))
    ev["sinal"] = np.where(ev["categoria"] == CAT["corte"], -1, 1)
    ev["mes"] = mes(ev["data"])
    ev.loc[ev["categoria"] == CAT["implantacao"], "tipo"] = "LNA"
    return ev
