"""Zpracování lednových souborů MV ČR do jedné tabulky obyvatel podle obcí.

Vstup:  data/YYYY-01 Čeští občané.xls(x), data/YYYY-01 Cizinci s pobytem.xls(x)
        ciselniky/pscoco.csv, ciselniky/cnumnuts.csv (stahni_data.py)
Výstup: vystup/obyvatele_obce.csv a .xlsx  – jeden řádek = obec × rok
        vystup/kontrola_souctu.csv         – součty za rok proti souborům MV
        vystup/cizinci_nesparovani.csv     – řádky cizinců bez přiřazeného kódu obce

Cizinci nemají v souborech od roku 2022 kód obce, kód se dohledává podle
názvu obce a okresu (číselník volby.gov.cz), pak podle názvů z let 2014–2021,
kdy kód v souborech byl, a nakonec podle jednoznačného názvu v kraji.

Použití:
    python zpracuj_data.py
"""
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CISELNIKY = ROOT / "ciselniky"
VYSTUP = ROOT / "vystup"

PRAHA = 554782


def bez_diakritiky(text):
    text = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in text if not unicodedata.combining(c))


def norm(text):
    """Text malými písmeny, s jednotnými mezerami a pomlčkami.

    Diakritika zůstává: Pohled a Pohleď jsou dvě obce v jednom okrese.
    """
    if pd.isna(text):
        return ""
    text = unicodedata.normalize("NFC", str(text)).lower()
    text = re.sub(r"[‐-―]", "-", text)
    text = re.sub(r"\s*-\s*", "-", text)
    return re.sub(r"\s+", " ", text).strip()


def klic(text):
    """Pro hlavičky tabulek: bez diakritiky."""
    return bez_diakritiky(norm(text))


def norm_okres(text):
    t = norm(text)
    return "praha" if klic(t) in ("hlavni mesto praha", "hlavni mesto paha", "praha") else t


def norm_kraj(text):
    t = klic(text).replace("kraj", "").strip()
    return "praha" if t.startswith("hlavni mesto") or t == "praha" else t


def nacti_excel(cesta, list_=None):
    engine = "openpyxl" if cesta.read_bytes()[:2] == b"PK" else "xlrd"
    xl = pd.ExcelFile(cesta, engine=engine)
    if list_ is None:
        return xl
    return pd.read_excel(xl, sheet_name=list_, header=None)


def je_kod_obce(x):
    try:
        return 500000 <= int(float(x)) <= 999999
    except (TypeError, ValueError):
        return False


def cislo(serie):
    return pd.to_numeric(serie, errors="coerce").fillna(0).astype(int)


# --- občané ČR ---------------------------------------------------------------

def nacti_obcany(cesta):
    xl = nacti_excel(cesta)
    list_ = next(s for s in xl.sheet_names if klic(s).startswith("obce") and "3" not in s)
    df = pd.read_excel(xl, sheet_name=list_, header=None)

    radek, sloupec = next(
        (r, c) for r in range(15) for c in range(df.shape[1]) if klic(df.iat[r, c]) == "kraj"
    )
    hlavicka = [klic(x) for x in df.iloc[radek, sloupec:sloupec + 10]]
    assert hlavicka[4:9] == ["muzi", "muzi 15+", "zeny", "zeny 15+", "celkem"], hlavicka

    d = df.iloc[radek + 1:, sloupec:sloupec + 10]
    d.columns = ["kraj", "orp", "kod_obce", "nazev_obce", "m", "m15", "z", "z15", "celkem", "c15"]
    d = d[d.kod_obce.map(je_kod_obce)].copy()
    d["kod_obce"] = d.kod_obce.astype(float).astype(int)
    for c in ["m", "m15", "z", "z15", "celkem", "c15"]:
        d[c] = cislo(d[c])
    return pd.DataFrame({
        "kod_obce": d.kod_obce,
        "nazev_obce": d.nazev_obce.astype(str).str.strip(),
        "orp": d.orp.astype(str).str.strip(),
        "kraj_mv": d.kraj.astype(str).str.strip(),
        "obcane_celkem": d.celkem,
        "obcane_muzi": d.m,
        "obcane_zeny": d.z,
    })


