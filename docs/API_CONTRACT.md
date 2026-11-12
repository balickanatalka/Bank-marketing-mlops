---
title: Kontrakt HTTP v1 — Bank Marketing
updated: 2026-11-12
---

# Kontrakt v1

Lokalna demonstracja, bez zastosowania do decyzji biznesowych. Pełny schemat:
[OpenAPI v1](api/openapi-v1.json), podczas pracy także `/openapi.json` i `/docs`.
Instrukcja uruchomienia: [udostępnianie modelu](MODEL_SERVING.pl.md).

`POST /v1/predict`, `Content-Type: application/json`. Obiekt zawiera wyłącznie
`records`: tablicę od 1 do 100 rekordów. Każdy rekord musi zawierać wszystkie
poniższe pola. Kolejność kluczy JSON nie ma znaczenia; serwer odtwarza kolejność
cech modelu. Nie dodaje nowych cech ani nie dopasowuje transformacji.

| Pole publiczne | Cecha zapisanego modelu | Typ i ograniczenia |
| --- | --- | --- |
| age_years | age | integer, 1–120 |
| job | job | string, słownik UCI |
| marital_status | marital | string, słownik UCI |
| education | education | string, słownik UCI |
| credit_default | default | string: no, yes, unknown |
| housing_loan | housing | string: no, yes, unknown |
| personal_loan | loan | string: no, yes, unknown |
| days_since_previous_contact | pdays | integer, 0–999; 999 oznacza brak poprzedniego kontaktu |
| previous_contacts | previous | integer, co najmniej 0 |
| previous_campaign_outcome | poutcome | string: failure, nonexistent, success |

Słowniki kategorii i zakresy pochodzą z istniejącego `src/data/schema.py`,
nie są wyznaczane z holdoutów. Pełne listy są w OpenAPI. Kategorie `unknown`
i `nonexistent` mają swoje istniejące znaczenie; nie zamieniamy ich na null.
Pydantic stosuje strict=True i extra=forbid. Odrzucamy null, bool zamiast int,
liczby zapisane jako string oraz 30.0 zamiast integer 30. Odrzucamy nieznane
kategorie i pola na każdym poziomie, w tym `duration`, `target`, `y`.

## Poprawne żądanie — dane syntetyczne

```json
{
  "records": [{
    "age_years": 30,
    "job": "admin.",
    "marital_status": "single",
    "education": "university.degree",
    "credit_default": "no",
    "housing_loan": "no",
    "personal_loan": "no",
    "days_since_previous_contact": 999,
    "previous_contacts": 0,
    "previous_campaign_outcome": "nonexistent"
  }]
}
```

## Odpowiedź 200

Wszystkie pola są wymagane. Przykładowa struktura poniżej ilustruje kontrakt;
liczba 0.1 nie jest wynikiem pomiaru modelu. Rzeczywiste odpowiedzi zapisuje demo.

```json
{
  "contract_version": "v1",
  "request_id": "identyfikator-generowany-przez-serwer",
  "model_name": "bank-marketing-validation",
  "model_version": "1",
  "mode": "demonstration",
  "decision_threshold": 0.5,
  "predictions": [{"probability_yes": 0.1, "class_label": "no"}]
}
```

Wyniki zachowują kolejność i liczbę rekordów wejściowych. `probability_yes` jest
skończoną liczbą z [0,1], drugą kolumną predict_proba dla klas [0,1].
`class_label=yes` wtedy i tylko wtedy, gdy prawdopodobieństwo >= 0.5.
Nie stroimy progu; pochodzi z lineage modelu. `request_id` jest nowy przy każdym
żądaniu i zgadza się z nagłówkiem `X-Request-ID`. Wersja modelu jest przypięta
na czas życia procesu. Odpowiedź jawnie oznacza tryb demonstracyjny.

## Błędne żądania i błędy

```json
{"records": []}
```

```json
{"records": [{"age_years": "30", "duration": 42}]}
```

Oba przykłady dają 422. Również dodanie `duration` do pełnego poprawnego rekordu
daje 422. Nie akceptujemy częściowo poprawnej paczki: całe żądanie jest odrzucane.

| Sytuacja | HTTP | error |
| --- | --- | --- |
| Brak pola, zły typ, kategoria, zakres, nadmiar pola, wadliwy JSON | 422 | invalid_request |
| Brak konfiguracji/dowodu/modelu, błędna wersja, niezgodny pakiet/schemat | 503 | model_unavailable |
| Błąd obliczeń lub niepoprawny wynik modelu | 500 | prediction_failed |

Stała postać błędu:

```json
{"contract_version": "v1", "request_id": "id", "error": "invalid_request"}
```

Nie zwracamy ścieżek, treści wyjątków, tracebacków ani wartości wejściowych.
`GET /health/live`: 200 z `status=alive`, niezależnie od modelu.
`GET /health/ready`: 200 z `status=ready` albo 503 w powyższym formacie błędu.
Odpowiedzi health zawierają także `contract_version=v1`.

## Stabilność kontraktu

To pierwszy zewnętrzny kontrakt, niezależny od wewnętrznych nazw kolumn.
Zmiana wymaganych pól, ich typów, semantyki, ograniczeń, struktury odpowiedzi
lub reguły progu wymaga nowej wersji ścieżki i planu migracji konsumenta.
Samo podmienienie modelu nie upoważnia do zmiany kontraktu v1.
Test porównuje wygenerowane OpenAPI z zapisanym snapshotem oraz wykrywa
usunięcie każdego wymaganego pola odpowiedzi. Zmiana snapshotu wymaga przeglądu,
nie automatycznego nadpisania po nieudanym teście.
