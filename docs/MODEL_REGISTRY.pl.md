---
title: Lokalny rejestr modeli — zajęcia 7
updated: 2026-11-11
---

# Rejestr bez historycznych lokalnych zależności

MLflow jest lokalne (SQLite), bez płatnych usług. Wersje zależności są w `uv.lock`;
skops jest jawną zależnością pakowania. Rejestracja modelu i promocja są osobne.
Główny rejestr nowego przebiegu otrzymuje tylko alias `challenger`.

## Odtworzenie od publicznych danych

Wymagane: Git, uv, Python 3.12.10 oraz sieć do instalacji i pobrania UCI.
Na nowym klonie nie potrzeba starego CSV, modeli, cache DVC ani baz MLflow:

```powershell
uv sync --locked
uv run --locked python -m scripts.verify_lesson7 --rebuild --execute-notebook
if ($LASTEXITCODE -ne 0) { throw "Odtworzenie zajęć 7 nie powiodło się" }
```

Istniejący `src.experiments.run_experiments` pobiera brakujący CSV z UCI,
sprawdza manifest, trenuje sześciu kandydatów tylko na train i ocenia validation.
Nowy batch jest jawnie przekazany do pakowania; nie szukamy najnowszego katalogu.
Pakowanie nie trenuje ponownie. Final test/replay nie są oceniane ani używane do wyboru.
Jeśli CSV istnieje, downloader weryfikuje go zamiast nadpisywać.

Komenda wypisuje `EVIDENCE=artifacts/lesson7/<nowy-id>/evidence.json`.
Każdy przebieg tworzy nowy katalog, bazę registry, pakiet i dowód schema 2.
Zapis modelu obejmuje preprocessing, sygnaturę I/O, syntetyczny przykład wejścia,
przypięte wymagania, kod i lineage. Manifest i hash w tagu wersji kontrolują
kompletność i integralność. Przed/po serializacji sprawdzane są klasy i prawdopodobieństwa.

## Jawny wybór już wygenerowanego batcha

Wynik uruchomienia `python -m src.experiments` zawiera pole `output`.
Wskaż dokładnie ten katalog, np. przez parametr PowerShell; nie kopiuj historycznych ID:

```powershell
$batch = Read-Host "Względny katalog batcha z pola output"
uv run --locked python -m scripts.verify_lesson7 --batch $batch --execute-notebook
```

Opcjonalne `--output artifacts/lesson7/<własny-nowy-katalog>` ułatwia zapis jawnej
lokalizacji. Istniejący katalog jest odrzucany. `--model-card docs/MODEL_CARD.md`
generuje kartę z metadanych dopiero po kontroli jakości.

## Notebook i przekazanie dowodu

Notebook 03 nie ma domyślnej ścieżki starego rejestru. Dla ręcznego uruchomienia
ustaw zmienną przed uruchomieniem kernela:

```powershell
$env:BANK_MARKETING_REGISTRY_EVIDENCE = Read-Host "Ścieżka evidence.json z EVIDENCE="
```

`--execute-notebook` przekazuje ją automatycznie do kernela i zapisuje wykonaną
kopię w katalogu nowego przebiegu. Źródłowy notebook pozostaje szablonem.
Dowód wskazuje katalog registry względem swojego położenia, konkretną wersję,
run pakowania i hash manifestu. Brak dowodu lub niezgodność daje błąd;
nie powstaje automatycznie pusty rejestr zamiast brakującego.

Notebook zapamiętuje aliasy i tożsamości wersji, odczytuje lineage/model, a następnie
porównuje stan. Działa z championem, bez championa i po zmianie challengera.
Nie wymaga, aby wszystkie aliasy wskazywały wersję z dowodu; ładuje konkretną
wersję dowodu. Kandydat zablokowany jakościowo jest pokazany jako niekwalifikujący
się do promocji, bez zmiany aliasów.

## Odczyt wersji i lineage

```python
from pathlib import Path
from src.registry import LocalRegistry

store = LocalRegistry.from_evidence(Path("<aktualny-evidence.json>"))
version = store.resolve("challenger")
model = store.load(version)
origin = store.lineage(version)
# store.predict(version, frame) sprawdza ścisły kontrakt wejścia.
```

Alias rozwiąż raz, następnie używaj dokładnej wersji. `load` sprawdza manifest
przed deserializacją; `predict` dodatkowo sprawdza kolejność kolumn, typy,
słowniki kategorii, zakresy i brak null. Bezpośredni sklearn ma mniej restrykcyjny kontrakt.

`python -m scripts.lineage --registry <aktualny-katalog-registry> --alias challenger`
pozwala przejść: alias → wersja → run pakowania/źródłowy run → Git SHA/dirty state →
manifest danych, splity, parametry, metryki, config, locki, zależności i preprocessing.
Obraz kontenera ma wartość null; wdrożenia nie rozpoczęto.
MLflow zapisuje lokalne URI artefaktów w bazie. Dowód jest przenośnym przekazaniem
lokalizacji w ramach nowego przebiegu, ale przeniesienie gotowej bazy na inny dysk
nie jest obsługiwane automatycznie. Po klonie odtwarzamy runy i rejestr od nowa.

