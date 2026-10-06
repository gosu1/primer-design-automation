"""config.json 읽기/쓰기. 이메일·API 키·저장 방식 체크박스 상태와 프라이머 설계 조건, 용어 설정을 담는다."""
import json
import os
from typing import Optional

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
DEFAULTS = {
    "email": "", "api_key": "", "per_item": True, "combined": False,
    "product_min": 70, "product_max": 1000, "tm_min": 57.0, "tm_opt": 60.0, "tm_max": 63.0,
    "num_return": 10, "organism": "",
    "results_dir": os.path.join(os.path.expanduser("~"), "Downloads", "primer_results"),
    "terms": "ko",   # 2단계 화면과 엑셀의 전문 용어: ko(한국어) / en(Primer-BLAST 영어)
}


def load(path: Optional[str] = None) -> dict:
    try:
        with open(path or CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return dict(DEFAULTS)
    return {key: data.get(key, default) for key, default in DEFAULTS.items()}


def save(config: dict, path: Optional[str] = None):
    """받은 항목만 기존 값 위에 덮어쓴다. 1단계와 2단계 화면이 서로의 값을 지우지 않게 하기 위해서다."""
    data = load(path)
    data.update({key: value for key, value in config.items() if key in DEFAULTS})
    with open(path or CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
