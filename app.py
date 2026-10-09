
from pathlib import Path
import pandas as pd
import numpy as np
import requests
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="Ação 413 — Pessoa Idosa",
    page_icon="📊",
    layout="wide",
)

BASE = Path(__file__).parent
DATA = BASE / "data"

AGE_BANDS = [
    "60 a 64 anos", "65 a 69 anos", "70 a 74 anos", "75 a 79 anos",
    "80 a 84 anos", "85 a 89 anos", "90 a 94 anos", "95 a 99 anos",
    "100 anos ou mais"
]
AGE_80 = ["80 a 84 anos","85 a 89 anos","90 a 94 anos","95 a 99 anos","100 anos ou mais"]

SIDRA_9514 = "https://apisidra.ibge.gov.br/values/t/9514/p/2022/v/allxp/n6/{codes}/c2/all/c287/all/c286/113635"
SIDRA_9606 = "https://apisidra.ibge.gov.br/values/t/9606/p/2022/v/allxp/n6/{codes}/c86/all/c2/all/c287/all"

@st.cache_data
def load_local():
    p = pd.read_csv(DATA/"processos_demo.csv", parse_dates=["data_autuacao","data_encerramento"])
    pp = pd.read_csv(DATA/"pessoas_processos_demo.csv",
                     parse_dates=["data_nascimento","data_referencia_idade"])
    ap = pd.read_csv(DATA/"assuntos_processos_demo.csv")
    m = pd.read_csv(DATA/"municipios_ap_ibge.csv", dtype={"codigo_ibge":str})
    codigo_map = dict(zip(m["municipio"], m["codigo_ibge"]))
    if "codigo_ibge" not in p.columns:
        p["codigo_ibge"] = p["municipio"].map(codigo_map)
    else:
        p["codigo_ibge"] = p["codigo_ibge"].astype(str)
    return p, pp, ap, m

def sidra_to_df(payload):
    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError("Resposta SIDRA vazia ou fora do formato esperado.")
    header = payload[0]
    df = pd.DataFrame(payload[1:])
    rename = {k:v for k,v in header.items() if k in df.columns}
    df = df.rename(columns=rename)
    if "Valor" in df.columns:
        df["Valor"] = pd.to_numeric(df["Valor"].replace(
            {"-":"0","..":np.nan,"...":np.nan,"X":np.nan}
        ), errors="coerce")
    return df

def find_col(df, needles):
    for col in df.columns:
        txt = str(col).lower()
        if all(n.lower() in txt for n in needles):
            return col
    return None

@st.cache_data(ttl=24*3600, show_spinner=False)
def fetch_ibge_age(codes):
    url = SIDRA_9514.format(codes=",".join(codes))
    r = requests.get(url, timeout=45)
    r.raise_for_status()
    df = sidra_to_df(r.json())

    mun_col = find_col(df, ["município"])
    sex_col = find_col(df, ["sexo"])
    age_col = find_col(df, ["idade"])
    if not all([mun_col, sex_col, age_col]):
        raise ValueError(f"Não foi possível identificar dimensões SIDRA 9514: {list(df.columns)}")

    code_col = None
    for c in df.columns:
        if "município" in str(c).lower() and "código" in str(c).lower():
            code_col = c
            break
    if code_col is None:
        for c in df.columns:
            if "código" in str(c).lower() and df[c].astype(str).str.len().median() >= 6:
                code_col = c
                break

    use = df[df[age_col].isin(AGE_BANDS)].copy()
    totals = df[(df[sex_col].eq("Total")) & (df[age_col].eq("Total"))].copy()

    out=[]
    for mun, g in use.groupby(mun_col):
        gt = g[g[sex_col].eq("Total")]
        gh = g[g[sex_col].eq("Homens")]
        gm = g[g[sex_col].eq("Mulheres")]
        pop60 = gt.loc[gt[age_col].isin(AGE_BANDS),"Valor"].sum(min_count=1)
        pop80 = gt.loc[gt[age_col].isin(AGE_80),"Valor"].sum(min_count=1)
        hom60 = gh["Valor"].sum(min_count=1)
        mul60 = gm["Valor"].sum(min_count=1)

        code = None
        if code_col and code_col in g.columns:
            code = str(g[code_col].iloc[0]).replace(".0","")
        total_row = totals[totals[mun_col].eq(mun)]
        pop_total = total_row["Valor"].iloc[0] if len(total_row) else np.nan
        out.append({
            "codigo_ibge":code,
            "municipio":mun,
            "pop_total_2022":pop_total,
            "pop_60mais":pop60,
            "pop_80mais":pop80,
            "homens_60mais":hom60,
            "mulheres_60mais":mul60,
        })
    out = pd.DataFrame(out)
    out["pct_60mais"] = 100*out["pop_60mais"]/out["pop_total_2022"]
    out["pct_80entre60"] = 100*out["pop_80mais"]/out["pop_60mais"]
    out["pct_mulheres_60mais"] = 100*out["mulheres_60mais"]/out["pop_60mais"]
    return out

