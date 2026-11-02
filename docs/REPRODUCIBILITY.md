# Odtwarzalność

## Lokalne eksperymenty MLflow

```powershell
uv sync --locked
uv run --locked python -m scripts.verify_lesson5
```

Weryfikator uruchamia dwie nowe, niezależne serie po sześć modeli, na tej samej
walidacji i konfiguracji. Sprawdza zgodność wszystkich metryk z tolerancją 1e-12,
wyboru modelu, protokołu, hashy splitów, odczytu MLflow i predykcji po serializacji.
Każda seria ma osobny SQLite i katalog artefaktów pod `artifacts/lesson5/`.
Nie nadpisuje wcześniejszych modeli i danych. Nowy raport ma unikalną nazwę
`reports/evidence/lesson5-reproduction-<timestamp>-<id>.json`.

Pojedyncza seria: `uv run --locked python -m src.experiments`.
Eksport wybranej serii: `uv run --locked python -m src.experiment_report artifacts/lesson5/<batch>`.
Eksporter odmawia nadpisania istniejących raportów; dla kolejnej serii użyj
`--reports artifacts/lesson5/<batch>/export`. Notebook odczytuje zapisany publiczny
snapshot, bez uczenia i bez dostępu do final test/replay.

Interfejs MLflow dla konkretnej serii, z katalogu głównego repozytorium:

```powershell
uv run --locked mlflow server --backend-store-uri sqlite:///artifacts/lesson5/<batch>/tracking/mlflow.db --host 127.0.0.1 --port 5005 --workers 1 --no-serve-artifacts
```

Zastąp `<batch>` identyfikatorem istniejącej serii. Magazyn artefaktów jest zapisany
w metadanych eksperymentu i pozostaje lokalny. SQLite, sidecary, modele oraz cache
są ignorowane przez Git. Nie uruchamiaj serwera na 0.0.0.0 ani nie dodawaj lokalnej bazy do Git.
MLflow na Windows nie zapewnia backendu wykonywania zadań; trening wykonuje CLI,
a serwer służy do przeglądania eksperymentów. Nie korzystamy z tego backendu zadań.

Odtworzenie potwierdzono w tym samym środowisku Python 3.12 i uv.lock, nie na drugim
komputerze. Run ID, czas, lokalny URI oraz metadane Git mogą się różnić, choć metryki
są zgodne. Kod niezacommitowany jest oznaczony jako dirty i identyfikowany hashami.

Dotychczasowy dvc.yaml nadal odtwarza baseline zajęć 4. Eksperymenty MLflow mają
osobny CLI i zapisują hash dvc.lock oraz przypięty SHA-256 tych samych danych.
Zmiany src/pipeline.py, pyproject.toml i uv.lock powodują prawidłową nieaktualność
odpowiednich zależności baseline w DVC. Nie nadpisano historycznego dvc.lock
ani nie uruchomiono repro w głównym workspace. Kolejność i semantyka etapów są zachowane.

MLflow/SQLAlchemy emitują ostrzeżenie deprecacyjne loadera `noload`; zapis i odczyt
wszystkich parametrów/metryk są osobno sprawdzane. Nie ukrywa się ostrzeżenia w testach.

Aktualizacja zajęć 4: 2026-11-02.

## Zajęcia 4: aktualny pipeline

`dvc.yaml` i `configs/lesson4.yaml` definiują etapy download, validate, prepare,
train i evaluate. Jawne deps obejmują kod, manifest, dane i artefakty; params
wskazują klucze konfiguracji YAML, a metrics wskazują raport validation.
Etap prepare obejmuje również pełną walidację jako zabezpieczenie samodzielnego CLI.
Nie dublujemy pobierania ani implementacji treningu.

```powershell
uv sync --locked
uv run --locked dvc repro
uv run --locked dvc repro
uv run --locked dvc status
uv run --locked python -m scripts.verify_lesson4
```

Pierwsze dwa repro weryfikator wykonuje w nowym katalogu systemowego TEMP,
bez oryginalnego CSV i cache. Kolejna próba zmienia wyłącznie model.max_iter;
przeliczają się train i evaluate. Następnie uszkadza tylko kopię CSV i wykonuje
`dvc repro --single-item validate`: oczekiwany błąd SHA-256 zatrzymuje ten przebieg,
bez zmiany modelu. To test wymuszonej walidacji uszkodzenia; zwykłe pełne repro
może wcześniej naprawić zmieniony raw z poprawnego cache, co jest poprawnym zachowaniem DVC.
Weryfikator kontroluje fingerprinty pierwotnych danych, modeli, raportów,
notebooka, prywatnych notatek, cache oraz indeksu Git.

