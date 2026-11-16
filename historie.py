"""Jednorázové očištění starších souborů MV: stav k 1. 1. 2004–2013.

Soubory MV před rokem 2014 mají čtyři různé formáty a nové už nevzniknou, proto se
nezpracovávají při každé aktualizaci. Tento skript je stáhne z archivu MV, převede na
jednotnou tabulku a výsledek uloží do repozitáře (složka historie/). zpracuj_data.py
pak historické roky jen připojí k rokům 2014+.

Formáty:
  2004–2006  okres + název obce (velkými písmeny), bez kódu obce; Praha rozdělená
             na části v "okresech" PRAHA 1–10. Kód obce se dohledává podle názvu.
  2007       kód obce ČSÚ; občané ČR, občané EU, cizinci (muži, ženy, celkem)
  2008–2012  kód obce ČSÚ; navíc počty osob 15+
  2013       občané ČR v jednom souboru, cizinci zvlášť po obcích a po MČ;
             cizinci poprvé s rozdělením na trvalý a přechodný pobyt

Výstup:
  historie/obce_2004_2013.csv           obec × rok
  historie/mestske_casti_2007_2013.csv  MČ × rok (starší soubory MČ nemají)
  historie/kontrola_2004_2013.csv       součty proti řádkům "Celkem" v souborech MV
  historie/parovani_2004_2006.csv       jak se řádkům bez kódu obce přiřadil kód

Použití:
    python historie.py             # stáhne, co chybí, a vše zpracuje
    python historie.py --prepsat   # stáhne soubory znovu
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd
import requests

from zpracuj_data import PRAHA, cislo, je_kod_obce, klic, nacti_ciselnik, nacti_excel, norm, norm_okres

ROOT = Path(__file__).resolve().parent
ZDROJ = ROOT / "data" / "historie"
CIL = ROOT / "historie"
ARCHIV = "https://archiv.mv.gov.cz/soubor/{}.aspx"
HLAVICKY = {"User-Agent": "Mozilla/5.0 (data-obyvatele)"}

# rok -> {druh: soubor v archivu MV}; stav k 1. 1. daného roku
SOUBORY = {
    2004: {"obyvatele": "statistiky-20031231-2004-xls"},
    2005: {"obyvatele": "statistiky-20041231-2005-xls"},
    2006: {"obyvatele": "pocet-obcane-leden06-2-xls"},
    2007: {"obyvatele": "pocet-obcane-leden07-xls"},
    2008: {"obyvatele": "pocet-obcane-leden08-xls"},
    2009: {"obyvatele": "statistiky-pocet-obcane-leden09-xls"},
    2010: {"obyvatele": "pocet-obcane-leden2010-xls"},
    2011: {"obyvatele": "pocet-obcane-leden2011-xls"},
    2012: {"obyvatele": "pocet-obcane-leden12-xls"},
    2013: {"obcane": "pocet-obcanecr20130101-xls",
           "cizinci": "obce-vse-uprav-web-xlsx",
           "cizinci_mc": "mestske-casti-uprav3-web1-xlsx"},
}

SLOUPCE = ["rok", "kod_obce", "nazev_obce",
           "obcane_celkem", "obcane_muzi", "obcane_zeny", "obcane_15plus",
           "cizinci_celkem", "cizinci_muzi", "cizinci_zeny", "cizinci_15plus", "cizinci_eu",
           "cizinci_trvaly_pobyt", "cizinci_prechodny_pobyt"]


def stahni(prepsat=False):
    ZDROJ.mkdir(parents=True, exist_ok=True)
    cesty = {}
    for rok, druhy in SOUBORY.items():
        for druh, slug in druhy.items():
            cesta = ZDROJ / f"{rok}-01 {druh}.xls{'x' if slug.endswith('xlsx') else ''}"
            if prepsat or not cesta.exists():
                r = requests.get(ARCHIV.format(slug), headers=HLAVICKY, timeout=120)
                r.raise_for_status()
                if r.content[:2] not in (b"PK", b"\xd0\xcf"):
                    raise RuntimeError(f"{slug} nevrátil Excel")
                cesta.write_bytes(r.content)
                print(f"  staženo {cesta.name}")
            cesty.setdefault(rok, {})[druh] = cesta
    return cesty


def list_(cesta, zacatek):
    xl = nacti_excel(cesta)
    jmeno = next(s for s in xl.sheet_names if klic(s).startswith(zacatek))
    return pd.read_excel(xl, sheet_name=jmeno, header=None)


def najdi_hlavicku(df, text, radku=15):
    """(řádek, sloupec) první buňky s textem (bez diakritiky, malými písmeny)."""
    return next((r, c) for r in range(radku) for c in range(df.shape[1]) if klic(df.iat[r, c]) == text)


# --- 2004–2006: bez kódu obce ------------------------------------------------

def nacti_bez_kodu(rok, cesta):
    """Řádky okres, obec, čísla. Praha je v "okresech" PRAHA 1–10 po částech -> jeden řádek."""
    xl = nacti_excel(cesta)
    if rok == 2005:  # dva listy: občané a cizinci (jen obce, kde nějaký cizinec je)
        ob = pd.read_excel(xl, sheet_name=0, header=None).iloc[:, :5]
        ciz = pd.read_excel(xl, sheet_name=1, header=None).iloc[:, :5]
        ob.columns = ciz.columns = ["okres", "obec", "m", "z", "c"]
        ob, ciz = (d[pd.to_numeric(d.c, errors="coerce").notna()] for d in (ob, ciz))
        # list cizinců řadí některé obce do jiného okresu než list občanů (Kaly: Žďár × Brno-venkov),
        # proto se oba listy párují na kód obce zvlášť a sčítají se až podle kódu
        ciz = ciz.rename(columns={"m": "m_ciz", "z": "z_ciz", "c": "c_ciz"})
        je_celkem = lambda x: x.okres.map(klic).eq("celkem")
        celkem = ob[je_celkem(ob)].iloc[:1].merge(ciz[je_celkem(ciz)].iloc[:1].drop(columns=["obec"]), on="okres")
        df = pd.concat([celkem, ob[~je_celkem(ob)], ciz[~je_celkem(ciz)]], ignore_index=True)
    else:
        df = pd.read_excel(xl, sheet_name=0 if rok == 2004 else "Statistiky 1.1.2006 - obce", header=None).iloc[:, :8]
        df.columns = ["okres", "obec", "m", "z", "c", "m_ciz", "z_ciz", "c_ciz"]
        df = df[pd.to_numeric(df.c, errors="coerce").notna()]
    for c in ["m", "z", "c", "m_ciz", "z_ciz", "c_ciz"]:
        df[c] = cislo(df[c])
    df["okres"], df["obec"] = df.okres.astype(str).str.strip(), df.obec.astype(str).str.strip()
    celkem_radek = df.okres.map(klic).eq("celkem")
    soucet = df[celkem_radek].iloc[0]
    df = df[~celkem_radek].copy()
    praha = df.okres.map(klic).str.fullmatch(r"praha \d+")
    if praha.any():
        p = df[praha][["m", "z", "c", "m_ciz", "z_ciz", "c_ciz"]].sum()
        df = pd.concat([df[~praha], pd.DataFrame([{"okres": "Praha", "obec": "PRAHA", **p}])], ignore_index=True)
    kontrola = {"obcane_soubor": int(soucet.c), "cizinci_soubor": int(soucet.c_ciz)}
    return df, kontrola


def zaklad_nazvu(text):
    """Název bez doplňků: "Březina (matrika Tišnov)", "Olší (okr. Jihlava)", "Mezholezy PSČ 34506"."""
    t = re.sub(r"\s*\((matrika|okr\.)[^)]*\)", "", str(text))
    return norm(re.sub(r"\s*PSČ\s*\d{3}\s*\d{2}", "", t))


def nazvy_csu():
    """{název: {kódy obcí}} ze sady ČSÚ OBY02A (obce od roku 2000 včetně zaniklých)."""
    d = pd.read_csv(ROOT / "data" / "csu" / "OBY02A.csv", dtype=str, usecols=["Všechna území", "UZ01234596C"])
    d = d[d.UZ01234596C.str.fullmatch(r"\d{6}")].drop_duplicates()
    out = {}
    for nazev, kod in zip(d["Všechna území"], d.UZ01234596C):
        out.setdefault(zaklad_nazvu(nazev), set()).add(int(kod))
    return out


def paruj_nazvy(roky_bez_kodu, ciselnik, s_kodem):
    """Kód obce pro řádky 2004–2006 podle okresu a názvu.

    Okresy obcí se od té doby měnily (2005 přesun obcí z Vysočiny do Jihomoravského kraje,
    2007 a 2021 úpravy okresů), proto se název hledá i v celé ČR a kandidát se ověří
    velikostí: počet občanů z MV musí odpovídat počtu obyvatel obce podle ČSÚ téhož roku.

    0. ruční tabulka historie/rucni_parovani_2004_2006.csv
    1. Praha a městské části 8 měst (Brno-Bohunice, Plzeň 1 …) -> celé město
    2. aktuální číselník: obec toho názvu v okrese (při více obcích rozhodne velikost)
    3. název v celé ČR (číselník, MV 2007–2012, ČSÚ včetně zaniklých obcí) mimo kódy už
       přiřazené v kroku 2: jediný kandidát, nebo ten, jehož velikost sedí výrazně nejlíp
    Řádky jen s cizinci (2005, list cizinců má starší okresy) se párují podle roku 2004.
    """
    v_okrese, v_cr = {}, {}
    for r in ciselnik.itertuples():
        v_okrese.setdefault((norm_okres(r.okres), zaklad_nazvu(r.nazev_cis)), set()).add(r.kod_obce)
    # názvy z MV 2007–2012 v aktuálním okrese obce (statutární města mají v číselníku voleb jen MČ)
    okres_kodu = dict(zip(ciselnik.kod_obce, ciselnik.okres.map(norm_okres)))
    for r in s_kodem.itertuples():
        if r.kod_obce in okres_kodu:
            v_okrese.setdefault((okres_kodu[r.kod_obce], zaklad_nazvu(r.nazev_obce)), set()).add(r.kod_obce)
    zdroje = [((zaklad_nazvu(r.nazev_cis), r.kod_obce) for r in ciselnik.itertuples()),
              ((zaklad_nazvu(r.nazev_obce), r.kod_obce) for r in s_kodem.itertuples()),
              ((n, k) for n, kody in nazvy_csu().items() for k in kody)]
    # MČ 8 měst: názvy MČ z číselníku a začátek názvu "Brno-…", "Plzeň 3" v okrese města
    pscoco = pd.read_csv(ROOT / "ciselniky" / "pscoco.csv")
    mc = pscoco[pscoco.OBEC != pscoco.OBEC_PREZ]
    kody_mc = set(mc.OBEC)
    for zdroj in zdroje:
        for n, k in zdroj:
            if k not in kody_mc:
                v_cr.setdefault(n, set()).add(k)
    mesta = ciselnik[ciselnik.kod_obce.isin(set(mc.OBEC_PREZ))]
    okres_mesta = {r.kod_obce: norm_okres(r.okres) for r in mesta.itertuples()}
    mc_nazvy = {(okres_mesta[r.OBEC_PREZ], norm(r.NAZEVOBCE)): r.OBEC_PREZ for r in mc.itertuples()}
    predpony = {(norm_okres(r.okres), norm(r.nazev_cis)): r.kod_obce for r in mesta.itertuples()}
    csu = pd.read_csv(ROOT / "data" / "csu" / "pocet_obyvatel_obce.csv").set_index(["rok", "kod_obce"]).obyvatele_csu
    rucni = {}
    cesta = CIL / "rucni_parovani_2004_2006.csv"
    if cesta.exists():
        for r in pd.read_csv(cesta, comment="#").itertuples():
            rucni[(norm_okres(r.okres), norm(r.obec))] = int(r.kod_obce)

    def odchylka(rok, kod, mv):
        """Relativní rozdíl počtu z MV proti ČSÚ; malé obce mají v registru klidně o 50 % víc."""
        v = csu.get((rok, kod))
        return abs(mv - v) / max(v, 1) if v is not None else 9.0

    def nejblizsi(rok, kandidati, mv):
        """Jednoznačný kandidát, nebo ten, jehož velikost sedí výrazně líp než u ostatních."""
        if len(kandidati) <= 1:
            return next(iter(kandidati), None)
        poradi = sorted(kandidati, key=lambda k: odchylka(rok, k, mv))
        a, b = (odchylka(rok, k, mv) for k in poradi[:2])
        return poradi[0] if a < 0.5 and b > 2 * a + 0.05 else None

    def najdi(rok, okres, obec, mv, obsazene, predchozi, podle_obcanu, jen_okres):
        o, n = norm_okres(okres), norm(obec)
        if (o, n) in rucni:
            return rucni[(o, n)], "ručně"
        if o == "praha" and n == "praha":
            return PRAHA, "praha"
        if (o, n) in mc_nazvy:
            return mc_nazvy[(o, n)], "MČ"
        for (okres_m, mesto), kod in predpony.items():
            if o == okres_m and n != mesto and (n.startswith(mesto + "-") or n.startswith(mesto + " ")):
                return kod, "MČ"
        z = zaklad_nazvu(obec)
        if mv is None:  # řádek z listu cizinců (2005): podle listu občanů, roku 2004, okresu
            if (o, z) in stejny_rok:
                return stejny_rok[(o, z)], "cizinci, podle občanů"
            if (o, z) in predchozi:
                return predchozi[(o, z)], "jen cizinci, podle roku 2004"
            k = v_okrese.get((o, z), set())
            if len(k) == 1:
                return next(iter(k)), "jen cizinci, okres"
            k = podle_obcanu.get(z, set())
            return (next(iter(k)), "jen cizinci, podle občanů") if len(k) == 1 else (None, "jen cizinci, nenalezeno")
        k = v_okrese.get((o, z), set()) - obsazene
        if k:
            kod = nejblizsi(rok, k, mv)
            return (kod, "okres") if kod else (None, "více obcí v okrese")
        if jen_okres:
            return None, None
        kod = nejblizsi(rok, v_cr.get(z, set()) - obsazene, mv)
        if kod:
            return kod, "název v ČR a velikost"
        return None, "více kandidátů" if v_cr.get(z) else "nenalezeno"

    parovani, predchozi = [], {}
    for rok, df in sorted(roky_bez_kodu.items()):
        df["kod_obce"], df["parovani"] = None, None
        obc = df.c > 0
        mv = df.c + df.c_ciz
        # 1. průchod: okres; 2. průchod: celá ČR mimo kódy obsazené v 1. průchodu
        # stejný název víckrát v jednom okrese (Věžnice v okrese Jihlava 2004, jedna později v okrese
        # Havlíčkův Brod): kandidáti z okresu i z ČR, přiřadí se podle nejbližší velikosti podle ČSÚ
        klic_radku = pd.Series([(norm_okres(o), zaklad_nazvu(n)) for o, n in zip(df.okres, df.obec)], index=df.index)
        vicekrat = obc & klic_radku.where(obc).duplicated(keep=False)
        for _, skupina in df[vicekrat].groupby(klic_radku[vicekrat]):
            o, z = klic_radku[skupina.index[0]]
            kandidati = v_okrese.get((o, z), set()) | v_cr.get(z, set())
            pary = sorted((odchylka(rok, k, mv[i]), i, k) for i in skupina.index for k in kandidati)
            hotovo = set()
            for chyba, i, k in pary:
                if i in hotovo or k in set(df.kod_obce.dropna()) or chyba > 0.5:
                    continue
                df.loc[i, ["kod_obce", "parovani"]] = [k, "stejný název v okrese, velikost"]
                hotovo.add(i)
        # (větší obce napřed, každý kód obce jen jednou – kromě MČ velkých měst)
        for jen_okres in (True, False):
            obsazene = set(df.kod_obce.dropna().astype(int))
            for i in mv[obc & df.kod_obce.isna()].sort_values(ascending=False).index:
                kod, jak = najdi(rok, df.okres[i], df.obec[i], mv[i], obsazene, {}, {}, jen_okres)
                df.loc[i, ["kod_obce", "parovani"]] = [kod, jak]
                if kod and jak not in ("MČ", "praha"):
                    obsazene.add(kod)
        podle_obcanu, stejny_rok = {}, {}
        for r in df[obc & df.kod_obce.notna()].itertuples():
            podle_obcanu.setdefault(zaklad_nazvu(r.obec), set()).add(int(r.kod_obce))
            stejny_rok[(norm_okres(r.okres), zaklad_nazvu(r.obec))] = int(r.kod_obce)
        if (~obc).any():
            vysledek = [najdi(rok, r.okres, r.obec, None, set(), predchozi, podle_obcanu, False)
                        for r in df[~obc].itertuples()]
            df.loc[~obc, "kod_obce"] = [v[0] for v in vysledek]
            df.loc[~obc, "parovani"] = [v[1] for v in vysledek]
        predchozi = {(norm_okres(r.okres), zaklad_nazvu(r.obec)): int(r.kod_obce)
                     for r in df[df.kod_obce.notna()].itertuples()}
        parovani.append(df.assign(rok=rok)[["rok", "okres", "obec", "kod_obce", "parovani", "c", "c_ciz"]])
    return pd.concat(parovani, ignore_index=True)


# --- 2007–2013: s kódem obce --------------------------------------------------

# pořadí číselných sloupců za sloupcem s názvem obce / MČ
FORMAT_2007 = ["obcane_muzi", "obcane_zeny", "obcane_celkem", "eu_m", "eu_z", "cizinci_eu",
               "cizinci_muzi", "cizinci_zeny", "cizinci_celkem"]
FORMAT_2008 = ["obcane_muzi", "obcane_m15", "obcane_zeny", "obcane_z15", "obcane_celkem", "obcane_15plus",
               "eu_m", "eu_m15", "eu_z", "eu_z15", "cizinci_eu", "eu_15",
               "cizinci_muzi", "cizinci_m15", "cizinci_zeny", "cizinci_z15", "cizinci_celkem", "cizinci_15plus"]
FORMAT_2013 = FORMAT_2008[:6]


def nacti_s_kodem(rok, cesta, list_zacatek):
    """List Obce nebo Městské části: [kraj, ORP/obvod, kód, název, čísla…]."""
    df = list_(cesta, list_zacatek)
    radek, sloupec = najdi_hlavicku(df, "kraj (mesto)" if rok == 2007 and "mest" in list_zacatek else "kraj")
    format_ = FORMAT_2007 if rok == 2007 else FORMAT_2013 if rok == 2013 else FORMAT_2008
    d = df.iloc[:, sloupec:sloupec + 4 + len(format_)].copy()
    d.columns = ["kraj_mv", "nadrazena", "kod", "nazev"] + format_
    celkem = d[d.kraj_mv.map(klic).eq("celkem")].iloc[0]
    d = d[d.kod.map(je_kod_obce)].copy()
    d["kod"] = d.kod.astype(float).astype(int)
    for c in format_:
        d[c] = cislo(d[c])
    for text in ["kraj_mv", "nadrazena", "nazev"]:
        d[text] = d[text].astype(str).str.strip()
    kontrola = {"obcane_soubor": int(float(celkem.obcane_celkem))}
    if "cizinci_celkem" in format_:
        kontrola["cizinci_soubor"] = int(float(celkem.cizinci_celkem))
    return d, kontrola


def nacti_cizince_2013(cesta, mc=False):
    """Soubor cizinců k 1. 1. 2013: hierarchie kraj/okres (u MČ město/obvod), řádky s kódem jsou obce (MČ).

    Sloupce: muži 15+, do 15, celkem; ženy 15+, do 15, celkem; celkem; pobyt
    (u obcí trvalý, přechodný; u MČ přechodný, trvalý). Prázdné buňky = 0.
    """
    df = pd.read_excel(nacti_excel(cesta), header=None)
    radek, _ = najdi_hlavicku(df, "trvaly" if not mc else "prechodny", radku=12)
    pobyt = [klic(x) for x in df.iloc[radek]]
    s_kodem = 1 if not mc else 2
    j_nazev = 0 if not mc else 1
    zac = s_kodem + 1
    d = df.iloc[radek + 1:].reset_index(drop=True)
    cisla = pd.DataFrame({
        "m15": cislo(d[zac]), "m_deti": cislo(d[zac + 1]), "muzi": cislo(d[zac + 2]),
        "z15": cislo(d[zac + 3]), "z_deti": cislo(d[zac + 4]), "zeny": cislo(d[zac + 5]),
        "celkem": cislo(d[zac + 6]),
        "trvaly": cislo(d[pobyt.index("trvaly")]), "prechodny": cislo(d[pobyt.index("prechodny")]),
    })
    soucet = int(cisla.celkem[d[s_kodem if not mc else 1].map(klic).eq("celkovy soucet")].iloc[0])
    je_kod = d[s_kodem].map(je_kod_obce)
    radky = cisla[je_kod].assign(kod=d[s_kodem][je_kod].astype(float).astype(int).values,
                                nazev=d[j_nazev][je_kod].astype(str).str.strip().values)
    if not mc:
        # bez určené obce: řádek "(prázdné)" na konci
        # "(prázdné)" je kraj bez určené obce a pod ním ještě okresy -> první (krajský) řádek
        nezjisteno = int(cisla.celkem[d[1].map(klic).str.contains("prazdn", na=False)].iloc[0])
        return radky, soucet, nezjisteno
    # MČ: řádky města/obvodu (název ve sloupci kódu) a "neurčena MČ" pod ním
    mesto, neurcene = None, []
    for i in range(len(d)):
        t = d.iat[i, s_kodem]
        if isinstance(t, str) and not je_kod_obce(t) and klic(t) not in ("", "nan"):
            mesto = t.strip()
        elif klic(d.iat[i, j_nazev]).startswith("neurc"):
            neurcene.append({"mesto": mesto, **cisla.iloc[i].to_dict()})
    return radky, soucet, pd.DataFrame(neurcene)


def obce_s_kodem(rok, cesty):
    if rok == 2013:
        ob, kontrola = nacti_s_kodem(rok, cesty["obcane"], "obce")
        ciz, soucet, nezjisteno = nacti_cizince_2013(cesty["cizinci"])
        kontrola.update(cizinci_soubor=soucet, cizinci_bez_obce=nezjisteno)
        ciz = ciz.groupby("kod").sum(numeric_only=True)
        t = ob.merge(ciz, left_on="kod", right_index=True, how="outer")
        mimo = t[t.obcane_celkem.isna()]
        assert mimo.empty, f"2013: cizinci v obcích mimo soubor občanů {mimo.kod.tolist()}"
        cis = ["muzi", "zeny", "celkem", "m15", "z15", "trvaly", "prechodny"]
        t[cis] = t[cis].fillna(0).astype(int)
        t = t.assign(cizinci_celkem=t.celkem, cizinci_muzi=t.muzi, cizinci_zeny=t.zeny,
                     cizinci_15plus=t.m15 + t.z15, cizinci_trvaly_pobyt=t.trvaly,
                     cizinci_prechodny_pobyt=t.prechodny)
    else:
        t, kontrola = nacti_s_kodem(rok, cesty["obyvatele"], "obce")
    return t.rename(columns={"kod": "kod_obce", "nazev": "nazev_obce"}), kontrola


# --- městské části 2007–2013 --------------------------------------------------

def mc_roku(rok, cesty, obce_roku, mesta_mc, nazvy_mest):
    """MČ s kódem z listu Městské části; cizinci 2013 ze samostatného souboru.

    Co v součtu MČ chybí do čísla za město (cizinci bez určené MČ), jde do řádku
    "nezjištěno" bez kódu MČ, stejně jako v letech 2014+.
    """
    d, _ = nacti_s_kodem(rok, cesty["obcane" if rok == 2013 else "obyvatele"], "mestske casti")

    def mesto(r):
        if r.kod in mesta_mc:
            return mesta_mc[r.kod]
        if klic(r.nadrazena).startswith("praha") or klic(r.kraj_mv).startswith("hlavni mesto"):
            return PRAHA
        return nazvy_mest.get(norm(r.nadrazena))
    d["kod_obce"] = d.apply(mesto, axis=1)
    assert d.kod_obce.notna().all(), f"{rok}: MČ bez města\n{d[d.kod_obce.isna()]}"
    d["kod_obce"] = d.kod_obce.astype(int)
    d = d.rename(columns={"kod": "kod_mc", "nazev": "nazev_mc"})
    d["spravni_obvod"] = d.nadrazena.where(d.kod_obce == PRAHA)

    if rok == 2013:
        ciz, _, _ = nacti_cizince_2013(cesty["cizinci_mc"], mc=True)
        ciz = ciz.groupby("kod").sum(numeric_only=True)
        d = d.merge(ciz, left_on="kod_mc", right_index=True, how="left")
        cis = ["muzi", "zeny", "celkem", "trvaly", "prechodny"]
        d[cis] = d[cis].fillna(0).astype(int)
        d = d.assign(cizinci_celkem=d.celkem, cizinci_muzi=d.muzi, cizinci_zeny=d.zeny,
                     cizinci_trvaly_pobyt=d.trvaly, cizinci_prechodny_pobyt=d.prechodny)

    cisla = ["obcane_celkem", "obcane_muzi", "obcane_zeny", "cizinci_celkem", "cizinci_muzi", "cizinci_zeny"]
    if rok == 2013:
        cisla += ["cizinci_trvaly_pobyt", "cizinci_prechodny_pobyt"]
    d = d[["kod_obce", "kod_mc", "nazev_mc", "spravni_obvod"] + cisla]
    # zbytek do čísla za město -> "nezjištěno"
    mesta = obce_roku.set_index("kod_obce").loc[d.kod_obce.unique(), cisla]
    zbytek = (mesta - d.groupby("kod_obce")[cisla].sum()).reset_index()
    zbytek = zbytek[(zbytek[cisla] != 0).any(axis=1)]
    zaporne = zbytek[(zbytek[cisla] < 0).any(axis=1)]
    assert zaporne.empty, f"{rok}: součet MČ je větší než město\n{zaporne}"
    d = pd.concat([d, zbytek.assign(kod_mc=pd.NA, nazev_mc="nezjištěno")], ignore_index=True)
    return d.assign(rok=rok)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepsat", action="store_true", help="stáhnout soubory znovu")
    args = parser.parse_args()
    CIL.mkdir(exist_ok=True)
    cesty = stahni(args.prepsat)
    ciselnik = nacti_ciselnik()

    kontrola, s_kodem = [], {}
    for rok in range(2007, 2014):
        t, k = obce_s_kodem(rok, cesty[rok])
        s_kodem[rok] = t
        kontrola.append({"rok": rok, **k})
    bez_kodu = {}
    for rok in (2004, 2005, 2006):
        df, k = nacti_bez_kodu(rok, cesty[rok]["obyvatele"])
        bez_kodu[rok] = df
        kontrola.append({"rok": rok, **k})

    vzor = pd.concat([s_kodem[r] for r in range(2007, 2013)])[["kod_obce", "nazev_obce", "kraj_mv"]].drop_duplicates()
    parovani = paruj_nazvy(bez_kodu, ciselnik, vzor)
    parovani.to_csv(CIL / "parovani_2004_2006.csv", index=False, encoding="utf-8")
    chybi = parovani[parovani.kod_obce.isna()]
    if len(chybi):
        print(f"Nespárované řádky 2004–2006 ({len(chybi)}), doplň historie/rucni_parovani_2004_2006.csv:")
        print(chybi.to_string(index=False))

    radky = []
    for rok, df in bez_kodu.items():
        d = df.dropna(subset=["kod_obce"]).assign(kod_obce=lambda x: x.kod_obce.astype(int))
        # víc řádků na jeden kód je v pořádku u MČ velkých měst a v roce 2005 (občané a cizinci
        # jsou zvlášť řádky); jinde by to byla chyba párování
        if rok != 2005:
            dupl = d[d.kod_obce.duplicated(keep=False) & ~d.parovani.isin(["MČ", "praha"])]
            assert dupl.empty, f"{rok}: více řádků s jedním kódem obce\n{dupl}"
        nazev = d.groupby("kod_obce").obec.first()
        d = d.groupby("kod_obce")[["m", "z", "c", "m_ciz", "z_ciz", "c_ciz"]].sum().reset_index()
        radky.append(pd.DataFrame({
            "rok": rok, "kod_obce": d.kod_obce, "nazev_obce": d.kod_obce.map(nazev),
            "obcane_celkem": d.c, "obcane_muzi": d.m, "obcane_zeny": d.z,
            "cizinci_celkem": d.c_ciz, "cizinci_muzi": d.m_ciz, "cizinci_zeny": d.z_ciz,
        }))
    for rok, t in s_kodem.items():
        radky.append(t.assign(rok=rok))
    obce = pd.concat(radky, ignore_index=True)
    # 2004–2006 mají názvy velkými písmeny: název z let 2007–2013, u zaniklých obcí od ČSÚ
    d = pd.read_csv(ROOT / "data" / "csu" / "OBY02A.csv", dtype=str, usecols=["Všechna území", "UZ01234596C"])
    d = d[d.UZ01234596C.str.fullmatch(r"\d{6}")].drop_duplicates("UZ01234596C")
    nazvy = dict(zip(d.UZ01234596C.astype(int), d["Všechna území"].str.replace(r"\s*\(okr\.[^)]*\)", "", regex=True)))
    nazvy.update(obce[obce.rok >= 2007].sort_values("rok").groupby("kod_obce").nazev_obce.last())
    stare = obce.rok < 2007
    obce.loc[stare, "nazev_obce"] = obce.kod_obce[stare].map(nazvy).fillna(obce.nazev_obce[stare])
    obce = obce.reindex(columns=SLOUPCE)
    obce[SLOUPCE[3:]] = obce[SLOUPCE[3:]].astype("Int64")
    obce = obce.sort_values(["rok", "kod_obce"])
    obce.to_csv(CIL / "obce_2004_2013.csv", index=False, encoding="utf-8")

    for k in kontrola:
        r = obce[obce.rok == k["rok"]]
        k["obcane_tabulka"] = int(r.obcane_celkem.sum())
        k["cizinci_tabulka"] = int(r.cizinci_celkem.sum())
        k["obcane_nesparovano"] = int(chybi[chybi.rok == k["rok"]].c.sum())
        k["cizinci_nesparovano"] = int(chybi[chybi.rok == k["rok"]].c_ciz.sum())
    kontrola = pd.DataFrame(kontrola).sort_values("rok")
    kontrola.to_csv(CIL / "kontrola_2004_2013.csv", index=False, encoding="utf-8")
    print(kontrola.to_string(index=False))

    # MČ
    pscoco = pd.read_csv(ROOT / "ciselniky" / "pscoco.csv")
    pscoco = pscoco[pscoco.OBEC != pscoco.OBEC_PREZ]
    mesta_mc = dict(zip(pscoco.OBEC, pscoco.OBEC_PREZ))
    mesta = set(mesta_mc.values()) | {PRAHA}
    nazvy_mest = {norm(r.nazev_cis): r.kod_obce for r in ciselnik[ciselnik.kod_obce.isin(mesta)].itertuples()}
    mc = pd.concat([mc_roku(rok, cesty[rok], obce[obce.rok == rok], mesta_mc, nazvy_mest)
                    for rok in range(2007, 2014)], ignore_index=True)
    sl_mc = ["rok", "kod_obce", "kod_mc", "nazev_mc", "spravni_obvod",
             "obcane_celkem", "obcane_muzi", "obcane_zeny", "cizinci_celkem", "cizinci_muzi", "cizinci_zeny",
             "cizinci_trvaly_pobyt", "cizinci_prechodny_pobyt"]
    mc = mc.reindex(columns=sl_mc)
    mc[sl_mc[5:]] = mc[sl_mc[5:]].astype("Int64")
    mc["kod_mc"] = mc.kod_mc.astype("Int64")
    mc = mc.sort_values(["rok", "kod_obce", "kod_mc"], na_position="last")
    mc.to_csv(CIL / "mestske_casti_2007_2013.csv", index=False, encoding="utf-8")
    print(mc.groupby(["rok", "kod_obce"]).size().unstack().to_string())
    print(f"Hotovo: {len(obce)} řádků obcí, {len(mc)} řádků MČ -> {CIL}")


if __name__ == "__main__":
    sys.exit(main())
