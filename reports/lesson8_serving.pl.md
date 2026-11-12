---
title: Zajęcia 8 — wznowienie i walidacja lokalnego API
updated: 2026-11-12
---

# Stan odzyskany po przerwaniu sesji

Zachowano istniejącą implementację FastAPI, kontrakt v1, snapshot OpenAPI,
testy API, notebook 04 oraz skrypty przygotowania i demonstracji.
Nie rozpoczynano implementacji od nowa.

## Dowody sprzed wznowienia

Katalog bazowy: `artifacts/lesson8/validation-20261112T161648360029Z/`.

- `api-tests-01.xml`: 51 testów, 0 błędów, 0 niepowodzeń, 0 pominięć.
- `full-tests-01.stdout.log`: niedokończony zapis, bez podsumowania i XML;
  nie stanowi dowodu PASS pełnego pytest ani bramki UCI.
- `isolation-01.stdout.log`: clone, sync, guard, rebuild i http-demo zakończone
  kodem 0. Brak końcowego `preparation.json` i wyniku izolowanych testów API;
  całego przygotowania nie można uznać za zakończone.
- `isolation-01/http-demo/evidence.json`: rzeczywisty HTTP PASS, live/ready 200,
  predykcja 200, błędne wejście 422, rejestr niezmieniony, serwer zatrzymany.
- Izolowany rebuild wykonał sześć eksperymentów i wybrał logistic.
  Podczas wznowienia nie powtarzano tego procesu.
- Brak zachowanych końcowych dowodów Ruff, pre-commit i kontroli uv.
  Nie można ustalić, czy każda z tych komend zdążyła wystartować przed awarią.

Kod API, kontrakt, skrypty, testy, OpenAPI, pyproject i lockfile porównano
bajtowo z izolowanym checkoutem: zgodne. Historyczny wynik HTTP pozostaje
adekwatny do obecnego kodu. Nie jest to dowód testu opublikowanego commita
ani innego komputera lub systemu operacyjnego.

## Wznowienie

Poprawiono polskie znaki w dopiskach README, notices i notebooku 04.
Rozdzielono przygotowanie sys.path i importy notebooka na osobne komórki,
usuwając dwa błędy Ruff E402. Kod inferencji i kontrakt nie wymagały zmian.
Wykonany notebook zapisano osobno; notebook źródłowy nie zawiera wyników.

## Końcowe wyniki

| Kontrola | Wynik | Dowód / polecenie |
| --- | --- | --- |
| Pełny pytest z rzeczywistą bramką UCI | PASS: 163, 0 pominięć, 238,39 s | `artifacts/lesson8/recovery-20261112-pytest.xml` i `.log` |
| API i kontrakt w izolowanym środowisku | PASS: 51, 0 pominięć, 114,25 s | `artifacts/lesson8/recovery-20261112-isolated-api.xml` i `.log` |
| Ruff lint całego repo | PASS | `.venv/Scripts/ruff.exe check .` |
| Ruff format całego repo | PASS: 64 pliki | `.venv/Scripts/ruff.exe format --check .` |
| pre-commit: jawna lista 16 plików zajęć 8 | PASS: oba hooki | `uv run --locked pre-commit run --files ...` |
| Lockfile | PASS: 201 pakietów | `uv lock --check --offline` |
| Zainstalowane zależności | PASS: 197 pakietów zgodnych | `uv pip check` |
| Importy lokalnej .venv | PASS | Python 3.12.10; FastAPI 0.162.0, Pydantic 2.14.1, Uvicorn 0.54.0, httpx 0.28.1 |
| Notebook 04 i rzeczywisty HTTP na izolowanym modelu | PASS: 4 komórki kodu | `artifacts/lesson8/recovery-20261112-notebook/04_model_serving.executed.ipynb` i `result.json` |
| Historyczna integralność | PASS: 1576 plików | `artifacts/lesson8/recovery-20261112-integrity.json` |
| Whitespace i pusty staging | PASS | `git diff --check`; `git diff --cached --exit-code` |

Pełny pytest uruchomiono przez `.venv/Scripts/python.exe -m pytest -q -rA`
z `BANK_MARKETING_QUALITY_CSV` wskazującym rzeczywisty
`data/raw/bank-additional-full.csv`, nowym basetemp i raportem XML.
Test potwierdził: train=24712, validation=6178, Dummy AP=0.128520557,
Logistic AP=0.185046394, recall=0.008816121 (7/794).
Testy korzystają z własnych katalogów tymczasowych; nie powtarzano
historycznych sześciu eksperymentów na UCI ani izolowanego rebuildu.

