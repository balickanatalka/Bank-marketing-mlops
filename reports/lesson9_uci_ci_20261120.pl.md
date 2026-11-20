---
title: Zajęcia 9 — obowiązkowa bramka jakości UCI w CI
updated: 2026-11-20
---

# Wynik i zakres

Przygotowano lokalnie minimalną zmianę functional_checks: pobranie publicznego
UCI, weryfikację manifestu i schematu oraz obowiązkowy dowód wykonania rzeczywistej
bramki jakości. Zachowano pełny pytest, syntetyczne testy i kontrolny trening.
Nie zmieniono bramek bezpieczeństwa ani reguły publikacji obrazu.

Punkt odniesienia: `26c640b9b872eb63c26415dad4f14e42b26be068`.
Poprzedni GitHub Actions miał 263 PASS/2 SKIP; jednym z pominiętych testów
była rzeczywista bramka UCI. Ten raport dotyczy nowej lokalnej poprawki.
**Zdalne potwierdzenie tej poprawki: NOT RUN.** Nie uruchamiano ponownie CI.

Nie wykonano stagingu, commita, pusha, publikacji obrazu, operacji DVC ani
kolejnych zajęć. Historyczne wyniki i prywatne dokumenty pozostają bez zmian.

# Przepływ na czystym runnerze

1. uv sync --locked i dotychczasowe kontrole polityki CI/Ruff odtwarzają środowisko.
2. scripts.ci_uci prepare tworzy nowy katalog artifacts/ci/uci/ i pobiera dokładny
   zagnieżdżony CSV przez istniejący downloader src/data/download.py.
3. Downloader weryfikuje SHA-256, rozmiar i wymiary z metadata/data_manifest.json.
   Nowy krok dodatkowo wykonuje istniejącą walidację schematu/jakości danych.
4. BANK_MARKETING_QUALITY_CSV w functional_checks wskazuje tę kopię CSV.
   Pełny pytest uruchamia niezmieniony test_uci_validation_quality_gate.
5. scripts.ci_uci verify-tests analizuje świeży JUnit. Wymaga dokładnie jednego
   przypadku tests.test_uci_quality.test_uci_validation_quality_gate bez
   skipped/failure/error. Brak, duplikat, niepoprawny XML lub brak pliku przerywa job.
6. Dotychczasowy syntetyczny trening kontrolny pozostaje osobnym krokiem.

Niedostępne UCI lub błędny CSV powoduje niezerowy kod wyjścia przygotowania.
Nie ma fallbacku do danych z poprzedniego komputera, syntetyki ani DVC cache.
Nowy katalog jest wymagany; skrypt odmawia nadpisania poprzedniego przebiegu.
Istniejący downloader wykonuje maksymalnie trzy próby z limitem czasu/rozmiaru.
Nie zmieniano tych limitów ani przypiętego manifestu.

Test jakości zachowuje historyczne progi: Average Precision LogisticRegression
musi przekraczać Dummy, recall nie może być niższy niż 7/794. Korzysta z train
i validation oraz wspólnego preprocessingu. Nie zapisuje nowego modelu do
głównego registry. Final_test i replay nie są używane do wyboru ani strojenia.

# Dane i prywatność artefaktów

