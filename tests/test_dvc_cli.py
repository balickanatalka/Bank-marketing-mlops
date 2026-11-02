import sys

import pytest

from src.dvc_cli import main


def test_dvc_refuses_untracked_seed_override(monkeypatch):
    monkeypatch.setenv("PROJEKT_SEED", "123")
    monkeypatch.setattr(sys, "argv", ["dvc_cli", "train"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
