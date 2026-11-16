"""MV, ČSÚ a sčítání: jak přesný je ČSÚ mezi sčítáními a jak daleko je od skutečnosti registr MV.

Počet obyvatel ČSÚ je změřený jen při sčítání. Mezi sčítáními ho ČSÚ dopočítává
z narozených, zemřelých a stěhování a po dalším sčítání stav k 1. 1. zpětně přepočítá.
V sadě OBY02A proto zůstávají vedle sebe dvě čísla pro stejný okamžik:
  - koncový stav k 31. 12. 2010 a 31. 12. 2020: dopočet od minulého sčítání (bez opravy)
  - počáteční stav k 1. 1. 2011 a 1. 1. 2021: přepočet podle Sčítání 2011 a 2021
Rozdíl je chyba, kterou dopočet ČSÚ za deset let nasbíral ("drift"). Stav k 1. 1. 2011
a 2021 je nejbližší skutečnosti, kterou máme po obcích, s ním se porovnává i MV.

Výstup do analyza/vystup/:
    scitani_obce.csv    obec: MV, ČSÚ před a po přepočtu, koeficienty 2011 a 2021
    scitani_cr.csv      ČR po letech 2004–2026: ČSÚ, MV a jejich poměr
    scitani_skupiny.csv souhrny podle velikosti obce

Použití (z kořene repozitáře, po zpracuj_data.py):
    python analyza/scitani.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CSU = ROOT / "data" / "csu" / "OBY02A.csv"
VYSTUP = Path(__file__).resolve().parent / "vystup"
SCITANI = (2011, 2021)
VELIKOSTI = [0, 200, 500, 2000, 10000, 50000, np.inf]
POPISY = ["do 199", "200–499", "500–1 999", "2 000–9 999", "10 000–49 999", "50 000+"]


def nacti_csu():
    d = pd.read_csv(CSU, dtype=str, usecols=["IndicatorType", "POHL2", "Roky", "UZ01234596C", "Hodnota"])
    d = d[(d.POHL2 == "0") & d.IndicatorType.isin(["2406P", "2406K2"]) & d.UZ01234596C.str.fullmatch(r"\d{6}")]
    d = d.assign(rok=d.Roky.astype(int), kod_obce=d.UZ01234596C.astype(int), h=d.Hodnota.astype(int))
    # koncový stav roku R = stav k 1. 1. roku R+1 před přepočtem
    k = d[d.IndicatorType == "2406K2"].assign(rok=lambda x: x.rok + 1)
    p = d[d.IndicatorType == "2406P"]
    return (p.set_index(["rok", "kod_obce"]).h.rename("csu"),
            k.set_index(["rok", "kod_obce"]).h.rename("csu_pred_prepoctem"))


def pct(x, des=1):
    return f"{x * 100:+.{des}f} %".replace(".", ",").replace("-", "−")


def main():
    VYSTUP.mkdir(exist_ok=True)
    mv = pd.read_csv(ROOT / "vystup" / "obyvatele_obce.csv")
    csu, pred = nacti_csu()
    m = mv.join(csu, on=["rok", "kod_obce"]).join(pred, on=["rok", "kod_obce"])

    # --- ČR po letech
    # jen obce (v ČSÚ jsou do 2022 se šestimístným kódem i MČ)
    cr = m.groupby("rok")[["obcane_celkem", "cizinci_celkem", "obyvatele_celkem", "csu",
                           "csu_pred_prepoctem"]].sum(min_count=1)
    cr.loc[~cr.index.isin(SCITANI), "csu_pred_prepoctem"] = np.nan
    cr["mv_proti_csu"] = cr.obyvatele_celkem / cr.csu - 1
    cr["podil_obcanu"] = (cr.csu - cr.cizinci_celkem) / cr.obcane_celkem
    cr["drift_csu"] = cr.csu_pred_prepoctem / cr.csu - 1
    cr.round(5).to_csv(VYSTUP / "scitani_cr.csv", encoding="utf-8")

    # --- obce při sčítáních
    t = m[m.rok.isin(SCITANI)].pivot_table(
        index="kod_obce", columns="rok",
        values=["obcane_celkem", "cizinci_celkem", "obyvatele_celkem", "csu", "csu_pred_prepoctem"])
    t.columns = [f"{a}_{b}" for a, b in t.columns]
    t = t.dropna(subset=["csu_2011", "csu_2021", "obcane_celkem_2011", "obcane_celkem_2021"])
    t = t[(t.obcane_celkem_2011 > 0) & (t.obcane_celkem_2021 > 0)]
    nazvy = mv.sort_values("rok").groupby("kod_obce")[["nazev_obce", "okres"]].last()
    t = nazvy.join(t, how="inner")
    for r in SCITANI:
        t[f"mv_proti_csu_{r}"] = t[f"obyvatele_celkem_{r}"] / t[f"csu_{r}"] - 1
        t[f"drift_{r}"] = t[f"csu_pred_prepoctem_{r}"] / t[f"csu_{r}"] - 1
        t[f"koef_{r}"] = (t[f"csu_{r}"] - t[f"cizinci_celkem_{r}"]) / t[f"obcane_celkem_{r}"]
    # odhad 2021 z dat MV s koeficientem ze Sčítání 2011 (jako by se deset let nic neopravovalo)
    t["odhad_2021_koef_2011"] = t.koef_2011 * t.obcane_celkem_2021 + t.cizinci_celkem_2021
    t["chyba_odhadu_2021"] = t.odhad_2021_koef_2011 / t.csu_2021 - 1
    cr.loc[2021, "odhad_koef_2011"] = t.odhad_2021_koef_2011.sum()
    cr["chyba_odhadu_koef_2011"] = cr.odhad_koef_2011 / cr.csu - 1
    cr.round(5).to_csv(VYSTUP / "scitani_cr.csv", encoding="utf-8")
    t["velikost"] = pd.cut(t.csu_2021, VELIKOSTI, labels=POPISY, right=False)
    t.round(5).to_csv(VYSTUP / "scitani_obce.csv", encoding="utf-8")

    def souhrn(g):
        out = {"obci": len(g), "obyvatel_2021": int(g.csu_2021.sum())}
        for r in SCITANI:
            out[f"mv_proti_csu_{r}_median"] = g[f"mv_proti_csu_{r}"].median()
            out[f"drift_{r}_median"] = g[f"drift_{r}"].median()
            out[f"drift_{r}_abs_median"] = g[f"drift_{r}"].abs().median()
            out[f"koef_{r}_median"] = g[f"koef_{r}"].median()
        out["koef_zmena_abs_median"] = (g.koef_2021 - g.koef_2011).abs().median()
        out["koef_korelace"] = g.koef_2011.corr(g.koef_2021)
        out["chyba_odhadu_2021_abs_median"] = g.chyba_odhadu_2021.abs().median()
        out["drift_2021_do_1pct"] = (g.drift_2021.abs() < 0.01).mean()
        out["odhad_2021_do_1pct"] = (g.chyba_odhadu_2021.abs() < 0.01).mean()
        out["odhad_lepsi_nez_csu"] = (g.chyba_odhadu_2021.abs() < g.drift_2021.abs()).mean()
        return pd.Series(out)

    skupiny = t.groupby("velikost", observed=True).apply(souhrn)
    skupiny.loc["všechny obce"] = souhrn(t)
    skupiny.round(5).to_csv(VYSTUP / "scitani_skupiny.csv", encoding="utf-8")

    pd.set_option("display.width", 250)
    print(cr.to_string())
    print(skupiny.T.to_string())
    for r in SCITANI:
        print(f"\nnejvětší drift {r} (obce nad 5 000):")
        print(t[t.csu_2021 >= 5000].sort_values(f"drift_{r}")[["nazev_obce", f"csu_{r}", f"drift_{r}",
              f"mv_proti_csu_{r}", f"koef_{r}"]].iloc[np.r_[0:5, -5:0]].to_string())
    print(t.loc[[554782, 582786, 554821, 554791], ["nazev_obce", "drift_2011", "drift_2021", "mv_proti_csu_2011",
          "mv_proti_csu_2021", "koef_2011", "koef_2021", "chyba_odhadu_2021"]].to_string())


if __name__ == "__main__":
    main()
