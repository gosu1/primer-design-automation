import json
import os

from app import config


def test_missing_file_gives_defaults(tmp_path):
    assert config.load(str(tmp_path / "none.json")) == {
        "email": "", "api_key": "", "per_item": True, "combined": False,
    }


def test_corrupt_file_gives_defaults(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("{not json")
    assert config.load(str(p))["per_item"] is True


def test_save_then_load_roundtrip_drops_unknown_keys(tmp_path):
    p = str(tmp_path / "c.json")
    config.save({"email": "a@b.c", "api_key": "K", "per_item": False, "combined": True, "junk": 1}, p)
    assert config.load(p) == {"email": "a@b.c", "api_key": "K", "per_item": False, "combined": True}
    assert "junk" not in json.load(open(p))


def test_default_path_is_repo_root_config_json():
    assert os.path.basename(config.CONFIG_PATH) == "config.json"
    assert os.path.isdir(os.path.join(os.path.dirname(config.CONFIG_PATH), "app"))
