"""
Baixa do SIDRA os dados do Censo 2022 usados pelo painel e salva snapshots locais.
Uso: py refresh_ibge.py
"""
from pathlib import Path

import pandas as pd
import requests

from dashboard_utils import SIDRA_9514, SIDRA_9606

BASE = Path(__file__).parent
DATA = BASE / "data"

municipios = pd.read_csv(
    DATA / "municipios_ap_ibge.csv",
    dtype={"codigo_ibge": str},
)
codes = ",".join(municipios["codigo_ibge"].tolist())

urls = {
    "sidra9514_v93_raw.json": SIDRA_9514.format(codes=codes),
    "sidra9606_v93_raw.json": SIDRA_9606.format(codes=codes),
}

for name, url in urls.items():
    response = requests.get(
        url,
        timeout=90,
        headers={"User-Agent": "acao413-mpap/0.3"},
    )
    response.raise_for_status()
    (DATA / name).write_text(response.text, encoding="utf-8")
    print("Salvo:", DATA / name)