Oficjalne źródło:
[UCI Bank Marketing](https://archive.ics.uci.edu/static/public/222/bank+marketing.zip).
Wariant: bank-additional-full, CC BY 4.0, 41 188 wierszy i 21 kolumn.
Przypięty SHA-256 CSV:
`74adfc578bf77a7ff4bb1ba4a9f8709d9e3c6907342959c2c8416847e0afb4d8`.
Rozmiar: 5 834 924 bajty. Źródło, licencja i metodologia pozostają zgodne
z repozytoryjnym manifestem i [kartą danych](../docs/DATA_CARD.md).

Do upload-artifact w functional_checks dopuszczono dokładnie:

```text
artifacts/ci/tests.xml
artifacts/ci/smoke/*.json
artifacts/ci/uci/validation.json
artifacts/ci/uci/quality-gate.json
```

Nie wysyłamy CSV, modeli, baz MLflow ani katalogu testów. Walidator polityki
odrzuca rozszerzenie tej listy na surowe dane. validation.json zawiera tylko
metadane i zagregowaną walidację oraz quality_test_executed=false; dowód
wykonania testu jest osobnym quality-gate.json z quality_test_executed=true.
Nie wolno mylić PASS pobrania/walidacji z PASS jakości modelu.

# Dowody lokalne

Nowy katalog dowodów: `artifacts/lesson9/uci-ci-20261120-01/`.
Rzeczywiste pobranie rozpoczęło się bez CSV w tym katalogu. Nie kopiowano
lokalnego data/raw, modeli ani baz. Otrzymane bajty i schemat przeszły kontrolę.

| Kontrola | Wynik / dowód |
| --- | --- |
| Rzeczywiste pobranie z UCI i manifest | PASS; official-download.result.json, uci/validation.json |
| Walidacja schematu | PASS: 41 188 wierszy, 21 kolumn |
| Testy modułu przygotowania, polityki CI i danych | PASS: 117 testów; unit-tests.xml |
| Pełny pytest z nowo pobranym CSV | PASS: 287 PASS, 1 SKIP (Docker); full-tests.xml i .result.json |
| Dowód niepominiętej bramki | PASS; quality-evidence.log, .result.json i uci/quality-gate.json |
| Próba JUnit bez bramki UCI | Oczekiwane odrzucenie kodem 1; negative-missing-gate.result.json |
| Próba JUnit ze SKIP bramki UCI | Oczekiwane odrzucenie kodem 1; negative-skipped-gate.result.json |
| Ruff check i format | PASS; ruff-check/ruff-format.result.json |
| actionlint 1.7.12 | PASS; actionlint.result.json |
| uv lock --check i uv pip check | PASS; bez zmian zależności |
| Wpływ na inne joby | PASS; impact.json |
| Integralność historycznych plików | integrity.json; znane pliki sprawdzone osobno od ograniczeń inwentaryzacji |

Testy negatywne obejmują niewłaściwy hash, zgodne bajty o błędnym schemacie,
niedostępność sieci i niewłaściwe źródło; żaden nie może utworzyć raportu PASS.
Kontrole JUnit obejmują SKIP, failure, error, brak, duplikat, inną nazwę/klasę
i uszkodzony XML. Testy polityki odrzucają usunięcie lub warunkowe pominięcie
przygotowania/weryfikacji, inny CSV/JUnit, filtrowanie pytest i upload CSV.

Nie wykonywano ponownych identycznych prób aktualizacji zależności lub obrazu,
pip-audit ani Trivy. Ta poprawka nie wymaga zmiany kontenera lub kodu API;
ich wcześniejsze wyniki pozostają dowodami historycznymi, nie nowymi testami.

# Niezmienione blokady i ograniczenia

Wszystkie joby poza functional_checks są niezmienione, podobnie jak wspólna
akcja obrazu, sekrety/tokeny, uprawnienia, triggery i warunek publish.
Security działa niezależnie od niepowodzenia UCI. Publish nadal wymaga sukcesu
wszystkich sześciu jobów, main i osobnego ręcznego opt-in; zwykły push nie
publikuje obrazu. Brak lub pominięcie UCI obniża functional_checks do FAIL,
więc nie może otworzyć publikacji obrazu.

Nadal otwarte według ostatnich potwierdzonych skanów:

- **FAIL:** diskcache 5.6.3 / PYSEC-2026-2447 w pełnym profilu developerskim.
- **FAIL:** 43 HIGH / 11 CVE systemowych w Trivy, 0 CRITICAL.
- **NOT RUN:** GitHub Actions nowej poprawki UCI; lokalny PASS nie zastępuje
  udanego pobrania i wykonania bramki na czystym runnerze.

Nie zaakceptowano ryzyka ani nie zmieniono progów. Zewnętrzna niedostępność
UCI może teraz prawidłowo spowodować FAIL functional_checks. Dalsza ocena
nie może pomijać tego ograniczenia dostępności źródła.

# Dokładna allowlista tej poprawki

```text
.github/workflows/ci.yml
scripts/ci_uci.py
scripts/verify_ci_policy.py
tests/test_ci_uci.py
tests/test_ci_policy.py
docs/CI_SUPPLY_CHAIN.pl.md
reports/lesson9_uci_ci_20261120.pl.md
```

Poprzedni nieśledzony raport próby naprawy bezpieczeństwa i historyczne dowody
innych zajęć nie należą do tej allowlisty. Prywatne dokumenty, notebooki 01–04,
dataset, modele, cache, bazy MLflow i artefakty pozostają poza publikacją zmian.
Nic nie zostało dodane do indeksu.
