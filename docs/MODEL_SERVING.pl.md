---
title: Lokalna usługa modelu — zajęcia 8
updated: 2026-11-12
---

# Przygotowanie i uruchomienie

FastAPI wybrano do demonstracji predykcji podczas interakcji użytkownika.
Ranking całej kampanii może być zadaniem wsadowym; nie udajemy, że wymaga
stale działającego serwera. API obsługuje paczki do 100 rekordów wspólną logiką
`score`, bez dodatkowego treningu i bez nowego preprocessingu.

## Po świeżym klonie

W PowerShell, z katalogu repozytorium, przy Pythonie 3.12.10 i dostępie do sieci:

```powershell
uv sync --locked
uv run --locked python -m scripts.prepare_lesson8
```

Skrypt tworzy nowy `artifacts/lesson8/preparation-<id>/checkout`, osobną .venv
i nowy rejestr z publicznych danych UCI. Korzysta z opublikowanego przebiegu zajęć 7:
sześć eksperymentów train/validation, istniejąca reguła wyboru, pakowanie zwycięzcy.
Nie kopiuje starych danych, modeli, baz, cache ani prywatnych dokumentów.
Nie zmienia głównego rejestru. Nowy rejestr otrzymuje tylko challenger.
Wynik zawiera `evidence` oraz ścieżki logów w katalogu przygotowania.
Wbudowany audit hook Pythona blokuje dostęp do źródłowych danych/modeli/prywatnych
planów podczas odtworzenia; nie jest sandboxem systemowym.

Przed publikacją skrypt testuje lokalny klon HEAD z jawną nakładką plików zajęć 8.
Lista i hashe nakładki są w preparation.json; nie jest to test opublikowanego
commita zajęć 8. Po publikacji te same pliki znajdują się w klonie. To wciąż
odtworzenie na tym samym komputerze, a nie dowód na innym OS.

Przygotowanie wykonuje rzeczywistą demonstrację HTTP, pomiar opóźnienia i testy API.
Instalacja bez starego cache i pobranie UCI wymagają sieci. Nie wywołuje dvc repro.
Istniejący katalog wynikowy jest odrzucany; kolejne uruchomienie tworzy nowy.

## Uruchomienie istniejącego modelu

Wskaż dokładnie `evidence` zwrócone przez przygotowanie. Brak domyślnego rejestru
po klonowaniu jest celowy; usługa wstanie z live=200, ale ready/predict=503.

```powershell
$env:BANK_MARKETING_SERVING_EVIDENCE = Read-Host 'Pełna ścieżka evidence.json'
$env:BANK_MARKETING_SERVING_VERSION = '1'
Remove-Item Env:BANK_MARKETING_SERVING_ALIAS -ErrorAction SilentlyContinue
uv run --locked uvicorn src.serving:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log --log-config configs/serving-logging.json
```

Dokumentacja: http://127.0.0.1:8000/docs. Zatrzymanie: Ctrl+C.
Proces jest lokalną demonstracją bez uwierzytelniania i TLS; nie wystawiaj go
na publicznym interfejsie. Nie zaprojektowano go jako produkcyjnej usługi.

Alternatywnie wybierz alias:

```powershell
Remove-Item Env:BANK_MARKETING_SERVING_VERSION -ErrorAction SilentlyContinue
$env:BANK_MARKETING_SERVING_ALIAS = 'challenger'
```

Podaj dokładnie jeden selektor: dodatnią wersję lub challenger. Alias jest
rozwiązywany raz, a konkretna wersja przypinana przy starcie. Zmiana aliasu
nie przeładowuje działającego procesu. Nie obsługujemy automatycznego wyboru
championa, promocji ani rollbacku. Challenger jest kandydatem demonstracyjnym.
Podany dowód musi pasować do istniejącej bazy; brak pliku nie tworzy pustego registry.

## Żądanie i demonstracja

