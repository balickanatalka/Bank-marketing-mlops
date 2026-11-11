---
title: Raport testów zajęć 6
updated: 2026-11-11
---

# Raport testów zajęć 6

Punkt wyjścia to commit `2ed597aa10c86bfc111faefffede872b0b5b55138`
i 67 testów z zajęć 5. Audyt wykazał istniejące pokrycie walidacji surowych
danych, wykluczenia `duration`, transformacji batch/single, serializacji
i dopasowania wyłącznie na train. Zajęcia 6 dodały siedem przypadków pytest
i rozszerzyły istniejący test etapów o kontrolę negatywną jakości.

## Wyniki końcowe

| Polecenie | Wynik |
| --- | --- |
| `uv run --locked pytest -q` z `BANK_MARKETING_QUALITY_CSV` | **PASS** — 74 testy, 19,83 s, bez pominięć. **WARN** — istniejące ostrzeżenie SQLAlchemy o przestarzałej strategii `noload` z testu MLflow. |
| `uv run --locked pytest -q -s tests/test_uci_quality.py` z `BANK_MARKETING_QUALITY_CSV` | **PASS** — 1 test, 6,70 s. Regresja zaakceptowana, Dummy odrzucony. |
| `uv run --locked ruff check .` | **PASS**. |
| `uv run --locked ruff format --check .` | **PASS**. |
| `uv run --locked pre-commit run --files <lista>` | **PASS** — oba hooki Ruff dla plików Python i notebooków śledzonych przez Git oraz nowych modułów Hypothesis i bramki UCI. |
| `uv lock --check` i `uv pip check` | **PASS** — spójny lockfile i zgodne zależności środowiska. |
| `dvc dag --dot` | **PASS** — graf od `download` do `evaluate`. |
| `dvc status --json` | **WARN** — ostatni odczyt wykazał cztery nieaktualne etapy. Stan zaakceptowany po audycie odczytowym, bez ponownego uruchamiania DVC przy dodaniu bramki UCI. |

## Bramka na rzeczywistej walidacji UCI

| Model odtworzony w pamięci | AP validation | Recall klasy dodatniej | Decyzja |
| --- | ---: | ---: | --- |
| Regresja logistyczna | 0,185046394 | 0,008816121 | **PASS** |
| Dummy | 0,128520557 | 0 | **Odrzucony zgodnie z oczekiwaniem** |

Fit obejmował 24 712 wierszy train, a ocena 6 178 wierszy validation.
Ta sama bramka wymaga AP ściśle powyżej zmierzonego AP Dummy i recall
co najmniej 7/794, zgodnie z referencją zajęć 5. Próg klasyfikacji wynosi 0,5.
Uruchomienie wykorzystało tymczasową kopię CSV z SHA-256 zgodnym z manifestem.
Historyczne modele i metryki służyły jako odniesienie dla konfiguracji i progu.
Wyniki w tabeli pochodzą ze świeżych predykcji. Bez wskazania pliku test
zgłasza `SKIP`, a wskazanie brakującego pliku powoduje `FAIL`.

## Dowody spełnienia wymagań

- Dwa testy jednostkowe preprocessingu, w tym osobne przypadki tekstu i nieskończoności.
- Walidacja i blokada `duration` pokryte istniejącymi testami oraz asercją na polach zapisanego modelu.
- Model logistyczny przechodzi próg AP 0,90 na syntetycznej walidacji, a Dummy z AP 0,50 uruchamia tę samą asercję odrzucającą.
- Testy zgodności batch/single, serializacji i fit tylko na train pozostają aktywne. Test artefaktu dodaje porównanie predykcji przed i po rekonstrukcji wejścia z JSON.
- Kontrakt sprawdza pola i typy wejściowe, klasy, kształty, typy i zakresy wyjścia. Usunięcie `age` wywołuje oczekiwany błąd.
- Dwa testy Hypothesis, po 40 przykładów, sprawdzają normalizację prawdopodobieństw i kształty dla partii od 1 do 20 rekordów.
- Hypothesis jest przypięty do `6.131.9`, a jego lokalny cache jest ignorowany przez Git.
- [Strategia testów](../docs/TEST_STRATEGY.md) zawiera mapę kryteriów i polecenia. README odsyła do strategii i raportu. Opcjonalny notebook pominięto.

## Stan DVC i granice walidacji

Ten sam zestaw rozbieżności widniał przed zmianami oraz w
[raporcie zajęć 5](evidence/lesson5-checks-20261102T154655424744Z-9a6c95d2.json).
`validate` zgłasza brak wyjścia w cache. `prepare`, `train` i `evaluate`
zgłaszają brakujące zależności lub wyjścia oraz zmieniony `src/pipeline.py`.
`train` i `evaluate` zgłaszają też zmienione `pyproject.toml` i `uv.lock`.
Dodanie Hypothesis zmienia te dwie zależności względem zapisanych przez DVC
odcisków. Odczyt wykonano narzędziem DVC z przypiętego środowiska.

Bramka 0,90 dotyczy fixture z przewidywalnym sygnałem. Metryki rzeczywistych
eksperymentów z zajęć 5 pozostają w historycznym raporcie. Notebooki 01/02 i
`dvc.lock` zachowały identyczne sumy SHA-256. Testy zapisywały artefakty
w katalogach tymczasowych pytest. Indeks Git jest pusty.
