# Obyvatelé obcí ČR

Počty obyvatel obcí a městských částí ČR za roky 2014–2026, vždy k 1. lednu.
Zdrojem jsou informativní počty obyvatel, které zveřejňuje Ministerstvo vnitra ČR.

- **Web s daty ke stažení:** https://opendatabrno.github.io/obyvatele/
- **Zdroj MV:** [aktuální data](https://mv.gov.cz/informativni-pocty-obyvatel-v-obcich-2) ·
  [archiv](https://archiv.mv.gov.cz/clanek/informativni-pocty-obyvatel-v-obcich.aspx?q=Y2hudW09Mg%3d%3d)

**Obsah:** [Datové sady](#datové-sady) · [Sloupce](#sloupce) · [Na co si dát pozor](#na-co-si-dát-pozor) ·
[Aktualizace dat](#aktualizace-dat) · [Kontroly](#kontroly) · [Soubory v repozitáři](#soubory-v-repozitáři) ·
[Jak se data zpracovávají](#jak-se-data-zpracovávají)

---

## Datové sady

| Soubor | Co obsahuje | Jeden řádek | Klíč |
|---|---|---|---|
| [`vystup/obyvatele_obce.csv`](vystup/obyvatele_obce.csv) | všechny obce ČR (~6 260) | obec × rok | `rok` + `kod_obce` |
| [`vystup/obyvatele_mestske_casti.csv`](vystup/obyvatele_mestske_casti.csv) | městské části 8 měst: Praha, Brno, Ostrava, Plzeň, Pardubice, Opava, Liberec, Ústí nad Labem | MČ × rok | `rok` + `kod_mc` |

- Formát: CSV, UTF-8, oddělovač čárka. Na [webu](https://opendatabrno.github.io/obyvatele/)
  jsou obě sady ke stažení i jako Excel (`.xlsx`), lokálně vzniká `.xlsx` při zpracování.
- Kódy obcí a MČ jsou kódy ČSÚ, takže se dají spojit s dalšími daty (např. s hranicemi MČ
  na [data.brno.cz](https://data.brno.cz)).
- **Řádky obou tabulek nesčítej dohromady.** MČ jsou části měst, která jsou v tabulce obcí
  už jako celek. Spojit je jde přes `rok` + `kod_obce`.

## Sloupce

| Sloupec | Význam | Tabulka |
|---|---|---|
| `rok` | rok, stav k 1. 1. | obě |
| `kod_obce`, `nazev_obce` | kód ČSÚ a název obce (u MČ města, kam patří) | obě |
| `orp` | obec s rozšířenou působností (podle MV) | obce |
| `kod_okresu`, `okres`, `kod_kraje`, `kraj` | okres a kraj podle aktuálního číselníku obcí | obce |
| `spravni_obvod` | správní obvod Prahy (Praha 1–22), jinde prázdné | MČ |
| `kod_mc`, `nazev_mc` | kód ČSÚ a název MČ; řádek `nezjištěno` = cizinci bez určené MČ | MČ |
| `obyvatele_celkem` | občané ČR + cizinci | obě |
| `obyvatele_csu` | oficiální počet obyvatel ČSÚ k 1. 1.; prázdné, dokud ho ČSÚ nezveřejní (v květnu) | obce |
| `odhad_csu` | obce: `obyvatele_csu`, a kde ještě chybí, odhad z dat MV; MČ: `odhad_csu` města rozdělený podle Sčítání 2021 (viz níže) | obě |
| `obyvatele_scitani_2021` | obyvatelé MČ s obvyklým pobytem podle Sčítání 2021 (26. 3. 2021), ve všech letech stejné | MČ |
| `koef_obcane` | podíl občanů z registru MV, kteří v MČ podle Sčítání 2021 opravdu bydlí | MČ |
| `obcane_celkem`, `obcane_muzi`, `obcane_zeny` | občané ČR s trvalým pobytem | obě |
| `cizinci_celkem`, `cizinci_muzi`, `cizinci_zeny` | cizinci s trvalým nebo přechodným pobytem nad 90 dní | obě |
| `cizinci_trvaly_pobyt`, `cizinci_prechodny_pobyt` | cizinci podle typu pobytu | obě |
| `cizinci_docasna_ochrana` | z toho lidé s dočasnou ochranou (od 2023, do 2022 nula) | obě |

**Jak se sloupce sčítají:**

```
obyvatele_celkem = obcane_celkem + cizinci_celkem
obcane_celkem    = obcane_muzi + obcane_zeny
cizinci_celkem   = cizinci_muzi + cizinci_zeny                         (± jednotky osob s neurčeným pohlavím)
cizinci_celkem   = cizinci_trvaly_pobyt + cizinci_prechodny_pobyt
cizinci_docasna_ochrana ⊂ cizinci_prechodny_pobyt                      (podmnožina, nepřičítat)
```

### Oficiální počet obyvatel (ČSÚ) a jeho odhad

MV je výpis z registrů a počty nadhodnocuje (2026 o 3,4 % proti ČSÚ), hlavně o občany
s trvalým pobytem v ČR, kteří tu nežijí. Oficiální je počet ČSÚ, který vychází ze sčítání
a bilance obyvatel. Tabulka obcí ho má ve sloupci `obyvatele_csu` (sada
[OBY02A](https://data.csu.gov.cz/datastat/info/SADA/OBY02A)).

ČSÚ zveřejňuje stav k 1. 1. až v květnu, MV už v lednu. Do té doby obsahuje `odhad_csu`
odhad z dat MV s koeficientem obce z posledního roku, kdy ČSÚ data má:

```
koeficient = (obyvatele_csu − cizinci_celkem) / obcane_celkem      (poslední rok s ČSÚ)
odhad_csu  = koeficient × obcane_celkem + cizinci_celkem             (nový rok)
```

Mimo roky se zlomem v datech se odhad liší od pozdějšího čísla ČSÚ v mediánu o 0,04–0,07 %
a u 97–98 % obcí o méně než 1 %. Podrobnosti jsou v
[analyza/POROVNANI_CSU.md](analyza/POROVNANI_CSU.md). Jakmile ČSÚ data zveřejní,
`odhad_csu` = `obyvatele_csu`.

**Městské části:** ČSÚ roční počty obyvatel MČ nevydává, proto se použije Sčítání 2021
(sada [SLDZOB01](https://data.csu.gov.cz/datastat/info/SADA/SLDZOB01), obyvatelé
s obvyklým pobytem, uložené v `ciselniky/scitani_2021_mc.csv`):

```
koef_obcane = (obyvatele_scitani_2021 − cizinci_celkem 2021) / obcane_celkem 2021
vaha MČ     = koef_obcane × obcane_celkem + cizinci_celkem
odhad_csu   = odhad_csu města rozdělený mezi MČ podle vah          (součet MČ = město)
```

Koeficient pod 1 znamená, že v MČ je v registru víc občanů, než kolik jich tam bydlí.
Nejvýrazněji Praha 1 (0,69) a Brno-střed (0,74): v Brně-střed má trvalý pobyt asi 23 tis.
občanů, kteří tam nežijí. Pravděpodobně jde o lidi s trvalým pobytem na adrese úřadu
a o občany žijící v zahraničí (např. zapsané ve zvláštní matrice v Brně); z dat MV je
od sebe rozlišit nejde. Koeficient nad 1 mají MČ, kde bydlí
lidé s trvalým pobytem jinde. U MČ bez údaje ze sčítání se použije koeficient města.

## Na co si dát pozor

- **Nejde o oficiální počet obyvatel ČSÚ.** MV započítává cizince s trvalým i přechodným
  pobytem nad 90 dní, proto jsou čísla vyšší.
- **Zlom v roce 2023:** MV od tohoto roku započítává do přechodného pobytu cizinců i lidi
  s dočasnou ochranou (válka na Ukrajině), přechodný pobyt proto skočil o ~450 tis.
  Jejich počet je ve sloupci `cizinci_docasna_ochrana`; pro srovnání v čase je odečti
  (`obyvatele_celkem − cizinci_docasna_ochrana`).
- **Dočasná ochrana je ze samostatného souboru MV** – týdenního snímku po obcích, ne přímo
  ze souboru cizinců. Bere se snímek nejbližší 1. 1. (datum v
  [`ciselniky/docasna_ochrana_snimky.csv`](ciselniky/docasna_ochrana_snimky.csv)), takže
  se od souboru cizinců může o pár dní lišit; v jednotkách obcí je proto vyšší než přechodný pobyt.
- **Zlom v roce 2022:** soubory cizinců od tohoto roku nemají kód obce, obce se přiřazují
  podle okresu a názvu (viz [Jak se data zpracovávají](#jak-se-data-zpracovávají)).
- **Cizinci bez adresy** (MV adresu neurčilo, ročně zhruba 1–13 tis. osob) nejsou
  u žádné obce. U MČ jsou cizinci bez určené MČ v řádku `nezjištěno`.
- **Opava 2015–2021:** MV cizince po MČ Opavy neuvádí, všichni jsou v řádku `nezjištěno`.
- **Bývalé obce a vojenské újezdy** nemají okres, protože nejsou v aktuálním číselníku.

---

## Aktualizace dat

### Automaticky (GitHub Actions)

Workflow [**Aktualizace dat MV**](.github/workflows/aktualizace.yml) hlídá stránku MV:
od ledna do března denně, zbytek roku 1. den v měsíci. Spustit se dá i ručně
(*Actions → Aktualizace dat MV → Run workflow*).

| Co se stane | Co udělá workflow | Co uděláš ty |
|---|---|---|
| Nic nového | nic | nic |
| MV zveřejnilo nová data | založí **pull request** `aktualizace-dat` se souhrnem kontrol | projdi souhrn a přehled kontrol (artefakt `kontrola` u běhu) a PR slouč |
| Data se načetla, ale kontrola nesedí | PR s názvem začínajícím **„⚠️ Kontrola nesedí“** | zjisti příčinu v přehledu kontrol, PR neslučuj bez opravy |
| MV změnilo formát souboru | založí **issue** `zmena-struktury` s ukázkou souboru | upravit parser (`zpracuj_data.py`, `mestske_casti.py`) podle ukázky v issue |

Po sloučení PR workflow [**GitHub Pages**](.github/workflows/pages.yml) automaticky
aktualizuje web.

**Jednorázové nastavení na GitHubu:**
1. *Settings → Pages → Source:* **GitHub Actions**
2. *Settings → Actions → General → Workflow permissions:* **Read and write permissions**
   a zaškrtnout **Allow GitHub Actions to create and approve pull requests**

> GitHub vypíná plánované workflows po 60 dnech bez aktivity v repozitáři (pošle e-mail).
> Před lednem zkontroluj v záložce *Actions*, že workflow „Aktualizace dat MV“ je zapnuté.

### Ručně

```bash
pip install -r requirements.txt   # jen poprvé
python stahni_data.py             # stáhne chybějící soubory MV do data/
python zpracuj_data.py            # zpracuje vše do vystup/ a vytvoří přehled kontrol
```

Pak otevři [`vystup/kontrola.html`](#kontroly). Soubor MV jde stáhnout i ručně, stačí ho
uložit jako `data/RRRR-01 Čeští občané.xlsx` a `data/RRRR-01 Cizinci s pobytem.xlsx`.

## Kontroly

Hlavní je stránka **`vystup/kontrola.html`** (lokálně po zpracování, online na webu).
Semafory u čtyř kontrol: zelená = v pořádku, modrá = známý rozdíl, oranžová = ověřit ručně,
červená = nesedí.

| Kontrola | Co hlídá | Podklad |
|---|---|---|
| Součty cizinců | přiřazení obcím + bez adresy + nespárovaní = součet MV; meziroční skok občanů nad 3 % (chyba) a cizinců nad 30 % (varování); chybějící snímek dočasné ochrany (varování) | `vystup/kontrola_souctu.csv` |
| Nespárované obce | řádky cizinců, které se nepřiřadily k obci | `vystup/cizinci_nesparovani.csv` |
| MČ proti obcím | součet MČ za město proti tabulce obcí | `vystup/kontrola_mc.csv` |
| Nespárované MČ | MČ cizinců a dočasné ochrany bez kódu | `vystup/mc_nesparovane.csv` (jen když nějaké jsou) |

**Známé rozdíly, které jsou v pořádku** (vznikají už v souborech MV): u nespárovaných obcí
Březina (Brno-venkov) a Mezholezy (Domažlice) bez PSČ, desítky osob ročně. U MČ jsou to
Praha 2014–2021 (+120 až +450 cizinců), Brno 2014–2021 (+17 až +65) a Ostrava (+4 občané).

**Když se objeví nespárovaná obec**, kterou umíš přiřadit: doplň řádek do
[`ciselniky/rucni_parovani.csv`](ciselniky/rucni_parovani.csv) (okres a obec přesně jako
v souboru MV, kód obce) a spusť zpracování znovu.

---

## Soubory v repozitáři

| Soubor | Účel |
|---|---|
| `stahni_data.py` | stažení souborů MV (archiv + aktuální stránka) a číselníků |
| `zpracuj_data.py` | zpracování do tabulky obcí, spouští i MČ a kontroly |
| `mestske_casti.py` | tabulka městských částí |
| `kontrola.py` | přehled kontrol `vystup/kontrola.html` a souhrn pro PR |
| `web.py` | sestavení webu pro GitHub Pages do `_site/` |
| `ciselniky/pscoco.csv`, `cnumnuts.csv` | číselník obcí s okresy a kraji (volby.gov.cz) |
| `ciselniky/rucni_parovani.csv` | ruční přiřazení obcí, které se nespárují automaticky |
| `ciselniky/docasna_ochrana_snimky.csv` | ke kterému dni je použitý snímek dočasné ochrany za každý rok |
| `vystup/` | výsledné datové sady a kontrolní soubory |
| `data/` | stažené soubory MV (není v repozitáři) |

## Jak se data zpracovávají

- **Občané** mají v souborech MV kód obce i kód MČ, berou se přímo.
- **Cizinci 2014–2021** mají kód obce. Od roku 2022 ho nemají a obec se dohledá podle
  **okresu a názvu** v číselníku obcí. Názvy se porovnávají včetně diakritiky
  (Pohled a Pohleď jsou dvě obce v okrese Havlíčkův Brod).
- **Stejnojmenné obce v jednom okrese** (Březina v Brně-venkově, Mezholezy v Domažlicích)
  MV odlišuje „PSČ xxxxx“ v názvu. Tyto varianty se párují podle let 2014–2021, kdy kód
  v souborech byl, nebo podle ručního párování. Název bez PSČ se nehádá.
- **MČ cizinců** se párují podle názvu na MČ ze souboru občanů téhož roku.
- **Dočasná ochrana** se bere z týdenních snímků MV „Počty osob s uděleným pobytovým
  oprávněním v souvislosti s válkou na Ukrajině“ (s kódem obce a názvem MČ). Pro roky
  2023–2026 jsou snímky pevně dané z archivu MV, pro další roky `stahni_data.py` najde
  v archivu snímek nejvýš 7 dní od 1. 1.
- **Okres a kraj** pocházejí z číselníku obcí. Ten se aktualizuje při každém stažení.
- **Neznámou strukturu souboru** zpracování ohlásí chybou s popisem listů a prvních řádků
  (`vystup/chyba_struktury.txt`), ze které workflow založí issue.
