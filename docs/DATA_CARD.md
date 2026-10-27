# Karta danych

Aktualizacja: 2026-10-27.

Źródło: [UCI](https://archive.ics.uci.edu/dataset/222/bank+marketing).
S. Moro, P. Rita, P. Cortez (2014), DOI: 10.24432/C5K306, CC BY 4.0.
Dokładny wariant to `bank-additional-full.csv`, 41 188 × 21, separator `;`.
UCI opisuje kolejność jako chronologiczną: maj 2008 – listopad 2010.
Zbiór nie zawiera pełnej daty każdego wiersza; zachowana jest kolejność źródłowa.

Target `y`: `yes` → 1, `no` → 0. Zaobserwowano 36 548 `no` i 4 640 `yes`.
Walidacja sprawdza komplet 21 kolumn, unikalne nazwy, liczbę wierszy, typy,
brak null, skończone liczby, klasy i zakresy. Kontrakt w `src/data/schema.py`
zawiera pełne słowniki kategorii oraz ograniczenia dziedzinowe. Walidacja
nie wyznacza zakresów ani kategorii z walidacji, final test lub replay.

Wiek jest całkowity w zakresie 1–120. `duration`, `previous` i `pdays` są
nieujemnymi liczbami całkowitymi, `campaign` jest całkowite i dodatnie.
`pdays` dopuszcza 0–998 oraz specjalną wartość 999. Indeksy `cons.price.idx`,
`euribor3m` i `nr.employed` muszą być dodatnie; wszystkie liczby muszą być
skończone. Pozostałe wskaźniki mogą być ujemne. To ograniczenia kontraktu
tego wariantu danych, nie dopasowanie do zaobserwowanych ekstremów.
Nie dopuszczamy null, NaN, nieskończoności ani nieznanych kontraktowi kategorii.
Wartość tekstowa `unknown` jest dozwolona tylko w polach, których słownik ją zawiera.

Zmienne liczbowe: age, duration, campaign, pdays, previous, emp.var.rate,
cons.price.idx, cons.conf.idx, euribor3m, nr.employed.
Pozostałe cechy są kategoryczne. Szczegółowa lista jest w `src/data/validation.py`.
`unknown` oznacza brak wiedzy; `nonexistent` brak poprzedniego wyniku kampanii.
`pdays=999` oznacza brak poprzedniego kontaktu, nie liczbę dni.

Znaleziono 12 identycznych wierszy. Nie są usuwane automatycznie; zachowane są
oryginalna zawartość i kolejność. Brak identyfikatora klienta uniemożliwia zagwarantowanie
niezależności osób; równość wierszy nie jest dowodem tożsamości klienta.
Karta nie stanowi zapewnienia braku wszystkich form leakage.

Manifest w `metadata/data_manifest.json` przypina SHA-256 rozpakowanego CSV,
rozmiar, datę pobrania i źródło. Dane nie trafiają do Git.
Manifest podaje również licencję i jej URL, wariant, ścieżkę w archiwum,
separator, kodowanie, target i zasady zachowania kolejności. Weryfikator
sprawdza checksum, rozmiar i wymiary przed użyciem danych. Suma DVC (MD5)
służy adresowaniu cache; nie zastępuje niezależnej kontroli SHA-256.
Zmiany w modelowaniu: selekcja 10 cech, mapowanie targetu, transformacja pdays,
chronologiczne części. Źródłowy CSV pozostaje niezmieniony.

Ograniczenia: historyczny rynek, zmiany rozkładu w czasie, brak pełnych snapshotów
i identyfikatorów osób, cechy demograficzne oraz brak dowodu bezstronności.
Model nie służy do podejmowania rzeczywistych decyzji finansowych.

## Odtworzenie danych

Metadane DVC i lokalny cache umożliwiają lokalne odtworzenie. DagsHub i zdalny
magazyn DVC nie są wymagane. Bez lokalnego CSV i cache downloader pobiera przypięty wariant
z UCI i sprawdza manifest. Procedura oraz ograniczenia: [REPRODUCIBILITY.md](REPRODUCIBILITY.md).
