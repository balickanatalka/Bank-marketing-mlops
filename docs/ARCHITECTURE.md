# Architektura eksperymentu

Eksperyment jest lokalnym programem Python z osobnym lokalnym rejestrem MLflow.
Nie uruchamia API, usług monitoringu ani LLM. Notebook i CLI korzystają z tej samej implementacji.

```text
UCI ZIP -> CSV -> SHA-256 -> walidacja -> podział chronologiczny
  -> train: transformacje + Dummy / LogisticRegression
  -> validation: predykcje -> metryki, macierze pomyłek, artefakty
```

`config.py` wczytuje YAML, stosuje PROJEKT_SEED i sprawdza cechy, proporcje oraz
ścieżki. `data/download.py` odczytuje wskazany plik z zagnieżdżonego ZIP i kontroluje
hash. `data/validation.py` sprawdza strukturę i podstawowe ograniczenia danych.
`pipeline.py` rozdziela dane, trenuje i zapisuje modele oraz oblicza metryki.
`features/build.py` dostarcza wspólny preprocessing zapisany wraz z klasyfikatorem.
Importy historyczne z `src.pipeline` nadal działają, również przy odczycie starych modeli.
`cli.py` udostępnia prepare, train, evaluate i all; `dvc_cli.py` obsługuje etapy DVC.

Stan etapów jest zapisywany na dysku. Hash konfiguracji i części danych wykrywa
niezgodność wejść; hash modelu jest sprawdzany przed deserializacją. Mechanizm
nie zastępuje uwierzytelnienia artefaktów i wymaga zaufanego lokalnego treningu.
Final test i replay są rozdzielone od części używanych do treningu i walidacji.

Kierunki rozwoju obejmują API, kontenery, CI/CD, monitoring i retraining.
Microsoft RAG ma korzystać z dokumentacji i raportów, nie obliczać predykcji ani
samodzielnie promować modeli. Wymienione przyszłe usługi nie są obecnie zaimplementowane.

DVC wykonuje `download -> validate -> prepare -> train -> evaluate` z `dvc.yaml`.
`download` jest jedynym właścicielem surowego CSV po zatwierdzonej migracji starego
pliku `.dvc`. Odtworzenie bez cache zapewnia oficjalne UCI i manifest SHA-256.
DagsHub i zdalny magazyn DVC nie są wymagane.

Konfiguracja `configs/lesson4.yaml` zapisuje nowe splity w `data/lesson4/processed`
oraz modele i raporty w `artifacts/lesson4/`. Nie nadpisuje wcześniejszych wyników.
Hash przygotowania obejmuje dane, split i ścieżkę splitów; hash treningu nadal
obejmuje całą efektywną konfigurację. Zmiana `model.max_iter` uruchamia tylko
trening i ewaluację. Metadane starego formatu nadal podlegają kontroli pełnego hasha.
Final test i replay powstają w prepare, ale nie są odczytywane do uczenia ani oceny.
Brak feature store uzasadnia [ADR 0001](ADR/0001-feature-store.md).

## Lokalne eksperymenty

`src/experiments.py` wykorzystuje istniejącą walidację, podział chronologiczny,
fabrykę preprocessingu i wspólne obliczanie metryk z `src/pipeline.py`.
Każda seria tworzy nowy katalog `artifacts/lesson5/<batch>/`: SQLite MLflow,
osobny magazyn artefaktów i sześć kompletnych Pipeline. Nie nadpisuje baseline.
Modele widzą wyłącznie train i validation; final test i replay nie są oceniane.

`configs/experiments.yaml` oraz [protokół](EXPERIMENT_PROTOCOL.md) definiują parametry,
seed, próg 0,5 i regułę wyboru przed treningiem. Wagi XGBoost powstają wyłącznie z train.
Klient MLflow otrzymuje jawny lokalny URI SQLite, niezależny od MLFLOW_TRACKING_URI.
Interfejs działa wyłącznie na localhost. Nie ma zdalnego trackingu, registry ani promocji.

`src/experiment_report.py` eksportuje tylko zagregowane wyniki i próbkę punktów krzywych
do małego snapshotu JSON oraz Markdown. Notebook `02_model_experiments.ipynb` odczytuje
ten snapshot; nie implementuje treningu. Pełne modele i krzywe pozostają lokalne.
Microsoft RAG pozostaje przyszłym konsumentem dokumentacji i raportów.

## Rejestr modeli — zajęcia 7

`src/registry.py` pakuje istniejący Pipeline z zajęć 5 do formatu MLflow/skops,
sprawdza odtworzenie metryk validation i tworzy wersję w osobnej bazie SQLite.
`register` nie przypisuje aliasu. `challenger`, kontrola jakości, zatwierdzona
promocja `champion` i rollback są osobnymi operacjami. W rejestrze projektu
pozostawiono tylko challenger; zmiany championa wykonywano w bazach testowych.

Manifest wiąże artefakty, schemat i lineage; wersja rejestru wskazuje run pakowania
oraz oryginalny run treningowy. Nie powstaje nowy model ani nowy preprocessing.
`src/model_card.py` generuje kartę z tych samych metadanych. Procedury i ograniczenia
lokalnej blokady aliasów opisuje [instrukcja rejestru](MODEL_REGISTRY.pl.md).
