# Porovnání MV a ČSÚ: která čísla jsou přesnější a jak je přepočítat

Srovnání informativních počtů obyvatel MV (tento repozitář) s oficiálním počtem obyvatel
ČSÚ, po obcích, stav k 1. 1. let 2014–2026.

- **ČSÚ:** datová sada [OBY02A](https://data.csu.gov.cz/datastat/info/SADA/OBY02A),
  ukazatel „Počet obyvatel k 1. 1.“
- **MV:** `vystup/obyvatele_obce.csv`
- **Skript:** [`porovnani_csu.py`](porovnani_csu.py), výstupy v [`vystup/`](vystup/)

## Shrnutí

1. **Oficiální a nejpřesnější je ČSÚ.** Vychází ze Sčítání 2021 a z bilance narozených,
   zemřelých a stěhování. MV je výpis z registrů. Je dřív (leden, ČSÚ až v květnu)
   a podrobnější (občané a cizinci, MČ), ale počty nadhodnocuje.
2. **MV má o 3,4 % víc obyvatel než ČSÚ** (2026: 11,28 mil. proti 10,92 mil.). Rozdíl je
   v občanech. Když se od ČSÚ odečtou všichni cizinci z MV, zbude **96,4 % občanů
   z registru MV** (před Sčítáním 2021 to bylo 98,2–98,4 %). Nejpravděpodobnější vysvětlení:
   v registru jsou lidé s trvalým pobytem v ČR, kteří tu nežijí (v zahraničí apod.).
   Sčítání 2021 je odhalilo: počet obyvatel ČSÚ k 1. 1. 2021 je o zhruba 200 tis. nižší
   než o rok dřív.
3. **Z dat MV jde počet ČSÚ odhadnout velmi přesně** s koeficientem každé obce z minulého
   roku. Medián chyby je 0,04–0,07 % a 97–98 % obcí je do 1 %. Výjimkou jsou roky se
   zlomem (2021, 2023, 2024).
4. **Bez dat ČSÚ** je nejlepší vzorec *občané + cizinci s trvalým pobytem + dočasná
   ochrana*. Za ČR sedí na ±0,5 %, v obci se ale typicky netrefí o 1 %.

## Celostátní součty (tis. osob)

| Rok | ČSÚ | Občané MV | Cizinci MV | MV celkem | MV − ČSÚ | Podíl občanů MV, který ČSÚ počítá |
|---|---:|---:|---:|---:|---:|---:|
| 2014 | 10 512 | 10 251 | 425 | 10 676 | +163 | 98,4 % |
| 2020 | 10 694 | 10 288 | 589 | 10 877 | +183 | 98,2 % |
| 2021 | 10 495 | 10 274 | 615 | 10 889 | +394 | 96,2 % |
| 2023 | 10 828 | 10 235 | 1 108 | 11 343 | +515 | 95,0 % |
| 2026 | 10 916 | 10 161 | 1 123 | 11 284 | +368 | 96,4 % |

Podíl = (ČSÚ − všichni cizinci MV) / občané MV. Je velmi stabilní, mění se jen v letech
zlomů. Plná řada je v [`vystup/soucty_cr.csv`](vystup/soucty_cr.csv).

## Jak dobře jednotlivé vzorce odhadují ČSÚ

Medián absolutní chyby po obcích / podíl obcí s chybou do 1 % / chyba za celou ČR:

| Odhad | 2020 | 2022 | 2026 |
|---|---|---|---|
| jen občané MV | 1,27 % / 42 % / −3,8 % | 1,02 % / 49 % / −2,5 % | 1,77 % / 32 % / −6,9 % |
| všichni obyvatelé MV | 0,99 % / 50 % / +1,7 % | 1,64 % / 28 % / +3,6 % | 1,61 % / 28 % / +3,4 % |
| **občané + cizinci TP + dočasná ochrana** | 0,89 % / 54 % / −1,0 % | 1,08 % / 47 % / +0,5 % | 1,08 % / 47 % / +0,3 % |
| loňský počet ČSÚ | 1,27 % / 42 % / −0,4 % | 1,32 % / 40 % / −0,2 % | 1,21 % / 43 % / −0,1 % |
| **koeficient obce z loňska** | **0,05 % / 97 % / +0,0 %** | **0,13 % / 94 % / −0,2 %** | **0,04 % / 98 % / +0,0 %** |

Všechny roky jsou v [`vystup/presnost_vzorcu.csv`](vystup/presnost_vzorcu.csv).

### Odhad s koeficientem obce (doporučený)

```
koeficient_obce(rok-1) = (ČSÚ(rok-1) − cizinci_celkem(rok-1)) / obcane_celkem(rok-1)
odhad_ČSÚ(rok)         = koeficient_obce(rok-1) × obcane_celkem(rok) + cizinci_celkem(rok)
```

Koeficient říká, kolik občanů z registru MV v dané obci opravdu žije. Typicky je 0,98
(90 % obcí mezi 0,95 a 1,00), ve velkých městech nižší (Praha 0,92, Brno 0,90). Odhad
je přesnější než loňský počet ČSÚ, takže změny v datech MV nesou skutečnou informaci.

**K čemu je:** v lednu jsou data MV k 1. 1., ČSÚ je zveřejní až v květnu. Odhad dá
počty ve „stylu ČSÚ“ o čtyři měsíce dřív. Funguje i pro roky, kdy ČSÚ data ještě nemá.

**Kdy nefunguje:** v letech se zlomem. V roce 2021 přišel přepočet podle sčítání
(medián chyby 1,1 %), v letech 2023–2024 nástup dočasné ochrany (0,5 %). Pokud se změní
metodika ČSÚ nebo MV, je potřeba počítat s horším odhadem.

### Jednoduchý odhad bez ČSÚ

`občané + cizinci_trvaly_pobyt + cizinci_docasna_ochrana`

Za celou ČR sedí dobře, ale spíš náhodou: vynechaní cizinci s přechodným pobytem (bez
dočasné ochrany) zhruba vyrovnají občany z registru, kteří v ČR nežijí. V jednotlivých
obcích chybuje o ~1 %. Selhává tam, kde jedna z těch skupin převládá (viz níže).

## Kde se MV a ČSÚ liší nejvíc

Chyba jednoduchého odhadu podle velikosti obce, 2026: v obcích do 20 tis. obyvatel je
medián +0,6 až +0,9 %, ve městech 20–100 tis. +1,3 %. U šesti měst nad 100 tis. je to
−0,1 %, ale s velkým rozptylem: Praha −2,9 %, Brno +3,3 %.
Chyba silně souvisí s podílem cizinců s přechodným pobytem (korelace −0,64). Nejvíc se
liší dva typy obcí (2026, obce nad 1 000 obyvatel):

- **Hodně cizinců s přechodným pobytem**, pravděpodobně ubytovny pracovníků: Čižice
  (−20 %), Lhenice (−10 %), Mladá Boleslav (−8 %), Hořovice (−7 %). ČSÚ tyto lidi
  počítá, jednoduchý odhad je vynechává.
- **Víc občanů v registru MV, než kolik jich ČSÚ počítá:** Obrnice (+16 %), Jáchymov
  (+8 %), Bečov (+8 %), Vejprty (+7 %), Krupka (+6 %). Pravděpodobně jde o lidi
  s trvalým pobytem, kteří v obci nežijí (např. trvalý pobyt na adrese úřadu).
  Z dostupných dat to nejde ověřit.

Odhad s koeficientem obce si s oběma typy poradí, protože koeficient je pro každou obec
vlastní.

## Doporučení

- **Pro oficiální čísla a srovnání s jinými statistikami** (přepočty na obyvatele,
  hustota zalidnění, srovnání s krajem či ČR) používej **ČSÚ**.
- **Pro členění na občany a cizince, městské části a nejčerstvější stav** používej **MV**.
  Mysli přitom na to, že občané jsou v MV nadhodnocení zhruba o 4 %, ve velkých městech
  až o 10 %.
- **Pro počty ve stylu ČSÚ hned v lednu** použij odhad s koeficientem obce, sloupec
  `odhad_csu` v hlavní tabulce obcí.
- **Pro čistou časovou řadu přes rok 2023** odečti dočasnou ochranu. Přes rok 2021
  pozor na přepočet ČSÚ podle sčítání.

## Další možné kroky

- ~~Sloupec `odhad_csu` v `vystup/obyvatele_obce.csv`~~: hotovo, tabulka obcí má sloupce
  `obyvatele_csu` (oficiální počet) a `odhad_csu` (počet ČSÚ, jinak odhad s koeficientem).
- ~~Odhad pro městské části~~: hotovo. OBY02A má MČ jen pro Prahu, proto tabulka MČ
  používá Sčítání 2021 (sloupce `obyvatele_scitani_2021`, `koef_obcane`, `odhad_csu`,
  viz README).

## Spuštění

```bash
python zpracuj_data.py             # výstupy MV
python analyza/porovnani_csu.py    # stáhne OBY02A (~200 MB) do data/csu/ a porovná
```
