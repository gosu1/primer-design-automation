"""config.json 읽기/쓰기. 이메일·API 키·저장 방식 체크박스 상태를 담는다."""
import json
import os
from typing import Optional

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
DEFAULTS = {"email": "", "api_key": "", "per_item": True, "combined": False}


def load(path: Optional[str] = None) -> dict:
    try:
        with open(path or CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return dict(DEFAULTS)
    return {key: data.get(key, default) for key, default in DEFAULTS.items()}


def save(config: dict, path: Optional[str] = None):
    data = {key: config.get(key, default) for key, default in DEFAULTS.items()}
    with open(path or CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
