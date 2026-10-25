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
