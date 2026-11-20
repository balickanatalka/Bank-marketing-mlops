---
title: Zajęcia 9 — CI, kontener i łańcuch dostaw
updated: 2026-11-19
---

# Zakres i bramki

Workflow `.github/workflows/ci.yml` uruchamia się na push, pull request oraz ręcznie.
`functional_checks` odtwarza środowisko z `uv.lock`, wykonuje Ruff, pytest,
kontrakt v1, walidację syntetyki, obowiązkową bramkę UCI i krótki trening Dummy/LogisticRegression.
`functional_image` zależy wyłącznie od tych testów i buduje oraz sprawdza HTTP
kandydata. Czerwony audyt developerski nie blokuje zbierania dowodów funkcjonalnych.

Niezależne joby bezpieczeństwa to `security_dev` (wszystkie grupy),
`security_runtime` (profil `--no-dev` na Linuxie), `security_history` (pełna
dostępna historia Git) i `security_image` (osobny kandydat, SBOM/provenance i Trivy).
Każdy skaner zachowuje rzeczywisty kod wyjścia. Nie ma `continue-on-error`.
Zielone joby funkcjonalne obok czerwonego security nie oznaczają zielonego workflow.

`publish` wymaga sukcesu wszystkich sześciu jobów, ręcznego opt-in i gałęzi main.
Przed logowaniem do GHCR ponownie buduje, testuje i skanuje dokładnego kandydata,
który miałby zostać opublikowany. Sprawdza jego digest, potem taguje go bez
ponownej budowy. Błąd tej kontroli również blokuje login/push.
Ustawienie `scan-security: false` dotyczy wyłącznie duplikatu funkcjonalnego;
nie jest publiczną opcją workflow i nie może wystąpić w jobie security/publish.

Obraz jest budowany z SBOM i provenance, testowany przez prawdziwe HTTP,
zinwentaryzowany przez Syft i skanowany przez Trivy. HIGH i CRITICAL blokują
publikację, także gdy nie ma poprawki. Nie ma listy ignorowanych podatności.
Raporty są zachowywane również po błędzie. Cache obejmuje zależności i warstwy
budowania; nie zastępuje testów ani aktualnego skanu.

Wspólna lokalna akcja `.github/actions/check-image/action.yml` nie publikuje obrazów.
Do Actions wysyła tylko JSON/XML/TXT, nigdy archiwum OCI kandydata. Oddzielne joby
budują własnych kandydatów; unikamy transferu niezatwierdzonego obrazu między
runnerami. Oznacza to dodatkowe budowy i nie daje gwarancji czasu poniżej 3 minut.
Regresyjny `scripts/verify_ci_policy.py` wiąże warunki publikacji z testowanym
kontraktem, weryfikuje profile skanów i zakazuje maskowania błędów.

Po budowaniu CI eksportuje obraz OCI i uruchamia `scripts/verify_image_evidence.py`.
Bramka weryfikuje digest indeksu z wyniku BuildKit, hashe konfiguracji i wszystkich
warstw oraz powiązanie pól `subject` atestacji SPDX i SLSA v1 z manifestem
linux/amd64. Brak atestacji, zmiana obrazu lub inny subject przerywają job.
`image-attestations.json` trafia do artefaktów CI; duży plik OCI pozostaje tylko
na runnerze. To kontrola integralności i powiązania, nie weryfikacja podpisu.

Python jest przypięty do **3.12.16**, uv w CI i Dockerze do **0.13.9**.
Digest bazy Python/Debian jest zapisany w Dockerfile. Zmiana względem etapu 8
(Python 3.12.10) wynika z rzeczywistych wyników skanu bezpieczeństwa.
Tornado podniesiono wyłącznie z 6.6 do 6.6.1 w locku.
Historyczne raporty zachowują pierwotne wersje i wyniki.

# Odtworzenie kontroli lokalnych

Po świeżym klonie wymagane są Python/uv i Docker Desktop w trybie Linux.
Starszy uv może nie znać nowych wydań Pythona: użyj uv 0.13.9.

```powershell
uv sync --locked
uv run --locked ruff check src tests scripts notebooks
uv run --locked ruff format --check src tests scripts notebooks
uv run --locked pytest -q
uv run --locked python -m scripts.ci_smoke --output artifacts/lesson9/my-smoke
docker build --sbom=true --provenance=mode=min -t bank-marketing-api:dev .
uv run --locked python -m scripts.container_smoke --image bank-marketing-api:dev
```

