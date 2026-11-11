---
title: Raport publicznej reprodukcji zajęć 7
updated: 2026-11-11
---

# Zajęcia 7 — publiczny zakres i odtwarzalność

## Wynik

**PASS w zakresie lokalnej implementacji i próby odtworzenia wersji roboczej.**
Projekt nie wymaga dokumentów organizacyjnych pozostających wyłącznie lokalnie.
Nie jest to potwierdzenie końcowej oceny ani test klonu z opublikowanego commita.
Główny rejestr projektu nadal ma challenger=1 i nie ma championa.
Nie wykonano stagingu, commita, push, dvc push ani dvc repro w głównym katalogu.
Nie rozpoczęto zajęć 8–13 ani Microsoft RAG.

## Zakres poprawek

- Obowiązkowa nakładka reprodukcji zawiera tylko 20 plików publicznych.
  Allowlista publikacji to te pliki oraz trzy aktualne podsumowania napraw: 23 pliki.
- Usunięto publiczne odsyłacze do dokumentów nieobecnych w repozytorium.
  Ich treści nie przenoszono do innych plików; dokumentacja lokalna pozostała bez zmian.
- Reprodukcja sprawdza brak dokumentów lokalnych w klonie i blokuje odczyty
  źródłowych danych, artefaktów, cache oraz dokumentacji lokalnej przez audit-hook.
  Blokada działa w procesie odtworzenia i zwykłych procesach Python przez sitecustomize.
  Własny self-test oraz kontrola procesu potomnego potwierdzają jej działanie.
- Pełny pytest z rzeczywistą bramką UCI jest teraz częścią próby w nowej .venv.
- Dodano testy regresji publicznej listy plików i blokady odczytu źródłowych zasobów.
- Nowe dowody powstały z aktualnych uruchomień i obliczonych hashy logów.
  Poprzednie podsumowania napraw zachowano lokalnie w ignorowanym katalogu;
  historycznych dowodów zajęć 1–6 nie zmieniano.
- Lokalne info/exclude zabezpiecza dwa dokumenty organizacyjne przed przypadkowym
  dodaniem. Publiczny .gitignore, indeks i historia Git pozostały niezmienione.

## Kontrole i rzeczywiste wyniki

| Kontrola | Status | Wynik / dowód |
| --- | --- | --- |
| Pełny pytest w głównym środowisku, bramka UCI włączona | PASS | 112 passed, 3 warnings in 208.04s (0:03:28) |
| Osobny przebieg testów rejestru | PASS | 38 passed, 3 warnings in 164.27s (0:02:44) |
| Pełny pytest w świeżej .venv bez dokumentacji lokalnej | PASS | 112 passed, 3 warnings in 201.46s (0:03:21) |
| Ruff check / format check | PASS | Dokładne komendy, kody wyjścia i hashe logów w aktualnym dowodzie kontroli. |
| Istniejące hooki pre-commit | PASS | Oba hooki kontrolne dla ośmiu plików Python/notebook, bez stagingu. |
| uv lock --check --offline / uv pip check | PASS | Lock i zależności spójne; w tej poprawce nie zmieniano zależności ani locka. |
| Rejestr, serializacja i lineage | PASS | Wersje, aliasy, blokady jakości, integralność pakietu i zgodne predykcje. |
| Notebook 03 | PASS | Bez championa, z championem, z innym challengerem; snapshot i bajty bazy niezmienione. |
| Izolowane demo rzeczywistych modeli UCI | PASS | Promocja/rollback dwóch wydań zwycięzcy; blokada gorszego AP logistic_balanced. |
| Ochrona źródłowych zasobów | PASS | Self-test siedmiu blokowanych celów oraz test procesu potomnego. |
| Odczyt grafu DVC | PASS | Bez wykonania pipeline'u. |
| Stan DVC | WARN | Wcześniejsze rozbieżności validate/prepare/train/evaluate; szczegóły w JSON. |
| Integralność chronionych zasobów | PASS | Aktualny fingerprint i porównanie z początkiem zadania; osobny dowód integralności. |
| Klon GitHub po publikacji / drugi komputer | WARN / NOT RUN | Nie publikowano; sprawdzono lokalny klon z nakładką wersji roboczej. |

Aktualne dowody do przeglądu:

- [kontrole i testy](evidence/lesson7-repair-checks.json);
- [odtworzenie bez dokumentów lokalnych](evidence/lesson7-repair-reproduction.json);
- [integralność i prywatność plików](evidence/lesson7-repair-integrity.json).

Trzy pierwotne dowody lesson7-registry/checks/integrity opisują wcześniejszy etap
implementacji. Nie są wejściem wymaganym do uruchomienia nowego registry ani notebooka.
Aktualny wynik opisują pliki lesson7-repair-* wskazane powyżej.

## Co rzeczywiście odtworzono

Skrypt utworzył lokalny klon z jawną publiczną nakładką zmian roboczych.
Przed instalacją nie było .venv, danych, modeli, baz MLflow ani cache DVC;
nie było także dokumentów przeznaczonych tylko do lokalnego użytku.
Instalacja użyła uv sync --locked --no-cache. Pobrano UCI ponownie, sprawdzono
manifest, wygenerowano nowy batch sześciu eksperymentów, jawnie przekazano go
do nowego rejestru i wykonano notebook na aktualnym pliku evidence.json.