# --- cizinci, formát 2014–2021 (s kódem obce, dvouřádková hlavička) ----------

def sloupce_cizincu(horni, dolni):
    """Pozice sloupců v dvouřádkové hlavičce souborů cizinců 2014–2021."""
    sloupce = {}
    blok = None
    for j, (h, s) in enumerate(zip(horni, dolni)):
        # 2017: "Celkem" za blokem MUŽI/ŽENY je v horním řádku hlavičky
        if h == "celkem" and blok and blok not in sloupce:
            sloupce[blok] = j
            continue
        blok = h if h in ("muzi", "zeny") else None
        if s.startswith("kod"):  # 2017, MČ: "Město" nahoře, "kód obvodu" pod ním
            sloupce["kod"] = j
        elif h in ("kraj", "okres", "obec", "mesto"):
            sloupce.setdefault(h, j)
        elif h.startswith("kod"):
            sloupce["kod"] = j
        elif h in ("muzi", "zeny"):
            if s == "celkem":
                sloupce[h] = j
            elif s in ("do 15", "-15", "-15.0"):
                sloupce[h + "_deti"] = j
        elif h in ("cizinci celkem", "celkem cizincu"):
            sloupce["celkem"] = j
        elif "trval" in h or "trval" in s:
            sloupce["trvaly"] = j
        elif "prech" in h or "prech" in s:
            sloupce["prechodny"] = j
        if s.startswith("nazev"):
            sloupce["nazev"] = j
    return sloupce


CISELNE = ["muzi", "zeny", "muzi_deti", "zeny_deti", "celkem", "trvaly", "prechodny"]


def nacti_cizince_stary(xl):
    list_ = next(s for s in xl.sheet_names if klic(s) == "obce")
    df = pd.read_excel(xl, sheet_name=list_, header=None)

    radek = next(r for r in range(15) if any(klic(x).startswith("kod") for x in df.iloc[r]))
    sloupce = sloupce_cizincu(df.iloc[radek].ffill().map(klic), df.iloc[radek + 1].map(klic))
    chybi = {"kraj", "okres", "obec", "kod", "muzi", "zeny", "muzi_deti", "zeny_deti",
             "celkem", "trvaly", "prechodny"} - set(sloupce)
    assert not chybi, f"chybí sloupce {chybi}"

    data = df.iloc[radek + 2:]
    sloupce.pop("nazev", None)
    out = pd.DataFrame({k: data.iloc[:, j] for k, j in sloupce.items()})
    for c in CISELNE:
        out[c] = cislo(out[c])

    obce = out[out.kod.map(je_kod_obce)].copy()
    obce["kod_obce"] = obce.kod.astype(float).astype(int)

    # 2014: Praha je jen jako souhrnný řádek bez kódu ("Hlavní město Paha")
    if PRAHA not in set(obce.kod_obce):
        praha = out[~out.kod.map(je_kod_obce)
                    & out[["kraj", "okres", "obec"]].apply(
                        lambda r: any(norm_okres(x) == "praha" for x in r), axis=1)]
        praha = praha.loc[[praha.celkem.idxmax()]].assign(kod_obce=PRAHA)
        obce = pd.concat([obce, praha])

    nezjisteno = out[out.kod.map(klic).str.contains("prazdn") | out.obec.map(klic).str.contains("prazdn")
                     | out.kraj.map(klic).str.contains("prazdn")].celkem.sum()
    soucet = out[out.kod.map(klic).str.contains("soucet") | out.obec.map(klic).str.contains("soucet")].celkem.max()
    return obce, int(nezjisteno), soucet


# --- cizinci, formát od 2022 (bez kódu obce, jen názvy) ---------------------

