"""HTML přehled kontrol zpracování – vystup/kontrola.html.

Čte kontrolní CSV, které vytváří zpracuj_data.py, a skládá z nich jednu stránku
se semafory, grafem vývoje a tabulkami. Spouští se automaticky na konci
zpracuj_data.py, samostatně:
    python kontrola.py
"""
import html
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
VYSTUP = ROOT / "vystup"

# Rozdíly MČ proti obcím, které jsou už v datech MV (viz README); větší se hlásí.
TOLERANCE_OBCANE = 10
TOLERANCE_CIZINCI = 500
# Meziroční změna, nad kterou je nejspíš chyba v načtení (občané se mění o desetiny procenta).
MAX_ZMENA_OBCANE = 0.03
MAX_ZMENA_CIZINCI = 0.30

ZLOMY = {2022: "nový formát souboru cizinců (bez kódu obce)",
         2023: "nově započtena dočasná ochrana (sloupec cizinci_docasna_ochrana)"}
PRVNI_ROK_DO = 2023


def cislo(x):
    return "" if pd.isna(x) else f"{int(x):,}".replace(",", " ")


def esc(x):
    return html.escape("" if pd.isna(x) else str(x))


def nacti(jmeno):
    cesta = VYSTUP / jmeno
    return pd.read_csv(cesta) if cesta.exists() else pd.DataFrame()


# --- vyhodnocení -------------------------------------------------------------

def vyhodnot_soucty(k):
    k = k.copy()
    k["dopocet"] = k.cizinci_prirazeno_obcim + k.cizinci_bez_adresy + k.cizinci_nesparovano
    k["rozdil"] = k.cizinci_soucet_mv - k.dopocet
    cizinci = k.cizinci_soucet_mv.fillna(k.dopocet)
    k["zmena_obcane"] = k.obcane_celkem.pct_change()
    k["zmena_cizinci"] = cizinci.pct_change()
    k["stav"] = "ok"
    k.loc[k.cizinci_nesparovano > 0, "stav"] = "info"
    skok_cizinci = (k.zmena_cizinci.abs() > MAX_ZMENA_CIZINCI) & ~k.rok.isin(ZLOMY)
    chybi_do = (k.rok >= PRVNI_ROK_DO) & k.docasna_ochrana_celkem.isna()
    k.loc[(k.obce_sparovane_jen_podle_kraje > 0) | skok_cizinci | chybi_do, "stav"] = "varovani"
    k.loc[(k.rozdil.fillna(0) != 0) | (k.zmena_obcane.abs() > MAX_ZMENA_OBCANE), "stav"] = "chyba"
    return k


def vyhodnot_mc(m):
    m = m.copy()
    o, c = m.obcane_celkem_rozdil.abs(), m.cizinci_celkem_rozdil.abs()
    m["stav"] = "ok"
    m.loc[(o > 0) | (c > 0), "stav"] = "info"
    m.loc[(o > TOLERANCE_OBCANE) | (c > TOLERANCE_CIZINCI), "stav"] = "chyba"
    return m


# --- grafy (inline SVG) ------------------------------------------------------

def graf_vyvoj(k):
    """Dva sloupcové grafy vedle sebe: občané a cizinci podle let."""
    def sloupce(hodnoty, roky, trida, nadpis):
        w, h, pad_l, pad_b, pad_t = 460, 220, 8, 26, 26
        n = len(hodnoty)
        sirka = (w - pad_l * 2) / n
        maxi = max(hodnoty) or 1
        casti = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{nadpis}">',
                 f'<text x="{pad_l}" y="16" class="g-nadpis">{nadpis}</text>']
        for i, (v, r) in enumerate(zip(hodnoty, roky)):
            vyska = (h - pad_b - pad_t) * v / maxi
            x = pad_l + i * sirka + 3
            y = h - pad_b - vyska
            zlom = " zlom" if r in ZLOMY else ""
            casti.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{sirka - 6:.1f}" height="{vyska:.1f}" '
                         f'rx="2" class="{trida}{zlom}"><title>{r}: {cislo(v)}</title></rect>')
            casti.append(f'<text x="{x + (sirka - 6) / 2:.1f}" y="{h - 9}" class="g-osa">{str(r)[2:]}</text>')
        casti.append("</svg>")
        return "".join(casti)

    roky = k.rok.tolist()
    cizinci = k.cizinci_soucet_mv.fillna(k.dopocet).tolist()
    return ('<div class="grafy">'
            + sloupce(k.obcane_celkem.tolist(), roky, "s-obcane", "Občané ČR")
            + sloupce(cizinci, roky, "s-cizinci", "Cizinci s pobytem")
            + "</div>")


