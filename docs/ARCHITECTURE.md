# Architektura eksperymentu

Eksperyment jest lokalnym programem Python. Nie uruchamia API, rejestru modeli,
usług monitoringu ani LLM. Notebook i CLI korzystają z tej samej implementacji.

```text
UCI ZIP -> CSV -> SHA-256 -> walidacja -> podział chronologiczny
  -> train: transformacje + Dummy / LogisticRegression
  -> validation: predykcje -> metryki, macierze pomyłek, artefakty
```

`config.py` wczytuje YAML, stosuje PROJEKT_SEED i sprawdza cechy, proporcje oraz
ścieżki. `data/download.py` odczytuje wskazany plik z zagnieżdżonego ZIP i kontroluje
hash. `data/validation.py` sprawdza strukturę i podstawowe ograniczenia danych.
`pipeline.py` rozdziela dane, buduje transformacje, trenuje i zapisuje modele
oraz oblicza metryki. `cli.py` udostępnia prepare, train, evaluate i all.

Stan etapów jest zapisywany na dysku. Hash konfiguracji i części danych wykrywa
niezgodność wejść; hash modelu jest sprawdzany przed deserializacją. Mechanizm
nie zastępuje uwierzytelnienia artefaktów i wymaga zaufanego lokalnego treningu.
Final test i replay są rozdzielone od części używanych do treningu i walidacji.

Kierunki rozwoju obejmują DVC, MLflow, API, kontenery, CI/CD, monitoring i retraining.
Microsoft RAG ma korzystać z dokumentacji i raportów, nie obliczać predykcji ani
samodzielnie promować modeli. Te funkcje nie są obecnie zaimplementowane.
