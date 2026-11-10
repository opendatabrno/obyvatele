"""Sestaví web pro GitHub Pages do složky _site/.

Úvodní stránka s popisem a odkazy ke stažení, přehled kontrol a samotná CSV.
Spouští ho workflow .github/workflows/pages.yml, lokálně:
    python web.py
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import kontrola

ROOT = Path(__file__).resolve().parent
VYSTUP = ROOT / "vystup"
WEB = ROOT / "_site"
REPO = "https://github.com/opendatabrno/obyvatele"

SADY = [
    ("obyvatele_obce.csv", "Obyvatelé obcí",
     "Všechny obce ČR, jeden řádek = obec × rok. Klíč rok + kod_obce."),
    ("obyvatele_mestske_casti.csv", "Obyvatelé městských částí",
     "MČ a obvody 8 statutárních měst (Praha, Brno, Ostrava, Plzeň, Pardubice, Opava, Liberec, "
     "Ústí nad Labem), jeden řádek = MČ × rok. Klíč rok + kod_mc."),
]

SLOUPCE = [
    ("rok", "rok, stav k 1. 1."),
    ("kod_obce, nazev_obce", "kód obce ČSÚ a název (u MČ kód a název města)"),
    ("orp, kod_okresu, okres, kod_kraje, kraj", "jen obce: ORP podle MV, okres a kraj podle číselníku"),
    ("spravni_obvod, kod_mc, nazev_mc", "jen MČ: správní obvod (Praha), kód a název MČ"),
    ("obyvatele_celkem", "občané ČR + cizinci s pobytem"),
    ("obyvatele_csu", "jen obce: oficiální počet obyvatel ČSÚ k 1. 1. (prázdné, dokud ho ČSÚ nezveřejní)"),
    ("odhad_csu", "obce: počet ČSÚ, a pro rok, který ČSÚ ještě nezveřejnil, odhad z dat MV; "
                  "MČ: odhad_csu města rozdělený na MČ podle Sčítání 2021"),
    ("obyvatele_scitani_2021, koef_obcane", "jen MČ: obyvatelé podle Sčítání 2021 (obvyklý pobyt) a podíl "
                                            "občanů z registru MV, kteří v MČ podle sčítání opravdu bydlí"),
    ("obcane_celkem, obcane_muzi, obcane_zeny", "občané ČR s trvalým pobytem"),
    ("cizinci_celkem, cizinci_muzi, cizinci_zeny", "cizinci s trvalým nebo přechodným pobytem nad 90 dní"),
    ("cizinci_trvaly_pobyt, cizinci_prechodny_pobyt", "cizinci podle typu pobytu (součet = cizinci_celkem)"),
    ("cizinci_docasna_ochrana", "z toho lidé s dočasnou ochranou (od 2023, část přechodného pobytu; "
                                "snímek MV nejbližší 1. 1.)"),
]


def velikost(cesta):
    mb = cesta.stat().st_size / 1_000_000
    return f"{mb:.1f} MB".replace(".", ",")


def main():
    if not (VYSTUP / "kontrola_souctu.csv").exists():
        print("Chybí výstupy ve vystup/ – nejdřív spusť zpracuj_data.py")
        return 1
    kontrola.main()
    shutil.rmtree(WEB, ignore_errors=True)
    WEB.mkdir()
    shutil.copy(VYSTUP / "kontrola.html", WEB / "kontrola.html")

    karty = []
    for soubor, nazev, popis in SADY:
        cesta = VYSTUP / soubor
        shutil.copy(cesta, WEB / soubor)
        # xlsx se v repozitáři neukládá, vzniká tady z CSV
        d = pd.read_csv(cesta, dtype={"cizinci_docasna_ochrana": "Int64"})
        xlsx = WEB / cesta.with_suffix(".xlsx").name
        d.to_excel(xlsx, index=False, freeze_panes=(1, 0))
        karty.append(
            f'<div class="karta ok"><h3>{nazev}</h3><p>{popis}</p>'
            f'<p class="meta">{d.rok.min()}–{d.rok.max()} · {kontrola.cislo(len(d))} řádků</p>'
            f'<div class="tlacitka"><a class="tlacitko" href="{soubor}" download>CSV · {velikost(cesta)}</a>'
            f'<a class="tlacitko druhe" href="{xlsx.name}" download>Excel · {velikost(xlsx)}</a></div></div>')
    sloupce = "".join(f"<tr><td><code>{s}</code></td><td>{p}</td></tr>" for s, p in SLOUPCE)
    stav = (VYSTUP / "kontrola_stav.txt").read_text(encoding="utf-8").strip()

    stranka = f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Obyvatelé obcí ČR</title><style>{kontrola.CSS}
.meta{{font-size:13px;margin-top:8px!important}}
.tlacitko{{display:inline-block;margin-top:12px;padding:7px 14px;border-radius:8px;background:var(--accent);
color:var(--panel);text-decoration:none;font-weight:600;font-size:14px}}
.tlacitko:hover{{filter:brightness(1.1)}}
.tlacitka{{display:flex;gap:8px;flex-wrap:wrap}}
.tlacitko.druhe{{background:transparent;color:var(--accent);box-shadow:inset 0 0 0 1.5px var(--accent)}}
a{{color:var(--info)}}
.odkazy{{display:flex;gap:16px;flex-wrap:wrap;margin-top:14px;align-items:center}}
</style></head><body><main>
<header><h1>Obyvatelé obcí ČR</h1>
<p>Informativní počty obyvatel ze souborů Ministerstva vnitra ČR, stav vždy k 1. lednu.</p>
<div class="odkazy">{kontrola.odznak(stav)}<a href="kontrola.html">Přehled kontrol</a>
<a href="{REPO}">Zdrojový kód a dokumentace</a></div></header>

<h2>Datové sady</h2>
<section class="karty">{''.join(karty)}</section>

<h2>Sloupce</h2>
<p class="popis">Kategorie se sčítají: muži + ženy = celkem, trvalý + přechodný pobyt = cizinci celkem,
občané + cizinci = obyvatelé celkem. Řádky obou tabulek nesčítej dohromady – MČ jsou části měst,
která jsou i v tabulce obcí.</p>
<div class="tab-obal"><table><thead><tr><th>Sloupec</th><th>Význam</th></tr></thead>
<tbody>{sloupce}</tbody></table></div>

<h2>Na co si dát pozor</h2>
<div class="panel"><ul>
<li>Nejde o oficiální počet obyvatel ČSÚ; MV počítá cizince s trvalým i přechodným pobytem nad 90 dní.</li>
<li>Od roku 2023 jsou mezi cizinci s přechodným pobytem i lidé s dočasnou ochranou (skok o ~450 tis.).
Pro srovnání v čase je odečti: <code>cizinci_celkem − cizinci_docasna_ochrana</code>.</li>
<li>Od roku 2022 nemají soubory cizinců kód obce, přiřazuje se podle okresu a názvu obce.</li>
<li>Cizinci, u kterých MV neurčilo adresu nebo městskou část, jsou mimo obce, resp. v řádku „nezjištěno“.</li>
</ul></div>

<footer>Zdroj: <a href="https://mv.gov.cz/informativni-pocty-obyvatel-v-obcich-2">MV ČR – informativní počty
obyvatel v obcích</a> · aktualizováno {datetime.now():%d. %m. %Y}</footer>
</main></body></html>"""
    (WEB / "index.html").write_text(stranka, encoding="utf-8")
    print(f"Web: {WEB}")


if __name__ == "__main__":
    sys.exit(main())