Katalog wynikowy treningu musi być nowy. Nie nadpisujemy poprzednich dowodów.
Test bez modelu sprawdza liveness 200, readiness 503 i predykcję 503.
To poprawny wynik testu awarii, a nie działająca usługa predykcyjna.
Pełne testy kontenera z własnym modelem syntetycznym:

```powershell
$env:BANK_MARKETING_TEST_IMAGE = 'bank-marketing-api:dev'
uv run --locked pytest tests/test_serving.py -q -k container_http
Remove-Item Env:BANK_MARKETING_TEST_IMAGE
```

Syntetyczny fixture CI jest generowany deterministycznie, walidowany tym samym kontraktem
21 kolumn i dzielony chronologicznie. Modele korzystają ze wspólnego preprocessingu.
Metryki dotyczą wyłącznie syntetycznej kontroli działania kodu. Nie dowodzą jakości
na UCI i nie zastępują bramki `tests/test_uci_quality.py`. Test UCI wymaga jawnego
`BANK_MARKETING_QUALITY_CSV`; lokalnie bez niego jest pomijany. W functional_checks
CI zmienna wskazuje świeżą kopię pobraną przez `scripts.ci_uci prepare` z oficjalnego
UCI do artifacts/ci/uci/. Pobranie weryfikuje manifest SHA-256, rozmiar, wymiary
i schemat przed testami. Po pytest `scripts.ci_uci verify-tests` wymaga dokładnie
jednego zakończonego sukcesem testu jakości UCI w JUnit. Brak testu, SKIP,
duplikat, failure lub error powoduje FAIL. Niedostępne lub błędne dane również
powodują FAIL; nie ma fallbacku do lokalnego zbioru ani syntetyki.
Do artefaktów trafiają tylko raporty JSON i JUnit, bez CSV, modeli i baz MLflow.
Final test i replay nie są używane do treningu ani wyboru modelu.

Zmiana bramki UCI jest przygotowana lokalnie. Jej potwierdzenie na GitHubie
wymaga osobno zatwierdzonej publikacji i nowego przebiegu; wcześniejszy CI
pomijał rzeczywistą bramkę UCI. Szczegóły i dowody lokalne:
[raport obowiązkowej bramki UCI](../reports/lesson9_uci_ci_20261120.pl.md).

# Model poza obrazem

Obraz zawiera aplikację, zależności i kontrakt, bez danych, modeli, notebooków,
sekretów i prywatnych dokumentów. Kontekst budowania ma jawną listę dozwolonych
plików w `.dockerignore`. Proces działa jako UID/GID 10001, bez dodatkowych
capabilities, na systemie plików tylko do odczytu; `/tmp` to nietrwały tmpfs.
Port Compose jest dostępny tylko na `127.0.0.1:8000`.

SQLite MLflow zapisuje bezwzględne URI, dlatego nie przenosimy rejestru Windows
wprost do kontenera Linux. Eksporter odczytuje wskazaną wersję, wykonuje istniejącą
bramkę jakości rejestru i kopiuje pakiet. Nie trenuje i nie zmienia aliasów.
Paczka zawiera model skops, manifest, lineage, ML-BOM i receipt. Hash receipt
operator przekazuje oddzielnie; obejmuje on hash manifestu modelu i ML-BOM.
Kod sprawdza komplet plików, zależności i integralność przed deserializacją.

Użyj istniejącego pliku `evidence.json` z udanego przygotowania zajęć 7/8 oraz
konkretnej wersji zapisanej w tym dowodzie. Zmienna `$evidence` poniżej musi wskazać
ten plik. Jeśli nie ma modelu po świeżym klonie, przygotuj go zgodnie z
[instrukcją zajęć 8](MODEL_SERVING.pl.md); nie kopiuj dawnych baz ani datasetów.

```powershell
# Ustaw $evidence na plik evidence.json, a $version na model_version z tego pliku.
$env:BANK_MARKETING_SERVING_RECEIPT_SHA256 = uv run --locked python -m src.serving_bundle --evidence $evidence --version $version --output artifacts/lesson9/my-bundle
$env:BANK_MARKETING_BUNDLE_DIR = (Resolve-Path artifacts/lesson9/my-bundle).Path
docker compose config --quiet
docker compose up --build -d
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

Swagger: `http://127.0.0.1:8000/docs`. Zatrzymanie: `docker compose stop`.
Zmiana modelu lub hasha wymaga świadomego restartu usługi. Hash nie jest podpisem:
osoba mogąca zmienić paczkę i konfigurację zaufania może podmienić oba.
Eksportowany ML-BOM wskazuje źródło/licencję/hash danych, wersję modelu,
metryki, eksperyment i kod. Syntetyczny ML-BOM CI jest oznaczony osobno i nie
udaje wdrożonego modelu UCI.