def tabulka_cizincu_novy(xl):
    """Řádky souboru cizinců od 2022 včetně sloupce městské části (mc)."""
    df = pd.read_excel(xl, sheet_name=xl.sheet_names[0], header=None)
    radek = next(r for r in range(10) if klic(df.iat[r, 0]) == "kraj")
    hlavicka = df.iloc[radek].map(klic).tolist()
    data = df.iloc[radek + 1:].reset_index(drop=True)
    data.columns = hlavicka

    def sl(*nazvy):
        for n in nazvy:
            if n in hlavicka:
                return cislo(data[n])
        raise KeyError(nazvy)

    mc = next(h for h in hlavicka if h.endswith("mestska cast"))
    out = pd.DataFrame({
        "kraj": data["kraj"], "okres": data["okres"], "obec": data["obec"], "mc": data[mc],
        "celkem": sl("celkem"),
        "trvaly": sl("trvaly pobyt", "trvale"),
        "prechodny": sl("prechodny pobyt", "prechodne"),
    })
    if "muzi<15" in hlavicka:  # 2022: sloupce Muži/Ženy jsou jen 15+
        out["muzi_deti"], out["zeny_deti"] = sl("muzi<15"), sl("zeny<15")
        out["muzi"], out["zeny"] = sl("muzi") + out.muzi_deti, sl("zeny") + out.zeny_deti
    else:
        out["muzi"], out["zeny"] = sl("muzi"), sl("zeny")
        out["muzi_deti"], out["zeny_deti"] = out.muzi - sl("muzi 15+"), out.zeny - sl("zeny 15+")
    return out


def nacti_cizince_novy(xl):
    out = tabulka_cizincu_novy(xl).drop(columns="mc")
    neznama = out.obec.isna() | out.obec.map(klic).isin(["*null", "null", ""])
    nezjisteno = int(out[neznama].celkem.sum())
    soucet = int(out.celkem.sum())
    obce = out[~neznama].groupby(["kraj", "okres", "obec"], as_index=False, dropna=False).sum(numeric_only=True)
    return obce, nezjisteno, soucet


# --- číselníky ---------------------------------------------------------------

def nacti_ciselnik():
    obce = pd.read_csv(CISELNIKY / "pscoco.csv")
    nuts = pd.read_csv(CISELNIKY / "cnumnuts.csv").set_index("NUMNUTS")
    obce = obce[obce.KRAJ.isin(nuts.index)]  # bez volebních okrsků v zahraničí
    obce = obce.drop_duplicates("OBEC_PREZ").copy()
    obce["kod_okresu"] = obce.OKRES.map(lambda k: "CZ0100" if k == 1100 else nuts.at[k, "NUTS"])
    obce["okres"] = obce.OKRES.map(lambda k: "Praha" if k == 1100 else nuts.at[k, "NAZEVNUTS"])
    obce["kod_kraje"] = obce.KRAJ.map(lambda k: nuts.at[k, "NUTS"])
    obce["kraj"] = obce.KRAJ.map(lambda k: nuts.at[k, "NAZEVNUTS"])
    # názvy obcí v číselníku voleb jsou pro statutární města po MČ; název celé obce z OBEC_PREZ
    return obce.rename(columns={"OBEC_PREZ": "kod_obce", "NAZEVOBCE": "nazev_cis"})[
        ["kod_obce", "nazev_cis", "kod_okresu", "okres", "kod_kraje", "kraj"]]