@st.cache_data(ttl=24*3600, show_spinner=False)
def fetch_ibge_race(codes):
    url = SIDRA_9606.format(codes=",".join(codes))
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    df = sidra_to_df(r.json())

    mun_col = find_col(df, ["município"])
    sex_col = find_col(df, ["sexo"])
    age_col = find_col(df, ["idade"])
    race_col = find_col(df, ["cor", "raça"])
    if not all([mun_col, sex_col, age_col, race_col]):
        raise ValueError(f"Não foi possível identificar dimensões SIDRA 9606: {list(df.columns)}")

    use = df[
        (df[sex_col].eq("Total")) &
        (df[age_col].isin(AGE_BANDS)) &
        (~df[race_col].eq("Total"))
    ].copy()
    race = (use.groupby([mun_col,race_col], as_index=False)["Valor"].sum()
               .rename(columns={mun_col:"municipio",race_col:"cor_raca","Valor":"pop_60mais"}))
    return race

def safe_ibge(m):
    codes = m["codigo_ibge"].astype(str).tolist()
    try:
        age = fetch_ibge_age(codes)
        age = age.drop(columns=["codigo_ibge"], errors="ignore").merge(
            m[["codigo_ibge","municipio"]], on="municipio", how="right"
        )
        race = fetch_ibge_race(codes)
        return age, race, None
    except Exception as exc:
        return pd.DataFrame(), pd.DataFrame(), str(exc)

p, pp, ap, municipios = load_local()
ibge_age, ibge_race, ibge_error = safe_ibge(municipios)

st.title("Ação 413 — Painel de Dados para Atuação Resolutiva")
st.caption("MVP v0.3 • Numeradores processuais sintéticos • Denominadores demográficos: IBGE, Censo 2022")

if ibge_error:
    st.warning(
        "Os dados do IBGE não puderam ser carregados neste momento. "
        "O restante do MVP continua disponível. Erro técnico: " + ibge_error
    )
else:
    st.success("Integração IBGE ativa: 16 municípios do Amapá • Censo 2022 • tabelas SIDRA 9514 e 9606")

st.sidebar.header("Filtros")
dt_min = p["data_autuacao"].min().date()
dt_max = p["data_autuacao"].max().date()
periodo = st.sidebar.date_input(
    "Autuação no período", value=(dt_min,dt_max), min_value=dt_min, max_value=dt_max
)
if isinstance(periodo, tuple) and len(periodo)==2:
    ini,fim = pd.Timestamp(periodo[0]),pd.Timestamp(periodo[1])
else:
    ini,fim = pd.Timestamp(dt_min),pd.Timestamp(dt_max)

sel_mun = st.sidebar.multiselect("Município", sorted(municipios["municipio"].tolist()),
                                 placeholder="Todos os municípios")
sel_uni = st.sidebar.multiselect("Unidade", sorted(p["unidade"].dropna().unique()),
                                 placeholder="Todas as unidades")
sel_cls = st.sidebar.multiselect("Classe", sorted(p["classe"].dropna().unique()),
                                 placeholder="Todas as classes")
sel_sit = st.sidebar.multiselect("Situação", sorted(p["situacao"].dropna().unique()),
                                 placeholder="Todas as situações")
sel_ass = st.sidebar.multiselect("Assunto", sorted(ap["assunto"].dropna().unique()),
                                 placeholder="Todos os assuntos")
faixa = st.sidebar.selectbox("Faixa etária", ["60+","60–79","80+"])

proc_ids_age = set(pp["processo_id"])
if faixa=="60–79":
    proc_ids_age=set(pp.loc[pp["idade_referencia"].between(60,79),"processo_id"])
elif faixa=="80+":
    proc_ids_age=set(pp.loc[pp["idade_referencia"]>=80,"processo_id"])