# --- sekce stránky -----------------------------------------------------------

STAVY = {"ok": ("V pořádku", "✓"), "info": ("Známý rozdíl", "i"),
         "varovani": ("Ověřit ručně", "!"), "chyba": ("Nesedí", "✕")}


def odznak(stav):
    text, ikona = STAVY[stav]
    return f'<span class="odznak {stav}"><b>{ikona}</b>{text}</span>'


def karta(nadpis, stav, popis):
    return (f'<div class="karta {stav}"><div class="karta-hlava">{odznak(stav)}</div>'
            f'<h3>{nadpis}</h3><p>{popis}</p></div>')


def nejhorsi(stavy):
    poradi = ["ok", "info", "varovani", "chyba"]
    return max(stavy, key=poradi.index) if len(stavy) else "ok"


def zmena(x, mez, znamy_zlom=False):
    if pd.isna(x):
        return ""
    trida = "zmena" + (" skok" if abs(x) > mez and not znamy_zlom else "")
    return f"<span class='{trida}'>{x:+.1%}</span>".replace(".", ",")


def snimky_do():
    cesta = ROOT / "ciselniky" / "docasna_ochrana_snimky.csv"
    return pd.read_csv(cesta).set_index("rok").stav_k if cesta.exists() else pd.Series(dtype=str)


def bunka_csu(r):
    """Oficiální počet obyvatel ČSÚ za ČR, nebo odhad z dat MV, dokud ho ČSÚ nezveřejní."""
    if pd.notna(getattr(r, "obyvatele_csu", None)):
        return cislo(r.obyvatele_csu)
    if pd.notna(getattr(r, "odhad_csu", None)):
        return f"<span class='zvyrazni'>{cislo(r.odhad_csu)}</span><span class='zmena'>odhad</span>"
    return '<span class="tlumene">–</span>'


def bunka_do(r):
    """Počet osob s dočasnou ochranou a datum snímku MV."""
    if r.rok < PRVNI_ROK_DO:
        return '<span class="tlumene">–</span>'
    if pd.isna(r.docasna_ochrana_celkem):
        return '<span class="zvyrazni">chybí snímek</span>'
    datum = SNIMKY.get(r.rok)
    datum = f"<span class='zmena'>k {pd.Timestamp(datum):%d. %m. %Y}</span>" if datum else ""
    return f"{cislo(r.docasna_ochrana_celkem)}{datum}"