Każdy przebieg zapisuje osobny `reports/evidence/lesson4-dvc-<timestamp>-<id>.json`,
także przy błędzie. Logi mają usunięte lokalne ścieżki. Kopia testowa pozostaje
w TEMP do inspekcji, bez automatycznego sprzątania. `baseline.lock` w tej kopii
zachowuje lock pierwszego poprawnego przebiegu, przed eksperymentami. Weryfikator
eksportuje go jako główny `dvc.lock` tylko jeśli plik jeszcze nie istnieje;
w przeciwnym razie raportuje zgodność, bez nadpisywania istniejącego locka.

Główny workspace nie przechodzi treningu podczas weryfikacji. Jego `dvc status`
może więc prawidłowo pokazywać brak nowych wyjść mimo zapisanego locka.
Zwykłe repro zapisuje nowe wyniki w `data/lesson4/processed` i `artifacts/lesson4/`;
stare katalogi data/processed, artifacts/models i artifacts/reports pozostają osobne.
Nie wykonuj `--force` na wcześniejszych wynikach bez świadomej zgody na ich odtworzenie.
Nie potrzeba remote ani DagsHub; `dvc push` nie jest częścią procedury.

Seed dla DVC ustawiaj w configs/lesson4.yaml. Obecność PROJEKT_SEED jest odrzucana,
aby DVC nie pominął zmiany nieśledzonego parametru. Dotychczasowe CLI nadal
obsługuje tę zmienną. Nie ma API; train/serve skew jest testowane przez porównanie
wsadu z pojedynczym rekordem i zapisanym Pipeline, bez ponownego fit.

`dvc.lock` pochodzi z izolowanej kopii bez SCM, na tym samym komputerze i w tym
samym środowisku uv.lock. Nie dowodzi niezależnej reprodukcji na innym sprzęcie;
metadane Git treningu w zwykłym repo będą inne niż w kopii bez SCM.
Final test i replay są tylko przygotowywane i hashowane, nigdy oceniane przez model.

Zakres projektu obejmuje lokalny pipeline MLOps: pobieranie i walidację danych,
przygotowanie cech, trening oraz ewaluację modeli na zbiorze validation.
Nie wykonano bezpośredniego porównania z pełnym archiwum materiałów prowadzącego,
które nie było dostępne. MLflow (zajęcia 5) i Microsoft RAG pozostają przyszłymi etapami.

Środowisko referencyjne: Windows, Python 3.12.10, uv 0.13.4.
`.python-version` przypina interpreter, `uv.lock` wersje zależności, a manifest
danych sumę SHA-256 źródłowego CSV. Polecenia z katalogu głównego repozytorium:

```powershell
uv sync --locked
uv run --locked dvc repro
uv run --locked pytest -q
uv run --locked python scripts/verify_reproduction.py
```

Pierwsze uruchomienie wymaga internetu do pobrania zależności i danych UCI.
Po przygotowaniu środowiska i CSV trening działa lokalnie bez usług płatnych.
Zmiana locka lub manifestu jest zmianą wersji eksperymentu, nie częścią zwykłego startu.

Skrypt reprodukcji tworzy lokalny klon historii w ignorowanym `artifacts/` i nakłada
bieżące pliki src/configs/metadata/tests oraz pliki środowiska. Odtwarza nową `.venv`,
pobiera CSV, wykonuje trening, ewaluację, testy, ponowienie oraz wariant seed=123.
Porównuje metryki i rzeczywistą wersję Pythona z pinem. Kopie kontrolne pozostają
na dysku; każde uruchomienie zajmuje dodatkowe miejsce.

Raport `reports/evidence/reproduction.json` zawiera komendy, kody wyjścia i wyniki.
Ścieżki lokalnego projektu i profilu są zastępowane przez `PROJECT_ROOT` i `<USER_HOME>`.
Kontrole stylu, testów i hooków zapisuje `scripts/verify_checks.py` w `checks.json`.

Potwierdzono zgodność metryk w nowym środowisku na tym samym komputerze oraz
przy powtórzeniu i seed=123. Nie wykonano niezależnego testu na drugim komputerze.
Lokalny klon z nałożonym kodem nie jest dowodem odtworzenia zdalnej opublikowanej wersji.
Procedurę niezależnej weryfikacji opisuje [INDEPENDENT_REVIEW.md](INDEPENDENT_REVIEW.md).
Na innym sprzęcie porównanie obliczeń powinno uwzględniać tolerancję numeryczną;
identyczne bajty plików joblib nie są wymagane.

## Zajęcia 3: historyczny punkt wyjścia

