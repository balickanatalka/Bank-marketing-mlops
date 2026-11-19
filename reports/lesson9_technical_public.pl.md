---
title: Zajęcia 9 — publiczny raport techniczny
updated: 2026-11-19
---

# Zakres i stan

Zajęcia 9 obejmują CI, kontener API v1 i kontrole łańcucha dostaw.
Środowisko pozostaje przypięte do Python 3.12.16, uv 0.13.9 i uv.lock,
na bazie Debian trixie przypiętej digestem w Dockerfile.
Instrukcje odtworzenia i działania bramek opisuje
[dokumentacja CI](../docs/CI_SUPPLY_CHAIN.pl.md).
Uruchomienie API i przygotowanie własnego pakietu modelu opisuje
[instrukcja udostępniania](../docs/MODEL_SERVING.pl.md), a kontrakt
[API v1](../docs/API_CONTRACT.md).

Nie wykonano zdalnego CI dla lokalnej implementacji ani publikacji obrazu.
Wyniki poniżej pochodzą z lokalnych kontroli z 2026-11-19, przed zmianami
prywatności dokumentacji. Te zmiany nie obejmują kodu aplikacji, testów,
workflow, Dockerfile, locka, danych ani modeli. Nie uruchamiano ponownie
treningu UCI ani skanów zależności i obrazu podczas porządkowania dokumentacji.

**Bezpieczeństwo pozostaje FAIL, publikacja obrazu jest zablokowana.**
Nie zaakceptowano wyjątków od bramek ani nie ukryto CVE.

# Niezależne wyniki CI i ścisła publikacja

`functional_checks` odtwarza środowisko, sprawdza politykę CI i Ruff,
uruchamia pytest, walidację syntetycznych danych i krótki trening kontrolny.
`functional_image` zależy tylko od tej części i wykonuje build oraz HTTP.
Syntetyczne metryki służą kontroli kodu; nie potwierdzają jakości na UCI.
Domyślny CI nie wymaga lokalnych danych, modeli ani prywatnego MLflow.
Rzeczywista bramka UCI wymaga jawnego CSV zgodnego z manifestem;
bez niego test jest pomijany. Final test i replay nie służą do selekcji modelu.

Niezależne audyty `security_dev`, `security_runtime`, `security_history`
i `security_image` zachowują rzeczywiste kody wyjścia. Skan obrazu obejmuje
HIGH/CRITICAL również bez dostępnej poprawki. Nie użyto continue-on-error.
Job `publish` wymaga sukcesu wszystkich sześciu jobów, main i ręcznego opt-in.
Przed uzyskaniem danych logowania ponownie sprawdza kandydata. Publikuje
ten sam obraz bez ponownej budowy, dopiero po kontroli digesta.
Do artefaktów Actions trafiają raporty, bez archiwum OCI kandydata.

# Ostatnie wykonane kontrole lokalne

| Kontrola | Wynik i zakres |
| --- | --- |
| pytest z rzeczywistą bramką jakości UCI | PASS: 232 PASS, 1 SKIP; pominięty Docker sprawdzony osobno |
| Docker HTTP | PASS osobno na poniższym kandydacie; model syntetyczny i brak modelu |
| Regresje polityki publikacji | PASS: 54 testy, także negatywne scenariusze bramek |
| Ruff check i format | PASS |
| pre-commit jawnej ówczesnej allowlisty | PASS; nie jest to skan nowego zestawu publikacyjnego |
| actionlint | PASS |
| uv lock --check i uv pip check | PASS; 196 zgodnych zainstalowanych pakietów |
| Walidacja i trening kontrolny | PASS, syntetyka, bez wyboru nowego modelu UCI |
| Build i rzeczywiste warstwy obrazu | PASS |
| SBOM i provenance | PASS powiązania z obrazem; bez weryfikacji podpisu kryptograficznego |
| pip-audit dev | FAIL: diskcache 5.6.3, PYSEC-2026-2447 |
| pip-audit rzeczywistego Linux runtime | PASS: 90 dystrybucji, bez DVC i diskcache |
| Trivy | FAIL: 43 HIGH, 0 CRITICAL, 11 unikalnych CVE systemowych |
| Gitleaks historii | PASS dla 9 dostępnych commitów |
| Gitleaks poprzedniego kandydata | PASS; aktualna allowlista wymaga osobnej kontroli |
| Integralność przy poprzedniej walidacji | WARN: 4768 bez zmian; 38 221 plików historycznych niedostępnych |
| Zdalny GitHub Actions | NIEURUCHOMIONY |

Dowody lokalne zachowano pod `artifacts/lesson9/variant1-20261119T210221Z/`.
Ten katalog jest lokalny, ignorowany i nie jest wymagany do odtworzenia CI.
Kluczowe dowody: pytest-contract-final.xml, container-focused.xml,
policy-identity.xml, dev-audit.json, linux-runtime-audit.json, trivy.json,
image-attestations.json, sbom.cdx.json oraz gitleaks-history.json.
Są to nazwy istniejących dowodów, nie odnośniki do publicznych plików.