f=p[p["processo_id"].isin(proc_ids_age)].copy()
f=f[f["data_autuacao"].between(ini,fim)]
if sel_mun: f=f[f["municipio"].isin(sel_mun)]
if sel_uni: f=f[f["unidade"].isin(sel_uni)]
if sel_cls: f=f[f["classe"].isin(sel_cls)]
if sel_sit: f=f[f["situacao"].isin(sel_sit)]
if sel_ass:
    ids_ass=set(ap.loc[ap["assunto"].isin(sel_ass),"processo_id"])
    f=f[f["processo_id"].isin(ids_ass)]

ids=set(f["processo_id"])
fpp=pp[pp["processo_id"].isin(ids)].copy()
fap=ap[ap["processo_id"].isin(ids)].copy()

page = st.sidebar.radio(
    "Página",
    ["Visão geral","Contexto IBGE","Território","Temas","Fluxo e tempo",
     "60+ / 80+","Qualidade dos dados","Resolutividade","Metodologia"]
)

def empty_guard():
    if f.empty:
        st.warning("Nenhum registro atende aos filtros atuais.")
        st.stop()

def fmt_int(x):
    try:
        return f"{int(round(x)):,}".replace(",",".")
    except Exception:
        return "—"

def context_ibge_filtered():
    if ibge_age.empty:
        return ibge_age.copy()
    g=ibge_age.copy()
    if sel_mun:
        g=g[g["municipio"].isin(sel_mun)]
    return g

if page=="Visão geral":
    empty_guard()
    gi=context_ibge_filtered()
    pop60=gi["pop_60mais"].sum() if not gi.empty else np.nan
    pop80=gi["pop_80mais"].sum() if not gi.empty else np.nan
    nproc=f["processo_id"].nunique()
    taxa60=(nproc/pop60*10000) if pd.notna(pop60) and pop60>0 else np.nan

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Processos (MVP)", nproc)
    c2.metric("Pessoas 60+ no MVP", fpp["pessoa_id"].nunique())
    c3.metric("População 60+ (IBGE)", fmt_int(pop60))
    c4.metric("População 80+ (IBGE)", fmt_int(pop80))
    c5.metric("Ativos", int((f["situacao"]=="Ativo").sum()))
    c6.metric("Taxa demonstrativa", "—" if pd.isna(taxa60) else f"{taxa60:.1f}/10 mil",
              help="Numerador sintético do MVP / população 60+ oficial do Censo 2022. Não interpretar como taxa real do MP-AP.")

    st.info(
        "A taxa acima é apenas uma demonstração técnica: o numerador ainda é sintético. "
        "Quando a extração real do Urano for incorporada, o mesmo cálculo passará a produzir "
        "uma taxa institucional de demanda por 10 mil pessoas idosas."
    )

    st.subheader("Autuações ao longo do tempo")
    tmp=f.assign(mes=f["data_autuacao"].dt.to_period("M").dt.to_timestamp())
    ts=tmp.groupby("mes",as_index=False)["processo_id"].nunique()
    st.plotly_chart(px.line(ts,x="mes",y="processo_id",markers=True,
                            labels={"mes":"Mês","processo_id":"Processos"}),
                    use_container_width=True)

elif page=="Contexto IBGE":
    if ibge_age.empty:
        st.error("Contexto IBGE indisponível nesta execução.")
        st.stop()

    gi=context_ibge_filtered()
    st.subheader("Contexto demográfico da população idosa — Censo 2022")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("População total", fmt_int(gi["pop_total_2022"].sum()))
    c2.metric("Pessoas 60+", fmt_int(gi["pop_60mais"].sum()))
    c3.metric("Pessoas 80+", fmt_int(gi["pop_80mais"].sum()))
    pct=100*gi["pop_60mais"].sum()/gi["pop_total_2022"].sum()
    c4.metric("60+ na população", f"{pct:.1f}%")

    dem=gi[["municipio","pop_60mais","pop_80mais","pct_60mais","pct_80entre60","pct_mulheres_60mais"]].copy()
    st.plotly_chart(
        px.bar(dem.sort_values("pop_60mais"),x="pop_60mais",y="municipio",orientation="h",
               labels={"pop_60mais":"População 60+","municipio":"Município"}),
        use_container_width=True
    )

    st.subheader("Composição por sexo — população 60+")
    sex = gi[["municipio","homens_60mais","mulheres_60mais"]].melt(
        id_vars="municipio", var_name="sexo", value_name="pessoas"
    )
    sex["sexo"]=sex["sexo"].map({"homens_60mais":"Homens","mulheres_60mais":"Mulheres"})
    st.plotly_chart(px.bar(sex,x="municipio",y="pessoas",color="sexo",barmode="stack"),
                    use_container_width=True)

    if not ibge_race.empty:
        st.subheader("Composição por cor ou raça — população 60+")
        rr=ibge_race.copy()
        if sel_mun: rr=rr[rr["municipio"].isin(sel_mun)]
        rr=rr.groupby("cor_raca",as_index=False)["pop_60mais"].sum().sort_values("pop_60mais",ascending=False)
        st.plotly_chart(px.bar(rr,x="cor_raca",y="pop_60mais",
                               labels={"cor_raca":"Cor ou raça","pop_60mais":"Pessoas 60+"}),
                        use_container_width=True)

    st.dataframe(
        dem.sort_values("pop_60mais",ascending=False).rename(columns={
            "municipio":"Município","pop_60mais":"60+","pop_80mais":"80+",
            "pct_60mais":"% 60+ na população","pct_80entre60":"% 80+ entre 60+",
            "pct_mulheres_60mais":"% mulheres entre 60+"
        }),
        use_container_width=True, hide_index=True
    )
    st.caption("Fonte: IBGE, Censo Demográfico 2022, SIDRA — tabelas 9514 e 9606. Dados do universo.")

