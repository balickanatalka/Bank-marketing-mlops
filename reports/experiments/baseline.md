# Eksperyment bazowy Bank Marketing

Data wykonania: 2026-10-25. Środowisko: Windows, Python 3.12.10, uv 0.13.4.
Modele: DummyClassifier(strategy="most_frequent") i LogisticRegression(max_iter=1000).
Konfiguracja referencyjna: configs/config.yaml, seed=42, 10 cech dostępnych przed kontaktem.
Kod źródłowy, parametry, wersje i hashe modeli są rejestrowane w lokalnym
artifacts/models/training_metadata.json. Wyniki poniżej pochodzą z rzeczywistego wykonania.

## Dane i podział


Pobrano oficjalny zagnieżdżony wariant bank-additional-full.csv z UCI.
SHA-256: `74adfc578bf77a7ff4bb1ba4a9f8709d9e3c6907342959c2c8416847e0afb4d8`.
Rozmiar: 5 834 924 bajty; 41 188 wierszy i 21 kolumn.
Klasy: no=36 548, yes=4 640. Brak null; 12 identycznych pełnych wierszy.
Liczba pdays=999: 39 673. unknown: job=330, marital=80, education=1 731,
default=8 597, housing=990, loan=990.

| Część | Wiersze | Przedział indeksów, koniec wyłączny | Rola |
|---|---:|---|---|
| train | 24 712 | [0, 24712) | Fit transformacji i modeli |
| validation | 6 178 | [24712, 30890) | Bieżące porównanie |
| final_test | 4 118 | [30890, 35008) | Odizolowany; nie oceniano |
| replay | 6 180 | [35008, 41188) | Przyszła symulacja utrzymania |

Sprawdzono przecięcia hashy pełnych wierszy dla wszystkich sześciu par części:
każde wyniosło 0. Nie dowodzi to niezależności klientów — brak ich identyfikatorów.

## Wyniki na zbiorze walidacyjnym

| Metryka | Dummy, most_frequent | Logistic Regression |
|---|---:|---:|
| Accuracy | 0.8714794432 | 0.8706701198 |
| Macro F1 | 0.4656633800 | 0.4740003659 |
| Average Precision | 0.1285205568 | 0.1850463938 |
| Precision yes | 0 | 0.3684210526 |
| Recall yes | 0 | 0.0088161209 |
| ROC-AUC | 0.5 | 0.5721377783 |
| Brier score | 0.1285205568 | 0.1182750907 |
| Lift@10% | Nie oceniano przy wszystkich remisach score | 1.8411751018 |

Support walidacji: no=5 384, yes=794. Domyślny próg klasyfikacji 0,5.
Logistic Regression poprawia AP, ale wykrywa tylko 7 z 794 przypadków yes.
Accuracy nie poprawia się. To ograniczony model początkowy, nie dobry gotowy produkt.
Nie strojono progu, nie wykonywano późniejszych eksperymentów i nie oceniano holdoutu.
Lift Dummy pozostaje null, ponieważ stały score nie daje sensownego rankingu.

## Zakres weryfikacji

Kontrole jakości i logi poleceń: [checks.json](../evidence/checks.json).
Odtworzenie środowiska i danych: [reproduction.json](../evidence/reproduction.json).
Potwierdzono powtarzalność na jednym komputerze; niezależna reprodukcja nie została wykonana.
Pełna ocena końcowego holdoutu, eksperymenty z dodatkowymi algorytmami, analiza podgrup
i progi jakości pozostają poza zakresem tego wyniku bazowego.
