# Odtwarzalność

Środowisko referencyjne: Windows, Python 3.12.10, uv 0.13.4.
`.python-version` przypina interpreter, `uv.lock` wersje zależności, a manifest
danych sumę SHA-256 źródłowego CSV. Polecenia z katalogu głównego repozytorium:

```powershell
uv sync --locked
uv run --locked python -m src.cli all
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

## Zajęcia 3: integralność i lokalne DVC

Stan: lokalna konfiguracja DVC, przypięte metadane CSV i cache. Zdalny magazyn DVC nie jest wymagany. Nie wykonano `dvc push` ani zdalnego `dvc pull`.
Metadane są w `metadata/bank-additional-full.csv.dvc`, ze ścieżką względną do
oryginalnego CSV. Cały `data/` pozostaje ignorowany przez Git; nie ma konfliktu
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
monitoring i Microsoft RAG pozostają w planie. Migracja do `dvc.yaml`: zajęcia 4.
Obecna konfiguracja DVC pozostaje bez zmian.

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
