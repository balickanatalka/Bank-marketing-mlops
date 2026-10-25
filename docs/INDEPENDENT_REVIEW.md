# Niezależna weryfikacja odtwarzalności

Status: nie wykonano. Ten dokument opisuje protokół i nie potwierdza pozytywnego wyniku.

Weryfikacja obejmuje świeży klon opublikowanej wersji, `uv sync --locked`,
`python -m src.cli all` przez `uv run --locked` oraz `uv run --locked pytest -q`.
Środowisko nie powinno zawierać wcześniejszej `.venv`, CSV ani modeli projektu.

Raport z wykonania powinien zawierać datę, SHA commita, system, wersje Python/uv,
użyte polecenia, kody wyjścia, hash danych, metryki i rozbieżności względem raportu
referencyjnego. Problemy należy powiązać z poprawkami i wynikiem ponowienia.
Identyfikator recenzenta może być pseudonimem; logi nie powinny zawierać sekretów
ani prywatnych ścieżek. Niezależnego wykonania nie zastępuje lokalny test reprodukcji.