def tabulka_souctu(k):
    maxi = k.cizinci_soucet_mv.fillna(k.dopocet).max()
    radky = []
    for r in k.itertuples():
        celkem = r.cizinci_soucet_mv if pd.notna(r.cizinci_soucet_mv) else r.dopocet
        sirka = 100 * celkem / maxi
        podil = 100 * r.cizinci_prirazeno_obcim / celkem if celkem else 0
        zlom = f'<span class="zlom-text">{esc(ZLOMY[r.rok])}</span>' if r.rok in ZLOMY else ""
        mv = cislo(r.cizinci_soucet_mv) if pd.notna(r.cizinci_soucet_mv) else '<span class="tlumene">bez součtu</span>'
        radky.append(
            f"<tr><td class='rok'>{r.rok}{zlom}</td>"
            f"<td class='c'>{cislo(r.obcane_celkem)}{zmena(r.zmena_obcane, MAX_ZMENA_OBCANE)}</td>"
            f"<td class='c'>{mv}{zmena(r.zmena_cizinci, MAX_ZMENA_CIZINCI, r.rok in ZLOMY)}</td>"
            f"<td><div class='pruh' style='width:{sirka:.1f}%'>"
            f"<span class='pruh-a' style='width:{podil:.2f}%'></span></div></td>"
            f"<td class='c'>{cislo(r.cizinci_prirazeno_obcim)}</td>"
            f"<td class='c'>{cislo(r.cizinci_bez_adresy)}</td>"
            f"<td class='c{' zvyrazni' if r.cizinci_nesparovano else ''}'>{cislo(r.cizinci_nesparovano)}</td>"
            f"<td class='c{' zvyrazni' if r.obce_sparovane_jen_podle_kraje else ''}'>{cislo(r.obce_sparovane_jen_podle_kraje)}</td>"
            f"<td class='c'>{bunka_do(r)}</td>"
            f"<td class='c'>{bunka_csu(r)}</td>"
            f"<td>{odznak(r.stav)}</td></tr>")
    return ("<div class='tab-obal'><table><thead><tr><th>Rok</th><th class='c'>Občané</th>"
            "<th class='c'>Cizinci (MV)</th><th class='pruh-th'>Přiřazeno obcím</th><th class='c'>Přiřazeno</th>"
            "<th class='c'>Bez adresy</th><th class='c'>Nespárováno</th><th class='c'>Jen podle kraje</th>"
            "<th class='c'>Dočasná ochrana</th><th class='c'>ČSÚ</th>"
            "<th>Stav</th></tr></thead><tbody>" + "".join(radky) + "</tbody></table></div>")


def mrizka_mc(m):
    roky = sorted(m.rok.unique())
    mesta = m.drop_duplicates("kod_obce").sort_values("nazev_obce")
    hlava = "".join(f"<th class='c'>{r}</th>" for r in roky)
    radky = []
    for mesto in mesta.itertuples():
        bunky = []
        for rok in roky:
            r = m[(m.kod_obce == mesto.kod_obce) & (m.rok == rok)]
            if r.empty:
                bunky.append("<td class='bunka prazdna'>–</td>")
                continue
            r = r.iloc[0]
            o, c = int(r.obcane_celkem_rozdil), int(r.cizinci_celkem_rozdil)
            obsah = []
            if c:
                obsah.append(f"<span>{c:+d}</span>")
            if o:
                obsah.append(f"<span class='obc'>{o:+d} obč.</span>")
            text = "".join(obsah) or "0"
            tip = f"{mesto.nazev_obce} {rok}: cizinci {c:+d}, občané {o:+d}"
            bunky.append(f"<td class='bunka {r.stav}' title='{esc(tip)}'>{text}</td>")
        radky.append(f"<tr><th class='mesto'>{esc(mesto.nazev_obce)}</th>{''.join(bunky)}</tr>")
    return ("<div class='tab-obal'><table class='mrizka'><thead><tr><th>Město</th>" + hlava
            + "</tr></thead><tbody>" + "".join(radky) + "</tbody></table></div>")


def tabulka_nesparovanych(n, sloupce, popisky):
    if n.empty:
        return "<p class='prazdne'>Nic – všechny řádky se spárovaly.</p>"
    hlava = "".join(f"<th{' class=c' if s in ('celkem', 'rok') else ''}>{p}</th>" for s, p in zip(sloupce, popisky))
    radky = "".join(
        "<tr>" + "".join(f"<td class='c'>{cislo(getattr(r, s))}</td>" if s in ("celkem",) else
                         f"<td>{esc(getattr(r, s))}</td>" for s in sloupce) + "</tr>"
        for r in n.itertuples())
    return f"<div class='tab-obal'><table><thead><tr>{hlava}</tr></thead><tbody>{radky}</tbody></table></div>"


