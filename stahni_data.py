"""Stažení lednových souborů MV ČR s informativními počty obyvatel v obcích.

Ukládá do složky data/ pod jednotnými názvy:
    YYYY-01 Čeští občané.xlsx
    YYYY-01 Cizinci s pobytem.xlsx
    YYYY-01 Dočasná ochrana.xlsx   (od 2023, snímek MV nejbližší 1. 1.)
Už stažené soubory přeskočí (pokud nepoužiješ --prepsat).

Zdroje:
  - archiv MV (2014–2025): pevný seznam odkazů níže
  - aktuální stránka MV: odkazy se hledají automaticky podle data "01-01-YYYY",
    takže v dalších letech stačí skript jen spustit.
  - dočasná ochrana: MV zveřejňuje týdenní snímky po obcích; bere se ten nejbližší
    1. lednu (2023–2026 pevně z archivu, další roky hledáním v archivu MV)
    a jeho datum se zapíše do ciselniky/docasna_ochrana_snimky.csv
  - číselník obcí s vazbou na okresy (volby.gov.cz) -> ciselniky/

Použití:
    python stahni_data.py            # vše, co chybí
    python stahni_data.py --prepsat  # stáhnout znovu
"""
import argparse
import csv
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CISELNIKY = ROOT / "ciselniky"

AKTUALNI = "https://mv.gov.cz/informativni-pocty-obyvatel-v-obcich-2"
ARCHIV = "https://archiv.mv.gov.cz/soubor/"
VOLBY = "https://volby.gov.cz/opendata/ps2025/csv_od/"

# rok -> (občané, cizinci); 2014 má cizince rozdělené na obce a městské části
ARCHIV_SOUBORY = {
    2014: ("pocet-obcane-leden14-xls", "obce-xls", "mc-xls"),
    2015: ("pocty-obyvatel-v-obcich-pocet-obcane-leden15-xlsx", "pocty-cizinci-01012015-xlsx"),
    2016: ("cr-pocet-obyvatel-k-1-1-2016-2-xlsx", "cizinci-xlsx"),
    2017: ("cr-pocet-obyvatel-k-01-01-2017-xlsx", "cizina-pocet-obyvatel-k-01-01-2017-xlsx"),
    2018: ("informativni-prehled-pocty-obcanu-cr-k-1-1-2018-xlsx", "informativni-prehled-pocty-cizincu-k-1-1-2018-xlsx"),
    2019: ("informativni-pocet-obcanu-cr-k-1-1-2019-xlsx", "informativni-pocet-cizincu-k-1-1-2019-xlsx"),
    2020: ("cr-pocet-obyvatel-k-1-1-2020-xlsx", "cizinci-2020-xlsx"),
    2021: ("cr-pocet-obyvatel-k-1-1-2021-xlsx", "cizinci-2021-xlsx"),
    2022: ("informativni-pocet-obcanu-cr-k-1-1-2022-xlsx", "pocty-obyvatel-v-obcich-informativni-pocet-cizincu-k-1-1-2022-xlsx"),
    2023: ("cr-pocet-obyvatel-k-1-1-2023-xlsx", "informativni-pocet-cizincu-k-01-01-2023-xlsx"),
    2024: ("cr-pocet-obyvatel-k-1-1-2024-xlsx", "informativni-pocet-cizincu-k-01-01-2024-xlsx"),
    2025: ("cr-pocet-obyvatel-k-1-1-2025-xlsx", "informativni-pocet-cizincu-k-01-01-2025-xlsx"),
}

# rok -> (soubor v archivu MV, stav ke dni) – snímek dočasné ochrany nejbližší 1. 1.
DO_ARCHIV = {
    2023: ("statistika-ukr-31-12-2022-xlsx", "2022-12-31"),
    2024: ("statistika-ukr-31-12-2023-xlsx", "2024-01-01"),
    2025: ("statistika-ukr-vse-29-12-2024-xlsx", "2024-12-30"),
    2026: ("statistika-obce-suk-vek-vse-28-12-2025-xlsx", "2025-12-29"),
}
DO_STRANKY = ["https://mv.gov.cz/statistika-v-souvislosti-s-valkou-na-ukrajine---archiv-{rok}", AKTUALNI]
DO_MAX_ODCHYLKA = 7  # dní od 1. 1.
DO_SNIMKY = CISELNIKY / "docasna_ochrana_snimky.csv"

HLAVICKY = {"User-Agent": "Mozilla/5.0 (data-obyvatele)"}


def nazev_souboru(rok, druh, pripona):
    jmena = {
        "obcane": "Čeští občané",
        "cizinci": "Cizinci s pobytem",
        "cizinci_mc": "Cizinci s pobytem - městské části",
        "docasna_ochrana": "Dočasná ochrana",
    }
    return DATA / f"{rok}-01 {jmena[druh]}.{pripona}"


def pripona_z_obsahu(obsah):
    # starší soubory .xls bývají ve skutečnosti xlsx (zip) a naopak
    return "xlsx" if obsah[:2] == b"PK" else "xls"


