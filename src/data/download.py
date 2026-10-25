"""Download only the pinned CSV, never extract arbitrary archive paths."""

import hashlib
import io
import json
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from zipfile import ZipFile

URL = "https://archive.ics.uci.edu/static/public/222/bank+marketing.zip"
MAX_BYTES = 20_000_000


def verify_manifest(path: Path, manifest: dict) -> None:
    """Reject changed CSV bytes instead of silently accepting a new dataset."""
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != manifest["sha256"]:
        raise ValueError("SHA-256 CSV nie zgadza się z przypiętym manifestem.")
    if len(content) != manifest["size_bytes"]:
        raise ValueError("Rozmiar CSV nie zgadza się z manifestem.")


def extract_csv(content: bytes) -> bytes:
    """Read the exact nested UCI member with bounded uncompressed size."""
    with ZipFile(io.BytesIO(content)) as outer:
        info = outer.getinfo("bank-additional.zip")
        if info.file_size > MAX_BYTES:
            raise ValueError("Archiwum przekracza limit rozmiaru.")
        nested = outer.read(info)
    with ZipFile(io.BytesIO(nested)) as inner:
        info = inner.getinfo("bank-additional/bank-additional-full.csv")
        if info.file_size > MAX_BYTES:
            raise ValueError("CSV przekracza limit rozmiaru.")
        return inner.read(info)


def ensure_data(path: Path, manifest_path: Path) -> dict:
    """Download missing data; verify both existing and downloaded bytes."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if path.exists():
        verify_manifest(path, manifest)
        return manifest
    for attempt in range(3):
        try:
            with urlopen(URL, timeout=60) as response:
                content = response.read(MAX_BYTES + 1)
            if len(content) > MAX_BYTES:
                raise ValueError("Odpowiedź UCI przekracza limit rozmiaru.")
            csv = extract_csv(content)
            if hashlib.sha256(csv).hexdigest() != manifest["sha256"]:
                raise ValueError(
                    "Pobrany CSV ma inny SHA-256; nie aktualizuj manifestu automatycznie."
                )
            if len(csv) != manifest["size_bytes"]:
                raise ValueError("Niepoprawny rozmiar pobranego CSV.")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(csv)
            return manifest
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise RuntimeError("Nie udało się pobrać danych.")
