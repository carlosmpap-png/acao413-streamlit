"""
Baixa do SIDRA os dados do Censo 2022 usados pelo painel e salva snapshots locais.
Uso: py refresh_ibge.py
"""
from pathlib import Path
import pandas as pd
import requests

BASE = Path(__file__).parent
DATA = BASE / "data"
m = pd.read_csv(DATA / "municipios_ap_ibge.csv", dtype={"codigo_ibge": str})
codes = ",".join(m["codigo_ibge"].tolist())

urls = {
    "sidra9514_raw.json": f"https://apisidra.ibge.gov.br/values/t/9514/p/2022/v/allxp/n6/{codes}/c2/all/c287/all/c286/113635",
    "sidra9606_raw.json": f"https://apisidra.ibge.gov.br/values/t/9606/p/2022/v/allxp/n6/{codes}/c86/all/c2/all/c287/all",
}

for name, url in urls.items():
    r = requests.get(url, timeout=90)
    r.raise_for_status()
    (DATA / name).write_text(r.text, encoding="utf-8")
    print("Salvo:", DATA / name)