Kompletny kontrakt i JSON: [API_CONTRACT.md](API_CONTRACT.md).
Syntetyczny przykład można uzyskać bez odczytu danych klienta:

```powershell
$body = uv run --locked python -c "import json; from src.serving_contract import example_request; print(json.dumps(example_request()))"
Invoke-RestMethod http://127.0.0.1:8000/v1/predict -Method Post -ContentType 'application/json' -Body $body
Invoke-RestMethod http://127.0.0.1:8000/health/live
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

Powtarzalna demonstracja samodzielnie uruchamia i zawsze zatrzymuje proces:

```powershell
$output = Join-Path 'artifacts/lesson8' ('manual-' + [guid]::NewGuid().ToString('N'))
uv run --locked python -m scripts.demo_lesson8 --evidence $env:BANK_MARKETING_SERVING_EVIDENCE --output $output
```

Zapisuje poprawne i błędne odpowiedzi, p50/p95/p99 dla 30 żądań po 1 i po 50
rekordów, logi serwera i potwierdzenie niezmienności rejestru. To pomiar lokalny,
bez deklaracji SLO czy wyników testu obciążeniowego. Dane są syntetyczne.
Notebook [04_model_serving.ipynb](../notebooks/04_model_serving.ipynb) używa tego
samego modułu demonstracji; nie przygotowuje modelu i nie trenuje.

## Działanie i obsługa niedostępności

Lifespan ładuje raz kompletny Pipeline przez LocalRegistry z zajęć 7.
Przed deserializacją weryfikowane są hashe, lineage i zależności. Model musi
mieć dokładnie dziesięć cech kontraktu, poprawną sygnaturę i klasy [0,1].
Istniejąca bramka validation oraz próg 0.5 pozostają bez zmian.
Inferencja nie odczytuje ponownie bazy i nie zmienia aliasów ani wersji.
Prawdopodobieństwo i klasa wynikają z tego samego zapisanego preprocessingu
co w treningu, w tym pdays=999, kodowanie kategorii i skalowanie.

Log JSON zawiera request_id, status, czas, liczbę rekordów i wersję/nazwę modelu.
Nie zawiera wartości cech, surowego body, ścieżek ani treści wyjątków. Middleware
generuje identyfikator zamiast ufać dowolnemu tekstowi klienta. Startup failure
ma ogólny event `model_load_failed`; operator lokalnie sprawdza dowód/pakiet
narzędziami zajęć 7. Serwer nie maskuje niedostępności wynikiem modelu.

Przy godzinnej niedostępności klient wstrzymuje decyzje i oznacza brak predykcji.
Może zachować zlecenia u siebie z własnym kluczem deduplikacji i ograniczonym
exponential backoff; nie ponawia nieskończenie i nie zamienia błędu na klasę no.
Usługa nie implementuje trwałej kolejki ani idempotency key. Powtórne żądanie
na tej samej wersji daje ten sam wynik, lecz nowy request_id. Gotowość nie jest
obietnicą automatycznego odtworzenia po awarii; uszkodzony model wymaga restartu
po świadomej korekcie konfiguracji. Brak modelu daje 503, proces nadal jest żywy.

Recall UCI to tylko **7/794** przy 0.5. Bramka akademicka nie potwierdza przydatności
do obsługi realnych kampanii. Nie przeprowadzono końcowej walidacji operacyjnej,
testów na final_test/replay, promocji produkcyjnej ani strojenia progu.

## Kontrole

```powershell
$env:BANK_MARKETING_QUALITY_CSV = (Resolve-Path data/raw/bank-additional-full.csv).Path
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv lock --check --offline
uv pip check
```

Testy API tworzą własne syntetyczne runy, pakiet i registry w tmp_path.
Nie wymagają prywatnych dokumentów ani głównych modeli. Snapshot OpenAPI jest
kontrolowany w pytest. Pełny przebieg i dowody opisuje [raport zajęć 8](../reports/lesson8_serving.pl.md).
