# Bank Marketing MLOps & Microsoft RAG Assistant

Projekt rozwijający odtwarzalny proces uczenia maszynowego dla danych
UCI Bank Marketing. Jego celem jest oszacowanie prawdopodobieństwa założenia lokaty
przez klienta oraz analiza rankingu kontaktów na potrzeby kampanii marketingowej.

Obecna implementacja obejmuje przygotowanie środowiska i danych,
analizę eksploracyjną, dwa modele klasyfikacyjne oraz powtarzalny eksperyment
uruchamiany z wiersza poleceń. System ma charakter eksperymentalny.
Nie jest przeznaczony do podejmowania rzeczywistych decyzji finansowych.

## Zakres projektu

| Zaimplementowane | Planowane w kolejnych etapach |
|---|---|
| Python, uv, plik blokady zależności i konfiguracja YAML | DVC: wersjonowanie danych, potok i cache |
| Automatyczne pobieranie UCI i kontrola SHA-256 | MLflow: eksperymenty, rejestr i pochodzenie modeli |
| Walidacja danych i podział chronologiczny | API, Docker oraz CI/CD z kontrolami jakości i bezpieczeństwa |
| Notebook EDA, DummyClassifier i LogisticRegression | Staging, shadow deployment i rollback |
| Wspólny preprocessing, trening i ewaluacja przez CLI | Monitoring, dryf, SLI/SLO i kontrolowany retraining |
| Testy pytest, Ruff i lokalne hooki pre-commit | Microsoft RAG z ewaluacją, cytowaniami i tracingiem |

Microsoft RAG będzie rozszerzeniem korzystającym z dokumentacji i raportów MLOps.
Nie zastępuje klasycznego modelu ani wymagań związanych z jego cyklem życia.

## Problem biznesowy i dane

Odbiorcą wyników jest analityk kampanii. Model rozwiązuje problem klasyfikacji
binarnej: `y=yes` oznacza założenie lokaty, a `y=no` brak jej założenia.
Prawdopodobieństwo klasy `yes` pozwala badać ranking kontaktów. Przewidywanie
odbywa się przed rozmową, na podstawie dopuszczonych informacji o kliencie
oraz poprzednich kampaniach.