CSS = """
:root{--bg:#f7f6f3;--panel:#fff;--text:#1d1f23;--muted:#6b6f76;--line:#e4e2dc;
--ok:#2f7d4f;--ok-bg:#e6f2ea;--info:#3a6ea5;--info-bg:#e7eef7;--warn:#a86a00;--warn-bg:#fbf0d9;
--err:#b3261e;--err-bg:#fbe5e3;--s-obc:#3a6ea5;--s-ciz:#c26a2e;--accent:#2f7d4f;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15171a;--panel:#1d2024;--text:#e8e6e1;
--muted:#9a9ea5;--line:#30343a;--ok:#6cc08f;--ok-bg:#1c3326;--info:#86b2e0;--info-bg:#1d2a3a;--warn:#e0b04f;
--warn-bg:#3a2e14;--err:#f08a80;--err-bg:#3d1f1c;--s-obc:#6f9fd4;--s-ciz:#e0925a;--accent:#6cc08f;}}
:root[data-theme="dark"]{--bg:#15171a;--panel:#1d2024;--text:#e8e6e1;--muted:#9a9ea5;--line:#30343a;--ok:#6cc08f;
--ok-bg:#1c3326;--info:#86b2e0;--info-bg:#1d2a3a;--warn:#e0b04f;--warn-bg:#3a2e14;--err:#f08a80;--err-bg:#3d1f1c;
--s-obc:#6f9fd4;--s-ciz:#e0925a;--accent:#6cc08f;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1180px;margin:0 auto;padding:28px 16px 64px}
header h1{font-size:26px;margin:0 0 4px;letter-spacing:-.01em}
header p{margin:0;color:var(--muted)}
h2{font-size:18px;margin:40px 0 6px}
.popis{color:var(--muted);margin:0 0 14px;max-width:780px}
.karty{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-top:22px}
.karta{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px;border-top:3px solid var(--line)}
.karta.ok{border-top-color:var(--ok)}.karta.info{border-top-color:var(--info)}
.karta.varovani{border-top-color:var(--warn)}.karta.chyba{border-top-color:var(--err)}
.karta h3{font-size:15px;margin:10px 0 4px}.karta p{margin:0;color:var(--muted);font-size:14px}
.odznak{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:600;padding:2px 9px 2px 3px;border-radius:999px;white-space:nowrap}
.odznak b{display:inline-grid;place-items:center;width:18px;height:18px;border-radius:50%;color:var(--panel);font-size:11px}
.odznak.ok{background:var(--ok-bg);color:var(--ok)}.odznak.ok b{background:var(--ok)}
.odznak.info{background:var(--info-bg);color:var(--info)}.odznak.info b{background:var(--info)}
.odznak.varovani{background:var(--warn-bg);color:var(--warn)}.odznak.varovani b{background:var(--warn)}
.odznak.chyba{background:var(--err-bg);color:var(--err)}.odznak.chyba b{background:var(--err)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px}
.grafy{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.grafy svg{width:100%;height:auto;display:block}
.g-nadpis{font-size:13px;font-weight:600;fill:var(--text)}.g-osa{font-size:11px;fill:var(--muted);text-anchor:middle}
.s-obcane{fill:var(--s-obc)}.s-cizinci{fill:var(--s-ciz)}rect.zlom{opacity:.75;stroke:var(--text);stroke-dasharray:3 2;stroke-width:1}
.legenda{color:var(--muted);font-size:13px;margin-top:8px}
.tab-obal{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
thead th{font-size:12.5px;color:var(--muted);font-weight:600;background:var(--panel);position:sticky;top:0}
tbody tr:last-child td,tbody tr:last-child th{border-bottom:0}
.c{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.rok{font-weight:600;white-space:nowrap}.zlom-text{display:block;font-weight:400;font-size:12px;color:var(--muted);white-space:normal;max-width:200px}
.tlumene{color:var(--muted);font-size:12.5px}
.zvyrazni{color:var(--warn);font-weight:600}
.zmena{display:block;font-size:12px;color:var(--muted)}.zmena.skok{color:var(--err);font-weight:600}
.pruh-th{min-width:150px}
.pruh{height:10px;background:var(--line);border-radius:5px;overflow:hidden;margin-top:6px}
.pruh-a{display:block;height:100%;background:var(--s-ciz)}
.mrizka th.mesto{font-weight:600;white-space:nowrap}
.bunka{text-align:center;font-variant-numeric:tabular-nums;font-size:13px;white-space:nowrap}
.bunka span{display:block}.bunka .obc{font-size:11.5px;opacity:.8}
.bunka.ok{color:var(--muted)}.bunka.info{background:var(--info-bg);color:var(--info)}
.bunka.chyba{background:var(--err-bg);color:var(--err);font-weight:600}.bunka.prazdna{color:var(--muted)}
.prazdne{background:var(--panel);border:1px dashed var(--line);border-radius:10px;padding:14px 16px;color:var(--muted);margin:0}
.navod{font-size:14px;color:var(--muted);margin-top:10px}
code{font-family:ui-monospace,Consolas,monospace;font-size:13px;background:var(--line);padding:1px 5px;border-radius:4px}
footer{margin-top:48px;color:var(--muted);font-size:13px}
"""