## Bramki jakości i kontrola promocji

- Wyłącznie validation; final_test i replay pozostają nieocenione.
- Próg 0,5; AP ściśle powyżej Dummy; recall co najmniej zwykła regresja logistyczna
  z tego samego batcha (w referencji UCI 7/794).
- Dla championa wymagane te same dane, splity, schemat i protokół; AP oraz recall
  nie mogą się pogorszyć. Remis jest dopuszczalny.
- Braki/niefinitywne metryki, niezgodne zależności (w tym skops), schemat,
  pliki lub lineage blokują kontrolę/promocję.
- Promocja wymaga challengera, jawnej zgody i oczekiwanej poprzedniej wersji.

`register` sprawdza integralność, nie ogłasza akceptacji jakościowej.
Przygotowanie wywołuje `check` przed przypisaniem challengera. Nieudana kontrola
może pozostawić zarejestrowaną wersję bez aliasu. `promote` zawsze ponawia bramki.
To próg akademicki, nie SLA; niski recall nie uzasadnia użycia operacyjnego.

Po osobnej zgodzie operatora można użyć:

```python
review = store.check(version)
receipt = store.promote(version, expected=review["champion"], approved=True)
store.rollback(receipt["event"], expected=version, approved=True)
```

To instrukcja, nie wykonana promocja głównego registry. `approved=True` oznacza
zgodę operatora, nie uwierzytelnienie. Rollback weryfikuje poprzedni pakiet;
przywraca poprzednią wersję lub brak championa. Receipts pending/applied są unikalne.
Awaria między aliasem a zapisem receipt wymaga ręcznej inspekcji, bez automatycznego retry.
`alias.lock` serializuje piszących przez moduł; UI/API MLflow może obejść blokadę.
Po awarii pozostawioną blokadę wolno usunąć dopiero po potwierdzeniu braku piszącego.

## Izolowana demonstracja rzeczywistego UCI

```powershell
uv run --locked python -m scripts.demo_lesson7 --evidence $env:BANK_MARKETING_REGISTRY_EVIDENCE
```

Tworzy nową bazę `isolated-demo/`, nigdy nie zmienia wskazanego głównego registry.
Promuje dwie wersje tego samego zweryfikowanego zwycięzcy, co testuje mechanikę
wydania i rollbacku; nie udaje poprawy jakości drugiej wersji. Osobno rejestruje
rzeczywisty `logistic_balanced` z tego batcha i sprawdza blokadę pogorszenia AP.
Wykonuje notebook z championem i bez niego, a następnie potwierdza niezmienność
stanu głównego rejestru. Wynik i wykonane notebooki pozostają w nowym katalogu.

## Izolowana próba wersji roboczej

```powershell
uv run --locked python -m scripts.reproduce_lesson7
```

Skrypt tworzy lokalny klon z jawną nakładką dozwolonych plików zajęć 7.
Nie przenosi roboczego notebooka 01, prywatnych planów, danych, modeli, starych
baz ani cache. Buduje nową .venv przez `uv sync --locked --no-cache`, używając
zainstalowanego Pythona 3.12. Pobiera UCI od nowa, generuje batch, registry i dowód,
wykonuje notebook, izolowane demo i pełny pytest z bramką UCI, a następnie
porównuje metryki z publiczną referencją. Pliki organizacyjne pozostające wyłącznie
lokalnie nie są kopiowane ani wymagane. Kontrola audit-hook blokuje odczyty
źródłowych danych, modeli, cache i dokumentacji lokalnej w procesie odtworzenia
oraz jego procesach Python; nie jest to sandbox uprawnień systemu operacyjnego.
Pełne logi oraz manifest nakładki pozostają pod artifacts/lesson7/reproduction-*.

To test bieżącej wersji roboczej na tym samym komputerze, nie prawdziwy zdalny
klon po publikacji ani niezależna weryfikacja. Do czasu osobnej zgody niczego
nie publikujemy. Nie uruchamiamy dvc repro w głównym workspace.

## Bezpieczeństwo i zakres

Źródłowy joblib/pickle może wykonać kod: przyjmujemy wyłącznie zaufane lokalne
artefakty po kontroli hashy. Pakiet skops jawnie ufa istniejącej funkcji
`src.features.build.history_features`. Manifest jest kotwiczony w tagu wersji;
nie chroni przed administratorem zmieniającym jednocześnie bazę i pliki.
Modele, bazy, dane i logi pozostają ignorowane przez Git. Publiczne dowody to
agregaty i hashe, bez danych klienta i ścieżek użytkownika. Nie wdrażamy API,
Docker, CI/CD, monitoringu, CT ani RAG w ramach zajęć 7.
