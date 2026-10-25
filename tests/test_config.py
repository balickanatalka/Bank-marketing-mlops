import pytest
import yaml

from src.config import load_config


def test_seed_override(monkeypatch):
    monkeypatch.setenv("PROJEKT_SEED", "123")
    assert load_config()["seed"] == 123


@pytest.mark.parametrize("change", ["split", "feature", "path"])
def test_invalid_config(tmp_path, change):
    config = load_config()
    if change == "split":
        config["split"]["train"] = 0.9
    elif change == "feature":
        config["data"]["features"].append("duration")
    else:
        config["data"]["raw"] = "../outside.csv"
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)