def main():
    global SNIMKY
    SNIMKY = snimky_do()
    k = nacti("kontrola_souctu.csv")
    if k.empty:
        print("Chybí vystup/kontrola_souctu.csv – nejdřív spusť zpracuj_data.py")
        return 1
    k = vyhodnot_soucty(k)
    m = vyhodnot_mc(nacti("kontrola_mc.csv"))
    nc = nacti("cizinci_nesparovani.csv")
    nmc = nacti("mc_nesparovane.csv")

    stav_soucty = nejhorsi(k.stav.replace("info", "ok"))
    stav_nesp = "info" if not nc.empty else "ok"
    stav_mc = nejhorsi(m.stav) if not m.empty else "ok"
    stav_nmc = "varovani" if not nmc.empty else "ok"

    chyby_soucty = k[k.stav == "chyba"].rok.tolist()
    varovani = k[k.stav == "varovani"].rok.tolist()  # skok cizinců, párování podle kraje, chybějící snímek DO
    popis_soucty = (f"Nesedí součet nebo podezřelý skok počtu občanů: {', '.join(map(str, chyby_soucty))}."
                    if chyby_soucty else
                    f"Ověř ručně (skok cizinců, párování jen podle kraje nebo chybí snímek dočasné ochrany): {', '.join(map(str, varovani))}."
                    if varovani else
                    "Ve všech letech: přiřazeno + bez adresy + nespárováno = součet MV, bez podezřelých skoků.")
    popis_nesp = (f"{len(nc)} řádků, celkem {cislo(nc.celkem.sum())} osob. Doplň případně "
                  "<code>ciselniky/rucni_parovani.csv</code>." if not nc.empty else "Všechny obce se spárovaly.")
    velke = m[m.stav == "chyba"]
    popis_mc = (f"Velký rozdíl: {', '.join(f'{r.nazev_obce} {r.rok}' for r in velke.itertuples())}."
                if len(velke) else "Jen drobné rozdíly, které jsou už v souborech MV.")
    popis_nmc = (f"{len(nmc)} MČ bez kódu, {cislo(nmc.celkem.sum())} osob ve „nezjištěno“."
                 if not nmc.empty else "Všechny MČ cizinců mají kód.")

    roky = f"{k.rok.min()}–{k.rok.max()}"
    stranka = f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kontrola zpracování</title><style>{CSS}</style></head><body><main>
<header><h1>Kontrola zpracování dat MV</h1>
<p>Informativní počty obyvatel, roky {roky} · vygenerováno {datetime.now():%d. %m. %Y %H:%M}</p></header>

<section class="karty">
{karta("Součty cizinců", stav_soucty, popis_soucty)}
{karta("Nespárované obce", stav_nesp, popis_nesp)}
{karta("MČ proti obcím", stav_mc, popis_mc)}
{karta("Nespárované MČ", stav_nmc, popis_nmc)}
</section>

