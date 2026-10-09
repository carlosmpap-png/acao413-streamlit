from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from dashboard_utils import (
    SIDRA_9514,
    SIDRA_9606,
    denominator_column,
    parse_sidra_9514,
    parse_sidra_9606,
    people_for_age_band,
    process_ids_for_age_band,
    ratio_per_10k,
)

st.set_page_config(
    page_title="Ação 413 — Pessoa Idosa",
    page_icon="📊",
    layout="wide",
)

BASE = Path(__file__).parent
DATA = BASE / "data"


@st.cache_data
def load_local():
    p = pd.read_csv(
        DATA / "processos_demo.csv",
        dtype={"codigo_ibge": str},
        parse_dates=["data_autuacao", "data_encerramento"],
    )
    pp = pd.read_csv(
        DATA / "pessoas_processos_demo.csv",
        parse_dates=["data_nascimento", "data_referencia_idade"],
    )
    ap = pd.read_csv(DATA / "assuntos_processos_demo.csv")
    municipios = pd.read_csv(DATA / "municipios_ap_ibge.csv", dtype={"codigo_ibge": str})

    codigo_map = dict(zip(municipios["municipio"], municipios["codigo_ibge"]))
    if "codigo_ibge" not in p.columns:
        p["codigo_ibge"] = p["municipio"].map(codigo_map)
    else:
        p["codigo_ibge"] = p["codigo_ibge"].astype(str)

    return p, pp, ap, municipios


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fetch_ibge_age(codes):
    url = SIDRA_9514.format(codes=",".join(codes))
    response = requests.get(
        url,
        timeout=60,
        headers={"User-Agent": "acao413-mpap/0.3"},
    )
    response.raise_for_status()
    return parse_sidra_9514(response.json())


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fetch_ibge_race(codes):
    url = SIDRA_9606.format(codes=",".join(codes))
    response = requests.get(
        url,
        timeout=90,
        headers={"User-Agent": "acao413-mpap/0.3"},
    )
    response.raise_for_status()
    return parse_sidra_9606(response.json())


def load_ibge(municipios):
    codes = municipios["codigo_ibge"].astype(str).tolist()
    errors = []

    age = pd.DataFrame()
    race = pd.DataFrame()

    try:
        raw_age = fetch_ibge_age(codes)
        age = municipios[["codigo_ibge", "municipio"]].merge(
            raw_age.drop(columns=["municipio_sidra"], errors="ignore"),
            on="codigo_ibge",
            how="left",
            validate="1:1",
        )
        missing = age.loc[age["pop_60mais"].isna(), "municipio"].tolist()
        if missing:
            raise ValueError(
                "Sem denominador 60+ para: " + ", ".join(missing)
            )
    except Exception as exc:
        errors.append("Tabela 9514: " + str(exc))
        age = pd.DataFrame()

    try:
        raw_race = fetch_ibge_race(codes)
        race = raw_race.merge(
            municipios[["codigo_ibge", "municipio"]],
            on="codigo_ibge",
            how="left",
            validate="m:1",
        )
    except Exception as exc:
        errors.append("Tabela 9606: " + str(exc))
        race = pd.DataFrame()

    return age, race, errors


p, pp, ap, municipios = load_local()
ibge_age, ibge_race, ibge_errors = load_ibge(municipios)

st.title("Ação 413 — Painel de Dados para Atuação Resolutiva")
st.caption(
    "MVP v0.3 • Numeradores processuais sintéticos • "
    "Denominadores demográficos oficiais: IBGE, Censo 2022"
)

if ibge_age.empty:
    st.warning(
        "Os denominadores demográficos do IBGE não puderam ser carregados nesta execução. "
        "O restante do MVP continua disponível."
    )
else:
    race_status = "com cor/raça" if not ibge_race.empty else "sem cor/raça nesta execução"
    st.success(
        "Integração demográfica IBGE ativa: 16 municípios do Amapá • "
        f"Censo 2022 • {race_status}"
    )

if ibge_errors:
    with st.expander("Detalhes da integração IBGE"):
        for err in ibge_errors:
            st.write("•", err)


# -----------------------------
# Filtros globais
# -----------------------------
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