def main():
    VYSTUP.mkdir(exist_ok=True)
    ciselnik = nacti_ciselnik()

    soubory = {}
    for p in DATA.glob("????-01 *"):
        rok = int(p.name[:4])
        if "občané" in p.name:
            soubory.setdefault(rok, {})["obcane"] = p
        elif p.stem.endswith("Cizinci s pobytem"):
            soubory.setdefault(rok, {})["cizinci"] = p
        elif p.stem.endswith("Cizinci s pobytem - městské části"):
            soubory.setdefault(rok, {})["cizinci_mc"] = p

    obcane, cizinci = {}, {}
    kontrola = []
    for rok in sorted(soubory):
        print(f"{rok} ...")
        obcane[rok] = nacti_obcany(soubory[rok]["obcane"])
        xl = nacti_excel(soubory[rok]["cizinci"])
        stary = any(klic(s) == "obce" for s in xl.sheet_names)
        obce, nezjisteno, soucet = (nacti_cizince_stary if stary else nacti_cizince_novy)(xl)
        cizinci[rok] = (obce, stary)
        kontrola.append({"rok": rok, "cizinci_soucet_mv": soucet, "cizinci_bez_adresy": nezjisteno})

    # slovník (okres, název) -> kód obce: číselník voleb + historické soubory cizinců s kódy
    # Názvy, které v okrese odpovídají více obcím (Mezholezy v okrese Domažlice, Březina
    # v Brně-venkově), se automaticky nepárují. MV je obvykle odliší "PSČ xxxxx" v názvu
    # a takové názvy se naučíme ze souborů 2014–2021; zbytek řeší ruční tabulka.
    kandidati = {}
    for _, r in ciselnik.iterrows():
        kandidati.setdefault((norm_okres(r.okres), norm(r.nazev_cis)), set()).add(r.kod_obce)
    historicke = {}  # jen názvy, které číselník nezná (např. "Březina PSČ 66601")
    for rok, (obce, stary) in cizinci.items():
        if stary:
            for _, r in obce.iterrows():
                klic_okres = (norm_okres(r.okres), norm(r.obec))
                if klic_okres not in kandidati:
                    historicke.setdefault(klic_okres, set()).add(r.kod_obce)
    kandidati.update(historicke)
    podle_okresu = {k: next(iter(v)) for k, v in kandidati.items() if len(v) == 1}
    rucni = pd.read_csv(CISELNIKY / "rucni_parovani.csv", comment="#")
    for _, r in rucni.iterrows():
        podle_okresu[(norm_okres(r.okres), norm(r.obec))] = int(r.kod_obce)
    podle_okresu[("praha", "praha")] = PRAHA

    nesparovani = []
    radky = []
    for rok in sorted(soubory):
        ob = obcane[rok]
        obce, stary = cizinci[rok]
        if not stary:
            # záloha: jednoznačný název obce v kraji podle občanů téhož roku
            ob_kraj = ob.assign(k=ob.kraj_mv.map(norm_kraj), n=ob.nazev_obce.map(norm))
            jednoznacne = ob_kraj.groupby(["k", "n"]).kod_obce.agg(lambda s: s.iloc[0] if len(s) == 1 else None)
            def najdi(r):
                klic_okres = (norm_okres(r.okres), norm(r.obec))
                kod = podle_okresu.get(klic_okres)
                if kod is not None:
                    return kod, "okres"
                if klic_okres in kandidati:  # název v okrese patří více obcím -> nehádat
                    return None, "nejednoznačné"
                return jednoznacne.get((norm_kraj(r.kraj), norm(r.obec))), "kraj"
            obce[["kod_obce", "parovani"]] = obce.apply(najdi, axis=1, result_type="expand")
            podle_kraje = obce[obce.parovani.eq("kraj") & obce.kod_obce.notna()]
            if len(podle_kraje):
                print(f"  spárováno jen podle kraje: {', '.join(podle_kraje.obec.astype(str))}")
            chybi = obce[obce.kod_obce.isna()]
            if len(chybi):
                nesparovani.append(chybi.assign(rok=rok))
            obce = obce.dropna(subset=["kod_obce"])
            obce["kod_obce"] = obce.kod_obce.astype(int)

        ciz = obce.groupby("kod_obce")[["celkem", "muzi", "zeny", "muzi_deti", "zeny_deti",
                                         "trvaly", "prechodny"]].sum()
        ciz = pd.DataFrame({
            "cizinci_celkem": ciz.celkem, "cizinci_muzi": ciz.muzi, "cizinci_zeny": ciz.zeny,
            "cizinci_trvaly_pobyt": ciz.trvaly, "cizinci_prechodny_pobyt": ciz.prechodny,
        })
        mimo = set(ciz.index) - set(ob.kod_obce)
        if mimo:
            print(f"  pozor: cizinci v obcích, které nejsou v souboru občanů: {sorted(mimo)}")

        # outer: cizinci v obci chybějící u občanů (např. vojenský újezd) se neztratí
        t = ob.merge(ciz, left_on="kod_obce", right_index=True, how="outer")
        nazvy = ciselnik.set_index("kod_obce").nazev_cis
        t["nazev_obce"] = t.nazev_obce.fillna(t.kod_obce.map(nazvy))
        cisla = [c for c in t.columns if c.startswith(("obcane_", "cizinci_"))]
        t[cisla] = t[cisla].fillna(0).astype(int)
        t.insert(0, "rok", rok)
        radky.append(t)

        k = next(x for x in kontrola if x["rok"] == rok)
        k.update({
            "obcane_celkem": int(ob.obcane_celkem.sum()),
            "cizinci_prirazeno_obcim": int(ciz.cizinci_celkem.sum()),
            "cizinci_nesparovano": int(sum(c.celkem.sum() for c in nesparovani if c.rok.iat[0] == rok)),
            "obce_sparovane_jen_podle_kraje": 0 if stary else len(podle_kraje),
        })

    vysledek = pd.concat(radky, ignore_index=True)
    popis = ["nazev_obce", "orp", "kraj_mv"]
    vysledek[popis] = vysledek.groupby("kod_obce")[popis].transform(lambda s: s.ffill().bfill())
    vysledek = vysledek.merge(ciselnik.drop(columns="nazev_cis"), on="kod_obce", how="left")
    # obce, které už v aktuálním číselníku nejsou: kraj aspoň z MV
    kraje = ciselnik.drop_duplicates("kraj").set_index(ciselnik.drop_duplicates("kraj").kraj.map(norm_kraj))
    chybi_kraj = vysledek.kraj.isna()
    vysledek.loc[chybi_kraj, "kod_kraje"] = vysledek.kraj_mv[chybi_kraj].map(norm_kraj).map(kraje.kod_kraje)
    vysledek.loc[chybi_kraj, "kraj"] = vysledek.kraj_mv[chybi_kraj].map(norm_kraj).map(kraje.kraj)
    vysledek["obyvatele_celkem"] = vysledek.obcane_celkem + vysledek.cizinci_celkem

    poradi = ["rok", "kod_obce", "nazev_obce", "orp", "kod_okresu", "okres", "kod_kraje", "kraj",
              "obyvatele_celkem",
              "obcane_celkem", "obcane_muzi", "obcane_zeny",
              "cizinci_celkem", "cizinci_muzi", "cizinci_zeny",
              "cizinci_trvaly_pobyt", "cizinci_prechodny_pobyt"]
    vysledek = vysledek[poradi].sort_values(["rok", "kod_obce"])

    vysledek.to_csv(VYSTUP / "obyvatele_obce.csv", index=False, encoding="utf-8-sig")
    vysledek.to_excel(VYSTUP / "obyvatele_obce.xlsx", index=False, freeze_panes=(1, 0))
    pd.DataFrame(kontrola).to_csv(VYSTUP / "kontrola_souctu.csv", index=False, encoding="utf-8-sig")
    if nesparovani:
        pd.concat(nesparovani)[["rok", "kraj", "okres", "obec", "celkem"]].to_csv(
            VYSTUP / "cizinci_nesparovani.csv", index=False, encoding="utf-8-sig")
    else:
        (VYSTUP / "cizinci_nesparovani.csv").unlink(missing_ok=True)

    print(pd.DataFrame(kontrola).to_string(index=False))
    print(f"Hotovo: {len(vysledek)} řádků -> {VYSTUP / 'obyvatele_obce.csv'}")

    from mestske_casti import zpracuj_mc
    zpracuj_mc(soubory, vysledek)


if __name__ == "__main__":
    sys.exit(main())