elif page=="Território":
    st.subheader("Demanda ministerial e denominador populacional")
    counts=f.groupby(["codigo_ibge","municipio"],dropna=False)["processo_id"].nunique().reset_index(name="processos_mvp")
    terr=municipios.merge(counts,on=["codigo_ibge","municipio"],how="left")
    terr["processos_mvp"]=terr["processos_mvp"].fillna(0).astype(int)

    if not ibge_age.empty:
        terr=terr.merge(ibge_age[["codigo_ibge","pop_60mais","pop_80mais"]],on="codigo_ibge",how="left")
        terr["taxa_60_10mil"]=10000*terr["processos_mvp"]/terr["pop_60mais"]
        ids80=set(pp.loc[pp["idade_referencia"]>=80,"processo_id"])
        p80=p[p["processo_id"].isin(ids80)]
        p80=p80[p80["data_autuacao"].between(ini,fim)]
        if sel_mun: p80=p80[p80["municipio"].isin(sel_mun)]
        c80=p80.groupby("codigo_ibge")["processo_id"].nunique()
        terr["proc_80_mvp"]=terr["codigo_ibge"].map(c80).fillna(0)
        terr["taxa_80_10mil"]=10000*terr["proc_80_mvp"]/terr["pop_80mais"]

    if sel_mun:
        terr=terr[terr["municipio"].isin(sel_mun)]

    xcol="taxa_60_10mil" if "taxa_60_10mil" in terr else "processos_mvp"
    st.plotly_chart(
        px.bar(terr.sort_values(xcol),x=xcol,y="municipio",orientation="h",
               labels={xcol:"Taxa demonstrativa por 10 mil 60+" if xcol=="taxa_60_10mil" else "Processos",
                       "municipio":"Município"}),
        use_container_width=True
    )
    st.warning(
        "As taxas territoriais nesta versão combinam numeradores sintéticos do MVP com denominadores oficiais do IBGE. "
        "Servem para validar a arquitetura de cálculo, não para comparar a atuação real entre municípios."
    )
    st.dataframe(terr.sort_values("processos_mvp",ascending=False),use_container_width=True,hide_index=True)

elif page=="Temas":
    empty_guard()
    st.subheader("Assuntos e classes")
    c1,c2=st.columns(2)
    with c1:
        a=fap.groupby("assunto")["processo_id"].nunique().sort_values().reset_index(name="processos")
        st.plotly_chart(px.bar(a,x="processos",y="assunto",orientation="h"),use_container_width=True)
    with c2:
        cl=f.groupby("classe",dropna=False)["processo_id"].nunique().sort_values().reset_index(name="processos")
        st.plotly_chart(px.bar(cl,x="processos",y="classe",orientation="h"),use_container_width=True)
    multi=fap.groupby("processo_id")["assunto"].nunique()
    st.metric("Processos com múltiplos assuntos",int((multi>1).sum()))
    st.caption("Processos são contados por chave única; múltiplos assuntos não multiplicam o total.")

elif page=="Fluxo e tempo":
    empty_guard()
    st.subheader("Tempo de tramitação")
    c1,c2,c3=st.columns(3)
    c1.metric("Mediana",f'{int(f["duracao_dias"].median())} dias')
    c2.metric("Média",f'{int(f["duracao_dias"].mean())} dias')
    ativos=f[f["situacao"]=="Ativo"]
    c3.metric("Ativos há > 730 dias",int((ativos["duracao_dias"]>730).sum()))
    st.plotly_chart(px.histogram(f,x="duracao_dias",nbins=30,
                                 labels={"duracao_dias":"Duração (dias)"}),
                    use_container_width=True)

