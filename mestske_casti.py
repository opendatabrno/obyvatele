"""Městské části statutárních měst (Praha, Brno, Ostrava, Plzeň, Pardubice, Opava,
Liberec, Ústí nad Labem) – spouští se ze zpracuj_data.py.

Výstup: vystup/obyvatele_mestske_casti.csv a .xlsx – jeden řádek = MČ × rok.
Cizinci nemají u MČ kód (kromě některých let), proto se párují podle názvu MČ v rámci
města na MČ ze souboru občanů téhož roku. Cizinci, u kterých MV MČ neurčilo, jsou
v řádku "nezjištěno" (bez kódu MČ), aby součet za město seděl na tabulku obcí.
"""
import re

import pandas as pd

from zpracuj_data import (CISELNE, CISELNIKY, PRAHA, VYSTUP, cislo, je_kod_obce, klic, nacti_excel,
                          norm, sloupce_cizincu, tabulka_cizincu_novy)

NEZJISTENO = "nezjištěno"

# v souborech cizinců 2014–2021 jsou v listu MČ všechna statutární města, i ta bez MČ
STATUTARNI = {norm(m) for m in [
    "Praha", "Brno", "Ostrava", "Plzeň", "Liberec", "Olomouc", "České Budějovice", "Hradec Králové",
    "Ústí nad Labem", "Pardubice", "Zlín", "Havířov", "Kladno", "Most", "Opava", "Frýdek-Místek",
    "Karviná", "Jihlava", "Teplice", "Děčín", "Karlovy Vary", "Jablonec nad Nisou", "Mladá Boleslav",
    "Prostějov", "Přerov", "Chomutov", "Třebíč", "Třinec", "Kroměříž"]}


def mesta_mc():
    """{kód MČ: kód města} z číselníku voleb."""
    c = pd.read_csv(CISELNIKY / "pscoco.csv")
    c = c[c.OBEC != c.OBEC_PREZ]
    return dict(zip(c.OBEC, c.OBEC_PREZ))


# --- občané ------------------------------------------------------------------

def nacti_obcany_mc(cesta, nazvy_obci):
    xl = nacti_excel(cesta)
    list_ = next(s for s in xl.sheet_names if klic(s).startswith("mestske casti"))
    df = pd.read_excel(xl, sheet_name=list_, header=None)
    radek, sloupec = next(
        (r, c) for r in range(15) for c in range(df.shape[1]) if klic(df.iat[r, c]) == "kraj"
    )
    hlavicka = [klic(x) for x in df.iloc[radek, sloupec:sloupec + 10]]
    assert hlavicka[4:9] == ["muzi", "muzi 15+", "zeny", "zeny 15+", "celkem"], hlavicka

    d = df.iloc[radek + 1:, sloupec:sloupec + 10]
    d.columns = ["kraj", "obvod", "kod_mc", "nazev_mc", "m", "m15", "z", "z15", "celkem", "c15"]
    d = d[d.kod_mc.map(je_kod_obce)].copy()
    d["kod_mc"] = d.kod_mc.astype(float).astype(int)
    for c in ["m", "m15", "z", "z15", "celkem", "c15"]:
        d[c] = cislo(d[c])

    mc_mesto = mesta_mc()
    def mesto(r):
        if r.kod_mc in mc_mesto:
            return mc_mesto[r.kod_mc]
        if klic(r.obvod).startswith("praha"):
            return PRAHA
        return nazvy_obci.get(norm(r.obvod))
    d["kod_obce"] = d.apply(mesto, axis=1)
    assert d.kod_obce.notna().all(), d[d.kod_obce.isna()]
    return pd.DataFrame({
        "kod_obce": d.kod_obce.astype(int),
        "kod_mc": d.kod_mc,
        "nazev_mc": d.nazev_mc.astype(str).str.strip(),
        "spravni_obvod": d.obvod.astype(str).str.strip().where(d.kod_obce == PRAHA),
        "obcane_celkem": d.celkem,
        "obcane_muzi": d.m,
        "obcane_zeny": d.z,
    })


# --- cizinci -----------------------------------------------------------------

def je_neurcena(nazev):
    k = klic(nazev)
    return k in ("", "*null", "null") or "prazdn" in k or "neurc" in k