<h2>Vývoj v čase</h2>
<p class="popis">Skok, který neodpovídá známým zlomům, obvykle znamená chybu v načtení souboru.
Čárkovaně jsou roky se známým zlomem v datech.</p>
<div class="panel">{graf_vyvoj(k)}
<p class="legenda">2022: {ZLOMY[2022]} · 2023: {ZLOMY[2023]}</p></div>

<h2>Součty cizinců podle let</h2>
<p class="popis">Cizinci ze souboru MV se dělí na přiřazené obcím, bez adresy (MV adresu neurčilo) a nespárované
(obec se nepodařilo najít). Součet musí dát číslo MV. Pruh ukazuje podíl přiřazených obcím.</p>
{tabulka_souctu(k)}

<h2>Cizinci bez kódu obce</h2>
<p class="popis">Řádky ze souborů cizinců, které se nepřiřadily k obci – typicky stejnojmenné obce v jednom okrese
bez PSČ v názvu.</p>
{tabulka_nesparovanych(nc, ["rok", "kraj", "okres", "obec", "celkem"], ["Rok", "Kraj", "Okres", "Obec (jak uvádí MV)", "Osob"])}
<p class="navod">Pokud víš, kam řádek patří, přidej do <code>ciselniky/rucni_parovani.csv</code> okres, obec přesně
jako výše a kód obce, a spusť <code>python zpracuj_data.py</code>.</p>

<h2>Městské části proti obcím</h2>
<p class="popis">Rozdíl součtu MČ a řádku města v tabulce obcí (kladné = v MČ víc). Horní číslo jsou cizinci,
menší „obč.“ občané. Modře drobné rozdíly do {TOLERANCE_CIZINCI} cizinců / {TOLERANCE_OBCANE} občanů,
které vznikají už v souborech MV; červeně větší.</p>
{mrizka_mc(m) if not m.empty else "<p class='prazdne'>Chybí vystup/kontrola_mc.csv.</p>"}

<h2>Městské části bez kódu</h2>
{tabulka_nesparovanych(nmc, ["rok", "kod_obce", "mc", "celkem"], ["Rok", "Kód města", "MČ (jak uvádí MV)", "Osob"])}

<footer>Zdroj: soubory v <code>vystup/</code> vytvořené <code>zpracuj_data.py</code>. Podrobnosti v README.</footer>
</main></body></html>"""
    cil = VYSTUP / "kontrola.html"
    cil.write_text(stranka, encoding="utf-8")

    # souhrn pro pull request z GitHub Actions + celkový stav do samostatného souboru
    celkem = nejhorsi([stav_soucty, stav_nesp, stav_mc, stav_nmc])
    ikony = {"ok": "✅", "info": "ℹ️", "varovani": "⚠️", "chyba": "❌"}
    posledni = k.iloc[-1]
    souhrn = [f"## Kontrola zpracování: {ikony[celkem]} {STAVY[celkem][0]}", "",
              f"Poslední rok **{posledni.rok}**: občané {cislo(posledni.obcane_celkem)}, "
              f"cizinci přiřazení obcím {cislo(posledni.cizinci_prirazeno_obcim)}.", "",
              "| Kontrola | Stav | Detail |", "|---|---|---|"]
    for nazev, stav, popis in [("Součty cizinců", stav_soucty, popis_soucty),
                               ("Nespárované obce", stav_nesp, popis_nesp),
                               ("MČ proti obcím", stav_mc, popis_mc),
                               ("Nespárované MČ", stav_nmc, popis_nmc)]:
        popis = re.sub(r"</?code>", "`", popis)
        souhrn.append(f"| {nazev} | {ikony[stav]} {STAVY[stav][0]} | {popis} |")
    (VYSTUP / "kontrola_souhrn.md").write_text("\n".join(souhrn) + "\n", encoding="utf-8")
    (VYSTUP / "kontrola_stav.txt").write_text(celkem, encoding="utf-8")
    print(f"Kontrola: {STAVY[celkem][0]} -> {cil}")


if __name__ == "__main__":
    sys.exit(main())