elif page=="60+ / 80+":
    empty_guard()
    st.subheader("Perfil etário no universo processual do MVP")
    c1,c2,c3=st.columns(3)
    c1.metric("Pessoas 60+",fpp["pessoa_id"].nunique())
    c2.metric("Pessoas 80+",fpp.loc[fpp["idade_referencia"]>=80,"pessoa_id"].nunique())
    denom=max(1,fpp["pessoa_id"].nunique())
    pct=100*fpp.loc[fpp["idade_referencia"]>=80,"pessoa_id"].nunique()/denom
    c3.metric("Participação 80+",f"{pct:.1f}%")
    st.plotly_chart(px.histogram(fpp,x="idade_referencia",nbins=20,
                                 labels={"idade_referencia":"Idade na data de referência"}),
                    use_container_width=True)

elif page=="Qualidade dos dados":
    st.subheader("Qualidade e consistência")
    fields=["processo_id","numero_processo","data_autuacao","situacao","classe","unidade","municipio","comarca","codigo_ibge"]
    q=pd.DataFrame({
        "campo":fields,
        "ausentes":[int(p[x].isna().sum()) for x in fields],
        "percentual_ausente":[round(100*p[x].isna().mean(),2) for x in fields],
    })
    st.dataframe(q,use_container_width=True,hide_index=True)
    c1,c2,c3=st.columns(3)
    c1.metric("IDs de processo duplicados",int(p["processo_id"].duplicated().sum()))
    c2.metric("Vínculos pessoa–processo",len(pp))
    c3.metric("Vínculos assunto–processo",len(ap))

    st.subheader("Cobertura territorial")
    cov=municipios.copy()
    cov["tem_processo_mvp"]=cov["codigo_ibge"].isin(set(p["codigo_ibge"]))
    if not ibge_age.empty:
        cov["tem_denominador_ibge"]=cov["codigo_ibge"].isin(set(ibge_age["codigo_ibge"]))
    st.dataframe(cov,use_container_width=True,hide_index=True)

elif page=="Resolutividade":
    st.subheader("Resolutividade: separação entre esforço e resultado")
    st.warning(
        "Encerramento não é sinônimo de resolutividade. Métricas de estoque, fluxo e duração medem esforço/produção. "
        "Resultado material exige evidência de efetivação no plano fático."
    )
    st.markdown("""
A futura camada de resultado deverá prever, conforme disponibilidade e validação institucional:

**resultado jurídico útil**, **providência adotada**, **cumprimento**, **data de efetivação**, **mudança concreta observada**,
**política ou serviço público afetado**, **evidência do resultado**, **status de monitoramento** e **fonte de comprovação**.
""")

elif page=="Metodologia":
    st.subheader("Ficha metodológica — integração IBGE")
    st.markdown("""
**Universo demográfico.** População residente no Censo Demográfico 2022.

**Pessoa idosa (60+).** Soma dos grupos 60–64, 65–69, 70–74, 75–79, 80–84, 85–89, 90–94, 95–99 e 100 anos ou mais.

**80+.** Soma dos grupos 80–84, 85–89, 90–94, 95–99 e 100 anos ou mais.

**Taxa de demanda 60+.** Processos distintos envolvendo 60+ ÷ população 60+ × 10.000.

**Taxa de demanda 80+.** Processos distintos envolvendo 80+ ÷ população 80+ × 10.000.

**Chave territorial.** Código IBGE de 7 dígitos. O nome do município é atributo de exibição, não chave de integração.

**Fontes.**
- SIDRA 9514 — população residente por sexo e idade.
- SIDRA 9606 — população residente por cor ou raça, sexo e idade.

**Limitação do MVP.** Os numeradores processuais são sintéticos. Os denominadores IBGE são oficiais. Portanto, as taxas exibidas nesta versão validam a arquitetura de cálculo, mas não representam a demanda real do MP-AP.
""")
    st.info(
        "Quando a base real do Urano for recebida da DIRTI, o código de cálculo e os denominadores permanecem; "
        "substitui-se apenas o numerador sintético pelo conjunto institucional validado."
    )

st.divider()
st.caption("Ação 413 • MVP v0.3 • Integração territorial IBGE • https://idosos.streamlit.app/")