# Publikacja i pozostałe dowody

Domyślne przebiegi nie publikują obrazu. Ręczny `workflow_dispatch` z `publish=true`
na `main` publikuje do GHCR dopiero po zielonych bramkach. Ten sam przetestowany
obraz jest tagowany i wysyłany bez ponownej budowy. Workflow zapisuje digest
budowania i digest opublikowany w rejestrze. Do dalszego dostarczania należy użyć
`ghcr.io/owner/repository@sha256:...`, zamiast ruchomego tagu.
Provenance nie jest tutaj podpisem kryptograficznym ani dowodem zakończonego wdrożenia.

Zdalne Actions, GHCR oraz ochrona gałęzi wymagają opublikowania zmian i konfiguracji
repozytorium przez uprawnionego właściciela. Wymagane checki to
`functional_checks`, `functional_image`, `security_dev`, `security_runtime`,
`security_history` i `security_image`. `publish` jest warunkowy i nie powinien
być wymaganym checkiem PR. Nie włączono ochrony gałęzi ani nie wysłano obrazu.
Nie ma jeszcze dowodu zielonego/czerwonego PR na GitHubie ani pomiaru czasu runnera.
Cel poniżej trzech minut pozostaje celem do zmierzenia.

Stan po lokalnym wdrożeniu wariantu 1 i rekomendowana allowlista:
[raport techniczny zajęć 9](../reports/lesson9_technical_public.pl.md).
Wyniki lokalne nie są wynikiem niewykonanego jeszcze GitHub Actions.

# Aktualne ograniczenia bezpieczeństwa

`diskcache==5.6.3`, zależność DVC, ma zgłoszenie `PYSEC-2026-2447` bez wydanej
poprawki: zapis do katalogu cache przez napastnika może prowadzić do wykonania
kodu przez pickle. Lokalny, zaufany cache ogranicza ekspozycję, ale nie usuwa
zgłoszenia. Pełny audyt pozostaje blokujący. Nie wolno udostępniać cache
niezaufanym użytkownikom ani akceptować cudzych plików cache/modeli.

Obraz Debian ma również zgłoszenia HIGH bez dostępnych poprawek według
ostatniego lokalnego skanu. Aktualny publiczny raport powyżej podaje wyniki,
stan dowodów i jawną allowlistę. Nie zastępuje nowego skanu przed publikacją.
Bieżąca minimalizacja usuwa wyłącznie niepotrzebny pakiet `mount`, bez autoremove
i bez usuwania Essential. Smoke test sprawdza brak mount/umount i zależności DVC
w runtime. Wynik spadł z 47 do 43 HIGH, ale 11 CVE i podatność developerskiego
diskcache pozostają otwarte według ostatnich lokalnych dowodów.
To otwarte ryzyka; nie deklarujemy czystego skanu ani ukończenia poziomu 4,0/5,0.
Kolejny krok to analiza tych zgłoszeń i bezpieczna naprawa lub uzasadniona decyzja
o zmianie komponentów. Nie dodajemy ogólnego `ignore-unfixed` ani `continue-on-error`.

# Źródła i licencje narzędzi

- [uv i Docker](https://docs.astral.sh/uv/guides/integration/docker/): MIT OR Apache-2.0.
- [Docker attestations](https://docs.docker.com/build/metadata/attestations/): SBOM i provenance.
- [pip-audit](https://github.com/pypa/pip-audit): Apache-2.0.
- [Gitleaks](https://github.com/gitleaks/gitleaks): MIT; skanuje również historię.
- [Trivy](https://github.com/aquasecurity/trivy): Apache-2.0.
- [Syft](https://github.com/anchore/syft): Apache-2.0.
- [actionlint](https://github.com/rhysd/actionlint): MIT.

Licencje bibliotek pozostają w zainstalowanych pakietach, a ich inwentarz w SBOM.
Przed publiczną redystrybucją obrazu trzeba domknąć przegląd notices i obowiązków
licencyjnych wszystkich faktycznie dołączonych komponentów.
