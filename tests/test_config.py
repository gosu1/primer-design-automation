import json
import os

from app import config


def test_missing_file_gives_defaults(tmp_path):
    loaded = config.load(str(tmp_path / "none.json"))
    assert loaded == config.DEFAULTS
    assert {k: loaded[k] for k in ("email", "api_key", "per_item", "combined")} == {
        "email": "", "api_key": "", "per_item": True, "combined": False,
    }
    assert (loaded["product_min"], loaded["product_max"], loaded["num_return"], loaded["organism"]) == (70, 1000, 10, "")
    assert (loaded["tm_min"], loaded["tm_opt"], loaded["tm_max"]) == (57.0, 60.0, 63.0)
    assert loaded["results_dir"].endswith("primer_results")
    assert loaded["terms"] == "ko"


def test_corrupt_file_gives_defaults(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("{not json")
    assert config.load(str(p))["per_item"] is True


def test_save_then_load_roundtrip_drops_unknown_keys(tmp_path):
    p = str(tmp_path / "c.json")
    config.save({"email": "a@b.c", "api_key": "K", "per_item": False, "combined": True, "junk": 1}, p)
    assert config.load(p) == {**config.DEFAULTS, "email": "a@b.c", "api_key": "K", "per_item": False, "combined": True}
    assert "junk" not in json.load(open(p))


def test_save_keeps_values_it_was_not_given(tmp_path):
    p = str(tmp_path / "c.json")
    config.save({"tm_opt": 61.5, "results_dir": "/r"}, p)
    config.save({"email": "a@b.c", "api_key": "", "per_item": True, "combined": False}, p)
    loaded = config.load(p)
    assert loaded["tm_opt"] == 61.5 and loaded["results_dir"] == "/r" and loaded["email"] == "a@b.c"


def test_default_path_is_repo_root_config_json():
    assert os.path.basename(config.CONFIG_PATH) == "config.json"
    assert os.path.isdir(os.path.join(os.path.dirname(config.CONFIG_PATH), "app"))
