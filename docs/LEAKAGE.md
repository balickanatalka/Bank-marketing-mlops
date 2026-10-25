# Moment predykcji i dostępność cech

Aktualizacja: 2026-10-25.

Predykcja dotyczy momentu przed rozmową. Konserwatywna lista dopuszcza informacje o kliencie
i zakończonych poprzednich kampaniach, zakładając ich obecność w systemie przed
rozmową: age, job, marital, education, default, housing, loan, pdays, previous, poutcome.
To jawne założenie demonstracji; UCI nie udostępnia historii zmian każdego pola.

| Pola | Decyzja | Powód |
|---|---|---|
| duration | Wykluczone | Długość bieżącej rozmowy jest znana po jej zakończeniu |
| contact, month, day_of_week | Wykluczone | Opis dotyczący ostatniego kontaktu nie potwierdza planowanego snapshotu |
| campaign | Wykluczone | Licznik zawiera bieżący/ostatni kontakt |
| emp.var.rate, cons.price.idx, cons.conf.idx, euribor3m, nr.employed | Wykluczone | Brak dat publikacji i dowodu dostępności wartości bez późniejszych rewizji |
| y | Tylko etykieta | Nigdy wejście modelu |

Podział jest przed fit: 60/15/10/15, bez tasowania. Fit scaler/encoder/model
korzysta wyłącznie z train. Ewaluacja używa validation. Final test nie służy
do bieżącego wyboru; jego jednorazowa ocena nastąpi po późniejszych eksperymentach.
Replay jest osobnym materiałem do przyszłej symulacji utrzymania.

Zmiana seed nie tasuje danych. Duplikaty nie są usuwane na podstawie wyników modeli.
Brak identyfikatora klienta pozostaje ograniczeniem; obecne zabezpieczenia
nie gwarantują niezależności wszystkich osób między oknami.