Źródło: [UCI Bank Marketing](https://archive.ics.uci.edu/dataset/222/bank+marketing),
S. Moro, P. Rita, P. Cortez (2014), DOI: [10.24432/C5K306](https://doi.org/10.24432/C5K306).
Dane są udostępniane na licencji [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Atrybucję i opis przekształceń zawiera [DATA_LICENSE.md](DATA_LICENSE.md).

| Właściwość | Wartość |
|---|---|
| Wariant | `bank-additional-full.csv` |
| Rozmiar | 41 188 rekordów, 20 cech i etykieta `y` |
| Okres opisany przez UCI | Maj 2008 – listopad 2010 |
| Kolejność | Chronologiczna według dokumentacji źródła |
| Separator CSV | `;` |
| Klasy w pełnym zbiorze | `no`: 36 548; `yes`: 4 640 |

Program pobiera zagnieżdżone archiwum UCI i odczytuje wskazany CSV. Przed analizą
sprawdza rozmiar i przypiętą sumę SHA-256 z `metadata/data_manifest.json`.
Niezgodny plik zatrzymuje przetwarzanie; manifest nie aktualizuje się automatycznie.
Surowe dane pozostają poza Git. Szczegółowy opis: [karta danych](docs/DATA_CARD.md).

## Metodologia i preprocessing

### Dostępność informacji

Model korzysta z cech `age`, `job`, `marital`, `education`, `default`, `housing`,
`loan`, `pdays`, `previous` i `poutcome`. Przyjęto założenie, że informacje te są
znane przed rozmową. Publiczny zbiór nie zawiera historii zmian każdego pola.

Wykluczono:

- `duration` — długość bieżącej rozmowy jest znana dopiero po jej zakończeniu;
- `contact`, `month`, `day_of_week` i `campaign` — brak potwierdzonego obrazu danych
  sprzed bieżącego kontaktu;
- wskaźniki ekonomiczne — brak dat publikacji i informacji o późniejszych rewizjach;
- `y` — etykieta jest używana wyłącznie jako wynik uczenia.

Uzasadnienie decyzji i ograniczenia opisano w [LEAKAGE.md](docs/LEAKAGE.md).

### Podział danych

Dane są dzielone bez tasowania, z zachowaniem kolejności wierszy:

| Część | Udział nominalny | Rekordy | Zastosowanie |
|---|---:|---:|---|
| Train | 60% | 24 712 | Dopasowanie transformacji i modeli |
| Validation | 15% | 6 178 | Porównanie modeli i bieżąca ewaluacja |
| Final test | 10% | 4 118 | Odizolowana końcowa ocena po wyborze rozwiązania |
| Replay | 15% | 6 180 | Przyszła symulacja monitoringu i retrainingu |

Różnice względem dokładnych proporcji wynikają z zaokrąglania liczby wierszy.
Obecne funkcje treningu i ewaluacji nie odczytują final test ani replay.
Pełny zbiór służy do kontroli struktury i podstawowego opisu danych; jego końcowa
część nie służy do strojenia ani obliczania przedstawionych metryk modeli.

### Wspólny potok cech

`Pipeline` łączy transformacje z klasyfikatorem:

1. `pdays=999` jest zamieniane na wskaźnik braku poprzedniego kontaktu oraz wartość
   zastępczą 0; nie jest interpretowane jako 999 dni.
2. Cechy liczbowe są skalowane przez `StandardScaler`.
3. Kategorie są kodowane przez `OneHotEncoder(handle_unknown="ignore")`.
   Wartości `unknown` i `nonexistent` pozostają jawnymi kategoriami.
4. Transformacje i model są dopasowywane wyłącznie na train.

Cały potok jest zapisywany razem z modelem, aby ponowne użycie nie wymagało
ręcznego odtwarzania preprocessingu.

## Modele i rzeczywiste wyniki

Punktem odniesienia jest `DummyClassifier(strategy="most_frequent")`, który zawsze
przewiduje klasę większościową. Pierwszym uczonym klasyfikatorem jest
`LogisticRegression(max_iter=1000)` z domyślnym progiem decyzji 0,5.

Główną metryką jest **Average Precision (AP)**, obliczana z prawdopodobieństw przez
`average_precision_score`. Nie jest to trapezowe pole pod krzywą precision–recall.
Accuracy, macro F1, precision, recall, ROC-AUC, Brier score i lift@10% uzupełniają ocenę.

Wyniki dotyczą tej samej walidacji: **5 384 rekordy `no` i 794 rekordy `yes`**.

| Metryka | DummyClassifier | LogisticRegression |
|---|---:|---:|
| Average Precision ↑ | 0,128521 | 0,185046 |
| Accuracy ↑ | 0,871479 | 0,870670 |
| Macro F1 ↑ | 0,465663 | 0,474000 |
| Precision klasy `yes` ↑ | 0,000000 | 0,368421 |
| Recall klasy `yes` ↑ | 0,000000 | 0,008816 |
| ROC-AUC ↑ | 0,500000 | 0,572138 |
| Brier score ↓ | 0,128521 | 0,118275 |
| Lift@10% ↑ | Nie oceniano: stały wynik | 1,841175 |

Regresja logistyczna poprawia ranking względem baseline, ale przy progu 0,5
wykrywa tylko **7 z 794** pozytywnych przypadków. Accuracy jest nieco niższe niż
w baseline. Wyniki nie uzasadniają uznania modelu za gotowy do zastosowania operacyjnego.
Nie wykonywano strojenia progu ani oceny modelu na końcowym zbiorze testowym.

Dodatkowe ograniczenia to historyczny charakter danych, zmienność rozkładów,
12 identycznych wierszy oraz brak identyfikatorów klientów. Między częściami
nie znaleziono identycznych pełnych wierszy, ale nie potwierdza to niezależności
osób. Nie przeprowadzono jeszcze pełnej analizy podgrup ani oceny bezstronności.

## Uruchomienie po sklonowaniu

Wymagane są Git, [uv](https://docs.astral.sh/uv/getting-started/installation/)
oraz dostęp do internetu do instalacji zależności i pierwszego pobrania danych.
Projekt przypina Python **3.12.10**; uv może pobrać brakujący interpreter.
Bieżący eksperyment nie wymaga GPU, konta Azure ani płatnej infrastruktury.
Zapotrzebowanie na zasoby nie zostało zmierzone na innych komputerach.

Poniższe polecenia dla PowerShell należy wykonać na wersji repozytorium zawierającej
pliki opisane w tej dokumentacji. Nieopublikowane zmiany lokalne nie są dostępne
w zdalnym klonie.

```powershell
git clone https://github.com/balickanatalka/Bank-marketing-mlops.git
cd Bank-marketing-mlops
uv sync --locked
uv run --locked python --version
uv run --locked python -m src.cli all
uv run --locked pytest -q
```

`uv sync --locked` odtwarza zależności bez zmiany `uv.lock`. Plik `pyproject.toml`
określa zależności bezpośrednie i ich zakresy, natomiast lock zapisuje konkretne
wersje zależności bezpośrednich i przechodnich. Po przygotowaniu środowiska i danych
sam trening nie wymaga sieci.

### Poszczególne etapy i konfiguracja

Polecenia wykonuje się z katalogu głównego repozytorium:

```powershell
uv run --locked python -m src.cli prepare
uv run --locked python -m src.cli train
uv run --locked python -m src.cli evaluate
uv run --locked python -m src.cli all --config configs/config.yaml
```

| Polecenie | Działanie |
|---|---|
| `prepare` | Pobranie brakujących danych, kontrola integralności, walidacja i zapis części |
| `train` | Kontrola przygotowanych danych, trening i zapis obu potoków |
| `evaluate` | Kontrola artefaktów oraz metryki i wykresy dla validation |
| `all` | Wykonanie trzech etapów we właściwej kolejności |

`configs/config.yaml` definiuje seed, cechy, podział, parametr modelu i ścieżki.
Zmiana konfiguracji wymaga ponownego wykonania etapów zależnych; `all` wykonuje je kolejno.
Ścieżki danych i artefaktów są względne wobec katalogu projektu.

Seed można nadpisać na czas procesu:

```powershell
$env:PROJEKT_SEED = '123'
uv run --locked python -m src.cli all
Remove-Item Env:PROJEKT_SEED
```

Zmiana seed nie tasuje podziału chronologicznego. Domyślny solver `lbfgs` nie korzysta
z tego parametru w sposób zmieniający ten eksperyment; zgodność wyników nie świadczy
o niedziałającym nadpisaniu konfiguracji.

## Struktura repozytorium

```text
configs/config.yaml                   Parametry eksperymentu
src/config.py                         Odczyt i kontrola konfiguracji
src/data/download.py                  Pobieranie i kontrola SHA-256
src/data/validation.py                Podstawowy kontrakt danych
src/pipeline.py                       Podział, preprocessing, trening i ewaluacja
src/cli.py                            Interfejs wiersza poleceń
notebooks/01_bank_marketing_eda.ipynb   Analiza eksploracyjna ze wspólnym kodem
metadata/data_manifest.json           Metadane i przypięta suma CSV
tests/                                Testy konfiguracji, danych i potoku
scripts/                              Kontrole jakości i odtwarzalności
docs/                                 Architektura, metodologia i odtwarzalność
reports/evidence/                     Niewielkie raporty i dowody kontroli
data/                                 Lokalne dane surowe i przygotowane; poza Git
artifacts/                            Lokalne modele, wykresy i kopie testowe; poza Git
pyproject.toml, uv.lock                Zależności projektu
.python-version                       Wersja interpretera
.pre-commit-config.yaml               Lokalne hooki jakości
```

## Artefakty i notebook

Po wykonaniu `all` powstają:

- `artifacts/models/dummy.joblib` i `model.joblib` — preprocessing wraz z klasyfikatorem;
- `artifacts/models/training_metadata.json` — konfiguracja, wersje, hashe danych,
  kodu i modeli, Git HEAD oraz informacja o niezatwierdzonych zmianach;
- `artifacts/reports/metrics.json` — metryki walidacyjne;
- `artifacts/reports/data_validation.json`, wykres klas i macierze pomyłek;
- `data/processed/` — rozdzielone części oraz metadane ich integralności.

Deserializacja artefaktów joblib wymaga zaufanego źródła. Kontrola hasha wykrywa
zmianę względem metadanych, lecz nie zastępuje uwierzytelnienia źródła artefaktu.

Notebook korzysta z tych samych funkcji co CLI. W VS Code należy wybrać interpreter
`.venv/Scripts/python.exe` oraz kernel tego środowiska; obsługa notebooków wymaga
rozszerzenia Jupyter. Źródłowy notebook nie zawiera zapisanych wyników wykonania.

## Testy i jakość kodu

```powershell
uv run --locked pytest -q
uv run --locked ruff check src tests scripts notebooks
uv run --locked ruff format --check src tests scripts notebooks
uv run --locked python scripts/verify_checks.py
```

Testy obejmują konfigurację i niedozwolone cechy, uszkodzony CSV, błędny schemat,
podział chronologiczny, dopasowanie preprocessingu tylko na train, nowe kategorie,
zapis i odczyt modelu, integralność artefaktów oraz izolację final test i replay.
Skrypt `verify_checks.py` zapisuje kody wyjścia i logi w `reports/evidence/checks.json`.

Opcjonalna instalacja lokalnych hooków:

```powershell
uv run --locked pre-commit install
uv run --locked pre-commit run --all-files
```

Hooki używają Ruff z wersji zapisanej w `uv.lock`. `--all-files` obejmuje pliki znane Git;
przed ich dodaniem skrypt `verify_checks.py` sprawdza pliki jawnie przez `--files`.
Instalacja hooka zmienia wyłącznie lokalne `.git/hooks`.

## Sprawdzenie odtwarzalności

Kontrola odtwarzalności wymaga wcześniejszego poprawnego wykonania `all`:

```powershell
uv run --locked python scripts/verify_reproduction.py
```

Skrypt tworzy lokalny klon istniejącej historii w nowym katalogu pod `artifacts/`
i nakłada bieżące pliki kodu, konfiguracji, testów i środowiska. Nie przenosi
lokalnej `.venv` ani CSV. Następnie odtwarza środowisko, pobiera dane, wykonuje
trening, ewaluację i testy oraz porównuje metryki przy ponowieniu i zmianie seed.
Nie usuwa katalogów; kolejne uruchomienia zajmują dodatkowe miejsce na dysku.

To kontrola na tym samym komputerze. Nie zastępuje testu zdalnego klonu opublikowanej
wersji ani przeglądu przez drugą osobę. Aktualne dowody i pozostałe braki:

- [wyniki eksperymentu bazowego](reports/experiments/baseline.md);
- [architektura](docs/ARCHITECTURE.md);
- [odtwarzalność](docs/REPRODUCIBILITY.md);
- [formularz niezależnej weryfikacji](docs/INDEPENDENT_REVIEW.md);
- [komponenty zewnętrzne](docs/THIRD_PARTY_NOTICES.md).

## Licencje

Licencja zbioru danych jest opisana w [DATA_LICENSE.md](DATA_LICENSE.md).
Informacje o zależnościach znajdują się w [THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md).
Repozytorium nie zawiera jeszcze deklaracji licencji własnego kodu; licencja danych
nie nadaje automatycznie praw do kodu projektu.
