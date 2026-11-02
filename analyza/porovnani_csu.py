"""Porovnání počtů obyvatel MV s oficiálními počty ČSÚ (stav k 1. 1., po obcích).

ČSÚ: datová sada OBY02A „Obyvatelstvo podle pohlaví“ (data.csu.gov.cz), ukazatel
„Počet obyvatel k 1. 1.“. Stáhne se do data/csu/ (není v repozitáři).

Výstup do analyza/vystup/:
    porovnani_obce.csv    – obec × rok: ČSÚ, složky MV a odhady ČSÚ z dat MV
    presnost_vzorcu.csv   – přesnost odhadů po letech (medián |chyby|, podíl obcí do 1 %)
    soucty_cr.csv         – celostátní součty ČSÚ a MV

Použití (z kořene repozitáře, po zpracuj_data.py):
    python analyza/porovnani_csu.py
"""
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
CSU = ROOT / "data" / "csu" / "OBY02A.csv"
CSU_URL = "https://data.csu.gov.cz/opendata/sady/OBY02A/distribuce/csv"
VYSTUP = Path(__file__).resolve().parent / "vystup"

# roky, kdy se mění metodika nebo základ (k těm se koeficient z minulého roku nehodí)
ZLOMY = {2021: "ČSÚ přepočítal počty podle Sčítání 2021",
         2023: "dočasná ochrana poprvé v datech MV i ČSÚ",
         2024: "ČSÚ a MV se srovnávají v započtení dočasné ochrany"}


def nacti_csu():
    if not CSU.exists():
        CSU.parent.mkdir(parents=True, exist_ok=True)
        print(f"Stahuji {CSU_URL} (~200 MB) …")
        with requests.get(CSU_URL, stream=True, timeout=600) as r:
            r.raise_for_status()
            with CSU.open("wb") as f:
                for kus in r.iter_content(1 << 20):
                    f.write(kus)
    d = pd.read_csv(CSU, dtype=str, usecols=["IndicatorType", "POHL2", "Roky", "UZ01234596C", "Hodnota"])
    # počet obyvatel k 1. 1., celkem; obce mají šestimístný kód (do 2022 jsou v sadě i MČ – vypadnou při spojení)
    d = d[(d.IndicatorType == "2406P") & (d.POHL2 == "0") & d.UZ01234596C.str.fullmatch(r"\d{6}")]
    return pd.DataFrame({"rok": d.Roky.astype(int), "kod_obce": d.UZ01234596C.astype(int),
                         "csu": d.Hodnota.astype(int)})


def main():
    VYSTUP.mkdir(exist_ok=True)
    mv = pd.read_csv(ROOT / "vystup" / "obyvatele_obce.csv")
    m = mv.merge(nacti_csu(), on=["rok", "kod_obce"], how="left").sort_values(["kod_obce", "rok"])
    m["docasna"] = m.cizinci_docasna_ochrana.fillna(0)

    # Koeficient obce: kolik občanů z registru MV ČSÚ skutečně počítá, když cizince bere všechny.
    # (ČSÚ − cizinci MV) / občané MV; pro odhad se bere z minulého roku.
    m["koef_obce"] = ((m.csu - m.cizinci_celkem) / m.obcane_celkem.where(m.obcane_celkem > 0))
    m["koef_obce_loni"] = m.groupby("kod_obce").koef_obce.shift(1)

    m["odhad_jednoduchy"] = m.obcane_celkem + m.cizinci_trvaly_pobyt + m.docasna
    m["odhad_koeficient"] = (m.koef_obce_loni * m.obcane_celkem + m.cizinci_celkem).round()
    m["csu_loni"] = m.groupby("kod_obce").csu.shift(1)

    odhady = {"obcane_celkem": "jen občané",
              "odhad_jednoduchy": "občané + cizinci TP + dočasná ochrana",
              "obyvatele_celkem": "všichni obyvatelé MV",
              "odhad_koeficient": "koeficient obce z loňska × občané + všichni cizinci",
              "csu_loni": "loňský počet ČSÚ"}
    radky = []
    for rok, g in m[m.csu > 0].groupby("rok"):
        for sloupec, popis in odhady.items():
            e = ((g[sloupec] - g.csu) / g.csu * 100).dropna()
            if len(e) < 1000:
                continue
            radky.append({"rok": rok, "odhad": popis, "obci": len(e),
                          "median_abs_chyba_pct": round(e.abs().median(), 2),
                          "podil_obci_do_1pct": round((e.abs() < 1).mean() * 100, 1),
                          "chyba_cr_pct": round((g.loc[e.index, sloupec].sum() / g.loc[e.index, "csu"].sum() - 1) * 100, 2),
                          "zlom": ZLOMY.get(rok, "")})
    presnost = pd.DataFrame(radky)

    cr = m.dropna(subset=["csu"]).groupby("rok")[
        ["csu", "obcane_celkem", "cizinci_trvaly_pobyt", "cizinci_prechodny_pobyt", "docasna", "cizinci_celkem"]].sum()
    cr["koef_cr"] = ((cr.csu - cr.cizinci_celkem) / cr.obcane_celkem).round(4)
    cr["csu_minus_mv"] = cr.csu - cr.obcane_celkem - cr.cizinci_celkem

    sloupce = ["rok", "kod_obce", "nazev_obce", "okres", "kraj", "csu", "obcane_celkem", "cizinci_trvaly_pobyt",
               "cizinci_prechodny_pobyt", "cizinci_docasna_ochrana", "obyvatele_celkem", "koef_obce",
               "odhad_jednoduchy", "odhad_koeficient"]
    m[sloupce].round({"koef_obce": 4}).to_csv(VYSTUP / "porovnani_obce.csv", index=False, encoding="utf-8-sig")
    presnost.to_csv(VYSTUP / "presnost_vzorcu.csv", index=False, encoding="utf-8-sig")
    cr.reset_index().to_csv(VYSTUP / "soucty_cr.csv", index=False, encoding="utf-8-sig")

    print(presnost.pivot(index="rok", columns="odhad", values="median_abs_chyba_pct").to_string())
    print(cr[["csu", "obcane_celkem", "cizinci_celkem", "koef_cr"]].to_string())
    print(f"Výstupy: {VYSTUP}")


if __name__ == "__main__":
    sys.exit(main())
