# Komponenty zewnętrzne

Aktualizacja: 2026-10-27. Zakres: zajęcia 3, źródła projektu i zależności
z `pyproject.toml` oraz `uv.lock`. Lock zawiera 153 zewnętrzne dystrybucje.
Sprawdzono metadane 150 dystrybucji z lokalnego środowiska oraz teksty licencji
bezpośrednich i istotnych pośrednich komponentów. Wersje odpowiadają lockowi.
Trzy zależności innych platform opisano na podstawie metadanych wydań PyPI;
tekst ISC potwierdzono również dla ptyprocess. Nie przejrzano pełnych archiwów
appnope i pexpect. Tabela nie jest audytem podatności ani pełnym SBOM.

Licencje i notices dystrybucji znajdują się m.in. w `dist-info/licenses`,
`LICENSE`, `LICENCE` i `COPYING` ignorowanego środowiska `.venv`.
Deklaracja ogólna BSD/PSF w tabeli nie zastępuje tekstu licencji konkretnego
wydania. Metadane wskazują deklarację wydawcy, nie dowodzą oryginalności pakietu.

## Dane, własny kod i narzędzia

Dane: Moro, Rita, Cortez (2014), UCI Bank Marketing, DOI
[10.24432/C5K306](https://doi.org/10.24432/C5K306),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Atrybucję, źródło i przekształcenia opisuje [DATA_LICENSE.md](../DATA_LICENSE.md).
Licencja danych nie obejmuje automatycznie własnego kodu ani zależności.
Własny kod projektu nie jest udostępniony na licencji open source. Dane UCI i komponenty zewnętrzne podlegają odrębnym licencjom opisanym w dokumentacji.

Python 3.12.10: PSF License; uv 0.13.4: MIT OR Apache-2.0; Git: GPL-2.0.
Są narzędziami zewnętrznymi, nie kopiami ich kodu w repozytorium.
pip z pierwotnego venv nie jest zależnością zadeklarowaną ani pozycją locka.
MLflow, Microsoft RAG, LLM, embeddingi, kontenery i monitoring pozostają
kolejnymi etapami projektu; nie mają jeszcze zainstalowanych komponentów
w deklarowanym zestawie zależności. Ich licencje wymagają osobnej oceny później.

## Istotne zależności i zakres obowiązków

- DVC 3.67.1 oraz główne komponenty DVC: Apache-2.0. Obecność
  dvc-studio-client/iterative-telemetry w locku nie oznacza skonfigurowania usługi;
  lokalna konfiguracja wyłącza analitykę i nie zawiera zdalnego magazynu.
- DVC zależy bezpośrednio od grandalf 0.8: tekst LICENSE dopuszcza wybór
  GPL-2.0-only albo EPL-1.0. Nie należy zapisywać tego jako obowiązkowego GPL.
- DVC -> scmrepo -> pygit2 1.20.1: GPLv2 z wyjątkiem linkowania opisanym w COPYING.
  Wyjątek pozwala na łączenie i dystrybucję kombinacji; nie znosi pozostałych
  obowiązków dotyczących samej biblioteki i jej modyfikacji.
- DVC -> scmrepo -> asyncssh 2.24.1: EPL-2.0; alternatywa GPL-2.0-or-later
  jest wskazana w metadanych i nagłówku źródła, pod warunkami Secondary License
  EPL. Nie jest bezwarunkowym zastąpieniem EPL przez dowolną licencję.
- Dulwich 1.2.20: Apache-2.0 OR GPL-2.0-or-later; wybraną ścieżkę trzeba stosować
  konsekwentnie do konkretnej dystrybucji komponentu.
- certifi, pathspec, shtab: MPL-2.0. orjson deklaruje
  `MPL-2.0 AND (Apache-2.0 OR MIT)`, a tqdm `MPL-2.0 AND MIT`.
  OR oznacza alternatywę, AND wymaga uwzględnienia obu wskazanych części.
- Matplotlib ma własny tekst licencji oparty na PSF i dodatkowe licencje
  fontów oraz innych zasobów. NumPy, SciPy i pyzmq również zawierają komponenty
  z odrębnymi licencjami. Nazwa licencji głównego pakietu nie opisuje całego wheel.

### Zależność od sposobu dystrybucji

1. **Obecne repozytorium:** publikuje własne źródła, konfiguracje, lock i małe
   raporty; nie zawiera wheel, `.venv`, kopii bibliotek, danych CSV ani modeli.
   Sam zapis zależności w locku nie jest redystrybucją kodu tej biblioteki
   i nie narzuca automatycznie GPL całemu projektowi.
2. **Kopiowanie fragmentów bibliotek lub ich modyfikowanie:** zachować
   właściwe nagłówki, licencje, atrybucję i wymagane oznaczenia zmian.
   Ta tabela nie zastępuje uprawnienia do kopiowania konkretnego fragmentu.
3. **Przyszłe wheel, obraz kontenera lub pakiet ze środowiskiem:** przed wydaniem
   ponownie zinwentaryzować faktycznie dołączone biblioteki i zasoby. Zachować
   wymagane copyright, teksty licencji i odpowiednie NOTICE, jeżeli występują.
   Dla Apache uwzględnić również oznaczenie zmian. Dla MPL/EPL/GPL ocenić
   obowiązki dotyczące źródeł właściwych komponentów i konkretnej formy
   dystrybucji, z uwzględnieniem alternatyw i wyjątków; nie sprowadzać ich do
   ogólnego stwierdzenia o licencji całego projektu. Nie rozpoczęto tego etapu.

Źródła warunków: [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0),
[EPL-2.0](https://www.eclipse.org/legal/epl-2.0/),
[EPL-1.0](https://www.eclipse.org/legal/epl-v10.html),
[MPL-2.0](https://www.mozilla.org/MPL/2.0/),
[GPLv2](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html).
Tekst wyjątku pygit2 i licencje składników trzeba zachować z właściwego wydania,
nie zastępować ich samymi linkami do ogólnych licencji.

## Wykaz wersji i deklaracji licencji

Tabela jest migawką locka. Źródłem deklaracji jest METADATA z odpowiedniej
dystrybucji, uzupełnione wyżej opisanym przeglądem tekstów licencji.
Linki prowadzą do stron konkretnych wydań, nie są treścią licencji.

| Dystrybucja | Wersja | Licencja / deklaracja | Źródło wydania |
|---|---|---|---|
| aiohappyeyeballs | 2.7.1 | Python Software Foundation License | [PyPI](https://pypi.org/project/aiohappyeyeballs/2.7.1/) |
| aiohttp | 3.14.5 | Apache-2.0 AND MIT | [PyPI](https://pypi.org/project/aiohttp/3.14.5/) |
| aiohttp-retry | 2.9.1 | MIT License | [PyPI](https://pypi.org/project/aiohttp-retry/2.9.1/) |
| aiosignal | 1.4.0 | Apache Software License | [PyPI](https://pypi.org/project/aiosignal/1.4.0/) |
| amqp | 5.4.1 | BSD License | [PyPI](https://pypi.org/project/amqp/5.4.1/) |
| annotated-types | 0.8.0 | MIT | [PyPI](https://pypi.org/project/annotated-types/0.8.0/) |
| antlr4-python3-runtime | 4.9.3 | BSD | [PyPI](https://pypi.org/project/antlr4-python3-runtime/4.9.3/) |
| appdirs | 1.4.4 | MIT License | [PyPI](https://pypi.org/project/appdirs/1.4.4/) |
| appnope | 1.0.0 | BSD-2-Clause (PyPI; niezainstalowane na Windows) | [PyPI](https://pypi.org/project/appnope/1.0.0/) |
| asttokens | 3.0.2 | Apache 2.0 | [PyPI](https://pypi.org/project/asttokens/3.0.2/) |
| asyncssh | 2.24.1 | EPL-2.0 OR GPL-2.0-or-later (warunki Secondary License) | [PyPI](https://pypi.org/project/asyncssh/2.24.1/) |
| atpublic | 9.0.0 | Apache Software License | [PyPI](https://pypi.org/project/atpublic/9.0.0/) |
| attrs | 26.1.0 | MIT | [PyPI](https://pypi.org/project/attrs/26.1.0/) |
| billiard | 4.3.1 | BSD License | [PyPI](https://pypi.org/project/billiard/4.3.1/) |
| celery | 5.6.3 | BSD-3-Clause | [PyPI](https://pypi.org/project/celery/5.6.3/) |
| certifi | 2026.10.23 | Mozilla Public License 2.0 (MPL 2.0) | [PyPI](https://pypi.org/project/certifi/2026.10.23/) |
| cffi | 2.1.1 | MIT-0 | [PyPI](https://pypi.org/project/cffi/2.1.1/) |
| cfgv | 3.5.0 | MIT | [PyPI](https://pypi.org/project/cfgv/3.5.0/) |
| charset-normalizer | 3.5.2 | MIT | [PyPI](https://pypi.org/project/charset-normalizer/3.5.2/) |
| click | 8.5.0 | BSD-3-Clause | [PyPI](https://pypi.org/project/click/8.5.0/) |
| click-didyoumean | 0.3.1 | MIT License | [PyPI](https://pypi.org/project/click-didyoumean/0.3.1/) |
| click-plugins | 1.1.1.2 | BSD License | [PyPI](https://pypi.org/project/click-plugins/1.1.1.2/) |
| click-repl | 0.4.1 | MIT | [PyPI](https://pypi.org/project/click-repl/0.4.1/) |
| cloudpickle | 3.1.2 | BSD License | [PyPI](https://pypi.org/project/cloudpickle/3.1.2/) |
| colorama | 0.4.6 | BSD License | [PyPI](https://pypi.org/project/colorama/0.4.6/) |
| comm | 0.2.3 | BSD License | [PyPI](https://pypi.org/project/comm/0.2.3/) |
| configobj | 5.0.9 | BSD License | [PyPI](https://pypi.org/project/configobj/5.0.9/) |
| contourpy | 1.4.0 | BSD-3-Clause | [PyPI](https://pypi.org/project/contourpy/1.4.0/) |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | [PyPI](https://pypi.org/project/cryptography/50.0.2/) |
| cycler | 0.12.1 | BSD License | [PyPI](https://pypi.org/project/cycler/0.12.1/) |
| debugpy | 1.8.22 | MIT License | [PyPI](https://pypi.org/project/debugpy/1.8.22/) |
| dictdiffer | 0.10.0 | MIT | [PyPI](https://pypi.org/project/dictdiffer/0.10.0/) |
| diskcache | 5.6.3 | Apache Software License | [PyPI](https://pypi.org/project/diskcache/5.6.3/) |
| distlib | 0.4.4 | Python Software Foundation License | [PyPI](https://pypi.org/project/distlib/0.4.4/) |
| distro | 1.9.0 | Apache Software License | [PyPI](https://pypi.org/project/distro/1.9.0/) |
| dpath | 2.2.0 | MIT License | [PyPI](https://pypi.org/project/dpath/2.2.0/) |
| dulwich | 1.2.20 | Apache-2.0 OR GPL-2.0-or-later | [PyPI](https://pypi.org/project/dulwich/1.2.20/) |
| dvc | 3.67.1 | Apache-2.0 | [PyPI](https://pypi.org/project/dvc/3.67.1/) |
| dvc-data | 3.18.3 | Apache-2.0 | [PyPI](https://pypi.org/project/dvc-data/3.18.3/) |
| dvc-http | 2.32.0 | Apache License 2.0 | [PyPI](https://pypi.org/project/dvc-http/2.32.0/) |
| dvc-objects | 5.2.0 | Apache-2.0 | [PyPI](https://pypi.org/project/dvc-objects/5.2.0/) |
| dvc-render | 1.0.2 | Apache-2.0 | [PyPI](https://pypi.org/project/dvc-render/1.0.2/) |
| dvc-studio-client | 0.23.0 | Apache-2.0 | [PyPI](https://pypi.org/project/dvc-studio-client/0.23.0/) |
| dvc-task | 0.40.2 | Apache-2.0 | [PyPI](https://pypi.org/project/dvc-task/0.40.2/) |
| entrypoints | 0.4.2 | MIT | [PyPI](https://pypi.org/project/entrypoints/0.4.2/) |
| executing | 2.3.0 | MIT License | [PyPI](https://pypi.org/project/executing/2.3.0/) |
| fastjsonschema | 2.22.2 | BSD License | [PyPI](https://pypi.org/project/fastjsonschema/2.22.2/) |
| filelock | 4.2.4 | MIT | [PyPI](https://pypi.org/project/filelock/4.2.4/) |
| flatten-dict | 0.5.0 | MIT License | [PyPI](https://pypi.org/project/flatten-dict/0.5.0/) |
| flufl-lock | 9.2.0 | Apache Software License | [PyPI](https://pypi.org/project/flufl-lock/9.2.0/) |
| fonttools | 4.67.0 | MIT | [PyPI](https://pypi.org/project/fonttools/4.67.0/) |
| frozenlist | 1.8.0 | Apache-2.0 | [PyPI](https://pypi.org/project/frozenlist/1.8.0/) |
| fsspec | 2026.9.0 | BSD-3-Clause | [PyPI](https://pypi.org/project/fsspec/2026.9.0/) |
| funcy | 2.1 | BSD License | [PyPI](https://pypi.org/project/funcy/2.1/) |
| gitdb | 4.0.12 | BSD License | [PyPI](https://pypi.org/project/gitdb/4.0.12/) |
| gitpython | 3.2.1 | BSD-3-Clause | [PyPI](https://pypi.org/project/gitpython/3.2.1/) |
| grandalf | 0.8 | GPL-2.0-only OR EPL-1.0 | [PyPI](https://pypi.org/project/grandalf/0.8/) |
| gto | 1.10.1 | Apache License 2.0 | [PyPI](https://pypi.org/project/gto/1.10.1/) |
| hydra-core | 1.3.8 | MIT License | [PyPI](https://pypi.org/project/hydra-core/1.3.8/) |
| identify | 2.6.20 | MIT | [PyPI](https://pypi.org/project/identify/2.6.20/) |
| idna | 3.20 | BSD-3-Clause | [PyPI](https://pypi.org/project/idna/3.20/) |
| iniconfig | 2.3.1 | MIT | [PyPI](https://pypi.org/project/iniconfig/2.3.1/) |
| ipykernel | 7.4.0 | BSD-3-Clause | [PyPI](https://pypi.org/project/ipykernel/7.4.0/) |
| ipython | 9.17.1 | BSD-3-Clause | [PyPI](https://pypi.org/project/ipython/9.17.1/) |
| ipython-pygments-lexers | 1.1.1 | BSD License | [PyPI](https://pypi.org/project/ipython-pygments-lexers/1.1.1/) |
| iterative-telemetry | 0.0.10 | Apache-2.0 | [PyPI](https://pypi.org/project/iterative-telemetry/0.0.10/) |
| jedi | 0.20.1 | MIT License | [PyPI](https://pypi.org/project/jedi/0.20.1/) |
| joblib | 1.6.0 | BSD-3-Clause | [PyPI](https://pypi.org/project/joblib/1.6.0/) |
| jsonschema | 4.26.0 | MIT | [PyPI](https://pypi.org/project/jsonschema/4.26.0/) |
| jsonschema-specifications | 2025.9.1 | MIT | [PyPI](https://pypi.org/project/jsonschema-specifications/2025.9.1/) |
| jupyter-client | 8.10.0 | BSD License | [PyPI](https://pypi.org/project/jupyter-client/8.10.0/) |
| jupyter-core | 5.9.1 | BSD-3-Clause | [PyPI](https://pypi.org/project/jupyter-core/5.9.1/) |
| kiwisolver | 1.5.1 | BSD License | [PyPI](https://pypi.org/project/kiwisolver/1.5.1/) |
| kombu | 5.6.2 | BSD-3-Clause | [PyPI](https://pypi.org/project/kombu/5.6.2/) |
| markdown-it-py | 4.2.0 | MIT License | [PyPI](https://pypi.org/project/markdown-it-py/4.2.0/) |
| matplotlib | 3.11.2 | Licencja Matplotlib (oparta na PSF) + licencje dołączonych zasobów | [PyPI](https://pypi.org/project/matplotlib/3.11.2/) |
| matplotlib-inline | 0.2.2 | BSD-3-Clause | [PyPI](https://pypi.org/project/matplotlib-inline/0.2.2/) |
| mdurl | 0.1.2 | MIT License | [PyPI](https://pypi.org/project/mdurl/0.1.2/) |
| multidict | 7.2.1 | Apache-2.0 | [PyPI](https://pypi.org/project/multidict/7.2.1/) |
| narwhals | 2.27.1 | MIT | [PyPI](https://pypi.org/project/narwhals/2.27.1/) |
| nbclient | 0.11.0 | BSD-3-Clause | [PyPI](https://pypi.org/project/nbclient/0.11.0/) |
| nbformat | 5.11.1 | BSD-3-Clause | [PyPI](https://pypi.org/project/nbformat/5.11.1/) |
| nest-asyncio2 | 1.7.4 | BSD License | [PyPI](https://pypi.org/project/nest-asyncio2/1.7.4/) |
| networkx | 3.7 | BSD-3-Clause | [PyPI](https://pypi.org/project/networkx/3.7/) |
| nodeenv | 1.11.0 | BSD License | [PyPI](https://pypi.org/project/nodeenv/1.11.0/) |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | [PyPI](https://pypi.org/project/numpy/2.5.4/) |
| omegaconf | 2.3.1 | BSD License | [PyPI](https://pypi.org/project/omegaconf/2.3.1/) |
| orjson | 3.13.0 | MPL-2.0 AND (Apache-2.0 OR MIT) | [PyPI](https://pypi.org/project/orjson/3.13.0/) |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | [PyPI](https://pypi.org/project/packaging/26.3/) |
| pandas | 2.3.3 | BSD-3-Clause | [PyPI](https://pypi.org/project/pandas/2.3.3/) |
| parso | 0.8.7 | MIT License | [PyPI](https://pypi.org/project/parso/0.8.7/) |
| pathspec | 1.1.1 | MPL-2.0 | [PyPI](https://pypi.org/project/pathspec/1.1.1/) |
| pexpect | 4.9.0 | ISC (PyPI; niezainstalowane na Windows) | [PyPI](https://pypi.org/project/pexpect/4.9.0/) |
| pillow | 13.0.0 | MIT-CMU | [PyPI](https://pypi.org/project/pillow/13.0.0/) |
| platformdirs | 4.13.5 | MIT | [PyPI](https://pypi.org/project/platformdirs/4.13.5/) |
| pluggy | 1.7.0 | MIT License | [PyPI](https://pypi.org/project/pluggy/1.7.0/) |
| pre-commit | 4.7.0 | MIT | [PyPI](https://pypi.org/project/pre-commit/4.7.0/) |
| prompt-toolkit | 3.0.53 | BSD License | [PyPI](https://pypi.org/project/prompt-toolkit/3.0.53/) |
| propcache | 0.5.4 | Apache-2.0 | [PyPI](https://pypi.org/project/propcache/0.5.4/) |
| psutil | 7.2.2 | BSD-3-Clause | [PyPI](https://pypi.org/project/psutil/7.2.2/) |
| ptyprocess | 0.7.0 | ISC (PyPI; niezainstalowane na Windows) | [PyPI](https://pypi.org/project/ptyprocess/0.7.0/) |
| pure-eval | 0.2.4 | MIT License | [PyPI](https://pypi.org/project/pure-eval/0.2.4/) |
| pycparser | 3.12 | BSD-3-Clause | [PyPI](https://pypi.org/project/pycparser/3.12/) |
| pydantic | 2.14.1 | MIT | [PyPI](https://pypi.org/project/pydantic/2.14.1/) |
| pydantic-core | 2.50.1 | MIT | [PyPI](https://pypi.org/project/pydantic-core/2.50.1/) |
| pydantic-settings | 2.16.1 | MIT | [PyPI](https://pypi.org/project/pydantic-settings/2.16.1/) |
| pydot | 4.0.1 | MIT | [PyPI](https://pypi.org/project/pydot/4.0.1/) |
| pygit2 | 1.20.1 | GPL-2.0-only z wyjątkiem linkowania (COPYING) | [PyPI](https://pypi.org/project/pygit2/1.20.1/) |
| pygments | 2.21.0 | BSD-2-Clause | [PyPI](https://pypi.org/project/pygments/2.21.0/) |
| pygtrie | 2.6.2 | Apache-2.0 | [PyPI](https://pypi.org/project/pygtrie/2.6.2/) |
| pyparsing | 3.3.3 | MIT | [PyPI](https://pypi.org/project/pyparsing/3.3.3/) |
| pytest | 9.1.1 | MIT | [PyPI](https://pypi.org/project/pytest/9.1.1/) |
| python-dateutil | 3.0.0 | Apache-2.0 OR BSD-3-Clause | [PyPI](https://pypi.org/project/python-dateutil/3.0.0/) |
| python-discovery | 1.6.4 | MIT License | [PyPI](https://pypi.org/project/python-discovery/1.6.4/) |
| python-dotenv | 1.2.4 | BSD-3-Clause | [PyPI](https://pypi.org/project/python-dotenv/1.2.4/) |
| pytz | 2026.5 | MIT License | [PyPI](https://pypi.org/project/pytz/2026.5/) |
| pywin32 | 312 | Python Software Foundation License | [PyPI](https://pypi.org/project/pywin32/312/) |
| pyyaml | 6.0.3 | MIT License | [PyPI](https://pypi.org/project/pyyaml/6.0.3/) |
| pyzmq | 27.2.0 | BSD-3-Clause; dołączone libzmq: MPL-2.0, libsodium: ISC | [PyPI](https://pypi.org/project/pyzmq/27.2.0/) |
| referencing | 0.37.0 | MIT | [PyPI](https://pypi.org/project/referencing/0.37.0/) |
| requests | 2.34.2 | Apache Software License | [PyPI](https://pypi.org/project/requests/2.34.2/) |
| rich | 15.0.0 | MIT License | [PyPI](https://pypi.org/project/rich/15.0.0/) |
| rpds-py | 2026.9.1 | MIT | [PyPI](https://pypi.org/project/rpds-py/2026.9.1/) |
| ruamel-yaml | 0.19.1 | MIT License | [PyPI](https://pypi.org/project/ruamel-yaml/0.19.1/) |
| ruff | 0.17.2 | MIT | [PyPI](https://pypi.org/project/ruff/0.17.2/) |
| scikit-learn | 1.9.1 | BSD-3-Clause | [PyPI](https://pypi.org/project/scikit-learn/1.9.1/) |
| scipy | 1.18.1 | BSD-3-Clause + licencje komponentów dystrybucji | [PyPI](https://pypi.org/project/scipy/1.18.1/) |
| scmrepo | 3.6.2 | Apache-2.0 | [PyPI](https://pypi.org/project/scmrepo/3.6.2/) |
| semver | 3.1.0 | BSD License | [PyPI](https://pypi.org/project/semver/3.1.0/) |
| setuptools | 84.2.1 | MIT | [PyPI](https://pypi.org/project/setuptools/84.2.1/) |
| shortuuid | 1.0.13 | BSD License | [PyPI](https://pypi.org/project/shortuuid/1.0.13/) |
| shtab | 1.13.0 | MPL-2.0 | [PyPI](https://pypi.org/project/shtab/1.13.0/) |
| six | 1.17.0 | MIT License | [PyPI](https://pypi.org/project/six/1.17.0/) |
| smmap | 5.0.3 | BSD License | [PyPI](https://pypi.org/project/smmap/5.0.3/) |
| sqltrie | 0.11.3 | Apache-2.0 | [PyPI](https://pypi.org/project/sqltrie/0.11.3/) |
| stack-data | 0.6.3 | MIT License | [PyPI](https://pypi.org/project/stack-data/0.6.3/) |
| tabulate | 0.10.0 | MIT | [PyPI](https://pypi.org/project/tabulate/0.10.0/) |
| threadpoolctl | 3.7.0 | BSD-3-Clause | [PyPI](https://pypi.org/project/threadpoolctl/3.7.0/) |
| tomlkit | 0.15.2 | MIT | [PyPI](https://pypi.org/project/tomlkit/0.15.2/) |
| tornado | 6.6 | Apache Software License | [PyPI](https://pypi.org/project/tornado/6.6/) |
| tqdm | 4.70.1 | MPL-2.0 AND MIT | [PyPI](https://pypi.org/project/tqdm/4.70.1/) |
| traitlets | 5.16.1 | BSD License | [PyPI](https://pypi.org/project/traitlets/5.16.1/) |
| typing-extensions | 4.16.0 | PSF-2.0 | [PyPI](https://pypi.org/project/typing-extensions/4.16.0/) |
| typing-inspection | 0.4.4 | MIT | [PyPI](https://pypi.org/project/typing-inspection/0.4.4/) |
| tzdata | 2026.5 | Apache-2.0 | [PyPI](https://pypi.org/project/tzdata/2026.5/) |
| tzlocal | 5.4.5 | MIT | [PyPI](https://pypi.org/project/tzlocal/5.4.5/) |
| urllib3 | 2.8.0 | MIT | [PyPI](https://pypi.org/project/urllib3/2.8.0/) |
| vine | 5.1.0 | BSD License | [PyPI](https://pypi.org/project/vine/5.1.0/) |
| virtualenv | 21.14.13 | MIT | [PyPI](https://pypi.org/project/virtualenv/21.14.13/) |
| voluptuous | 0.16.0 | BSD License | [PyPI](https://pypi.org/project/voluptuous/0.16.0/) |
| wcwidth | 0.9.4 | MIT License | [PyPI](https://pypi.org/project/wcwidth/0.9.4/) |
| yarl | 1.25.1 | Apache-2.0 | [PyPI](https://pypi.org/project/yarl/1.25.1/) |
| zc-lockfile | 4.0 | ZPL-2.1 | [PyPI](https://pypi.org/project/zc-lockfile/4.0/) |
