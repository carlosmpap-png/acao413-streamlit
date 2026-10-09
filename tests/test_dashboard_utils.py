import math

import pandas as pd

from dashboard_utils import (
    denominator_column,
    parse_sidra_9514,
    parse_sidra_9606,
    process_ids_for_age_band,
    ratio_per_10k,
)


def test_parser_9514_uses_exact_dimension_names_and_ibge_code():
    header = {
        "NC": "Nível Territorial (Código)",
        "NN": "Nível Territorial",
        "MC": "Unidade de Medida (Código)",
        "MN": "Unidade de Medida",
        "V": "Valor",
        "D1C": "Município (Código)",
        "D1N": "Município",
        "D2C": "Sexo (Código)",
        "D2N": "Sexo",
        "D3C": "Idade (Código)",
        "D3N": "Idade",
        "D4C": "Forma de declaração da idade (Código)",
        "D4N": "Forma de declaração da idade",
    }
    rows = [
        {"NC":"6","NN":"Município","MC":"45","MN":"Pessoas","V":"1000","D1C":"1600303","D1N":"Macapá (AP)","D2C":"0","D2N":"Total","D3C":"0","D3N":"Total","D4C":"113635","D4N":"Total"},
        {"NC":"6","NN":"Município","MC":"45","MN":"Pessoas","V":"100","D1C":"1600303","D1N":"Macapá (AP)","D2C":"0","D2N":"Total","D3C":"60","D3N":"60 a 64 anos","D4C":"113635","D4N":"Total"},
        {"NC":"6","NN":"Município","MC":"45","MN":"Pessoas","V":"20","D1C":"1600303","D1N":"Macapá (AP)","D2C":"0","D2N":"Total","D3C":"80","D3N":"80 a 84 anos","D4C":"113635","D4N":"Total"},
        {"NC":"6","NN":"Município","MC":"45","MN":"Pessoas","V":"45","D1C":"1600303","D1N":"Macapá (AP)","D2C":"1","D2N":"Homens","D3C":"60","D3N":"60 a 64 anos","D4C":"113635","D4N":"Total"},
        {"NC":"6","NN":"Município","MC":"45","MN":"Pessoas","V":"10","D1C":"1600303","D1N":"Macapá (AP)","D2C":"1","D2N":"Homens","D3C":"80","D3N":"80 a 84 anos","D4C":"113635","D4N":"Total"},
        {"NC":"6","NN":"Município","MC":"45","MN":"Pessoas","V":"55","D1C":"1600303","D1N":"Macapá (AP)","D2C":"2","D2N":"Mulheres","D3C":"60","D3N":"60 a 64 anos","D4C":"113635","D4N":"Total"},
        {"NC":"6","NN":"Município","MC":"45","MN":"Pessoas","V":"10","D1C":"1600303","D1N":"Macapá (AP)","D2C":"2","D2N":"Mulheres","D3C":"80","D3N":"80 a 84 anos","D4C":"113635","D4N":"Total"},
    ]
    out = parse_sidra_9514([header, *rows])
    row = out.iloc[0]
    assert row["codigo_ibge"] == "1600303"
    assert row["municipio_sidra"] == "Macapá (AP)"
    assert row["pop_total_2022"] == 1000
    assert row["pop_60mais"] == 120
    assert row["pop_80mais"] == 20
    assert row["pop_60a79"] == 100
    assert row["homens_60mais"] == 55
    assert row["mulheres_60mais"] == 65


def test_parser_9606_returns_race_by_code_not_name_join():
    header = {
        "NC": "Nível Territorial (Código)",
        "NN": "Nível Territorial",
        "MC": "Unidade de Medida (Código)",
        "MN": "Unidade de Medida",
        "V": "Valor",
        "D1C": "Município (Código)",
        "D1N": "Município",
        "D2C": "Cor ou raça (Código)",
        "D2N": "Cor ou raça",
        "D3C": "Sexo (Código)",
        "D3N": "Sexo",
        "D4C": "Idade (Código)",
        "D4N": "Idade",
    }
    rows = [
        {"NC":"6","NN":"Município","MC":"45","MN":"Pessoas","V":"70","D1C":"1600303","D1N":"Macapá (AP)","D2C":"1","D2N":"Parda","D3C":"0","D3N":"Total","D4C":"60","D4N":"60 a 64 anos"},
        {"NC":"6","NN":"Município","MC":"45","MN":"Pessoas","V":"10","D1C":"1600303","D1N":"Macapá (AP)","D2C":"1","D2N":"Parda","D3C":"0","D3N":"Total","D4C":"80","D4N":"80 a 84 anos"},
        {"NC":"6","NN":"Município","MC":"45","MN":"Pessoas","V":"30","D1C":"1600303","D1N":"Macapá (AP)","D2C":"2","D2N":"Preta","D3C":"0","D3N":"Total","D4C":"60","D4N":"60 a 64 anos"},
    ]
    out = parse_sidra_9606([header, *rows])
    parda = out[out["cor_raca"] == "Parda"].iloc[0]
    assert parda["codigo_ibge"] == "1600303"
    assert parda["pop_60mais"] == 80


def test_age_band_denominators_and_process_selection():
    assert denominator_column("60+") == "pop_60mais"
    assert denominator_column("60–79") == "pop_60a79"
    assert denominator_column("80+") == "pop_80mais"

    pp = pd.DataFrame(
        {
            "processo_id": ["P1", "P2", "P3", "P3"],
            "idade_referencia": [61, 82, 78, 85],
        }
    )
    assert process_ids_for_age_band(pp, "60+") == {"P1", "P2", "P3"}
    assert process_ids_for_age_band(pp, "60–79") == {"P1", "P3"}
    assert process_ids_for_age_band(pp, "80+") == {"P2", "P3"}


def test_ratio_per_10k():
    assert ratio_per_10k(25, 5000) == 50
    assert math.isnan(ratio_per_10k(1, 0))
