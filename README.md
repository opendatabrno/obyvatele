# Obyvatelé obcí ČR (MV ČR, stav k 1. 1.)

Jedna tabulka obyvatel podle obcí za roky 2014–2026, sestavená z informativních
počtů obyvatel, které zveřejňuje MV ČR:
- aktuální: https://mv.gov.cz/informativni-pocty-obyvatel-v-obcich-2
- archiv: https://archiv.mv.gov.cz/clanek/informativni-pocty-obyvatel-v-obcich.aspx?q=Y2hudW09Mg%3d%3d

## Každoroční aktualizace

Poprvé nainstaluj knihovny (`pip install -r requirements.txt`). Zdrojové Excely MV
nejsou v repozitáři, `stahni_data.py` je stáhne do `Data/`.

```bash
python stahni_data.py
python zpracuj_data.py
```

`stahni_data.py` najde na aktuální stránce MV lednové soubory nového roku (podle
„01-01-RRRR“ v odkazu) a uloží je do `Data/`. Soubor můžeš stáhnout i ručně a uložit
jako `Data/RRRR-01 Čeští občané.xlsx` a `Data/RRRR-01 Cizinci s pobytem.xlsx`.
Pak zkontroluj `vystup/kontrola_souctu.csv`, `vystup/cizinci_nesparovani.csv`
a u městských částí `vystup/kontrola_mc.csv` a `vystup/mc_nesparovane.csv`.

## Výstup `vystup/obyvatele_obce.csv` (UTF-8) a `.xlsx`

Jeden řádek = obec × rok, klíč `rok` + `kod_obce` (kód obce ČSÚ).

| sloupec | význam |
|---|---|
| `kod_obce`, `nazev_obce`, `orp` | obec podle souboru občanů |
| `kod_okresu`, `okres`, `kod_kraje`, `kraj` | podle aktuálního číselníku (NUTS/LAU) |
| `obyvatele_celkem`, `obyvatele_deti_0_14` | občané + cizinci |
| `obcane_*` | občané ČR: celkem, muži, ženy, děti 0–14 |
| `cizinci_*` | cizinci s pobytem: celkem, muži, ženy, děti 0–14, trvalý a přechodný pobyt |

Děti 0–14 = celkem − osoby 15+.

## Výstup `vystup/obyvatele_mestske_casti.csv` (UTF-8) a `.xlsx`

Městské části a obvody 8 měst, která je mají (Praha, Brno, Ostrava, Plzeň, Pardubice,
Opava, Liberec, Ústí nad Labem). Jeden řádek = MČ × rok, klíč `rok` + `kod_mc` (kód ČSÚ),
`kod_obce` je kód města. Sloupce s počty jsou stejné jako u obcí, u Prahy navíc `spravni_obvod`.

- Cizinci se k MČ párují podle názvu na MČ ze souboru občanů téhož roku (bez kódu MČ
  v souborech cizinců se jinak neobejde). Spárované jsou všechny MČ ve všech letech;
  co by se nespárovalo, objeví se v `vystup/mc_nesparovane.csv`.
- Řádek `nazev_mc = nezjištěno` (bez kódu MČ) = cizinci, u kterých MV MČ neurčilo.
  Opava 2015–2021: MV v těch letech cizince po MČ Opavy neuvádí, takže jsou všichni v tomto řádku.
- `vystup/kontrola_mc.csv` porovnává součet MČ za město s tabulkou obcí. Drobné rozdíly
  jsou už v souborech MV: u Prahy 2014–2021 mají listy MČ o 120–450 cizinců víc než list obcí
  a u Ostravy je v listu MČ o 4 občany víc.

## Co je dobré vědět

- **Cizinci = trvalý + přechodný pobyt (nad 90 dní)**, ne jen trvalý. Rozdělení je ve
  sloupcích `cizinci_trvaly_pobyt` a `cizinci_prechodny_pobyt`.
- **Kódy obcí u cizinců:** v souborech 2014–2021 kód obce je, od roku 2022 už ne. Kód se
  dohledá podle okresu a názvu obce (číselník `ciselniky/pscoco.csv` z volby.gov.cz).
  Diakritika se při porovnávání zachovává (Pohled a Pohleď jsou dvě obce v okrese Havlíčkův Brod).
- **Duplicitní názvy v okrese** (Březina v okrese Brno-venkov, Mezholezy v okrese Domažlice):
  MV je odlišuje „PSČ xxxxx“ v názvu. Tyto varianty se párují podle let 2014–2021,
  kdy kód obce v souborech byl, nebo podle `ciselniky/rucni_parovani.csv`. Řádek bez PSČ
  se nehádá a skončí v `vystup/cizinci_nesparovani.csv` (desítky osob ročně).
- **Cizinci bez adresy** („*NULL“, „(prázdné)“) nejsou přiřazeni žádné obci; jejich počet je
  v `kontrola_souctu.csv`.
- **Zlomy v řadě:** v roce 2022 se změnil formát souboru cizinců a v roce 2023 jejich počet
  skočil o ~470 tis. (pravděpodobně se začali započítávat cizinci s dočasnou ochranou).
  Někdejší obce a vojenské újezdy nemají okres v aktuálním číselníku, kraj se jim doplní z MV.