sel_mun = st.sidebar.multiselect(
    "Município",
    sorted(municipios["municipio"].tolist()),
    placeholder="Todos os municípios",
)
sel_uni = st.sidebar.multiselect(
    "Unidade",
    sorted(p["unidade"].dropna().unique()),
    placeholder="Todas as unidades",
)
sel_cls = st.sidebar.multiselect(
    "Classe",
    sorted(p["classe"].dropna().unique()),
    placeholder="Todas as classes",
)
sel_sit = st.sidebar.multiselect(
    "Situação",
    sorted(p["situacao"].dropna().unique()),
    placeholder="Todas as situações",
)
sel_ass = st.sidebar.multiselect(
    "Assunto",
    sorted(ap["assunto"].dropna().unique()),
    placeholder="Todos os assuntos",
)
faixa = st.sidebar.selectbox("Faixa etária", ["60+", "60–79", "80+"])

proc_ids_age = process_ids_for_age_band(pp, faixa)

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
fpp_all = pp[pp["processo_id"].isin(ids)].copy()
fpp = people_for_age_band(fpp_all, faixa)
fap = ap[ap["processo_id"].isin(ids)].copy()

page = st.sidebar.radio(
    "Página",
    [
        "Visão geral",
        "Contexto IBGE",
        "Território",
        "Temas",
        "Fluxo e tempo",
        "60+ / 80+",
        "Qualidade dos dados",
        "Resolutividade",
        "Metodologia",
    ],
)

denom_col = denominator_column(faixa)
periodo_label = f"{ini.date().strftime('%d/%m/%Y')} a {fim.date().strftime('%d/%m/%Y')}"


def empty_guard():
    if f.empty:
        st.warning("Nenhum registro atende aos filtros atuais.")
        st.stop()


def fmt_int(value):
    try:
        return f"{int(round(value)):,}".replace(",", ".")
    except Exception:
        return "—"


def context_ibge_filtered():
    if ibge_age.empty:
        return ibge_age.copy()
    out = ibge_age.copy()
    if sel_mun:
        out = out[out["municipio"].isin(sel_mun)]
    return out


def current_denominator(df):
    if df.empty or denom_col not in df.columns:
        return np.nan
    return df[denom_col].sum(min_count=1)