def uloz(url, rok, druh, prepsat):
    existujici = [p for p in DATA.glob(f"{rok}-01 *") if p.stem == nazev_souboru(rok, druh, "x").stem]
    if existujici and not prepsat:
        print(f"  {existujici[0].name} už existuje")
        return False
    r = requests.get(url, headers=HLAVICKY, timeout=60)
    r.raise_for_status()
    if r.content[:2] not in (b"PK", b"\xd0\xcf"):
        raise RuntimeError(f"{url} nevrátil Excel soubor")
    cil = nazev_souboru(rok, druh, pripona_z_obsahu(r.content))
    for p in existujici:
        p.unlink()
    cil.write_bytes(r.content)
    print(f"  staženo {cil.name} ({len(r.content) // 1024} kB)")
    return True


def odkazy_aktualni():
    """Najde na aktuální stránce MV lednové soubory: {rok: {druh: url}}."""
    html = requests.get(AKTUALNI, headers=HLAVICKY, timeout=60).text
    nalezeno = {}
    for url in set(re.findall(r'https://mv\.gov\.cz/documents/[^"\\?]+', html)):
        slug = url.rsplit("/", 1)[-1].lower()
        m = re.search(r"k0?1-0?1-(\d{4})", slug)
        if not m:
            continue
        if "cizinc" in slug:
            druh = "cizinci"
        elif "obcan" in slug or "obyvatel" in slug:
            druh = "obcane"
        else:
            continue
        nalezeno.setdefault(int(m.group(1)), {})[druh] = url + "?disposition=attachment"
    return nalezeno


def snimky_docasne_ochrany(rok):
    """Týdenní snímky dočasné ochrany na stránkách MV: [(stav ke dni, url)].

    Odkaz má tvar .../statistikaobcesuavekvse-2026-01-04 = stav k půlnoci ze 4. na 5. 1.
    """
    nalezeno = {}
    for stranka in {u.format(rok=r) for u in DO_STRANKY for r in (rok - 1, rok)}:
        try:
            html = requests.get(stranka, headers=HLAVICKY, timeout=60).text
        except requests.RequestException:
            continue
        for url, d in re.findall(r'(https://mv\.gov\.cz/documents/statistika[\w-]*?(\d{4}-\d{2}-\d{2}))', html):
            nalezeno[date.fromisoformat(d) + timedelta(days=1)] = url + "?disposition=attachment"
    return sorted(nalezeno.items())


def zapis_snimek(rok, stav_k, url):
    radky = {}
    if DO_SNIMKY.exists():
        with DO_SNIMKY.open(encoding="utf-8") as f:
            radky = {int(r["rok"]): r for r in csv.DictReader(f)}
    radky[rok] = {"rok": rok, "stav_k": stav_k, "url": url}
    with DO_SNIMKY.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["rok", "stav_k", "url"])
        w.writeheader()
        w.writerows(radky[r] for r in sorted(radky))


def stahni_docasnou_ochranu(roky, prepsat):
    for rok in roky:
        if rok in DO_ARCHIV:
            slug, stav_k = DO_ARCHIV[rok]
            url = f"{ARCHIV}{slug}.aspx"
        else:
            kandidati = [(abs((d - date(rok, 1, 1)).days), d, u) for d, u in snimky_docasne_ochrany(rok)]
            kandidati = [k for k in kandidati if k[0] <= DO_MAX_ODCHYLKA]
            if not kandidati:
                print(f"  {rok}: snímek dočasné ochrany do {DO_MAX_ODCHYLKA} dní od 1. 1. zatím není")
                continue
            _, d, url = min(kandidati)
            stav_k = d.isoformat()
        if uloz(url, rok, "docasna_ochrana", prepsat):
            zapis_snimek(rok, stav_k, url)


def stahni_ciselniky():
    CISELNIKY.mkdir(exist_ok=True)
    for jmeno in ("pscoco.csv", "cnumnuts.csv"):
        r = requests.get(VOLBY + jmeno, headers=HLAVICKY, timeout=60)
        r.raise_for_status()
        (CISELNIKY / jmeno).write_bytes(r.content)
    print("  číselníky obcí a okresů aktualizovány")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepsat", action="store_true", help="stáhnout i soubory, které už existují")
    args = ap.parse_args()
    DATA.mkdir(exist_ok=True)

    print("Archiv MV:")
    for rok, slugy in ARCHIV_SOUBORY.items():
        druhy = ("obcane", "cizinci", "cizinci_mc")
        for druh, slug in zip(druhy, slugy):
            uloz(f"{ARCHIV}{slug}.aspx", rok, druh, args.prepsat)

    print("Aktuální stránka MV:")
    for rok, soubory in sorted(odkazy_aktualni().items()):
        for druh, url in soubory.items():
            uloz(url, rok, druh, args.prepsat)

    print("Dočasná ochrana:")
    roky = sorted({int(p.name[:4]) for p in DATA.glob("????-01 Cizinci s pobytem.*")})
    stahni_docasnou_ochranu([r for r in roky if r >= 2023], args.prepsat)

    print("Číselníky:")
    stahni_ciselniky()


if __name__ == "__main__":
    sys.exit(main())