def nacti_cizince_mc_stary(xl, nazvy_mest):
    """Formát 2014–2021: řádek města (velkými písmeny) a pod ním jeho MČ.

    Praha je navíc členěná podle správních obvodů ("PRAHA 4" a pod ním Praha 4,
    Praha 11, Praha-Kunratice …). Vrací řádky (kod_obce, mc, čísla).
    """
    list_ = next(s for s in xl.sheet_names if klic(s).startswith("mestske") or klic(s) == "mc")
    df = pd.read_excel(xl, sheet_name=list_, header=None)
    radek = next(r for r in range(15) if any(klic(x) == "mesto" for x in df.iloc[r]))
    sloupce = sloupce_cizincu(df.iloc[radek].ffill().map(klic), df.iloc[radek + 1].map(klic))
    chybi = set(CISELNE) - set(sloupce)
    assert not chybi, f"chybí sloupce {chybi}"
    jmeno = sloupce.get("nazev", sloupce["mesto"])
    kod = sloupce.get("kod")

    data = df.iloc[radek + 2:].reset_index(drop=True)
    text = lambda x: "" if pd.isna(x) else str(x).strip()
    nazvy = data.iloc[:, jmeno].map(text)
    kody = data.iloc[:, kod].map(text) if kod is not None else pd.Series("", index=data.index)
    # 2017: název města a "(prázdné)" jsou ve sloupci kódu, sloupec názvu je prázdný
    z_kodu = (nazvy == "") & (kody != "") & ~kody.map(je_kod_obce)
    nazvy = nazvy.where(~z_kodu, kody)
    kody = kody.map(klic)

    radky = []
    mesto = None
    for i, nazev in nazvy.items():
        if "soucet" in klic(nazev):
            break
        if not nazev and not kody[i]:
            continue
        dalsi = nazvy[i + 1] if i + 1 in nazvy.index else ""
        hlavicka = ((nazev.isupper() or norm(nazev) == norm(dalsi) or z_kodu[i]
                     or norm(nazev) in STATUTARNI) and not je_neurcena(nazev))
        if hlavicka:
            k = norm(nazev)
            mesto = PRAHA if re.fullmatch(r"praha( \d+)?", k) else nazvy_mest.get(k)
            continue
        if mesto is None:
            continue
        r = {c: data.iat[i, sloupce[c]] for c in CISELNE}
        r.update(kod_obce=mesto, mc=NEZJISTENO if je_neurcena(nazev) or "prazdn" in kody[i] else nazev)
        radky.append(r)
    out = pd.DataFrame(radky)
    for c in CISELNE:
        out[c] = cislo(out[c])
    return out


def nacti_cizince_mc_novy(xl, okresy_mest):
    """Formát od 2022: sloupec městská část u řádků statutárních měst."""
    out = tabulka_cizincu_novy(xl)
    klice = list(zip(out.okres.map(norm), out.obec.map(norm)))
    out["kod_obce"] = [okresy_mest.get(k) for k in klice]
    out = out[out.kod_obce.notna()].copy()
    out["kod_obce"] = out.kod_obce.astype(int)
    out["mc"] = out.mc.map(lambda x: NEZJISTENO if je_neurcena(x) else str(x).strip())
    return out[["kod_obce", "mc"] + CISELNE]


def paruj(ciz, ob):
    """Doplní kod_mc podle názvu MČ v rámci města; jinak jednoznačná shoda začátku názvu."""
    kandidati = {}
    for r in ob.itertuples():
        kandidati.setdefault(r.kod_obce, {})[norm(r.nazev_mc)] = r.kod_mc

    def najdi(r):
        if r.mc == NEZJISTENO:
            return None
        mc = kandidati.get(r.kod_obce, {})
        n = norm(r.mc)
        if n in mc:
            return mc[n]
        # "Praha-Újezd" ~ "Praha-Újezd u Průhonic", "Liberec (nečleněná část…)" ~ "Liberec"
        shoda = {k for nazev, k in mc.items() if nazev.startswith(n) or n.startswith(nazev)}
        return shoda.pop() if len(shoda) == 1 else None

    ciz = ciz.copy()
    ciz["kod_mc"] = ciz.apply(najdi, axis=1)
    return ciz


