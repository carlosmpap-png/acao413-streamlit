
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="Ação 413 — Painel de Dados",
    page_icon="📊",
    layout="wide",
)

BASE = Path(__file__).parent
DATA = BASE / "data"

@st.cache_data
def load_data():
    p = pd.read_csv(DATA / "processos_demo.csv", parse_dates=["data_autuacao","data_encerramento"])
    pp = pd.read_csv(DATA / "pessoas_processos_demo.csv",
                     parse_dates=["data_nascimento","data_referencia_idade"])
    ap = pd.read_csv(DATA / "assuntos_processos_demo.csv")
    m = pd.read_csv(DATA / "municipios_demo.csv")
    return p, pp, ap, m

p, pp, ap, mun = load_data()

st.title("Ação 413 — Painel de Dados para Atuação Resolutiva")
st.caption("PROTÓTIPO DEMONSTRATIVO • Dados 100% sintéticos • Não contém dados do Urano")

# ---------- Sidebar filters ----------
st.sidebar.header("Filtros")
dt_min = p["data_autuacao"].min().date()
dt_max = p["data_autuacao"].max().date()
periodo = st.sidebar.date_input(
    "Autuação no período",
    value=(dt_min, dt_max),
    min_value=dt_min,
    max_value=dt_max,
)

if isinstance(periodo, tuple) and len(periodo) == 2:
    ini, fim = pd.Timestamp(periodo[0]), pd.Timestamp(periodo[1])
else:
    ini, fim = pd.Timestamp(dt_min), pd.Timestamp(dt_max)

sel_mun = st.sidebar.multiselect("Município", sorted(p["municipio"].dropna().unique()))
sel_uni = st.sidebar.multiselect("Unidade", sorted(p["unidade"].dropna().unique()))
sel_cls = st.sidebar.multiselect("Classe", sorted(p["classe"].dropna().unique()))
sel_sit = st.sidebar.multiselect("Situação", sorted(p["situacao"].dropna().unique()))
sel_ass = st.sidebar.multiselect("Assunto", sorted(ap["assunto"].dropna().unique()))
faixa = st.sidebar.selectbox("Faixa etária", ["60+", "60–79", "80+"])

proc_ids_age = set(pp["processo_id"])
if faixa == "60–79":
    proc_ids_age = set(pp.loc[pp["idade_referencia"].between(60,79), "processo_id"])
elif faixa == "80+":
    proc_ids_age = set(pp.loc[pp["idade_referencia"] >= 80, "processo_id"])

f = p[p["processo_id"].isin(proc_ids_age)].copy()
f = f[f["data_autuacao"].between(ini, fim)]
if sel_mun:
    f = f[f["municipio"].isin(sel_mun)]
if sel_uni:
    f = f[f["unidade"].isin(sel_uni)]
if sel_cls:
    f = f[f["classe"].isin(sel_cls)]
if sel_sit:
    f = f[f["situacao"].isin(sel_sit)]
if sel_ass:
    ids_ass = set(ap.loc[ap["assunto"].isin(sel_ass), "processo_id"])
    f = f[f["processo_id"].isin(ids_ass)]

ids = set(f["processo_id"])
fpp = pp[pp["processo_id"].isin(ids)].copy()
fap = ap[ap["processo_id"].isin(ids)].copy()

page = st.sidebar.radio(
    "Página",
    ["Visão geral", "Território", "Temas", "Fluxo e tempo", "60+ / 80+",
     "Qualidade dos dados", "Resolutividade", "Metodologia"],
)

def metric_card(label, value, help_text=None):
    st.metric(label, value, help=help_text)

def empty_guard():
    if f.empty:
        st.warning("Nenhum registro atende aos filtros atuais.")
        st.stop()

