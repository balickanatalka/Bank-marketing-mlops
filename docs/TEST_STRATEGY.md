---
title: Strategia testów
updated: 2026-11-11
---

# Strategia testów — zajęcia 6

| Wymaganie prowadzącego | Pokrycie |
| --- | --- |
| Preprocessing | `tests/test_features.py` sprawdza wartości po skalowaniu, kodowanie znanej i niewidzianej kategorii, zachowanie wejścia oraz odrzucenie tekstu i nieskończoności w kolumnie liczbowej. `tests/test_pipeline.py` sprawdza znacznik `pdays=999`. |
| Walidacja danych | `tests/test_data.py` sprawdza brakujące, nadmiarowe i powielone kolumny, typy, nulle, kategorie i zakresy. Surowy schemat UCI zawiera `duration`. `tests/test_config.py` i `tests/test_features.py` odrzucają ją jako cechę, a test kontraktu sprawdza jej brak na wejściu modelu. |
| Jakość modelu | `test_stages_do_not_consume_holdout` sprawdza syntetyczny próg AP. `test_uci_validation_quality_gate` odtwarza regresję logistyczną i Dummy na danych UCI, sprawdza AP i recall na rzeczywistej walidacji oraz potwierdza odrzucenie Dummy. |
| Train/serve skew | `test_batch_single_record_determinism_and_serialization` porównuje transformację partii i rekordu oraz predykcje po serializacji. `test_transformers_fit_only_training_rows_and_never_in_evaluation` kontroluje fit w rzeczywistych etapach pipeline’u. |
| Kontrakt predykcji | `test_saved_pipeline_prediction_contract` ładuje artefakt z etapu `train` i sprawdza pola, typy JSON, klasy, kształty, zakresy, normalizację i brakujące pole. |
| Testy własnościowe | `tests/test_prediction_properties.py` generuje po 40 przykładów na test. Pierwszy sprawdza skończone i znormalizowane prawdopodobieństwa, drugi sprawdza liczbę wierszy i stałą szerokość transformacji. |
| Kontrole negatywne | Dummy poniżej progu, wadliwa liczba w preprocessingu, brak pola w predykcji, uszkodzone dane lub artefakt, zmieniona konfiguracja oraz uszkodzone syntetyczne partycje holdout. |
| Dokumentacja i wyniki | Ten dokument, [README](../README.md) i [raport wyników](../reports/lesson6_test_results.md). |

## Bramka jakości

Na rzeczywistej walidacji UCI minimalny wynik AP to **AP powyżej świeżo
wyliczonego Dummy** (historycznie 0,128521). Minimalny recall wynosi
**7/794 ≈ 0,008816**, zgodnie z wynikiem referencyjnej regresji logistycznej
z zajęć 5. Próg decyzji pozostaje 0,5. Model referencyjny osiągnął wtedy
AP 0,185046. Reguła pochodzi z [protokołu eksperymentów](EXPERIMENT_PROTOCOL.md).

Test w pamięci odtwarza dwa pipeline’y z konfiguracji zajęć 5, z tym samym
seedem, gęstym preprocessingiem i jednym wątkiem. Fit obejmuje chronologiczny
train, a metryki pochodzą wyłącznie z validation. Test nie korzysta z plików
partycji ani zapisanych modeli, nie zapisuje eksperymentów MLflow i nie wymaga DVC.

Syntetyczny fixture ma powtarzalny sygnał idealnie rozdzielający klasy i 50%
pozytywów w walidacji. Idealny ranking osiąga AP 1,00, a stały ranking Dummy
osiąga AP 0,50. Próg 0,90 wykrywa utratę większości tego sygnału.
To próg regresji na fixture. Protokół porównania na danych UCI określa
[protokół eksperymentów](EXPERIMENT_PROTOCOL.md).

Test korzysta z deterministycznego podziału chronologicznego. Dopasowanie używa
train, a pomiar AP używa validation. Syntetyczne pliki final test i replay
zawierają znacznik uszkodzenia, żeby test wykrył ich przypadkowy odczyt.

## Granica kontraktu

Wejściem predykcji jest DataFrame ze skonfigurowanymi cechami. Test odtwarza
rekordy z JSON w pamięci i używa zapisanego pipeline’u scikit-learn.
Etykiety są liczbami całkowitymi 0 lub 1, a kolumny `predict_proba`
odpowiadają klasom w kolejności `[0, 1]`. Kontrola dodatkowych kolumn i
dozwolonych wartości dotyczy walidatora surowych danych. Encoder obsługuje
niewidziane kategorie zgodnie z `handle_unknown="ignore"`.

## Uruchomienie

```powershell
uv sync --locked
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pre-commit run --all-files
uv run --locked dvc dag --dot
uv run --locked dvc status --json
```

Przed stagingiem użyj `pre-commit run --files` z jawną listą plików
obejmującą oba nowe moduły testów. Kontrole DVC odczytują graf i porównują
zależności oraz wyjścia ze stanem zapisanym w lockfile.

### Uruchomienie bramki UCI

Wskaż lokalny oryginalny CSV, np. `$env:BANK_MARKETING_QUALITY_CSV = (Resolve-Path
data/raw/bank-additional-full.csv).Path`. Na czystym środowisku pobierz dokładnie
ten sam wariant z oficjalnego źródła UCI do nowego pliku tymczasowego:

```powershell
uv sync --locked
$env:BANK_MARKETING_QUALITY_CSV = Join-Path ([System.IO.Path]::GetTempPath()) (
    "bank-marketing-" + [guid]::NewGuid().ToString("N") + ".csv"
)
uv run --locked python -c "import os; from pathlib import Path; from src.data.download import ensure_data; ensure_data(Path(os.environ['BANK_MARKETING_QUALITY_CSV']), Path('metadata/data_manifest.json'))"
if ($LASTEXITCODE -ne 0) { throw "Pobranie i weryfikacja danych UCI nie powiodły się" }
uv run --locked pytest -q -s tests/test_uci_quality.py
```

Test ponownie weryfikuje SHA-256, rozmiar i wymiary pliku. Brak zmiennej daje
jawny `SKIP`. Wskazanie nieistniejącego lub zmienionego pliku powoduje
`FAIL`. Aby włączyć bramkę do pełnego przebiegu, uruchom w tej samej sesji
`uv run --locked pytest -q`.
