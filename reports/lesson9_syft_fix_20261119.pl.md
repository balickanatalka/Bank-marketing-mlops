---
title: Zajęcia 9 — lokalna poprawka integracji Syft z OCI
updated: 2026-11-19
---

# Wynik i zakres

Naprawiono lokalnie źródło Syft: jawne `oci-archive:` wskazuje archiwum
wyeksportowane z tego samego kandydata, którego digest, warstwy, SPDX/provenance
i HTTP sprawdza wspólna akcja. Dodano osobną blokującą kontrolę podmiotu
CycloneDX. Nie zmieniono progów Trivy, audytu dev/runtime, kontraktu API,
bazy Debian, Pythona 3.12.16, locka ani sposobu wyboru modelu.

**Lokalna poprawka Syft: PASS. Pełne bezpieczeństwo: nadal FAIL.**
Nie wykonano stagingu, commita, pusha, publikacji obrazu ani rerun CI.
Nie wykonano treningu, operacji DVC ani kolejnych zajęć.

# Przyczyna potwierdzonego błędu

Punktem odniesienia jest [przebieg GitHub Actions 44626367673](https://github.com/balickanatalka/Bank-marketing-mlops/actions/runs/44626367673)
dla commita `9882fc9700f5a8ae199646332d21bd8faca06f72`.
Joby functional_checks i functional_image przeszły, security_runtime i
security_history również. security_dev i security_image zakończyły się FAIL,
a publish został SKIPPED.

Docker CLI używał kontekstu `setup-docker-action` i osobnego demona.
Wejście `image: bank-marketing-api:ci` przekazywało do Syft niekwalifikowany tag,
uruchamiając automatyczne rozwiązywanie źródła. Biblioteka klienta Docker
Syft 1.57.2 (stereoscope 0.4.2) konfiguruje klienta przez FromEnv/DOCKER_HOST;
wybór kontekstu CLI nie stanowił jawnego wskazania tego endpointu skanerowi.
Syft nie znalazł dostępnego lokalnego źródła i próbował Docker Hub:

```text
could not determine source
docker: pull failed: ... pull access denied for bank-marketing-api
oci-registry: ... library/bank-marketing-api ... UNAUTHORIZED
```

To błąd rozwiązywania źródła/kontekstu w CI, nie błąd aplikacji i nie potrzeba
logowania do GHCR. Poprawka całkowicie usuwa zależność Syft od demona/rejestru
przy odczycie kandydata.

Przeanalizowano [kod przypiętej akcji](https://raw.githubusercontent.com/anchore/sbom-action/66cbf4bc1f1c0d2edc94016e65bc221b6bb0ad6c/src/github/SyftGithubAction.ts)
oraz [klienta stereoscope](https://raw.githubusercontent.com/anchore/stereoscope/v0.4.2/internal/docker/client.go).
Pole image jest przekazywane bez zmian, jeśli nie podano registry-username.
Pole file dodaje prefiks `file:`. Dlatego użyto:

```yaml
image: oci-archive:${{ env.BANK_CI_EVIDENCE_DIR }}/image.oci.tar
```

To parametr źródła skanowania, nie publikacja obrazu i nie próba pobrania tagu.

# Powiązanie obrazu i raportu

1. Build pozostaje load=true/push=false z SPDX i SLSA provenance.
2. Istniejący etap eksportuje archiwum i weryfikuje indeks z outputs.digest,
   konfigurację, wszystkie warstwy oraz podmioty obu atestacji.
3. Test HTTP używa tego kandydata. Błąd HTTP nadal oznacza FAIL akcji.
4. Syft 1.57.2 czyta jawne OCI wyłącznie po udanej kontroli archiwum.
5. Nowa kontrola ponownie weryfikuje bajty archiwum oraz format, wersję,
   producenta, niepuste komponenty i dokładny podmiot CycloneDX.
6. Podmiot musi odpowiadać manifestowi platformy linux/amd64, nie indeksowi,
   konfiguracji ani innemu obrazowi. Raport otrzymuje własny SHA-256.
7. Trivy nadal wykonuje blokujący skan HIGH/CRITICAL, również po błędzie SBOM.
   Nie ma continue-on-error ani zmiany ignore-unfixed.

Weryfikator kontroluje strukturę i powiązanie raportu Syft/CycloneDX 1.7;
nie jest pełnym walidatorem JSON Schema ani weryfikacją podpisu kryptograficznego.
Nie porównuje liczby komponentów różnych katalogerów jako warunku równości.

Brak raportu, niepoprawny JSON, pusty wykaz, inny producent lub błędny digest
przerywają bramkę. Publish nadal wymaga sukcesu security_image i pozostałych
pięciu jobów oraz osobnego ręcznego opt-in na main. Wszystkie warunki
publikacji i plik workflow pozostają niezmienione.

# Nowe dowody lokalne

Dowody są wyłącznie lokalne w `artifacts/lesson9/syft-fix-20261119-01/`.
Poprzednie raporty, archiwa oraz wyniki PASS/FAIL nie były nadpisywane.

| Kontrola | Wynik / dowód |
| --- | --- |
| Syft 1.57.2 z jawnym oci-archive | PASS, kod 0; syft-oci-offline.result.json |
| Brak dostępu do rejestru | Kontener miał network=none i źródło read-only; nie montowano socketu Docker |
| Raport CycloneDX | Wersja 1.7, 3059 komponentów; sbom-offline.cdx.json |
| Powiązanie raportu i archiwum | PASS; real-binding.log i .result.json |
| Testy polityki CI i weryfikatora | PASS: 92 testy; tests.xml |
| actionlint 1.7.12 | PASS; actionlint.result.json |
| Ruff check i format check | PASS; ruff-check/ruff-format-check.result.json |
| Izolacja wpływu | PASS; impact.json: workflow, build, HTTP i Trivy niezmienione |
| Integralność | integrity.json; porównanie znanych plików i archiwum, z wcześniejszym ograniczeniem pełnej inwentaryzacji |

Użyto zachowanego lokalnego obrazu, który przeszedł wcześniej HTTP,
SPDX/provenance i kontrolę digestów. Nie budowano kolejnego obrazu i nie
ponawiano testu HTTP, bo kod aplikacji, Dockerfile i lock nie zmieniły się.
To dowód lokalny, nie wynik nowego przebiegu GitHub Actions poprawki.
Nie jest to również ponowny skan archiwum zdalnego obrazu, którego nie pobierano.

Zweryfikowany indeks:
`sha256:ca5d7fd849a7b82bd9b971e3705a3cbcae34f23c38eae60b502fcac999741bf5`.
Manifest platformy i podmiot CycloneDX:
`sha256:90e26c378ddf1de1e9194195df122139472dce0c8733f888fa4f88a7db4d36b4`.
SHA-256 niezmienionego pliku archiwum:
`3b39ede2ccdec8fe505afb7dbe62f1a595fd1354bd6532c01dfa570fd853864a`.
SHA-256 nowego raportu:
`408bee0a6a6d302ba08c71609f491d6f027a8c1c43383a3a55ca3769b03c7751`.

## Zachowane próby negatywne i ograniczenia

Pierwsze dwie próby kontenerowe zakończyły się kodem 1, ponieważ read-only
filesystem nie zapewniał zapisywalnego /tmp do rozpakowania archiwum.
Zachowano syft-oci.log i syft-file-provider.log. Udane próby dodały wyłącznie
izolowany tmpfs i wyłączyły sprawdzanie aktualizacji aplikacji; sieć pozostała
wyłączona, źródło read-only. Nie wyłączano żadnego skanera podatności.

Próba dokładnej składni file: używanej przez wrapper również zwróciła kod 0,
ale nadała podmiotowi inny digest:
`sha256:aa781a6c674cc14f99e22871b4a0b0d71e31cb1d4aa36f80f5eb5c434f281826`.
Weryfikator odrzucił ten raport kodem 1 (reject-file-provider.result.json).
Dlatego samo zastąpienie image przez file nie jest wystarczającą poprawką.

Testy obejmują niejawny tag/rejestr, niewłaściwe archiwum lub eksport,
brak/pominięcie bramki raportu, błędny digest, kolejność kontroli,
niepoprawny/brakujący raport i zmianę bajtów archiwum. Zachowano regresje
blokujące publikację przy failure/cancelled/skipped lub braku wyniku security_image.

## Dokładny zakres zmienionych plików

```text
.github/actions/check-image/action.yml
scripts/verify_ci_policy.py
scripts/verify_image_evidence.py
tests/test_ci_policy.py
tests/test_image_evidence.py
reports/lesson9_syft_fix_20261119.pl.md
```

# Nadal nierozwiązane

- **FAIL:** diskcache 5.6.3 / PYSEC-2026-2447 w profilu developerskim.
- **FAIL:** ostatni rzeczywisty Trivy: 43 HIGH, 11 CVE systemowych, bez
  FixedVersion w zapisanym raporcie. Nie wykonano nowego skanu w ramach tej poprawki.
- **SKIPPED na GitHubie:** rzeczywista bramka jakości UCI; główny pytest CI
  miał 231 PASS/2 SKIP, a trening kontrolny używał jawnej syntetyki.
- **NOT RUN:** GitHub Actions dla tej lokalnej poprawki Syft. Zgodę na publikację
  i nowy przebieg należy uzyskać osobno.

Nie przyjęto ryzyka jako wyjątku. Poprawka Syft nie oznacza zielonego
security_image ani gotowości publikacji obrazu. Dane, modele, notebooki,
prywatne dokumenty i registry pozostają poza zakresem zmian.