if page == "Visão geral":
    empty_guard()
    c1,c2,c3,c4,c5 = st.columns(5)
    with c1: metric_card("Processos", f["processo_id"].nunique())
    with c2: metric_card("Pessoas 60+", fpp["pessoa_id"].nunique())
    with c3: metric_card("Ativos", int((f["situacao"]=="Ativo").sum()))
    with c4: metric_card("Encerrados", int((f["situacao"]=="Encerrado").sum()))
    with c5: metric_card("Duração mediana", f'{int(f["duracao_dias"].median())} dias')

    st.subheader("Autuações ao longo do tempo")
    tmp = f.assign(mes=f["data_autuacao"].dt.to_period("M").dt.to_timestamp())
    ts = tmp.groupby("mes", as_index=False)["processo_id"].nunique()
    st.plotly_chart(px.line(ts, x="mes", y="processo_id", markers=True,
                            labels={"mes":"Mês","processo_id":"Processos"}),
                    use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        s = f["situacao"].value_counts().rename_axis("situação").reset_index(name="processos")
        st.plotly_chart(px.bar(s, x="situação", y="processos"), use_container_width=True)
    with c2:
        g = fpp.assign(faixa=np.where(fpp["idade_referencia"]>=80, "80+", "60–79"))
        g = g["faixa"].value_counts().rename_axis("faixa").reset_index(name="pessoas")
        st.plotly_chart(px.bar(g, x="faixa", y="pessoas"), use_container_width=True)

elif page == "Território":
    empty_guard()
    st.subheader("Distribuição territorial")
    t = f.groupby(["municipio","comarca"], dropna=False)["processo_id"].nunique().reset_index(name="processos")
    t = t.merge(mun[["municipio","latitude","longitude"]], on="municipio", how="left")
    st.plotly_chart(px.bar(t.sort_values("processos"), x="processos", y="municipio",
                           orientation="h", labels={"municipio":"Município"}),
                    use_container_width=True)
    st.map(t.rename(columns={"latitude":"lat","longitude":"lon"}), latitude="lat", longitude="lon", size="processos")
    st.dataframe(t.sort_values("processos", ascending=False), use_container_width=True, hide_index=True)

elif page == "Temas":
    empty_guard()
    st.subheader("Assuntos e classes")
    c1, c2 = st.columns(2)
    with c1:
        a = fap.groupby("assunto")["processo_id"].nunique().sort_values().reset_index(name="processos")
        st.plotly_chart(px.bar(a, x="processos", y="assunto", orientation="h"),
                        use_container_width=True)
    with c2:
        cl = f.groupby("classe", dropna=False)["processo_id"].nunique().sort_values().reset_index(name="processos")
        st.plotly_chart(px.bar(cl, x="processos", y="classe", orientation="h"),
                        use_container_width=True)
    multi = fap.groupby("processo_id")["assunto"].nunique()
    st.metric("Processos com múltiplos assuntos", int((multi > 1).sum()))
    st.caption("A contagem de processos usa chave única. Um processo com vários assuntos continua sendo um único processo.")

elif page == "Fluxo e tempo":
    empty_guard()
    st.subheader("Tempo de tramitação")
    c1,c2,c3 = st.columns(3)
    with c1: st.metric("Mediana", f'{int(f["duracao_dias"].median())} dias')
    with c2: st.metric("Média", f'{int(f["duracao_dias"].mean())} dias')
    ativos = f[f["situacao"]=="Ativo"]
    with c3: st.metric("Ativos há > 730 dias", int((ativos["duracao_dias"]>730).sum()))
    st.plotly_chart(px.histogram(f, x="duracao_dias", nbins=30,
                                 labels={"duracao_dias":"Duração (dias)"}),
                    use_container_width=True)
    bands = pd.cut(
        ativos["duracao_dias"],
        bins=[-1,180,365,730,10_000],
        labels=["≤180 dias","181–365","366–730",">730 dias"]
    )
    b = bands.value_counts(sort=False).rename_axis("faixa").reset_index(name="ativos")
    st.plotly_chart(px.bar(b, x="faixa", y="ativos"), use_container_width=True)

elif page == "60+ / 80+":
    empty_guard()
    st.subheader("Perfil etário do universo 60+")
    c1,c2,c3 = st.columns(3)
    with c1: st.metric("Pessoas 60+", fpp["pessoa_id"].nunique())
    with c2: st.metric("Pessoas 80+", fpp.loc[fpp["idade_referencia"]>=80,"pessoa_id"].nunique())
    with c3:
        denom = max(1, fpp["pessoa_id"].nunique())
        pct = 100 * fpp.loc[fpp["idade_referencia"]>=80,"pessoa_id"].nunique() / denom
        st.metric("Participação 80+", f"{pct:.1f}%")
    st.plotly_chart(px.histogram(fpp, x="idade_referencia", nbins=20,
                                 labels={"idade_referencia":"Idade na data de referência"}),
                    use_container_width=True)
    per_proc = fpp.groupby("processo_id")["pessoa_id"].nunique()
    st.metric("Processos com mais de uma pessoa idosa", int((per_proc > 1).sum()))

elif page == "Qualidade dos dados":
    st.subheader("Qualidade e consistência")
    fields = ["processo_id","numero_processo","data_autuacao","situacao","classe","unidade","municipio","comarca"]
    q = pd.DataFrame({
        "campo": fields,
        "ausentes": [int(p[x].isna().sum()) for x in fields],
        "percentual_ausente": [round(100*p[x].isna().mean(),2) for x in fields],
    })
    st.dataframe(q, use_container_width=True, hide_index=True)
    c1,c2,c3 = st.columns(3)
    with c1: st.metric("IDs de processo duplicados", int(p["processo_id"].duplicated().sum()))
    with c2: st.metric("Vínculos pessoa–processo", len(pp))
    with c3: st.metric("Vínculos assunto–processo", len(ap))
    st.info("Nesta versão, as inconsistências são artificiais e servem apenas para testar a aba de qualidade.")

elif page == "Resolutividade":
    st.subheader("Resolutividade: camada analítica futura")
    st.warning(
        "Encerramento do processo NÃO é tratado como sinônimo de resolutividade. "
        "O painel só poderá medir resultado material quando houver dados capazes de demonstrar "
        "resultado jurídico útil e sua efetivação no plano fático."
    )
    st.markdown("""
Para a futura camada de resolutividade, a especificação deve prever, conforme disponibilidade e validação institucional, campos como:

**resultado jurídico útil**, **tipo de providência**, **cumprimento da providência**, **data de efetivação**, **mudança concreta observada**, **política/serviço público afetado**, **evidência do resultado**, **status de monitoramento** e **fonte de comprovação**.

Até lá, esta página deve exibir apenas métricas de **fluxo, esforço, tempo e cobertura**, sem rotulá-las como impacto social.
""")

elif page == "Metodologia":
    st.subheader("Ficha metodológica do protótipo")
    st.markdown("""
**Finalidade.** Apoiar diagnóstico, priorização e planejamento da atuação, sem substituir análise jurídica do caso individual.

**Universo inicial.** Processos/procedimentos com pessoa de 60 anos ou mais na data de referência definida para o evento.

**Unidade de contagem.** Indicadores de processo usam `processo_id` distinto. Indicadores de pessoa usam `pessoa_id` distinto. Assuntos são relação muitos-para-muitos.

**Superidoso.** Pessoa com 80 anos ou mais na data de referência.

**Duração.** Encerrados: data de encerramento − data de autuação. Ativos: data de corte − data de autuação.

**Privacidade.** Este protótipo usa exclusivamente dados sintéticos. Dados reais não devem ser publicados em ambiente público sem governança, base jurídica, controles de acesso e tratamento de risco adequados.

**Limitação central.** Situação “encerrado” não demonstra, por si só, resultado material ou impacto social.
""")
    with st.expander("Estrutura das tabelas"):
        st.write("processos_demo.csv — uma linha por processo")
        st.write("pessoas_processos_demo.csv — uma linha por vínculo pessoa–processo")
        st.write("assuntos_processos_demo.csv — uma linha por vínculo assunto–processo")
        st.write("municipios_demo.csv — dimensão territorial do protótipo")

st.divider()
st.caption("Ação 413 • MVP demonstrativo • Dados sintéticos • versão 0.1")
