# PLAN: undeciphered-scripts

Roboczy plan działania.
Zasada: **jeden krok naraz**. Po każdym kroku krótki raport i aktualizacja tego pliku. Następny krok zaczynam dopiero po Twoim „ok”.

---

## Stan na teraz

### Na GitHubie (`main`)
- README projektu, LICENSE, `scripts/fetch_okr.sh`, `scripts/fetch_lexicons.sh`
- Study 01 (Khipu-ML): kod, wyniki, wykres. **Zakończone.**
- uv (`pyproject.toml`, `uv.lock`), `AGENTS.md`, ruff, ten plan

### Lokalnie, jeszcze bez commita
- Study 02: skrypt `null_test.py` (**niedokończony**, patrz krok 2)

### Zablokowane: wymaga Ciebie
Proxy nie pozwala mi zmieniać ustawień repozytorium. Do zrobienia w GitHub → Settings:
- **Nazwa:** `undeciphered-scripts`
- **Description:**
  `Reproducible, skeptical computational studies of undeciphered writing systems (Inca khipu, Indus, Linear A, Rongorongo, Proto-Elamite): replications and null tests of AI decipherment claims.`
- **Topics:**
  `khipu quipu decipherment undeciphered-scripts writing-systems computational-linguistics digital-humanities archaeology inca quechua linear-a indus-script rongorongo machine-learning reproducibility replication null-hypothesis-testing python`

---

## Kroki

### Krok 1: commit „uv + AGENTS.md + lint” ✅
- [x] Study 01 przez `uv run`: `results/` bez zmian.
- [x] Commit i push na `main`.

### Krok 2: Study 02, test zerowy dla ALBA
Problem: pierwsze uruchomienie zostało przerwane po 10 minutach. Pełna przestrzeń (6,2 mln mapowań × 4 modele zerowe × 40 losowań, plus ocena na khipu spoza kalibracji) jest za wolna.
- [ ] Optymalizacja: na khipu spoza kalibracji liczyć percentyl na próbce 200 tys. mapowań zamiast wszystkich 6,2 mln.
- [ ] Najpierw przestrzeń `Ca_syllables` (43 680 mapowań, 200 losowań), szybko. Raport.
- [ ] Potem `all_CV_syllables` (40 losowań) w tle, z limitem czasu.
- [ ] README badania według szablonu z AGENTS.md, tabela w głównym README, commit, push.

### Krok 3: Study 03, replikacja modelu BERT dla kolorów (Clindaniel)
- [ ] Ustalić, czy kod i dane są dostępne (Zenodo jest zablokowane w moim środowisku, może GitHub).
- [ ] Replikacja plus test zerowy, np. przetasowane kolory w obrębie khipu.

### Krok 4: coś pozytywnego, zbiór testowy
- [ ] Zebrać pary khipu–dokument kolonialny o znanej treści: dolina Santa (Medrano i Urton 2018), Collata (Hyland).
- [ ] Zdefiniować test, który każda przyszła propozycja odszyfrowania musi zdać.

### Później
- Linear A, proto-elamickie: rozpoznanie dostępnych korpusów.

---

## Dziennik
- 2026-10-01: krok 1 zrobiony (uv, AGENTS.md, push). Repo publiczne: jutro publikacja wątku o Study 01.
- 2026-10-01: repozytorium utworzone, Study 01 wypchnięte. Przejście na uv i AGENTS.md lokalnie. Study 02 przerwane (timeout).