Osobne testy API wykonano interpreterem `.venv` wcześniejszego izolowanego
checkoutu przeciw aktualnym, zgodnym bajtowo plikom testów i kodu API.
To domyka brakujący krok testowy, ale nie dopisuje wyniku do starego
`preparation.json`; wcześniejsze niekompletne dowody pozostają nienaruszone.

Pre-commit otrzymał dokładnie pliki 1–16 z listy poniżej. Raport Markdown
utworzono później; hooki są ograniczone do Python/PYI/Jupyter.
Polecenia i zaobserwowane wyniki uv/Ruff/hooków zapisano w
`artifacts/lesson8/recovery-20261112-checks.json`.

**WARN:** pełny pytest zgłosił 5 ostrzeżeń: deprecacje TestClient/httpx
i SQLAlchemy, wskazówki MLflow dotyczące schematu integer oraz Windows
Proactor/ZMQ. Izolowane testy zgłosiły 3 ostrzeżenia tych bibliotek.
Nie zmieniano zależności ani schematu treningowego w celu ich ukrycia.
Notebook zgłosił również ostrzeżenia Jupyter/ZMQ dotyczące lokalnego kernela.
Wszystkie komórki i asercje zakończyły się poprawnie.

Helper routingu Skillpack nie zadziałał (`ModeDispatch.ps1`, null-valued
expression). Instrukcje wybranych skilli odczytano bezpośrednio.
Pierwsze kontrole uv blokował dostęp sandboxa do cache; zatwierdzone
wykonanie poza sandboxem zakończyło się PASS. Nie są to błędy implementacji API.

**Zajęcia 8 są kompletne w zakresie lokalnej implementacji i walidacji.**
Brak otwartych FAIL. Przed publikacją trzeba osobno zatwierdzić allowlistę,
staging i commit/push; test opublikowanego commita pozostaje niewykonany.

## Ochrona historycznych zasobów

`artifacts/lesson8/recovery-20261112-integrity.json` porównuje SHA-256 wszystkich
1576 ścieżek z `before.json`: brak usuniętych plików i nieoczekiwanych zmian.
Różnią się wyłącznie sześć oczekiwanych plików konfiguracji i dokumentacji:
`.gitignore`, README, ARCHITECTURE, THIRD_PARTY_NOTICES, pyproject i uv.lock.
Snapshot nie obejmuje plików zajęć 8 dodanych później.

Notebooki 01–03, historyczne dane, modele i rejestry objęte snapshotem
pozostają zgodne bajtowo. SHA-256 notebooka 01:
`bde4cafc0f78de987ff3aff2edd20e8b5002fc80781574b56292b57ba7f0bbc9`.
Jego wcześniejsza lokalna różnica względem HEAD została zachowana.

`docs/AI_USAGE.pl.md` i `docs/MOODLE_COMPLIANCE.pl.md` są ignorowane,
nie figurują w indeksie; `git log --all -- <oba pliki>` nie zwraca wpisów
w dostępnej lokalnie historii. Nie przesyłano ich do żadnej usługi.

## Zakres plików zajęć 8

1. `.gitignore`
2. `README.md`
3. `docs/ARCHITECTURE.md`
4. `docs/THIRD_PARTY_NOTICES.md`
5. `pyproject.toml`
6. `uv.lock`
7. `configs/serving-logging.json`
8. `docs/API_CONTRACT.md`
9. `docs/MODEL_SERVING.pl.md`
10. `docs/api/openapi-v1.json`
11. `notebooks/04_model_serving.ipynb`
12. `scripts/demo_lesson8.py`
13. `scripts/prepare_lesson8.py`
14. `src/serving.py`
15. `src/serving_contract.py`
16. `tests/test_serving.py`
17. `reports/lesson8_serving.pl.md`

Podczas wznowienia zmodyfikowano tylko README, THIRD_PARTY_NOTICES i notebook 04
oraz dodano ten raport i nowe lokalne dowody `artifacts/lesson8/recovery-20261112*`.
Stan Git zawiera ponadto wcześniejszą zmianę notebooka 01 oraz 12 nieśledzonych
raportów evidence zajęć 3–5; nie należą do allowlisty zajęć 8 i nie były edytowane.

## Ograniczenia

API pozostaje lokalną demonstracją. Recall validation to 7/794 przy progu 0.5;
nie potwierdza to przydatności biznesowej. Nie wykonywano ewaluacji final_test
ani replay, promocji modelu, wdrożenia, zajęć 9–13 ani Microsoft RAG.
Nie wykonywano stagingu, commita, push, dvc push, dvc repro, restore, reset,
clean ani usuwania istniejących plików. Publikacja wymaga osobnej zgody.
