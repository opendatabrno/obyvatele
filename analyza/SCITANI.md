# MV, ČSÚ a sčítání: jak daleko je registr od skutečnosti

Počet obyvatel ČSÚ je opravdu změřený jen při sčítání. Mezi sčítáními ho ČSÚ dopočítává
z narozených, zemřelých a stěhování. Po dalším sčítání pak stav k 1. 1. zpětně přepočítá.
V sadě [OBY02A](https://data.csu.gov.cz/datastat/info/SADA/OBY02A) proto po obcích
zůstávají pro stejný okamžik dvě čísla:

- **koncový stav k 31. 12. 2010 a 2020**: dopočet od minulého sčítání, bez opravy;
- **počáteční stav k 1. 1. 2011 a 2021**: přepočet podle Sčítání 2011 a 2021.

Rozdíl mezi nimi je chyba, kterou dopočet ČSÚ za deset let nasbíral (dál „drift“).
Přepočtený stav k 1. 1. 2011 a 2021 je nejbližší skutečnosti, kterou máme po obcích,
a porovnávají se s ním i data MV. Data MV jsou v repozitáři od roku 2004, takže pokrývají
dvě sčítání.

- **Skript:** [`scitani.py`](scitani.py); výstupy v [`vystup/`](vystup/): `scitani_cr.csv`,
  `scitani_obce.csv`, `scitani_skupiny.csv`
- **Koeficient** (stejný, jaký používá `odhad_csu`): `(ČSÚ − cizinci MV) / občané MV`,
  tedy podíl občanů z registru MV, které ČSÚ skutečně počítá jako obyvatele.

## Shrnutí

1. **ČSÚ mezi sčítáními ujíždí.** Za léta 2001–2011 dopočet nadhodnotil ČR o 46 tis.
   (+0,44 %), za léta 2011–2021 o 207 tis. (+1,97 %). V obci je typická chyba ±1,1 %,
   u 5 % obcí víc než +4 %. Praha byla k 31. 12. 2020 nadhodnocená o 6,0 %, Plzeň o 4,1 %.
   Drift je větší tam, kde je víc cizinců: v pětině obcí s nejvyšším podílem cizinců
   má medián +1,7 %, v pětině s nejnižším podílem +0,4 %. Nejspíš jde o lidi, kteří odešli
   a nehlásili to.
2. **MV je nad skutečností o 2–4 % a rozdíl roste.** Proti počtu podle sčítání měl registr
   MV v roce 2011 o 2,1 % víc obyvatel, v roce 2021 o 3,8 %. V obci typicky o 1,7 %,
   ve městech nad 50 tis. o 4,3 %, v Praze o 7,7 % a v Brně o 8,6 %.
3. **Koeficient je jen o kousek menší než 1 a pomalu klesá.** Celostátně ČSÚ v roce 2011
   počítal 97,8 % občanů z registru MV, v roce 2021 už 96,2 %. Ve velkých městech je
   nižší (Praha 0,950 → 0,914, Brno 0,935 → 0,914) a mezi sčítáními je stabilní
   (korelace 0,80). V malých obcích kolísá náhodně, protože pár lidí tam znamená procenta.
4. **Odhad z dat MV s koeficientem ze sčítání je stejně přesný jako ČSÚ.** Kdyby se
   koeficient ze Sčítání 2011 deset let neměnil a násobil jen aktuální data MV, odhad
   k 1. 1. 2021 by se od přepočtu podle sčítání lišil celostátně o +1,6 % (ČSÚ o +2,0 %).
   V obci je typická odchylka 1,13 % (ČSÚ 1,09 %), vážená počtem obyvatel 1,7 %
   (ČSÚ 2,1 %). Obě metody ale dělají stejnou chybu: odchod lidí, kteří se neodhlásí,
   nevidí ani registr, ani bilance ČSÚ.

**Co z toho plyne:** ČSÚ je standard, se kterým počítají ostatní statistiky, ale přesný je
jen kolem sčítání. Koncem desetiletí může být v obci vedle o jednotky procent, ve velkých
městech i víc. Data MV jsou vždy nad skutečností. Po přepočtu koeficientem ze sčítání
dávají číslo stejně dobré jako ČSÚ a mají ho o čtyři měsíce dřív.

## Celostátní součty (tis. osob, stav k 1. 1.)

| Rok | ČSÚ | ČSÚ před přepočtem | Drift ČSÚ | Občané MV | Cizinci MV | MV celkem | MV − ČSÚ | Koeficient |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2005 | 10 219 | | | 10 196 | 263 | 10 460 | +2,4 % | 0,976 |
| 2010 | 10 507 | | | 10 241 | 458 | 10 698 | +1,8 % | 0,981 |
| **2011** | **10 487** | 10 533 | **+0,44 %** | 10 251 | 459 | 10 710 | +2,1 % | 0,978 |
| 2015 | 10 538 | | | 10 262 | 445 | 10 707 | +1,6 % | 0,984 |
| 2020 | 10 694 | | | 10 288 | 589 | 10 877 | +1,7 % | 0,982 |
| **2021** | **10 495** | 10 702 | **+1,97 %** | 10 274 | 615 | 10 889 | +3,8 % | 0,962 |
| 2026 | 10 916 | | | 10 161 | 1 123 | 11 284 | +3,4 % | 0,964 |

Rok 2004 chybí záměrně: cizinci v něm ještě nejsou v evidenci MV všichni (53 tis.).
Plná řada je v [`vystup/scitani_cr.csv`](vystup/scitani_cr.csv). Koeficient v letech mezi
sčítáními počítá s ČSÚ, které ještě nebylo opravené. Jeho skok v roce 2021 je tedy
z velké části oprava ČSÚ, ne změna v registru.

## Podle velikosti obce (stav k 1. 1. 2021, mediány)

| Obyvatel | Obcí | MV − ČSÚ | Koeficient 2011 | Koeficient 2021 | Drift ČSÚ (absolutně) | Odhad z MV (absolutně) | Odhad z MV lepší než ČSÚ |
|---|---:|---:|---:|---:|---:|---:|---:|
| do 199 | 1 409 | +1,1 % | 0,995 | 0,988 | 1,3 % | 1,3 % | 40 % obcí |
| 200–499 | 1 989 | +1,5 % | 0,994 | 0,985 | 1,1 % | 1,1 % | 46 % |
| 500–1 999 | 2 146 | +1,8 % | 0,993 | 0,982 | 1,0 % | 1,0 % | 44 % |
| 2 000–9 999 | 575 | +2,2 % | 0,990 | 0,977 | 1,2 % | 1,2 % | 45 % |
| 10 000–49 999 | 109 | +3,2 % | 0,983 | 0,968 | 1,4 % | 1,5 % | 41 % |
| 50 000+ | 18 | +4,3 % | 0,972 | 0,958 | 1,4 % | 1,4 % | 50 % |
| **všechny** | **6 246** | **+1,7 %** | **0,993** | **0,983** | **1,1 %** | **1,1 %** | **44 %** |

*Drift ČSÚ* = o kolik se dopočet ČSÚ k 31. 12. 2020 lišil od přepočtu podle Sčítání 2021.
*Odhad z MV* = koeficient obce ze Sčítání 2011 × občané MV 2021 + cizinci MV 2021, proti
přepočtu podle Sčítání 2021.

## Velká města

| Město | Drift ČSÚ 2011 | Drift ČSÚ 2021 | MV − ČSÚ 2011 | MV − ČSÚ 2021 | Koeficient 2011 | Koeficient 2021 | Odhad z MV 2021 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Praha | +1,9 % | +6,0 % | +4,5 % | +7,7 % | 0,950 | 0,914 | +3,2 % |
| Brno | −2,2 % | +1,1 % | +6,6 % | +8,6 % | 0,935 | 0,914 | +2,1 % |
| Ostrava | +0,6 % | +1,0 % | +3,2 % | +4,3 % | 0,968 | 0,957 | +1,1 % |
| Plzeň | +0,7 % | +4,1 % | +2,2 % | +5,3 % | 0,977 | 0,943 | +3,1 % |

## Omezení

- Přepočtený stav k 1. 1. není sčítání samo. Je to stav ze dne sčítání (26. 3.) posunutý
  o bilanci prvního čtvrtletí, pro porovnání po obcích je ale nejlepší dostupný.
- ČSÚ a MV počítají cizince jinak: ČSÚ ty s dlouhodobým a trvalým pobytem, MV i přechodný
  pobyt nad 90 dní. Koeficient tenhle rozdíl schovává v části „občané“.
- V roce 2011 jsou čísla MV ze souborů jiného formátu (viz README, Starší roky), MČ do
  analýzy nevstupují.