Stan zajęć 3: lokalna konfiguracja DVC, przypięte metadane CSV i cache. Zdalny magazyn DVC nie jest wymagany. Nie wykonano `dvc push` ani zdalnego `dvc pull`.
Metadane były w `metadata/bank-additional-full.csv.dvc`, ze ścieżką względną do
oryginalnego CSV. Po zatwierdzonej migracji zajęć 4 ich treść i hash zachowuje
`reports/evidence/lesson4-migration-*.json`; CSV jest wyjściem etapu download.
Cały `data/` pozostaje ignorowany przez Git; nie ma konfliktu
między plikiem CSV śledzonym przez DVC a plikami śledzonymi przez Git.
`.dvc/config` wyłącza autostaging, telemetrię i sprawdzanie aktualizacji.
Zwykłe `dvc init` automatycznie dodaje pliki do indeksu Git, dlatego konfiguracja
została przygotowana bez tej komendy. [Opis inicjalizacji DVC](https://doc.dvc.org/command-reference/init).

### Trzy osobne sytuacje

1. **Brak CSV i cache:** downloader pobiera przypięty wariant z oficjalnego UCI
   i sprawdza SHA-256, rozmiar oraz wymiary. Nie korzysta z DVC i nie tworzy jego
   cache. Polecenie odtworzenia samego CSV podano poniżej.
2. **Lokalny cache DVC:** `dvc checkout` odtwarza plik z obiektu dostępnego już
   w lokalnym cache. Metadane `.dvc` w Git same nie zawierają danych ani cache.
   Bez obiektu cache checkout nie zastąpi downloadu z UCI.
3. **Pełny weryfikator zajęć 3:** wymaga przygotowanego środowiska z DVC,
   oryginalnego lokalnego CSV zgodnego z manifestem, odpowiadającego mu obiektu
   w `.dvc/cache`, notebooka oraz indeksu Git. Używa ich tylko do odczytu i kopii
   kontrolnych. `--download` dodatkowo wymaga dostępu HTTPS do UCI.

Świeży klon nie ma cache DVC. Samo `uv sync` ani pobranie CSV nie przygotowują
wszystkich warunków pełnego weryfikatora. Brak cache to niespełniony warunek
testu lokalnego DVC, a nie dowód nieskuteczności odtwarzania z UCI.
Poniższe polecenia pełnej weryfikacji dotyczą przygotowanego lokalnego projektu:

```powershell
uv sync --locked
uv run --locked dvc status
uv run --locked python -m scripts.verify_lesson3 --download
```

Weryfikator tworzy nowy katalog pod ignorowanym `artifacts/lesson3/`, kontroluje
manifest i kontrakt, odrzuca uszkodzoną kopię i niepoprawną kategorię, a następnie
odtwarza CSV do pustego workspace przez `dvc checkout` z kopii lokalnego cache.
Opcja `--download` wykonuje dodatkowo rzeczywisty download z UCI do osobnego,
początkowo pustego katalogu; nie kopiuje tam lokalnego CSV. Kopie kontrolne
pozostają do inspekcji. Raport: `reports/evidence/lesson3-<timestamp>-<id>.json`.

Po utracie CSV oraz cache istniejący downloader odtwarza dane z UCI:

```powershell
uv run --locked python -c "from pathlib import Path; from src.data.download import ensure_data; ensure_data(Path('data/raw/bank-additional-full.csv'), Path('metadata/data_manifest.json'))"
```

Nie trzeba uruchamiać `prepare` ani nadpisywać przygotowanych splitów, aby odzyskać
sam surowy CSV. Istniejący niezgodny plik jest odrzucany, a nie nadpisywany.

### Zakres i dowody

DagsHub i zdalny magazyn DVC nie są wymagane. DVC, MLflow, lineage, CI/CD,
monitoring i Microsoft RAG pozostają w planie. Migrację do `dvc.yaml` wykonano
w zajęciach 4. Historyczny weryfikator odtwarza stary pointer z raportu migracji
wyłącznie we własnym izolowanym workspace; nie przywraca go do głównego repo.

Test UCI uruchamia kopię downloadera i manifestu w osobnym procesie Python `-I`
w pustym katalogu, przed skopiowaniem cache DVC. Nie przekazuje oryginalnego CSV
ani cache. Python audit hook blokuje odczyty oryginalnego `data/` i `.dvc/cache/`
i sprawdza aktywność blokady. Wynik przechodzi manifest oraz kontrakt.
To kontrola dostępu w Python, nie sandbox uprawnień OS.
Osobny test DVC odtwarza dane z kopii lokalnego cache i sprawdza ten sam kontrakt.
Pełny PASS wymaga `--download`; bez niego wynik UCI jest NOT_RUN.
Nowe raporty mają unikalną nazwę `reports/evidence/lesson3-<timestamp>-<id>.json`.

Raport otrzymuje PASS dopiero po wykonaniu wszystkich żądanych kontroli oraz
końcowym potwierdzeniu niezmienności chronionych plików. Zmiana lub brak pliku
chronionego daje FAIL. Bez `--download` wynik jest `INCOMPLETE_UCI_NOT_RUN`.
Nowe nazwy zawierają także losowy identyfikator; zapis wyłączny nie nadpisuje
istniejących raportów. Komunikaty błędów i pola tekstowe raportu są anonimizowane
przed wypisaniem lub zapisem. Historyczne raporty pozostają bez zmian.