# -----------------------------
# Páginas
# -----------------------------
if page == "Visão geral":
    empty_guard()

    gi = context_ibge_filtered()
    denominador = current_denominator(gi)
    nproc = f["processo_id"].nunique()
    razao = ratio_per_10k(nproc, denominador)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Processos (MVP)", nproc)
    c2.metric(f"Pessoas {faixa} no MVP", fpp["pessoa_id"].nunique())
    c3.metric(f"População {faixa} (IBGE)", fmt_int(denominador))
    c4.metric(
        "População 60+ (IBGE)",
        fmt_int(gi["pop_60mais"].sum()) if not gi.empty else "—",
    )
    c5.metric(
        "População 80+ (IBGE)",
        fmt_int(gi["pop_80mais"].sum()) if not gi.empty else "—",
    )
    c6.metric(
        "Razão demonstrativa",
        "—" if pd.isna(razao) else f"{razao:.1f}/10 mil",
        help=(
            f"Processos distintos no período {periodo_label} ÷ população {faixa} "
            "do Censo 2022 × 10.000. O numerador do MVP é sintético."
        ),
    )

    st.info(
        "A razão acima é acumulada para o período selecionado e usa como denominador "
        "a população do Censo 2022. Ela serve para comparar a arquitetura do indicador, "
        "não representa incidência anual nem demanda real do MP-AP enquanto o numerador "
        "processual for sintético."
    )

    st.subheader("Autuações ao longo do tempo")
    tmp = f.assign(mes=f["data_autuacao"].dt.to_period("M").dt.to_timestamp())
    ts = tmp.groupby("mes", as_index=False)["processo_id"].nunique()
    st.plotly_chart(
        px.line(
            ts,
            x="mes",
            y="processo_id",
            markers=True,
            labels={"mes": "Mês", "processo_id": "Processos"},
        ),
        use_container_width=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        sit = (
            f["situacao"]
            .value_counts()
            .rename_axis("situação")
            .reset_index(name="processos")
        )
        st.plotly_chart(
            px.bar(sit, x="situação", y="processos"),
            use_container_width=True,
        )
    with c2:
        age = fpp_all.assign(
            faixa=np.where(fpp_all["idade_referencia"] >= 80, "80+", "60–79")
        )
        age = (
            age["faixa"]
            .value_counts()
            .rename_axis("faixa")
            .reset_index(name="pessoas")
        )
        st.plotly_chart(
            px.bar(age, x="faixa", y="pessoas"),
            use_container_width=True,
        )


elif page == "Contexto IBGE":
    if ibge_age.empty:
        st.error("Contexto demográfico IBGE indisponível nesta execução.")
        st.stop()

    gi = context_ibge_filtered()

    st.subheader("Contexto demográfico da população idosa — Censo 2022")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("População total", fmt_int(gi["pop_total_2022"].sum()))
    c2.metric("Pessoas 60+", fmt_int(gi["pop_60mais"].sum()))
    c3.metric("Pessoas 80+", fmt_int(gi["pop_80mais"].sum()))
    pct = 100 * gi["pop_60mais"].sum() / gi["pop_total_2022"].sum()
    c4.metric("60+ na população", f"{pct:.1f}%")

    dem = gi[
        [
            "municipio",
            "pop_60mais",
            "pop_60a79",
            "pop_80mais",
            "pct_60mais",
            "pct_80entre60",
            "pct_mulheres_60mais",
        ]
    ].copy()

    st.plotly_chart(
        px.bar(
            dem.sort_values("pop_60mais"),
            x="pop_60mais",
            y="municipio",
            orientation="h",
            labels={"pop_60mais": "População 60+", "municipio": "Município"},
        ),
        use_container_width=True,
    )

    st.subheader("Composição por sexo — população 60+")
    sex = gi[["municipio", "homens_60mais", "mulheres_60mais"]].melt(
        id_vars="municipio",
        var_name="sexo",
        value_name="pessoas",
    )
    sex["sexo"] = sex["sexo"].map(
        {"homens_60mais": "Homens", "mulheres_60mais": "Mulheres"}
    )
    st.plotly_chart(
        px.bar(
            sex,
            x="municipio",
            y="pessoas",
            color="sexo",
            barmode="stack",
        ),
        use_container_width=True,
    )

    if not ibge_race.empty:
        st.subheader("Composição por cor ou raça — população 60+")
        race = ibge_race.copy()
        if sel_mun:
            race = race[race["municipio"].isin(sel_mun)]
        race = (
            race.groupby("cor_raca", as_index=False)["pop_60mais"]
            .sum()
            .sort_values("pop_60mais", ascending=False)
        )
        st.plotly_chart(
            px.bar(
                race,
                x="cor_raca",
                y="pop_60mais",
                labels={"cor_raca": "Cor ou raça", "pop_60mais": "Pessoas 60+"},
            ),
            use_container_width=True,
        )
    else:
        st.caption(
            "A composição por cor ou raça ficou indisponível nesta execução; "
            "os demais denominadores demográficos permanecem válidos."
        )

    st.dataframe(
        dem.sort_values("pop_60mais", ascending=False).rename(
            columns={
                "municipio": "Município",
                "pop_60mais": "60+",
                "pop_60a79": "60–79",
                "pop_80mais": "80+",
                "pct_60mais": "% 60+ na população",
                "pct_80entre60": "% 80+ entre 60+",
                "pct_mulheres_60mais": "% mulheres entre 60+",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "Fonte: IBGE, Censo Demográfico 2022, SIDRA — tabelas 9514 e 9606; "
        "variável 93 (População residente). Dados do universo."
    )


elif page == "Território":
    st.subheader("Demanda ministerial e denominador populacional")

    counts = (
        f.groupby(["codigo_ibge", "municipio"], dropna=False)["processo_id"]
        .nunique()
        .reset_index(name="processos_mvp")
    )

    terr = municipios.merge(
        counts,
        on=["codigo_ibge", "municipio"],
        how="left",
        validate="1:1",
    )
    terr["processos_mvp"] = terr["processos_mvp"].fillna(0).astype(int)

    if not ibge_age.empty:
        terr = terr.merge(
            ibge_age[
                [
                    "codigo_ibge",
                    "pop_60mais",
                    "pop_60a79",
                    "pop_80mais",
                ]
            ],
            on="codigo_ibge",
            how="left",
            validate="1:1",
        )
        terr["denominador_faixa"] = terr[denom_col]
        terr["razao_demandas_10mil"] = terr.apply(
            lambda row: ratio_per_10k(
                row["processos_mvp"],
                row["denominador_faixa"],
            ),
            axis=1,
        )

    if sel_mun:
        terr = terr[terr["municipio"].isin(sel_mun)]

    if "razao_demandas_10mil" in terr.columns:
        xcol = "razao_demandas_10mil"
        xlabel = f"Razão demonstrativa por 10 mil pessoas {faixa}"
    else:
        xcol = "processos_mvp"
        xlabel = "Processos sintéticos"

    st.plotly_chart(
        px.bar(
            terr.sort_values(xcol),
            x=xcol,
            y="municipio",
            orientation="h",
            labels={xcol: xlabel, "municipio": "Município"},
        ),
        use_container_width=True,
    )

    st.warning(
        f"A razão territorial usa processos sintéticos acumulados no período {periodo_label} "
        f"e a população {faixa} do Censo 2022. Todos os filtros globais — período, município, "
        "unidade, classe, situação, assunto e faixa etária — incidem sobre o numerador."
    )

    st.dataframe(
        terr.sort_values("processos_mvp", ascending=False),
        use_container_width=True,
        hide_index=True,
    )


elif page == "Temas":
    empty_guard()
    st.subheader("Assuntos e classes")

    c1, c2 = st.columns(2)
    with c1:
        assuntos = (
            fap.groupby("assunto")["processo_id"]
            .nunique()
            .sort_values()
            .reset_index(name="processos")
        )
        st.plotly_chart(
            px.bar(
                assuntos,
                x="processos",
                y="assunto",
                orientation="h",
            ),
            use_container_width=True,
        )

    with c2:
        classes = (
            f.groupby("classe", dropna=False)["processo_id"]
            .nunique()
            .sort_values()
            .reset_index(name="processos")
        )
        st.plotly_chart(
            px.bar(
                classes,
                x="processos",
                y="classe",
                orientation="h",
            ),
            use_container_width=True,
        )

    multi = fap.groupby("processo_id")["assunto"].nunique()
    st.metric("Processos com múltiplos assuntos", int((multi > 1).sum()))
    st.caption(
        "Processos são contados por chave única; múltiplos assuntos não multiplicam o total."
    )


elif page == "Fluxo e tempo":
    empty_guard()
    st.subheader("Tempo de tramitação")

    c1, c2, c3 = st.columns(3)
    c1.metric("Mediana", f'{int(f["duracao_dias"].median())} dias')
    c2.metric("Média", f'{int(f["duracao_dias"].mean())} dias')

    ativos = f[f["situacao"] == "Ativo"]
    c3.metric("Ativos há > 730 dias", int((ativos["duracao_dias"] > 730).sum()))

    st.plotly_chart(
        px.histogram(
            f,
            x="duracao_dias",
            nbins=30,
            labels={"duracao_dias": "Duração (dias)"},
        ),
        use_container_width=True,
    )

    if not ativos.empty:
        bands = pd.cut(
            ativos["duracao_dias"],
            bins=[-1, 180, 365, 730, 10000],
            labels=["≤180 dias", "181–365", "366–730", ">730 dias"],
        )
        band_df = (
            bands.value_counts(sort=False)
            .rename_axis("faixa")
            .reset_index(name="ativos")
        )
        st.plotly_chart(
            px.bar(band_df, x="faixa", y="ativos"),
            use_container_width=True,
        )


elif page == "60+ / 80+":
    empty_guard()
    st.subheader("Perfil etário no universo processual do MVP")

    c1, c2, c3 = st.columns(3)
    c1.metric("Pessoas 60+", fpp_all["pessoa_id"].nunique())
    c2.metric(
        "Pessoas 80+",
        fpp_all.loc[fpp_all["idade_referencia"] >= 80, "pessoa_id"].nunique(),
    )

    denom = max(1, fpp_all["pessoa_id"].nunique())
    pct = (
        100
        * fpp_all.loc[fpp_all["idade_referencia"] >= 80, "pessoa_id"].nunique()
        / denom
    )
    c3.metric("Participação 80+", f"{pct:.1f}%")

    st.plotly_chart(
        px.histogram(
            fpp_all,
            x="idade_referencia",
            nbins=20,
            labels={"idade_referencia": "Idade na data de referência"},
        ),
        use_container_width=True,
    )

    per_proc = fpp_all.groupby("processo_id")["pessoa_id"].nunique()
    st.metric(
        "Processos com mais de uma pessoa idosa",
        int((per_proc > 1).sum()),
    )


elif page == "Qualidade dos dados":
    st.subheader("Qualidade e consistência")

    fields = [
        "processo_id",
        "numero_processo",
        "data_autuacao",
        "situacao",
        "classe",
        "unidade",
        "municipio",
        "comarca",
        "codigo_ibge",
    ]

    q = pd.DataFrame(
        {
            "campo": fields,
            "ausentes": [int(p[col].isna().sum()) for col in fields],
            "percentual_ausente": [
                round(100 * p[col].isna().mean(), 2) for col in fields
            ],
        }
    )

    st.dataframe(q, use_container_width=True, hide_index=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("IDs de processo duplicados", int(p["processo_id"].duplicated().sum()))
    c2.metric("Vínculos pessoa–processo", len(pp))
    c3.metric("Vínculos assunto–processo", len(ap))

    st.subheader("Cobertura territorial")
    cov = municipios.copy()
    cov["tem_processo_mvp"] = cov["codigo_ibge"].isin(set(p["codigo_ibge"]))
    if not ibge_age.empty:
        cov["tem_denominador_ibge"] = cov["codigo_ibge"].isin(
            set(ibge_age["codigo_ibge"])
        )
    st.dataframe(cov, use_container_width=True, hide_index=True)

    min_year = int(p["data_autuacao"].dt.year.min())
    max_year = int(p["data_autuacao"].dt.year.max())
    st.caption(
        f"Cobertura temporal do conjunto sintético atual: {min_year}–{max_year}."
    )


elif page == "Resolutividade":
    st.subheader("Resolutividade: separação entre esforço e resultado")
    st.warning(
        "Encerramento não é sinônimo de resolutividade. Métricas de estoque, fluxo "
        "e duração medem esforço/produção. Resultado material exige evidência de "
        "efetivação no plano fático."
    )

    st.markdown(
        """
A futura camada de resultado deverá prever, conforme disponibilidade e validação institucional:

**resultado jurídico útil**, **providência adotada**, **cumprimento**, **data de efetivação**,
**mudança concreta observada**, **política ou serviço público afetado**, **evidência do resultado**,
**status de monitoramento** e **fonte de comprovação**.
"""
    )


elif page == "Metodologia":
    st.subheader("Ficha metodológica — integração IBGE")

    st.markdown(
        f"""
**Universo demográfico.** População residente no Censo Demográfico 2022.

**Pessoa idosa (60+).** Soma dos grupos 60–64, 65–69, 70–74, 75–79, 80–84,
85–89, 90–94, 95–99 e 100 anos ou mais.

**Faixa 60–79.** População 60+ menos população 80+.

**80+.** Soma dos grupos 80–84, 85–89, 90–94, 95–99 e 100 anos ou mais.

**Razão demonstrativa de demandas por 10 mil pessoas idosas no período.**
Processos distintos que atendem aos filtros ÷ população da faixa etária selecionada
no Censo 2022 × 10.000.

**Interpretação.** O indicador é uma razão acumulada para o período selecionado;
não é apresentado como incidência anual.

**Chave territorial.** Código IBGE de 7 dígitos. O nome do município é atributo
de exibição, não chave de integração.

**Fontes demográficas.**
- SIDRA 9514 — população residente por sexo e idade;
- SIDRA 9606 — população residente por cor ou raça, sexo e idade;
- variável 93 — População residente (Pessoas).

**Filtros.** Período, município, unidade, classe, situação, assunto e faixa etária
incidem sobre o numerador processual.

**Limitação do MVP.** Os numeradores processuais são sintéticos. Os denominadores
IBGE são oficiais. Portanto, as razões exibidas validam a arquitetura de cálculo,
mas não representam a demanda real do MP-AP.

**Período sintético do MVP.** {int(p["data_autuacao"].dt.year.min())}–{int(p["data_autuacao"].dt.year.max())}.
"""
    )

    st.info(
        "Quando a base real do Urano for recebida e validada institucionalmente, "
        "o cálculo e os denominadores permanecem; substitui-se o numerador sintético "
        "pelo conjunto institucional aprovado."
    )


st.divider()
st.caption(
    "Ação 413 • MVP v0.3 • Integração territorial IBGE • "
    "https://idosos.streamlit.app/"
)
