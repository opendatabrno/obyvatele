"""Stažení lednových souborů MV ČR s informativními počty obyvatel v obcích.

Ukládá do složky data/ pod jednotnými názvy:
    YYYY-01 Čeští občané.xlsx
    YYYY-01 Cizinci s pobytem.xlsx
Už stažené soubory přeskočí (pokud nepoužiješ --prepsat).

Zdroje:
  - archiv MV (2014–2025): pevný seznam odkazů níže
  - aktuální stránka MV: odkazy se hledají automaticky podle data "01-01-YYYY",
    takže v dalších letech stačí skript jen spustit.
  - číselník obcí s vazbou na okresy (volby.gov.cz) -> ciselniky/

Použití:
    python stahni_data.py            # vše, co chybí
    python stahni_data.py --prepsat  # stáhnout znovu
"""
import argparse
import re
import sys
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

HLAVICKY = {"User-Agent": "Mozilla/5.0 (data-obyvatele)"}


def nazev_souboru(rok, druh, pripona):
    jmena = {
        "obcane": "Čeští občané",
        "cizinci": "Cizinci s pobytem",
        "cizinci_mc": "Cizinci s pobytem - městské části",
    }
    return DATA / f"{rok}-01 {jmena[druh]}.{pripona}"


def pripona_z_obsahu(obsah):
    # starší soubory .xls bývají ve skutečnosti xlsx (zip) a naopak
    return "xlsx" if obsah[:2] == b"PK" else "xls"


def uloz(url, rok, druh, prepsat):
    existujici = [p for p in DATA.glob(f"{rok}-01 *") if p.stem == nazev_souboru(rok, druh, "x").stem]
    if existujici and not prepsat:
        print(f"  {existujici[0].name} už existuje")
        return
    r = requests.get(url, headers=HLAVICKY, timeout=60)
    r.raise_for_status()
    if r.content[:2] not in (b"PK", b"\xd0\xcf"):
        raise RuntimeError(f"{url} nevrátil Excel soubor")
    cil = nazev_souboru(rok, druh, pripona_z_obsahu(r.content))
    for p in existujici:
        p.unlink()
    cil.write_bytes(r.content)
    print(f"  staženo {cil.name} ({len(r.content) // 1024} kB)")


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

    print("Číselníky:")
    stahni_ciselniky()


if __name__ == "__main__":
    sys.exit(main())