def zpracuj_mc(soubory, obce):
    """soubory: {rok: {"obcane": cesta, "cizinci": cesta}}, obce: hotová tabulka obcí."""
    nazvy_obci = {}
    okresy_mest = {}
    mesta = set(mesta_mc().values()) | {PRAHA}
    for r in obce[obce.kod_obce.isin(mesta)].drop_duplicates("kod_obce").itertuples():
        nazvy_obci[norm(r.nazev_obce)] = r.kod_obce
        okresy_mest[(norm(r.okres), norm(r.nazev_obce))] = r.kod_obce
    okresy_mest[("hlavní město praha", "praha")] = PRAHA

    radky, nesparovani = [], []
    for rok in sorted(soubory):
        print(f"{rok} MČ ...")
        ob = nacti_obcany_mc(soubory[rok]["obcane"], nazvy_obci)
        xl = nacti_excel(soubory[rok]["cizinci"])
        if any(klic(s) == "obce" for s in xl.sheet_names):
            mc_soubor = soubory[rok].get("cizinci_mc")  # 2014: MČ v samostatném souboru
            ciz = nacti_cizince_mc_stary(nacti_excel(mc_soubor) if mc_soubor else xl, nazvy_obci)
        else:
            ciz = nacti_cizince_mc_novy(xl, okresy_mest)
        ciz = ciz[ciz.kod_obce.isin(set(ob.kod_obce))]
        ciz = paruj(ciz, ob)

        chybi = ciz[(ciz.mc != NEZJISTENO) & ciz.kod_mc.isna()]
        if len(chybi):
            nesparovani.append(chybi.assign(rok=rok)[["rok", "kod_obce", "mc", "celkem"]])
        # nespárované MČ jdou do "nezjištěno", ať sedí součet za město
        ciz.loc[ciz.kod_mc.isna(), "mc"] = NEZJISTENO

        g = ciz.groupby(["kod_obce", ciz.kod_mc.fillna(0).astype(int)])[CISELNE].sum()
        g = pd.DataFrame({
            "cizinci_celkem": g.celkem, "cizinci_muzi": g.muzi, "cizinci_zeny": g.zeny,
            "cizinci_trvaly_pobyt": g.trvaly, "cizinci_prechodny_pobyt": g.prechodny,
        }).reset_index()
        # město bez cizinců po MČ (Opava 2015–2021 v listu "krajských měst" chybí):
        # všichni jeho cizinci do "nezjištěno" podle tabulky obcí
        bez_mc = set(ob.kod_obce) - set(g.kod_obce)
        if bez_mc:
            doplnek = obce[(obce.rok == rok) & obce.kod_obce.isin(bez_mc)][["kod_obce"] + [
                c for c in g.columns if c.startswith("cizinci_")]]
            g = pd.concat([g, doplnek.assign(kod_mc=0)], ignore_index=True)
        t = ob.merge(g, on=["kod_obce", "kod_mc"], how="outer")
        t.loc[t.kod_mc == 0, ["kod_mc", "nazev_mc"]] = [None, NEZJISTENO]
        cisla = [c for c in t.columns if c.startswith(("obcane_", "cizinci_"))]
        t[cisla] = t[cisla].fillna(0).astype(int)
        t.insert(0, "rok", rok)
        radky.append(t)

    vysledek = pd.concat(radky, ignore_index=True)
    vysledek["kod_mc"] = vysledek.kod_mc.astype("Int64")
    nazvy = obce.drop_duplicates("kod_obce").set_index("kod_obce").nazev_obce
    vysledek.insert(2, "nazev_obce", vysledek.kod_obce.map(nazvy))
    vysledek["obyvatele_celkem"] = vysledek.obcane_celkem + vysledek.cizinci_celkem
    poradi = ["rok", "kod_obce", "nazev_obce", "spravni_obvod", "kod_mc", "nazev_mc",
              "obyvatele_celkem",
              "obcane_celkem", "obcane_muzi", "obcane_zeny",
              "cizinci_celkem", "cizinci_muzi", "cizinci_zeny",
              "cizinci_trvaly_pobyt", "cizinci_prechodny_pobyt"]
    vysledek = vysledek[poradi].sort_values(["rok", "kod_obce", "kod_mc"], na_position="last")
    vysledek.to_csv(VYSTUP / "obyvatele_mestske_casti.csv", index=False, encoding="utf-8-sig")
    vysledek.to_excel(VYSTUP / "obyvatele_mestske_casti.xlsx", index=False, freeze_panes=(1, 0))

    cesta = VYSTUP / "mc_nesparovane.csv"
    if nesparovani:
        pd.concat(nesparovani).to_csv(cesta, index=False, encoding="utf-8-sig")
    else:
        cesta.unlink(missing_ok=True)

    # kontrola: součet MČ za město proti tabulce obcí
    mc_soucet = vysledek.groupby(["rok", "kod_obce"])[["obcane_celkem", "cizinci_celkem"]].sum()
    mesta_obce = obce.set_index(["rok", "kod_obce"]).loc[mc_soucet.index, ["obcane_celkem", "cizinci_celkem"]]
    rozdil = (mc_soucet - mesta_obce).rename(columns=lambda c: c + "_rozdil")
    kontrola = pd.concat([mc_soucet, rozdil], axis=1).reset_index()
    kontrola.insert(2, "nazev_obce", kontrola.kod_obce.map(nazvy))
    kontrola.to_csv(VYSTUP / "kontrola_mc.csv", index=False, encoding="utf-8-sig")
    odchylky = kontrola[(kontrola.obcane_celkem_rozdil != 0) | (kontrola.cizinci_celkem_rozdil != 0)]
    if len(odchylky):
        print("Součty MČ nesedí na obce:")
        print(odchylky.to_string(index=False))
    print(f"Hotovo: {len(vysledek)} řádků -> {VYSTUP / 'obyvatele_mestske_casti.csv'}")
