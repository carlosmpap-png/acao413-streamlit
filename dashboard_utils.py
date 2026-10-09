from __future__ import annotations

import re
import unicodedata
from typing import Iterable

import numpy as np
import pandas as pd

AGE_BANDS = [
    "60 a 64 anos",
    "65 a 69 anos",
    "70 a 74 anos",
    "75 a 79 anos",
    "80 a 84 anos",
    "85 a 89 anos",
    "90 a 94 anos",
    "95 a 99 anos",
    "100 anos ou mais",
]

AGE_80 = [
    "80 a 84 anos",
    "85 a 89 anos",
    "90 a 94 anos",
    "95 a 99 anos",
    "100 anos ou mais",
]

# Variável 93 = População residente (Pessoas).
SIDRA_9514 = (
    "https://apisidra.ibge.gov.br/values/t/9514/p/2022/v/93/"
    "n6/{codes}/c2/all/c287/all/c286/113635"
)
SIDRA_9606 = (
    "https://apisidra.ibge.gov.br/values/t/9606/p/2022/v/93/"
    "n6/{codes}/c86/all/c2/all/c287/all"
)


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.strip().lower().split())


def _header_key(header: dict, label: str) -> str:
    target = _norm(label)
    matches = [key for key, value in header.items() if _norm(value) == target]
    if len(matches) != 1:
        raise KeyError(
            f"Dimensão SIDRA '{label}' não identificada de forma unívoca. "
            f"Cabeçalho recebido: {header}"
        )
    return matches[0]


def _payload(payload: list[dict]) -> tuple[dict, pd.DataFrame]:
    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError("Resposta SIDRA vazia ou fora do formato esperado.")
    header = payload[0]
    frame = pd.DataFrame(payload[1:])
    if frame.empty:
        raise ValueError("Resposta SIDRA sem linhas de dados.")
    return header, frame


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.replace({"-": "0", "..": np.nan, "...": np.nan, "X": np.nan, "x": np.nan}),
        errors="coerce",
    )


def _ibge_code(value: object) -> str:
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return ""
    return digits.zfill(7)


def parse_sidra_9514(payload: list[dict]) -> pd.DataFrame:
    """Converte a Tabela 9514 em denominadores municipais 60+/80+.

    O parser identifica dimensões pelo rótulo exato do cabeçalho da API,
    evitando colisões como 'Idade' x 'Unidade de Medida'.
    """
    header, df = _payload(payload)

    k_code = _header_key(header, "Município (Código)")
    k_mun = _header_key(header, "Município")
    k_sex = _header_key(header, "Sexo")
    k_age = _header_key(header, "Idade")
    k_value = _header_key(header, "Valor")

    work = pd.DataFrame(
        {
            "codigo_ibge": df[k_code].map(_ibge_code),
            "municipio_sidra": df[k_mun].astype(str),
            "sexo": df[k_sex].astype(str),
            "idade": df[k_age].astype(str),
            "valor": _numeric(df[k_value]),
        }
    )

    use = work[work["idade"].isin(AGE_BANDS)].copy()
    totals = work[(work["sexo"] == "Total") & (work["idade"] == "Total")].copy()

    rows = []
    for code, g in use.groupby("codigo_ibge", dropna=False):
        if not code:
            continue
        gt = g[g["sexo"] == "Total"]
        gh = g[g["sexo"] == "Homens"]
        gm = g[g["sexo"] == "Mulheres"]

        total_row = totals[totals["codigo_ibge"] == code]
        pop_total = total_row["valor"].sum(min_count=1) if not total_row.empty else np.nan

        rows.append(
            {
                "codigo_ibge": code,
                "municipio_sidra": g["municipio_sidra"].iloc[0],
                "pop_total_2022": pop_total,
                "pop_60mais": gt.loc[gt["idade"].isin(AGE_BANDS), "valor"].sum(min_count=1),
                "pop_80mais": gt.loc[gt["idade"].isin(AGE_80), "valor"].sum(min_count=1),
                "homens_60mais": gh.loc[gh["idade"].isin(AGE_BANDS), "valor"].sum(min_count=1),
                "mulheres_60mais": gm.loc[gm["idade"].isin(AGE_BANDS), "valor"].sum(min_count=1),
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError("Tabela 9514 não retornou faixas etárias 60+ reconhecidas.")

    out["pop_60a79"] = out["pop_60mais"] - out["pop_80mais"]
    out["pct_60mais"] = 100 * out["pop_60mais"] / out["pop_total_2022"]
    out["pct_80entre60"] = 100 * out["pop_80mais"] / out["pop_60mais"]
    out["pct_mulheres_60mais"] = 100 * out["mulheres_60mais"] / out["pop_60mais"]
    return out


def parse_sidra_9606(payload: list[dict]) -> pd.DataFrame:
    """Converte a Tabela 9606 em população 60+ por cor/raça e município."""
    header, df = _payload(payload)

    k_code = _header_key(header, "Município (Código)")
    k_mun = _header_key(header, "Município")
    k_race = _header_key(header, "Cor ou raça")
    k_sex = _header_key(header, "Sexo")
    k_age = _header_key(header, "Idade")
    k_value = _header_key(header, "Valor")

    work = pd.DataFrame(
        {
            "codigo_ibge": df[k_code].map(_ibge_code),
            "municipio_sidra": df[k_mun].astype(str),
            "cor_raca": df[k_race].astype(str),
            "sexo": df[k_sex].astype(str),
            "idade": df[k_age].astype(str),
            "valor": _numeric(df[k_value]),
        }
    )

    use = work[
        (work["sexo"] == "Total")
        & (work["idade"].isin(AGE_BANDS))
        & (work["cor_raca"] != "Total")
    ].copy()

    out = (
        use.groupby(["codigo_ibge", "municipio_sidra", "cor_raca"], as_index=False)["valor"]
        .sum(min_count=1)
        .rename(columns={"valor": "pop_60mais"})
    )
    if out.empty:
        raise ValueError("Tabela 9606 não retornou composição 60+ por cor ou raça.")
    return out


def denominator_column(age_band: str) -> str:
    mapping = {
        "60+": "pop_60mais",
        "60–79": "pop_60a79",
        "80+": "pop_80mais",
    }
    if age_band not in mapping:
        raise ValueError(f"Faixa etária não suportada: {age_band}")
    return mapping[age_band]


def process_ids_for_age_band(pp: pd.DataFrame, age_band: str) -> set[str]:
    if age_band == "60+":
        return set(pp["processo_id"])
    if age_band == "60–79":
        return set(pp.loc[pp["idade_referencia"].between(60, 79), "processo_id"])
    if age_band == "80+":
        return set(pp.loc[pp["idade_referencia"] >= 80, "processo_id"])
    raise ValueError(f"Faixa etária não suportada: {age_band}")


def people_for_age_band(pp: pd.DataFrame, age_band: str) -> pd.DataFrame:
    if age_band == "60+":
        return pp.copy()
    if age_band == "60–79":
        return pp[pp["idade_referencia"].between(60, 79)].copy()
    if age_band == "80+":
        return pp[pp["idade_referencia"] >= 80].copy()
    raise ValueError(f"Faixa etária não suportada: {age_band}")


def ratio_per_10k(numerator: float, denominator: float) -> float:
    if denominator is None or pd.isna(denominator) or denominator <= 0:
        return np.nan
    return float(numerator) / float(denominator) * 10_000