Zweryfikowany indeks obrazu:
`sha256:ca5d7fd849a7b82bd9b971e3705a3cbcae34f23c38eae60b502fcac999741bf5`.
Manifest linux/amd64:
`sha256:90e26c378ddf1de1e9194195df122139472dce0c8733f888fa4f88a7db4d36b4`.
Konfiguracja:
`sha256:1f98cf8f17f4c7586ad4ab1308c421fcc996b26c26fa3f68fbb62926e6de1de6`.
Trivy wskazuje konfigurację, Syft manifest platformy; atestacje zweryfikowano
w odniesieniu do manifestu i rzeczywistych warstw archiwum OCI.

# Otwarte ryzyka

diskcache pochodzi z developerskiego łańcucha DVC → dvc-data → diskcache.
Nie ma go w rzeczywistym profilu uruchomieniowym API. To rozdzielenie profili,
nie wyłączenie podatności: pełny audyt developerski nadal blokuje publikację.
Zgłoszenie ma aliasy CVE-2025-69872 i GHSA-w8v5-vhqr-4h9v.
Według ostatniego audytu nie wskazano poprawionej wersji.

43 zgłoszenia HIGH obejmują 11 CVE pakietów systemowych. Według zapisanego
Trivy nie miały FixedVersion. Usunięcie zbędnego mount obniżyło wcześniejsze
47 zgłoszeń do 43; nie usunęło wszystkich podatności. Stan baz i poprawek
może się zmienić, dlatego przed publikacją wymagany jest nowy skan.
Sam brak poprawki nie daje automatycznej akceptacji ryzyka.

# Granice publikacji dokumentacji

Prywatna dokumentacja i notatki pozostają wyłącznie lokalnie.
Wcześniejsze raporty zajęć 9 oraz dawne kandydaty i allowlisty zachowano
bez nadpisywania; nie są aktualną instrukcją publikacji i są z niej wykluczone.
Publiczna instrukcja uruchomienia nie zależy od prywatnej dokumentacji.
Wykluczenie pliku przez Git nie jest kontrolą sekretów ani zabezpieczeniem
przed świadomym wymuszeniem dodania pliku.

Zmiany prywatności sprawdzane są osobno: odnośniki, jawna allowlista,
sekrety i ścieżki użytkownika, sumy chronionych plików, HEAD i pusty indeks.
Wyniki tego audytu nie zastępują poprzednich kontroli funkcjonalnych ani
nie zmieniają FAIL bezpieczeństwa. Ograniczony dostęp do historycznych
katalogów należy jawnie raportować zamiast deklarować pełny PASS.

## Lokalna kontrola prywatności dokumentacji

Kontrola obejmuje 25 plików aktualnej allowlisty. Git potwierdza ignorowanie
i brak śledzenia prywatnych dokumentów oraz czterech dawnych raportów zajęć 9.
Prywatna dokumentacja nie zmieniła zawartości. Odnośniki względne z publicznych
plików Markdown prowadzą do istniejących plików śledzonych lub ujętych
w allowliście; nie prowadzą do wykluczonych raportów ani prywatnej dokumentacji.
Kontrola wzorców prywatnych ścieżek użytkownika i danych kontaktowych nie
wykryła trafień. Lokalny Gitleaks nie wykrył sekretów w sprawdzonym kandydacie.
Taki wynik dotyczy jawnego zakresu, nie dowodzi braku wszelkich danych poufnych.

Porównanie integralności obejmuje 46 402 znane pliki. Jedyną zatwierdzoną
zmianą w tym zbiorze jest odnośnik w docs/REPRODUCIBILITY.md; brak innych zmian
lub brakujących plików. Obejmuje to znane notebooki, dane, modele, rejestry
MLflow, historyczne wyniki i cztery zachowane raporty. Pełna inwentaryzacja
ma jednak status WARN: podczas zbierania baseline nie można było wyliczyć
zawartości 35 katalogów historycznych. Nie zmieniano uprawnień; pliki znane
z wcześniejszego manifestu zostały porównane niezależnie od tych błędów.
HEAD pozostał bez zmian, indeks jest pusty. Lokalne dowody kontroli pozostają
w ignorowanym katalogu artifacts/lesson9/privacy-20261119-01/.

# Aktualna rekomendowana allowlista zajęć 9

Lista dotyczy wyłącznie lokalnie przygotowanych zmian zajęć 9, a nie całej
zawartości istniejącego repozytorium. Nie jest zgodą na staging lub publikację.

```text
.gitignore
.pre-commit-config.yaml
.python-version
.dockerignore
.github/workflows/ci.yml
.github/actions/check-image/action.yml
Dockerfile
compose.yaml
README.md
uv.lock
docs/REPRODUCIBILITY.md
docs/THIRD_PARTY_NOTICES.md
docs/CI_SUPPLY_CHAIN.pl.md
scripts/prepare_lesson8.py
scripts/ci_smoke.py
scripts/container_smoke.py
scripts/verify_image_evidence.py
scripts/verify_ci_policy.py
src/serving.py
src/serving_bundle.py
tests/test_serving.py
tests/test_ci_smoke.py
tests/test_image_evidence.py
tests/test_ci_policy.py
reports/lesson9_technical_public.pl.md
```

Wykluczone pozostają prywatne dokumenty i plany, dawne raporty zajęć 9,
artifacts/, dane, modele, bazy MLflow, notebooki 01–04 z wcześniejszą lokalną
modyfikacją 01 oraz nieśledzone historyczne dowody innych zajęć.
Nie wykonano stagingu, commita, pusha, publikacji obrazu ani operacji DVC.
Kolejne etapy kursu pozostają poza zakresem tego raportu.