AP oraz recall odtworzonego zwycięzcy porównano automatycznie z publiczną
referencją do 1e-12. Reguła wyboru nadal używa wyłącznie validation:
AP powyżej Dummy, recall co najmniej referencja zwykłej regresji logistycznej,
próg 0,5. Final test i replay nie służyły do wyboru, strojenia ani promocji.
Niski recall 7/794 pozostaje ograniczeniem modelu, bez deklaracji gotowości operacyjnej.

Oddzielny demo registry sprawdził promocję i rollback dwóch wersji tego samego
rzeczywistego zwycięzcy. To test wydania, nie deklaracja poprawy jakości drugiej
wersji. Osobny kandydat logistic_balanced został zablokowany jako pogarszający AP.
Główny registry demonstracji pozostał niezmieniony. Oryginalny główny registry
projektu jest dodatkowo objęty fingerprintem i nie został promowany.
Następnie cała suita pytest z bramką UCI przeszła w nowej .venv bez dokumentów lokalnych.

Dowód odtworzenia zawiera manifest dokładnej nakładki, kody wyjścia i hashe logów.
Nie zawiera hashy ani treści dokumentacji lokalnej. Raport końcowy jest finalizowany
po pomiarach; manifest nakładki wskazuje dokładną wersję wejść rzeczywistej próby.
Pełne logi, bazy, modele i wykonane notebooki pozostają ignorowane pod
artifacts/lesson7/public-20261111T150401795662Z/.

## Ograniczenia i ostrzeżenia

- To ten sam komputer i istniejący Python 3.12.10, z nową .venv i bez starego cache uv.
  Nie jest to niezależna maszyna, zdalny klon ani opublikowany commit.
- Audit-hook jest kontrolą regresji zaufanego kodu Python, nie sandboxem systemu
  operacyjnego. Nie obejmuje natywnych procesów; Python uruchomiony z -I ignoruje
  sitecustomize. Brak danych/cache i dokumentów w kopii jest sprawdzany niezależnie.
- Pierwszą instalację zablokował sandbox sieciowy. Po uzyskaniu dostępu do sieci
  wykonano nową próbę w nowym katalogu; wszystkie jej etapy zakończyły się kodem 0.
- SQLAlchemy noload, sygnatura integer/null MLflow oraz Windows Proactor/ZMQ
  pozostają jawnymi ostrzeżeniami. Rzeczywiste null są odrzucane przez kontrakt.
- Helper routingu Skillpack zgłosił błąd; instrukcje skilli odczytano bezpośrednio.
- Lokalne URI MLflow nie są automatycznie przenoszone między dyskami. Po klonie
  procedura tworzy nowe runy i rejestr zamiast kopiowania historycznych baz.
- SHA-256 nie jest podpisem cyfrowym; alias.lock nie obejmuje edycji UI/API.
  Receipts pending wymagają ręcznej inspekcji po awarii.
- Nie przeprowadzono jeszcze pełnego skanu łańcucha dostaw, SBOM, wdrożenia ani obrony.
  Dokumenty organizacyjne nie są częścią tej publikacji i nie są wymagane przez kod.

## Dokładna allowlista przyszłego commita — 23 pliki

```text
README.md
pyproject.toml
uv.lock
docs/ARCHITECTURE.md
docs/MODEL_CARD.md
docs/MODEL_REGISTRY.pl.md
docs/TEST_STRATEGY.md
docs/THIRD_PARTY_NOTICES.md
notebooks/03_model_registry.ipynb
scripts/lineage.py
scripts/verify_lesson7.py
scripts/demo_lesson7.py
scripts/reproduce_lesson7.py
src/model_card.py
src/registry.py
tests/test_registry.py
reports/lesson7_registry.pl.md
reports/evidence/lesson7-registry.json
reports/evidence/lesson7-checks.json
reports/evidence/lesson7-integrity.json
reports/evidence/lesson7-repair-checks.json
reports/evidence/lesson7-repair-reproduction.json
reports/evidence/lesson7-repair-integrity.json
```

Poza listą pozostają dokumenty lokalne, prywatne plany i notatki, notebooki 01/02,
dvc.lock, dane, modele, bazy, cache, pełne logi oraz stare nieśledzone dowody zajęć 3–5.
Local info/exclude nie jest plikiem publikacji.

## Pozostałe etapy

Zajęcia 8: udostępnienie i wersjonowany kontrakt. 9: CI, build runtime, skany i SBOM.
10: dostarczanie, bezpieczna zmiana wersji i rollback usługi. 11: monitoring i SLI/SLO.
12: dryf, kontrolowane CT, ryzyka i runbook. 13: game day i samodzielna prezentacja.
Microsoft RAG pozostaje planowanym rozszerzeniem nad dokumentacją i lineage;
nie zastępuje obowiązkowych elementów MLOps i nie został rozpoczęty.
