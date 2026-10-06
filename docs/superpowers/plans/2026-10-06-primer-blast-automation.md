# Primer-BLAST 자동 제출 도구 (2단계) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 서열 번호 목록을 NCBI Primer-BLAST 웹사이트에 하나씩 자동 제출하고, 비슷한 서열 확인 화면을 자동 처리한 뒤, 프라이머 쌍 결과를 엑셀 파일 하나로 모으는 화면을 1단계 도구에 붙인다.

**Architecture:** `app/primerblast.py`가 사이트 통신과 페이지 해석을 맡고(화면·파일 모름), `app/designer.py`가 백그라운드 스레드로 서열을 하나씩 처리하며 엑셀을 저장한다(1단계 `Downloader`와 같은 구조). `app/main.py`에 요청 경로 4개를, `app/static/primer.html`에 새 화면을 더한다. 페이지 해석은 실제 사이트 페이지 7개(`tests/fixtures/primerblast/`)로 시험하고, 자동 시험은 사이트에 접속하지 않는다.

**Tech Stack:** Python 3.9+, Flask ≥ 2.0, requests, openpyxl, pytest (개발용). 화면은 바닐라 HTML/JavaScript.

설계 문서: `docs/superpowers/specs/2026-10-06-primer-blast-automation-design.md`

## Global Constraints

- 작업 브랜치: `feature/primer-blast`. 모든 Task는 이 브랜치에서 커밋한다.
- Python 3.9 이상에서 동작해야 한다 (`match` 문, `X | Y` 타입 표기 금지. `typing.Optional`, `List` 사용).
- 실행 의존성은 `flask`, `requests`, `openpyxl` 세 개뿐이다. 다른 패키지를 추가하지 않는다.
- Primer-BLAST 웹사이트(`www.ncbi.nlm.nih.gov/tools/primer-blast/`) 요청은 `app/primerblast.py`에서만 보낸다. 사용자가 NCBI 스크립팅 금지 방침(KA-05510)을 안내받고도 택한 방식이다.
- 자동 테스트는 NCBI에 실제 접속하지 않는다. 시험 중에 사이트에 요청을 보내지 않는다.
- 속도 상수: `POLL_INTERVAL = 15`초, `BETWEEN_JOBS = 10`초, `MAX_ROWS = 50`, `MAX_CONSECUTIVE_FAILURES = 3`, `JOB_TIMEOUT = 600`초, `RETRY_WAITS = (2, 4, 8)`.
- 요청 머리글 `User-Agent`는 `primer-design-automation (python-requests/<버전>)`.
- 엑셀 파일 이름 `primers_YYYYMMDD_HHMM.xlsx`, 잠겨 있으면 `primers_YYYYMMDD_HHMM_2.xlsx`. 시트 이름 `결과`.
- 해석 실패 페이지 원문은 `<서열번호>_page.html`로 엑셀과 같은 폴더에 저장한다.
- 화면과 오류 메시지는 한국어. 코드 주석과 커밋 메시지도 한국어(기존 커밋 관례).
- 파일 쓰기는 `encoding="utf-8", newline="\n"` 으로 통일한다.
- 테스트 실행 명령: `.venv/bin/python -m pytest -q` (저장소 루트에서). 처음 한 번 `.venv/bin/pip install -r requirements-dev.txt`로 `openpyxl`을 설치한다(Task 4 이후).
- 각 Task 끝에 커밋한다. 커밋 메시지 끝에 빈 줄과 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>` 줄을 붙인다.

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `tests/fixtures/primerblast/*.html` | 실제 사이트 페이지 7개 (식별 값 제거, 이 계획과 함께 이미 커밋됨) |
| `app/config.py` | 설정 기본값에 2단계 항목 추가, `save()`가 기존 값 위에 덮어씀 |
| `app/primerblast.py` | 자료형, 페이지 해석 순수 함수, `PrimerBlastClient`(제출·확인 화면·대기·재시도) |
| `app/designer.py` | 폴더에서 서열 번호 찾기, 엑셀 줄 만들기·저장, 화면 입력 검사, `Designer`(스레드·상태·중단) |
| `app/main.py` | 요청 경로 4개 추가 |
| `app/static/primer.html` | 2단계 화면 |
| `app/static/index.html` | 두 화면을 오가는 링크 |
| `requirements.txt` | `openpyxl` 추가 |
| `README.md` | 2단계 사용법, 주의 사항, 문제 해결 |
| `tests/test_config.py`, `tests/test_primerblast.py`, `tests/test_designer.py`, `tests/test_main.py` | 시험 |

### 시험용 페이지 (`tests/fixtures/primerblast/`)

| 파일 | 내용 |
|---|---|
| `form.html` | 입력 화면. 기본값이 `defVal` 속성에 있다 |
| `waiting.html` | 제출 직후 대기 화면. `id="statInfo"`, `job_key=JOBKEY` |
| `review.html` | 비슷한 서열 확인 화면(`id="userGuidedForm"`). NM_000546, TP53 판본 5줄 |
| `results.html` | 결과 10쌍. 잘못 붙는 대상(같은/다른 유전자) 수가 쌍마다 다름 |
| `results_own_primers.html` | 박사님 프라이머 검사 결과 1쌍 |
| `no_primers.html` | `<p class="info">No primers were found...` |
| `error.html` | `<p class="error">Exception error: Sequence ID not found: 'ref|NM_99999999|'` |

---

### Task 1: 설정 저장을 "덮어쓰기"로 바꾸고 2단계 항목 추가

지금의 `config.save()`는 받은 값에 없는 항목을 기본값으로 되돌린다. 그대로 두면 1단계 설정 저장(이메일·API 키·체크박스만 보냄)이 2단계 조건을 지운다.

**Files:**
- Modify: `app/config.py` (전체 교체)
- Test: `tests/test_config.py` (전체 교체)

**Interfaces:**
- Produces: `config.DEFAULTS`에 `product_min`(70), `product_max`(1000), `tm_min`(57.0), `tm_opt`(60.0), `tm_max`(63.0), `num_return`(10), `organism`(""), `results_dir`(`~/Downloads/primer_results` 절대 경로). `config.save(dict, path=None)`는 `DEFAULTS`에 있는 키만, 기존 파일 값 위에 덮어쓴다. 키 이름은 Task 2의 `Common` 필드 이름과 같다(Task 6이 `dataclasses.asdict(common)`을 그대로 저장한다).

- [ ] **Step 1: 시험을 먼저 바꾼다**

`tests/test_config.py` 전체를 다음으로 바꾼다.

```python
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
```

- [ ] **Step 2: 실패를 확인한다**

Run: `.venv/bin/python -m pytest -q tests/test_config.py`
Expected: 2 failed, 3 passed. `test_missing_file_gives_defaults`(`KeyError: 'product_min'`)와 `test_save_keeps_values_it_was_not_given`(`KeyError: 'tm_opt'`)이 실패한다.

- [ ] **Step 3: 구현한다**

`app/config.py` 전체를 다음으로 바꾼다.

```python
"""config.json 읽기/쓰기. 이메일·API 키·저장 방식 체크박스 상태와 프라이머 설계 조건을 담는다."""
import json
import os
from typing import Optional

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
DEFAULTS = {
    "email": "", "api_key": "", "per_item": True, "combined": False,
    "product_min": 70, "product_max": 1000, "tm_min": 57.0, "tm_opt": 60.0, "tm_max": 63.0,
    "num_return": 10, "organism": "",
    "results_dir": os.path.join(os.path.expanduser("~"), "Downloads", "primer_results"),
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
```

- [ ] **Step 4: 통과를 확인한다**

Run: `.venv/bin/python -m pytest -q`
Expected: 51 passed, 1 skipped (`tests/test_main.py::test_config_roundtrip_updates_client` 포함).

- [ ] **Step 5: 커밋한다**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: 설정에 프라이머 설계 조건 추가, 저장은 기존 값 위에 덮어씀

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Primer-BLAST 페이지 해석

사이트 페이지 원문을 받아 값을 꺼내는 순수 함수들이다. 통신은 Task 3에서 붙인다.

**Files:**
- Create: `app/primerblast.py`
- Test: `tests/test_primerblast.py` (새 파일)
- 이미 있음: `tests/fixtures/primerblast/*.html`

**Interfaces:**
- Produces (Task 3, 4, 5가 씀):
  - 자료형 `Common(product_min=70, product_max=1000, tm_min=57.0, tm_opt=60.0, tm_max=63.0, num_return=10, organism="")`, `Row(accession, start=None, end=None, left="", right="")`, `Primer(seq, start, stop, length, tm, gc)`, `Pair(left, right, product_length, unintended_same_gene, unintended_other_gene)`, `Hit(accession, title, seqloc)`, `Outcome(title="", pairs=[], accepted=[], url="", note="", failed=False, raw_page="")`
  - `class PrimerBlastError(Exception)`
  - 상수 `BASE_URL`, `SUBMIT_URL`, `USER_AGENT`, `POLL_INTERVAL`, `JOB_TIMEOUT`, `RETRY_WAITS`, `TIMEOUT`, `NO_PRIMERS`, `UNINTENDED`, `UNREADABLE = "결과 페이지를 읽지 못함"`
  - `parse_form_defaults(page) -> List[Tuple[str, str]]`, `page_kind(page) -> "review"|"results"|"error"|"waiting"|"unknown"`, `job_key(page) -> str`, `error_message(page) -> str`, `template_title(page) -> str`, `gene_symbol(title) -> str`, `parse_review(page) -> (hidden_fields, template_title, hits)`, `pick_same_gene(title, hits) -> List[Hit]`, `parse_results(page) -> Outcome`, `build_fields(defaults, row, common) -> List[Tuple[str, str]]`

- [ ] **Step 1: 시험을 쓴다**

`tests/test_primerblast.py`를 다음 내용으로 만든다.

```python
import os

import pytest

from app.primerblast import (
    Common, Hit, PrimerBlastError, Row, build_fields, error_message, gene_symbol, job_key, page_kind,
    parse_form_defaults, parse_results, parse_review, pick_same_gene,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "primerblast")


def page(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read()


# ---- 페이지 해석

def test_form_defaults_use_defval_and_skip_files():
    fields = parse_form_defaults(page("form.html"))
    values = dict(fields)
    assert len(values) == len(fields)  # 같은 이름은 한 번만
    assert values["PRIMER_PRODUCT_MIN"] == "70" and values["PRIMER_PRODUCT_MAX"] == "1000"
    assert values["PRIMER_MIN_TM"] == "57.0" and values["PRIMER_OPT_TM"] == "60.0" and values["PRIMER_MAX_TM"] == "63.0"
    assert values["PRIMER_NUM_RETURN"] == "10"
    assert values["SEARCH_SPECIFIC_PRIMER"] == "on"
    assert values["PRIMER_SPECIFICITY_DATABASE"] == "refseq_mrna"
    assert values["ORGANISM"] == "Homo sapien (taxid:9606)"
    assert values["CMD"] == "request"
    assert values["INPUT_SEQUENCE"] == ""
    assert "SEQFILE" not in values and "EXCLUDE_XM" not in values


def test_form_defaults_reject_page_without_form():
    with pytest.raises(PrimerBlastError, match="입력 화면"):
        parse_form_defaults("<html><body>점검 중</body></html>")


@pytest.mark.parametrize("name, kind", [
    ("form.html", "unknown"),
    ("waiting.html", "waiting"),
    ("review.html", "review"),
    ("results.html", "results"),
    ("results_own_primers.html", "results"),
    ("no_primers.html", "results"),
    ("error.html", "error"),
])
def test_page_kind(name, kind):
    assert page_kind(page(name)) == kind


def test_job_key_from_waiting_page():
    assert job_key(page("waiting.html")) == "JOBKEY"
    assert job_key(page("error.html")) == ""


def test_error_message():
    assert error_message(page("error.html")) == "Exception error: Sequence ID not found: 'ref|NM_99999999|'"


@pytest.mark.parametrize("title, gene", [
    ("Homo sapiens tumor protein p53 (TP53), transcript variant 1, mRNA", "TP53"),
    ("PREDICTED: Homo sapiens KIAA0753 (KIAA0753), transcript variant X2, mRNA", "KIAA0753"),
    ("Mus musculus transformation related protein 53 (Trp53), transcript variant 1, mRNA", "Trp53"),
    ("my sequence", ""),
])
def test_gene_symbol(title, gene):
    assert gene_symbol(title) == gene


def test_parse_review():
    hidden, title, hits = parse_review(page("review.html"))
    assert ("INPUT_SEQUENCE", "NM_000546") in hidden
    assert ("TRY_USER_GUIDE", "yes") in hidden
    assert all(name != "USER_SEQLOC" for name, _ in hidden)
    assert title == "Homo sapiens tumor protein p53 (TP53), transcript variant 1, mRNA"
    assert len(hits) == 5
    assert hits[0] == Hit("NM_001276761.3", "Homo sapiens tumor protein p53 (TP53), transcript variant 2, mRNA",
                          "ref|NM_001276761.3|?0?2508")


def test_pick_same_gene_keeps_only_same_gene():
    hits = [Hit("A", "x (TP53), variant 2", "a"), Hit("B", "y (MDM2), variant 1", "b"), Hit("C", "no gene", "c")]
    assert pick_same_gene("x (TP53), variant 1", hits) == [hits[0]]


def test_pick_same_gene_without_template_gene_picks_nothing():
    assert pick_same_gene("my sequence", [Hit("A", "x (TP53)", "a")]) == []


def test_parse_results_reads_pairs_and_unintended_counts():
    outcome = parse_results(page("results.html"))
    assert outcome.title == "Homo sapiens tumor protein p53 (TP53), transcript variant 1, mRNA"
    assert outcome.note == ""
    assert len(outcome.pairs) == 10
    first = outcome.pairs[0]
    assert (first.left.seq, first.left.start, first.left.stop, first.left.length) == ("ACCTATGGAAACTACTTCCTGAAA", 204, 227, 24)
    assert (first.left.tm, first.left.gc) == (57.30, 37.50)
    assert (first.right.seq, first.right.start, first.right.stop, first.right.length) == ("ACCATCGCTATCTGAGCAGC", 703, 684, 20)
    assert (first.right.tm, first.right.gc) == (59.97, 55.00)
    assert first.product_length == 500
    assert [(p.unintended_same_gene, p.unintended_other_gene) for p in outcome.pairs] == [
        (4, 0), (4, 4), (4, 0), (4, 0), (4, 4), (4, 1), (4, 0), (4, 0), (4, 3), (4, 0)]


def test_parse_results_own_primers():
    outcome = parse_results(page("results_own_primers.html"))
    assert len(outcome.pairs) == 1
    assert outcome.pairs[0].left.seq == "ACCTATGGAAACTACTTCCTGAAA"
    assert outcome.pairs[0].right.seq == "ACCATCGCTATCTGAGCAGC"


def test_parse_results_no_primers_keeps_site_explanation():
    outcome = parse_results(page("no_primers.html"))
    assert outcome.pairs == []
    assert outcome.note.startswith("후보 없음: No primers were found")
    assert "low tm 341" in outcome.note


def test_build_fields_overrides_only_given_values():
    defaults = [("INPUT_SEQUENCE", ""), ("PRIMER5_START", ""), ("PRIMER3_END", ""), ("PRIMER_LEFT_INPUT", ""),
                ("PRIMER_RIGHT_INPUT", ""), ("PRIMER_PRODUCT_MIN", "70"), ("PRIMER_PRODUCT_MAX", "1000"),
                ("PRIMER_MIN_TM", "57.0"), ("PRIMER_OPT_TM", "60.0"), ("PRIMER_MAX_TM", "63.0"),
                ("PRIMER_NUM_RETURN", "10"), ("ORGANISM", "Homo sapien (taxid:9606)"), ("CMD", "request")]
    row = Row("NM_000546", start=200, left="ACGT")
    common = Common(product_min=100, tm_opt=61.5, num_return=5)
    assert dict(build_fields(defaults, row, common)) == {
        "INPUT_SEQUENCE": "NM_000546", "PRIMER5_START": "200", "PRIMER3_END": "", "PRIMER_LEFT_INPUT": "ACGT",
        "PRIMER_RIGHT_INPUT": "", "PRIMER_PRODUCT_MIN": "100", "PRIMER_PRODUCT_MAX": "1000",
        "PRIMER_MIN_TM": "57.0", "PRIMER_OPT_TM": "61.5", "PRIMER_MAX_TM": "63.0",
        "PRIMER_NUM_RETURN": "5", "ORGANISM": "Homo sapien (taxid:9606)", "CMD": "request",
    }
    assert dict(build_fields(defaults, row, Common(organism="Mus musculus")))["ORGANISM"] == "Mus musculus"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `.venv/bin/python -m pytest -q tests/test_primerblast.py`
Expected: `ModuleNotFoundError: No module named 'app.primerblast'`

- [ ] **Step 3: 구현한다**

`app/primerblast.py`를 다음 내용으로 만든다. (`time`, `Callable`은 Task 3에서 쓴다.)

```python
"""NCBI Primer-BLAST 웹사이트 자동 제출. 화면, 파일, 엑셀은 모른다.

NCBI는 웹페이지에 대한 스크립트 접근을 허용하지 않는다(KA-05510). 사용자가 위험을 알고 택한 방식이므로
요청 빈도를 사람이 브라우저로 쓰는 수준으로 묶어 둔다(설계 문서 7절).
"""
import html
import re
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Callable, List, Optional, Tuple

import requests

BASE_URL = "https://www.ncbi.nlm.nih.gov/tools/primer-blast/"
SUBMIT_URL = BASE_URL + "primertool.cgi"
USER_AGENT = "primer-design-automation (python-requests/%s)" % requests.__version__
POLL_INTERVAL = 15       # 진행 상황 확인 간격(초)
JOB_TIMEOUT = 600        # 서열 하나의 최대 대기(초)
RETRY_WAITS = (2, 4, 8)  # 통신 오류 시 재시도 전 대기(초)
TIMEOUT = 120

Fields = List[Tuple[str, str]]


class PrimerBlastError(Exception):
    """재시도해도 안 된 통신 오류, 시간 초과, 확인 화면 반복, 중단. 사람이 읽을 메시지를 담는다."""


@dataclass
class Common:
    product_min: int = 70
    product_max: int = 1000
    tm_min: float = 57.0
    tm_opt: float = 60.0
    tm_max: float = 63.0
    num_return: int = 10
    organism: str = ""   # 비면 사이트 기본값(사람)


@dataclass
class Row:
    accession: str
    start: Optional[int] = None
    end: Optional[int] = None
    left: str = ""
    right: str = ""


@dataclass
class Primer:
    seq: str
    start: int
    stop: int
    length: int
    tm: float
    gc: float


@dataclass
class Pair:
    left: Primer
    right: Primer
    product_length: int
    unintended_same_gene: int
    unintended_other_gene: int


@dataclass
class Hit:
    accession: str
    title: str
    seqloc: str   # 확인 화면 체크박스 값(USER_SEQLOC)


@dataclass
class Outcome:
    title: str = ""
    pairs: List[Pair] = field(default_factory=list)
    accepted: List[str] = field(default_factory=list)
    url: str = ""
    note: str = ""
    failed: bool = False   # 사이트 오류 메시지 또는 해석 실패
    raw_page: str = ""     # 해석 실패 시에만 채움


# ---- 페이지 해석 (순수 함수)

def _text(fragment: str) -> str:
    """태그를 지우고 공백을 하나로 줄인 글자."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


class _FormReader(HTMLParser):
    """id가 form_id인 form 안의 항목을 브라우저가 보낼 값으로 모은다."""

    def __init__(self, form_id: str):
        super().__init__()
        self.form_id = form_id
        self.inside = False
        self.fields: Fields = []
        self._select: Optional[str] = None
        self._first_option: Optional[str] = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.inside = a.get("id") == self.form_id
        if not self.inside:
            return
        name = a.get("name")
        if tag == "input" and name:
            kind = (a.get("type") or "text").lower()
            if kind == "file":
                return
            if kind == "checkbox":
                if "checked" in a:
                    self.fields.append((name, a.get("value") or "on"))
                return
            # 사이트는 기본값을 defVal 속성에 두고 자바스크립트로 채운다
            self.fields.append((name, a.get("value") or a.get("defval") or ""))
        elif tag == "textarea" and name:
            self.fields.append((name, ""))
        elif tag == "select" and name:
            self._select, self._first_option = name, None
        elif tag == "option" and self._select:
            if self._first_option is None:
                self._first_option = a.get("value") or ""
            if "selected" in a:
                self.fields.append((self._select, a.get("value") or ""))
                self._select = None

    def handle_endtag(self, tag):
        if tag == "select" and self._select:
            self.fields.append((self._select, self._first_option or ""))
            self._select = None
        elif tag == "form":
            self.inside = False


def parse_form_defaults(page: str) -> Fields:
    """입력 화면에서 사이트 기본값을 읽는다. 같은 이름이 두 번 나오면 첫 값만 쓴다."""
    reader = _FormReader("searchForm")
    reader.feed(page)
    seen, fields = set(), []
    for name, value in reader.fields:
        if name not in seen:
            seen.add(name)
            fields.append((name, value))
    if not fields:
        raise PrimerBlastError("Primer-BLAST 입력 화면을 읽지 못했습니다")
    return fields


NO_PRIMERS = "No primers were found"


def page_kind(page: str) -> str:
    if 'id="userGuidedForm"' in page:
        return "review"
    if 'class="prPairInfo"' in page or NO_PRIMERS in page:
        return "results"
    if '<p class="error">' in page:
        return "error"
    if 'id="statInfo"' in page:
        return "waiting"
    return "unknown"


def job_key(page: str) -> str:
    m = re.search(r"job_key=([\w\-]+)", page)
    return m.group(1) if m else ""


def error_message(page: str) -> str:
    m = re.search(r'<p class="error">(.*?)</p>', page, re.S)
    return _text(m.group(1)).rstrip(" .") if m else ""


def template_title(page: str) -> str:
    """'Input PCR template' 칸의 서열 이름(번호 링크 뒤 글자)."""
    m = re.search(r"<dt>Input PCR template</dt>\s*<dd>(.*?)</dd>", page, re.S)
    if not m:
        return ""
    return _text(re.sub(r"<a [^>]*>.*?</a>", "", m.group(1), flags=re.S))


def gene_symbol(title: str) -> str:
    """제목에서 처음 나오는 괄호 안 값. '... p53 (TP53), transcript variant 1' → 'TP53'."""
    m = re.search(r"\(([^()\s,]+)\)", title)
    return m.group(1) if m else ""


def parse_review(page: str) -> Tuple[Fields, str, List[Hit]]:
    """확인 화면의 숨은 항목(중복 포함), 입력 서열 이름, 비슷한 서열 목록."""
    form = page[page.index('id="userGuidedForm"'):]
    form = form[:form.index("</form>")]
    hidden = re.findall(r'<input type="hidden"\s+name="([^"]+)" value="([^"]*)"', form)
    hits = [
        Hit(accession=acc, title=_text(title), seqloc=html.unescape(seqloc))
        for seqloc, acc, title in re.findall(
            r'name="USER_SEQLOC" value="([^"]*)".*?<a [^>]*>([^<]*)</a></td><td>(.*?)</td>', form, re.S)
    ]
    return [(n, html.unescape(v)) for n, v in hidden], template_title(page), hits


def pick_same_gene(title: str, hits: List[Hit]) -> List[Hit]:
    gene = gene_symbol(title)
    if not gene:
        return []
    return [h for h in hits if gene_symbol(h.title) == gene]


def _primer(values: dict, side: str) -> Primer:
    return Primer(
        seq=values[side + "_PRIMER_SEQ"],
        start=int(values[side + "_PRIMER_START"]),
        stop=int(values[side + "_PRIMER_STOP"]),
        length=int(values[side + "_PRIMER_LEN"]),
        tm=float(values[side + "_PRIMER_TM"]),
        gc=float(values[side + "_PRIMER_GC"]),
    )


UNINTENDED = "Products on potentially unintended templates"
UNREADABLE = "결과 페이지를 읽지 못함"


def parse_results(page: str) -> Outcome:
    title = template_title(page)
    gene = gene_symbol(title)
    pairs = []
    for block in page.split('<div class="prPairInfo">')[1:]:
        values = dict(
            (name, html.unescape(value))
            for value, name in re.findall(r'<input type="hidden" value="([^"]*)"\s+name="([A-Z_]+?)_\d+"', block)
        )
        same = other = 0
        if UNINTENDED in block:
            section = block[block.index(UNINTENDED):]
            for hit_title in re.findall(r'name="RESUB_SEQLOC".*?</a>([^\n<]*)', section, re.S):
                if gene and gene_symbol(hit_title) == gene:
                    same += 1
                else:
                    other += 1
        pairs.append(Pair(
            left=_primer(values, "FW"),
            right=_primer(values, "RV"),
            product_length=int(values["PRODUCT_LENGTH"]),
            unintended_same_gene=same,
            unintended_other_gene=other,
        ))
    note = ""
    if not pairs:
        m = re.search(r'<p class="info">(.*?)</p>', page, re.S)
        note = "후보 없음" + (": " + _text(m.group(1)) if m else "")
    return Outcome(title=title, pairs=pairs, note=note)


def build_fields(defaults: Fields, row: Row, common: Common) -> Fields:
    """사이트 기본값 위에 이 줄의 값과 공통 조건을 덮어쓴다. 빈 값은 빈 채로 보낸다."""
    override = {
        "INPUT_SEQUENCE": row.accession,
        "PRIMER5_START": "" if row.start is None else str(row.start),
        "PRIMER3_END": "" if row.end is None else str(row.end),
        "PRIMER_LEFT_INPUT": row.left,
        "PRIMER_RIGHT_INPUT": row.right,
        "PRIMER_PRODUCT_MIN": str(common.product_min),
        "PRIMER_PRODUCT_MAX": str(common.product_max),
        "PRIMER_MIN_TM": str(common.tm_min),
        "PRIMER_OPT_TM": str(common.tm_opt),
        "PRIMER_MAX_TM": str(common.tm_max),
        "PRIMER_NUM_RETURN": str(common.num_return),
    }
    if common.organism:
        override["ORGANISM"] = common.organism
    return [(name, override.get(name, value)) for name, value in defaults]
```

- [ ] **Step 4: 통과를 확인한다**

Run: `.venv/bin/python -m pytest -q tests/test_primerblast.py`
Expected: 22 passed

- [ ] **Step 5: 커밋한다**

```bash
git add app/primerblast.py tests/test_primerblast.py
git commit -m "feat: Primer-BLAST 페이지 해석 함수 추가

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Primer-BLAST 제출 흐름

**Files:**
- Modify: `app/primerblast.py` (파일 끝에 클래스 추가)
- Test: `tests/test_primerblast.py` (import 교체, 파일 끝에 시험 추가)

**Interfaces:**
- Consumes: Task 2의 자료형과 해석 함수 전부.
- Produces: `PrimerBlastClient()` — 속성 `session`(requests.Session, 머리글에 `USER_AGENT`), `_sleep`, `_clock`(시험에서 바꿔 끼움). 메서드 `design(row: Row, common: Common, should_stop: Callable[[], bool]) -> Outcome`. 정상 응답(결과·후보 없음·사이트 오류·해석 실패)은 `Outcome`으로, 통신 실패·시간 초과·확인 화면 반복·중단은 `PrimerBlastError`로 끝난다. 입력 화면은 클라이언트 하나당 한 번만 GET한다.

동작 규칙:
- 제출은 multipart POST(`files=[(이름, (None, 값)), ...]`), 확인 화면 재제출은 일반 POST(`data=[...]`), 진행 확인은 `GET SUBMIT_URL params={"job_key": key}`.
- 확인 화면에서 고른 서열 번호는 중복을 없앤다. 결과 주소(`url`)는 결과를 GET으로 받았을 때만 남긴다.
- 기다리는 동안 1초 단위로 `should_stop()`과 마감 시각을 확인한다.
- 통신 오류·429·5xx는 2, 4, 8초 쉬고 재시도, 그 밖의 4xx는 바로 `PrimerBlastError`.

- [ ] **Step 1: 시험을 쓴다**

`tests/test_primerblast.py` 맨 위의 import 부분(첫 줄부터 `FIXTURES = ...` 앞까지)을 다음으로 바꾼다.

```python
import os

import pytest
import requests

from app.primerblast import (
    BASE_URL, JOB_TIMEOUT, POLL_INTERVAL, SUBMIT_URL, Common, Hit, PrimerBlastClient, PrimerBlastError, Row,
    build_fields, error_message, gene_symbol, job_key, page_kind, parse_form_defaults, parse_results,
    parse_review, pick_same_gene,
)
```

그리고 파일 끝에 다음을 붙인다.

```python
# ---- 제출 흐름 (가짜 사이트)

class FakeResponse:
    def __init__(self, text="", status_code=200):
        self.text = text
        self.status_code = status_code


class FakeSession:
    """준비된 응답을 순서대로 돌려주고 받은 요청을 기록한다. 문자열은 200 응답, 예외 객체는 던진다."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def request(self, method, url, timeout=None, **kwargs):
        self.calls.append((method, url, kwargs))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item) if isinstance(item, str) else item


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(responses):
    client = PrimerBlastClient()
    client.session = FakeSession(responses)
    client.clock = FakeClock()
    client._sleep = client.clock.sleep
    client._clock = lambda: client.clock.now
    return client


def never():
    return False


def test_user_agent_names_the_tool():
    assert "primer-design-automation" in PrimerBlastClient().session.headers["User-Agent"]


def test_design_full_flow_with_review():
    client = make_client([page("form.html"), page("waiting.html"), page("review.html"),
                          page("waiting.html"), page("results.html")])
    outcome = client.design(Row("NM_000546"), Common(), never)
    assert len(outcome.pairs) == 10 and not outcome.failed
    assert outcome.accepted == ["NM_001276761.3", "NM_001407262.1", "NM_001407266.1", "NM_001407265.1"]
    assert outcome.url == SUBMIT_URL + "?job_key=JOBKEY"
    calls = client.session.calls
    assert [(m, u) for m, u, _ in calls] == [("GET", BASE_URL), ("POST", SUBMIT_URL), ("GET", SUBMIT_URL),
                                            ("POST", SUBMIT_URL), ("GET", SUBMIT_URL)]
    submitted = dict((name, value) for name, (_, value) in calls[1][2]["files"])
    assert submitted["INPUT_SEQUENCE"] == "NM_000546" and submitted["PRIMER_PRODUCT_MIN"] == "70"
    assert calls[2][2]["params"] == {"job_key": "JOBKEY"}
    review_post = calls[3][2]["data"]
    assert [v for n, v in review_post if n == "USER_SEQLOC"] == [
        "ref|NM_001276761.3|?0?2508", "ref|NM_001407262.1|?216?2614", "ref|NM_001407262.1|?0?113",
        "ref|NM_001407266.1|?126?2524", "ref|NM_001407265.1|?124?2521"]
    assert ("INPUT_SEQUENCE", "NM_000546") in review_post
    assert client.clock.sleeps == [1.0] * (2 * POLL_INTERVAL)


def test_form_is_read_once_per_client():
    client = make_client([page("form.html"), page("error.html"), page("error.html")])
    client.design(Row("NM_99999999"), Common(), never)
    client.design(Row("NM_99999998"), Common(), never)
    assert [m for m, _, _ in client.session.calls] == ["GET", "POST", "POST"]


def test_site_error_becomes_failed_outcome():
    client = make_client([page("form.html"), page("error.html")])
    outcome = client.design(Row("NM_99999999"), Common(), never)
    assert outcome.failed and outcome.pairs == []
    assert outcome.note == "Exception error: Sequence ID not found: 'ref|NM_99999999|'"


def test_no_primers_is_not_a_failure():
    client = make_client([page("form.html"), page("waiting.html"), page("no_primers.html")])
    outcome = client.design(Row("NM_000546"), Common(), never)
    assert not outcome.failed and outcome.pairs == []
    assert outcome.note.startswith("후보 없음")
    assert outcome.url == SUBMIT_URL + "?job_key=JOBKEY"


def test_results_right_after_review_have_no_url():
    client = make_client([page("form.html"), page("review.html"), page("no_primers.html")])
    outcome = client.design(Row("NM_000546"), Common(), never)
    assert outcome.url == "" and len(outcome.accepted) == 4


def test_unknown_page_keeps_raw_page():
    client = make_client([page("form.html"), "<html>점검 중</html>"])
    outcome = client.design(Row("NM_000546"), Common(), never)
    assert outcome.failed and outcome.note == "결과 페이지를 읽지 못함"
    assert outcome.raw_page == "<html>점검 중</html>"


def test_unparseable_results_keep_raw_page():
    broken = '<div class="prPairInfo"><input type="hidden" value="x" name="FW_PRIMER_SEQ_0"/>'
    client = make_client([page("form.html"), broken])
    outcome = client.design(Row("NM_000546"), Common(), never)
    assert outcome.failed and outcome.raw_page == broken


def test_second_review_raises():
    client = make_client([page("form.html"), page("review.html"), page("review.html")])
    with pytest.raises(PrimerBlastError, match="확인 화면이 반복됨"):
        client.design(Row("NM_000546"), Common(), never)


def test_retries_network_errors_then_succeeds():
    client = make_client([page("form.html"), requests.ConnectionError("x"), FakeResponse("", 503),
                          page("error.html")])
    outcome = client.design(Row("NM_99999999"), Common(), never)
    assert outcome.failed
    assert client.clock.sleeps == [2, 4]


def test_gives_up_after_retries():
    client = make_client([page("form.html")] + [FakeResponse("", 503)] * 4)
    with pytest.raises(PrimerBlastError, match="응답이 없습니다"):
        client.design(Row("NM_000546"), Common(), never)
    assert client.clock.sleeps == [2, 4, 8]


def test_client_error_is_not_retried():
    client = make_client([page("form.html"), FakeResponse("", 403)])
    with pytest.raises(PrimerBlastError, match="HTTP 403"):
        client.design(Row("NM_000546"), Common(), never)


def test_times_out_when_results_never_come():
    client = make_client([page("form.html")] + [page("waiting.html")] * 100)
    with pytest.raises(PrimerBlastError, match="시간 초과"):
        client.design(Row("NM_000546"), Common(), never)
    assert client.clock.now <= JOB_TIMEOUT + 1


def test_stop_while_waiting():
    client = make_client([page("form.html"), page("waiting.html")])
    with pytest.raises(PrimerBlastError, match="중단"):
        client.design(Row("NM_000546"), Common(), lambda: True)
```

- [ ] **Step 2: 실패를 확인한다**

Run: `.venv/bin/python -m pytest -q tests/test_primerblast.py`
Expected: `ImportError: cannot import name 'PrimerBlastClient'`

- [ ] **Step 3: 구현한다**

`app/primerblast.py` 끝에 다음을 붙인다.

```python
class PrimerBlastClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._sleep = time.sleep
        self._clock = time.monotonic
        self._defaults: Optional[Fields] = None

    def design(self, row: Row, common: Common, should_stop: Callable[[], bool]) -> Outcome:
        if self._defaults is None:
            self._defaults = parse_form_defaults(self._request("GET", BASE_URL).text)
        fields = build_fields(self._defaults, row, common)
        page = self._request("POST", SUBMIT_URL, files=[(n, (None, v)) for n, v in fields]).text
        deadline = self._clock() + JOB_TIMEOUT
        reviewed = False
        accepted: List[str] = []
        url = ""   # 결과를 GET으로 받았을 때만 그 주소를 남긴다
        while True:
            kind = page_kind(page)
            if kind == "review":
                if reviewed:
                    raise PrimerBlastError("확인 화면이 반복됨")
                reviewed = True
                hidden, title, hits = parse_review(page)
                chosen = pick_same_gene(title, hits)
                accepted = list(dict.fromkeys(h.accession for h in chosen))  # 같은 번호가 구간만 달리해 두 번 나올 수 있다
                page = self._request("POST", SUBMIT_URL, data=hidden + [("USER_SEQLOC", h.seqloc) for h in chosen]).text
                url = ""
                continue
            if kind == "results":
                try:
                    outcome = parse_results(page)
                except Exception:  # 사이트 구조가 바뀐 경우: 원문을 남겨 개발자가 고치게 한다
                    return Outcome(accepted=accepted, url=url, note=UNREADABLE, failed=True, raw_page=page)
                outcome.accepted, outcome.url = accepted, url
                return outcome
            if kind == "error":
                return Outcome(accepted=accepted, url=url, note=error_message(page), failed=True)
            key = job_key(page)
            if kind == "unknown" or not key:
                return Outcome(accepted=accepted, url=url, note=UNREADABLE, failed=True, raw_page=page)
            self._pause(POLL_INTERVAL, deadline, should_stop)
            page = self._request("GET", SUBMIT_URL, params={"job_key": key}).text
            url = SUBMIT_URL + "?job_key=" + key

    def _pause(self, seconds: float, deadline: float, should_stop: Callable[[], bool]):
        end = self._clock() + seconds
        while self._clock() < end:
            if should_stop():
                raise PrimerBlastError("중단")
            if self._clock() >= deadline:
                raise PrimerBlastError("시간 초과 (%d분)" % (JOB_TIMEOUT // 60))
            self._sleep(min(1.0, end - self._clock()))

    def _request(self, method: str, url: str, **kwargs):
        for wait in RETRY_WAITS + (None,):
            try:
                resp = self.session.request(method, url, timeout=TIMEOUT, **kwargs)
            except requests.RequestException:
                resp = None
            if resp is not None:
                if resp.status_code == 200:
                    return resp
                if resp.status_code != 429 and resp.status_code < 500:
                    raise PrimerBlastError("사이트가 요청을 거부했습니다 (HTTP %d)" % resp.status_code)
            if wait is None:
                raise PrimerBlastError("사이트 응답이 없습니다")
            self._sleep(wait)
```

- [ ] **Step 4: 통과를 확인한다**

Run: `.venv/bin/python -m pytest -q tests/test_primerblast.py`
Expected: 36 passed

- [ ] **Step 5: 커밋한다**

```bash
git add app/primerblast.py tests/test_primerblast.py
git commit -m "feat: Primer-BLAST 제출, 확인 화면 처리, 결과 대기 추가

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 엑셀 저장과 화면 입력 검사

**Files:**
- Modify: `requirements.txt`
- Create: `app/designer.py`
- Test: `tests/test_designer.py` (새 파일)

**Interfaces:**
- Consumes: `app.primerblast`의 `Common`, `Outcome`, `Row`. `app.downloader.safe_filename`(Task 5).
- Produces: 상수 `MAX_ROWS`, `MAX_CONSECUTIVE_FAILURES`, `BETWEEN_JOBS`, `SHEET_TITLE`, `HEADERS`(21칸), `PAIR_COLUMNS`(16), `FASTA_EXTENSIONS`. 함수 `accessions_in_folder(folder) -> List[str]`, `excel_rows(row, outcome) -> List[list]`, `write_workbook(path, rows)`, `request_from_json(body) -> DesignRequest`(문제가 있으면 한국어 `ValueError`). 자료형 `DesignRequest(rows: List[Row], common: Common, folder: str)` — `folder`는 `~`를 펼친 경로.

- [ ] **Step 1: 의존성을 추가하고 설치한다**

`requirements.txt`를 다음으로 바꾼다.

```
flask>=2.0
requests>=2.25
openpyxl>=3.0
```

Run: `.venv/bin/pip install -q -r requirements-dev.txt`
Expected: 오류 없이 끝남

- [ ] **Step 2: 시험을 쓴다**

`tests/test_designer.py`를 다음 내용으로 만든다.

```python
import pytest
from openpyxl import load_workbook

from app.designer import HEADERS, MAX_ROWS, accessions_in_folder, excel_rows, request_from_json, write_workbook
from app.primerblast import Common, Outcome, Pair, Primer, Row


def pair(n=1):
    return Pair(left=Primer("AAAA", 10 * n, 13 * n, 4, 57.3, 50.0),
                right=Primer("TTTT", 100 * n, 97 * n, 4, 59.9, 25.0),
                product_length=91, unintended_same_gene=2, unintended_other_gene=n)


def found(n_pairs=1, **kwargs):
    return Outcome(title="t (G1)", pairs=[pair(i) for i in range(1, n_pairs + 1)], accepted=["X.1"],
                   url="http://r", **kwargs)


# ---- 폴더에서 서열 번호 찾기

def test_accessions_in_folder(tmp_path):
    (tmp_path / "b.txt").write_text(">NM_2.1 two\nACGT\n")
    (tmp_path / "a.txt").write_text(">NM_1.1 one\nACGT\n")
    (tmp_path / "combined.fasta").write_text(">NM_1.1 one\nAC\n>NM_3.1 three\nGT\n")
    (tmp_path / "notes.md").write_text(">NM_9.9 무시\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.txt").write_text(">NM_8.8 무시\n")
    assert accessions_in_folder(str(tmp_path)) == ["NM_1.1", "NM_2.1", "NM_3.1"]


# ---- 엑셀

def test_excel_rows_one_line_per_pair():
    lines = excel_rows(Row("NM_1"), found(2))
    assert len(lines) == 2 and all(len(line) == len(HEADERS) for line in lines)
    assert lines[1] == ["NM_1", "t (G1)", 2, "AAAA", 20, 26, 4, 57.3, 50.0, "TTTT", 200, 194, 4, 59.9, 25.0,
                        91, 2, 2, "X.1", "http://r", ""]


def test_excel_rows_without_pairs_keeps_one_line():
    lines = excel_rows(Row("NM_1"), Outcome(note="후보 없음"))
    assert lines == [["NM_1", ""] + [None] * 16 + ["", "", "후보 없음"]]


def test_write_workbook_roundtrip(tmp_path):
    path = str(tmp_path / "r.xlsx")
    write_workbook(path, excel_rows(Row("NM_1"), found(1)))
    sheet = load_workbook(path)["결과"]
    values = list(sheet.values)
    assert list(values[0]) == HEADERS
    assert values[1][0] == "NM_1" and values[1][3] == "AAAA" and values[1][7] == 57.3


# ---- 화면 입력 검사

GOOD = {
    "rows": [{"accession": " NM_1 ", "start": "200", "end": "", "left": " ACGT ", "right": ""}],
    "common": {"product_min": "70", "product_max": "1000", "tm_min": "57", "tm_opt": "60", "tm_max": "63",
               "num_return": "10", "organism": " Mus musculus "},
    "folder": "~/out",
}


def test_request_from_json():
    req = request_from_json(GOOD)
    assert req.rows == [Row("NM_1", start=200, end=None, left="ACGT", right="")]
    assert req.common == Common(70, 1000, 57.0, 60.0, 63.0, 10, "Mus musculus")
    assert not req.folder.startswith("~")


@pytest.mark.parametrize("change, message", [
    ({"rows": []}, "서열이 없습니다"),
    ({"rows": [{"accession": "A"}] * (MAX_ROWS + 1)}, "까지만"),
    ({"folder": " "}, "저장 폴더"),
    ({"rows": [{"accession": " "}]}, "빈 줄"),
    ({"rows": [{"accession": "NM_1", "start": "abc"}]}, "NM_1 구간 시작"),
    ({"common": {**GOOD["common"], "tm_opt": ""}}, "녹는 온도 적정"),
    ({"common": {**GOOD["common"], "product_min": "70.5"}}, "조각 길이 최소"),
])
def test_request_from_json_rejects(change, message):
    with pytest.raises(ValueError, match=message):
        request_from_json({**GOOD, **change})
```

- [ ] **Step 3: 실패를 확인한다**

Run: `.venv/bin/python -m pytest -q tests/test_designer.py`
Expected: `ModuleNotFoundError: No module named 'app.designer'`

- [ ] **Step 4: 구현한다**

`app/designer.py`를 다음 내용으로 만든다. (`threading`, `time`, `safe_filename`, `PrimerBlastError`는 Task 5에서 쓴다.)

```python
"""Primer-BLAST 설계 작업. 서열을 하나씩 처리하고 결과를 엑셀 파일 하나에 모은다."""
import os
import threading
import time
from dataclasses import dataclass
from typing import List

from openpyxl import Workbook

from app.downloader import safe_filename
from app.primerblast import Common, Outcome, PrimerBlastError, Row

MAX_ROWS = 50
MAX_CONSECUTIVE_FAILURES = 3
BETWEEN_JOBS = 10   # 다음 서열 제출 전 대기(초)
SHEET_TITLE = "결과"
HEADERS = [
    "서열 번호", "서열 이름", "후보 순번",
    "앞쪽 서열", "앞쪽 시작", "앞쪽 끝", "앞쪽 길이", "앞쪽 녹는 온도", "앞쪽 GC%",
    "뒤쪽 서열", "뒤쪽 시작", "뒤쪽 끝", "뒤쪽 길이", "뒤쪽 녹는 온도", "뒤쪽 GC%",
    "조각 길이", "잘못 붙는 대상(같은 유전자)", "잘못 붙는 대상(다른 유전자)",
    "자동으로 고른 비슷한 서열", "결과 페이지 주소", "메모",
]
PAIR_COLUMNS = 16   # 후보 순번부터 잘못 붙는 대상(다른 유전자)까지
FASTA_EXTENSIONS = (".txt", ".fasta", ".fa")


def accessions_in_folder(folder: str) -> List[str]:
    """폴더(하위 폴더 제외)의 서열 파일에서 '>' 줄의 첫 단어를 파일 이름 순서대로, 중복 없이 모은다."""
    found = {}
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if not (os.path.isfile(path) and name.lower().endswith(FASTA_EXTENSIONS)):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                words = line[1:].split()
                if line.startswith(">") and words:
                    found.setdefault(words[0], None)
    return list(found)


def excel_rows(row: Row, outcome: Outcome) -> List[list]:
    """후보 하나가 한 줄. 후보가 없으면 후보 칸을 비운 한 줄."""
    head = [row.accession, outcome.title]
    tail = [", ".join(outcome.accepted), outcome.url, outcome.note]
    if not outcome.pairs:
        return [head + [None] * PAIR_COLUMNS + tail]
    return [
        head + [number,
                p.left.seq, p.left.start, p.left.stop, p.left.length, p.left.tm, p.left.gc,
                p.right.seq, p.right.start, p.right.stop, p.right.length, p.right.tm, p.right.gc,
                p.product_length, p.unintended_same_gene, p.unintended_other_gene] + tail
        for number, p in enumerate(outcome.pairs, 1)
    ]


def write_workbook(path: str, rows: List[list]):
    book = Workbook()
    sheet = book.active
    sheet.title = SHEET_TITLE
    sheet.append(HEADERS)
    for values in rows:
        sheet.append(values)
    sheet.freeze_panes = "A2"
    book.save(path)


@dataclass
class DesignRequest:
    rows: List[Row]
    common: Common
    folder: str


def _number(values: dict, key: str, kind, label: str, required: bool = True):
    value = values.get(key)
    if value is None or str(value).strip() == "":
        if required:
            raise ValueError(label + " 값을 입력하세요")
        return None
    try:
        return kind(str(value).strip())
    except ValueError:
        raise ValueError("%s 값이 올바른 숫자가 아닙니다: %s" % (label, value))


def request_from_json(body: dict) -> DesignRequest:
    """화면이 보낸 JSON을 검사해 작업 입력으로 바꾼다. 문제가 있으면 사람이 읽을 ValueError."""
    items = body.get("rows") or []
    if not items:
        raise ValueError("설계할 서열이 없습니다")
    if len(items) > MAX_ROWS:
        raise ValueError("한 번에 %d개까지만 설계할 수 있습니다" % MAX_ROWS)
    folder = str(body.get("folder") or "").strip()
    if not folder:
        raise ValueError("저장 폴더를 입력하세요")
    c = body.get("common") or {}
    common = Common(
        product_min=_number(c, "product_min", int, "조각 길이 최소"),
        product_max=_number(c, "product_max", int, "조각 길이 최대"),
        tm_min=_number(c, "tm_min", float, "녹는 온도 최소"),
        tm_opt=_number(c, "tm_opt", float, "녹는 온도 적정"),
        tm_max=_number(c, "tm_max", float, "녹는 온도 최대"),
        num_return=_number(c, "num_return", int, "후보 개수"),
        organism=str(c.get("organism") or "").strip(),
    )
    rows = []
    for item in items:
        accession = str(item.get("accession") or "").strip()
        if not accession:
            raise ValueError("서열 번호가 빈 줄이 있습니다")
        rows.append(Row(
            accession=accession,
            start=_number(item, "start", int, accession + " 구간 시작", required=False),
            end=_number(item, "end", int, accession + " 구간 끝", required=False),
            left=str(item.get("left") or "").strip(),
            right=str(item.get("right") or "").strip(),
        ))
    return DesignRequest(rows=rows, common=common, folder=os.path.expanduser(folder))
```

- [ ] **Step 5: 통과를 확인한다**

Run: `.venv/bin/python -m pytest -q tests/test_designer.py`
Expected: 12 passed

- [ ] **Step 6: 커밋한다**

```bash
git add requirements.txt app/designer.py tests/test_designer.py
git commit -m "feat: 설계 결과 엑셀 저장과 화면 입력 검사 추가

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 설계 작업 (백그라운드 스레드)

**Files:**
- Modify: `app/designer.py` (파일 끝에 클래스 추가)
- Test: `tests/test_designer.py` (import 교체, 파일 끝에 시험 추가)

**Interfaces:**
- Consumes: Task 3의 `PrimerBlastClient.design(row, common, should_stop)` 모양(시험에서는 가짜). Task 4의 함수 전부.
- Produces: `Designer(client)` — 속성 `between_jobs`(기본 `BETWEEN_JOBS`, 시험에서 0). 메서드 `status() -> dict`, `is_running() -> bool`, `start(DesignRequest)`(작업 중이면 `RuntimeError`), `stop()`, `wait()`. 상태: `{"phase": "idle"|"running"|"done"|"stopped"|"error", "total", "done", "current", "rows": [{"accession", "status": "대기"|"진행 중"|"완료"|"후보 없음"|"실패"|"중단", "note"}], "file", "message"}`.

동작 규칙:
- 줄 사이에 `between_jobs`초 쉰다(중단 신호가 오면 바로 깸).
- `PrimerBlastError`는 실패로 세고, 3번 연속이면 `phase="error"`, `message="연속으로 실패해 멈췄습니다. 사이트 상태를 확인하세요."`. 성공하거나 사이트가 정상 응답(`Outcome`)하면 연속 횟수를 0으로 되돌린다.
- 중단으로 빠져나온 줄은 `중단`으로 표시하고 엑셀에 넣지 않는다.
- 서열 하나가 끝날 때마다 엑셀 전체를 다시 저장한다. 엑셀에 넣을 줄이 없으면 파일을 만들지 않는다. `PermissionError`는 다음 저장 때 다시 시도하고, 마지막 저장에서도 나면 `_2.xlsx`로 저장한다. `file`에는 실제로 저장된 경로가 들어간다.

- [ ] **Step 1: 시험을 쓴다**

`tests/test_designer.py` 맨 위의 import 부분(첫 줄부터 `def pair(` 앞까지)을 다음으로 바꾼다.

```python
import threading

import pytest
from openpyxl import load_workbook

from app import designer
from app.designer import (
    HEADERS, MAX_ROWS, Designer, DesignRequest, accessions_in_folder, excel_rows, request_from_json,
    write_workbook,
)
from app.primerblast import Common, Outcome, Pair, Primer, PrimerBlastError, Row
```

그리고 파일 끝에 다음을 붙인다.

```python
# ---- 작업

class FakeClient:
    """준비된 결과를 순서대로 돌려준다. 예외는 던지고, 함수는 should_stop을 받아 실행한다."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def design(self, row, common, should_stop):
        self.calls.append(row.accession)
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        if callable(item):
            return item(should_stop)
        return item


def run(client, tmp_path, n_rows):
    d = Designer(client)
    d.between_jobs = 0
    d.start(DesignRequest(rows=[Row("NM_%d" % i) for i in range(n_rows)], common=Common(),
                          folder=str(tmp_path / "out")))
    d.wait()
    return d


def sheet_rows(path):
    return list(load_workbook(path)["결과"].values)[1:]


def test_initial_status_is_idle():
    assert Designer(FakeClient([])).status() == {
        "phase": "idle", "total": 0, "done": 0, "current": "", "rows": [], "file": "", "message": ""}


def test_runs_rows_in_order_and_saves_excel(tmp_path):
    d = run(FakeClient([found(2), Outcome(title="t", note="후보 없음"), Outcome(note="Sequence ID not found", failed=True)]),
            tmp_path, 3)
    s = d.status()
    assert s["phase"] == "done" and s["done"] == 3 and s["total"] == 3 and s["current"] == ""
    assert [(r["status"], r["note"]) for r in s["rows"]] == [
        ("완료", ""), ("후보 없음", "후보 없음"), ("실패", "Sequence ID not found")]
    assert s["file"].startswith(str(tmp_path / "out" / "primers_")) and s["file"].endswith(".xlsx")
    rows = sheet_rows(s["file"])
    assert [r[0] for r in rows] == ["NM_0", "NM_0", "NM_1", "NM_2"]
    assert rows[3][-1] == "Sequence ID not found"


def test_stops_after_three_consecutive_failures(tmp_path):
    client = FakeClient([PrimerBlastError("시간 초과 (10분)")] * 3 + [found()])
    d = run(client, tmp_path, 4)
    s = d.status()
    assert s["phase"] == "error" and "연속으로 실패" in s["message"]
    assert client.calls == ["NM_0", "NM_1", "NM_2"]
    assert [r["status"] for r in s["rows"]] == ["실패", "실패", "실패", "대기"]
    assert len(sheet_rows(s["file"])) == 3


def test_success_resets_failure_count(tmp_path):
    client = FakeClient([PrimerBlastError("x"), PrimerBlastError("x"), found(),
                         PrimerBlastError("x"), PrimerBlastError("x")])
    assert run(client, tmp_path, 5).status()["phase"] == "done"


def test_site_error_outcome_does_not_count_as_failure(tmp_path):
    client = FakeClient([PrimerBlastError("x"), PrimerBlastError("x"), Outcome(note="bad", failed=True),
                         PrimerBlastError("x")])
    assert run(client, tmp_path, 4).status()["phase"] == "done"


def test_stop_keeps_finished_results(tmp_path):
    d = Designer(None)

    def stop_then_raise(should_stop):
        d.stop()
        assert should_stop() is True
        raise PrimerBlastError("중단")

    d.client = FakeClient([found(), stop_then_raise])
    d.between_jobs = 0
    d.start(DesignRequest(rows=[Row("NM_0"), Row("NM_1"), Row("NM_2")], common=Common(), folder=str(tmp_path)))
    d.wait()
    s = d.status()
    assert s["phase"] == "stopped" and s["done"] == 1
    assert [r["status"] for r in s["rows"]] == ["완료", "중단", "대기"]
    assert [r[0] for r in sheet_rows(s["file"])] == ["NM_0"]


def test_stop_before_any_result_writes_no_file(tmp_path):
    d = Designer(None)

    def stop_then_raise(should_stop):
        d.stop()
        raise PrimerBlastError("중단")

    d.client = FakeClient([stop_then_raise])
    d.start(DesignRequest(rows=[Row("NM_0")], common=Common(), folder=str(tmp_path)))
    d.wait()
    assert d.status()["phase"] == "stopped" and d.status()["file"] == ""
    assert list(tmp_path.iterdir()) == []


def test_unreadable_page_is_saved_next_to_excel(tmp_path):
    d = run(FakeClient([Outcome(note="결과 페이지를 읽지 못함", failed=True, raw_page="<html>x</html>")]), tmp_path, 1)
    assert (tmp_path / "out" / "NM_0_page.html").read_text() == "<html>x</html>"


def test_locked_excel_is_saved_under_another_name(tmp_path, monkeypatch):
    real = designer.write_workbook

    def locked(path, rows):
        if not path.endswith("_2.xlsx"):
            raise PermissionError(path)
        real(path, rows)

    monkeypatch.setattr(designer, "write_workbook", locked)
    s = run(FakeClient([found()]), tmp_path, 1).status()
    assert s["phase"] == "done" and s["file"].endswith("_2.xlsx")
    assert len(sheet_rows(s["file"])) == 1


def test_start_while_running_is_rejected(tmp_path):
    release = threading.Event()

    def blocked(should_stop):
        release.wait(5)
        return found()

    d = Designer(FakeClient([blocked]))
    req = DesignRequest(rows=[Row("NM_0")], common=Common(), folder=str(tmp_path))
    d.start(req)
    with pytest.raises(RuntimeError):
        d.start(req)
    release.set()
    d.wait()
    assert d.status()["phase"] == "done"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `.venv/bin/python -m pytest -q tests/test_designer.py`
Expected: `ImportError: cannot import name 'Designer'`

- [ ] **Step 3: 구현한다**

`app/designer.py` 끝에 다음을 붙인다.

```python
class Designer:
    """한 번에 작업 하나만 돌린다. 상태는 status()로 읽는다."""

    def __init__(self, client):
        self.client = client
        self.between_jobs = BETWEEN_JOBS
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._state = {"phase": "idle", "total": 0, "done": 0, "current": "", "rows": [], "file": "", "message": ""}

    def status(self) -> dict:
        with self._lock:
            return dict(self._state)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, request: DesignRequest):
        if self.is_running():
            raise RuntimeError("이미 설계 중입니다")
        self._stop.clear()
        self._set(phase="running", total=len(request.rows), done=0, current="", file="", message="",
                  rows=[{"accession": r.accession, "status": "대기", "note": ""} for r in request.rows])
        self._thread = threading.Thread(target=self._run, args=(request,), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def wait(self):
        if self._thread is not None:
            self._thread.join()

    def _set(self, **fields):
        with self._lock:
            self._state.update(fields)

    def _mark(self, index: int, status: str, note: str = ""):
        with self._lock:
            rows = [dict(r) for r in self._state["rows"]]
            rows[index].update(status=status, note=note)
            self._state["rows"] = rows

    def _run(self, request: DesignRequest):
        try:
            os.makedirs(request.folder, exist_ok=True)
            path = os.path.join(request.folder, time.strftime("primers_%Y%m%d_%H%M.xlsx"))
            sheet: List[list] = []
            failures = 0
            for i, row in enumerate(request.rows):
                if (i and self._stop.wait(self.between_jobs)) or self._stop.is_set():
                    break
                self._mark(i, "진행 중")
                self._set(current=row.accession)
                try:
                    outcome = self.client.design(row, request.common, self._stop.is_set)
                    failures = 0
                except PrimerBlastError as exc:
                    if self._stop.is_set():
                        self._mark(i, "중단")
                        break
                    failures += 1
                    outcome = Outcome(note=str(exc), failed=True)
                sheet.extend(excel_rows(row, outcome))
                if outcome.raw_page:
                    with open(os.path.join(request.folder, safe_filename(row.accession) + "_page.html"),
                              "w", encoding="utf-8", newline="\n") as f:
                        f.write(outcome.raw_page)
                self._mark(i, "실패" if outcome.failed else ("완료" if outcome.pairs else "후보 없음"), outcome.note)
                self._set(done=i + 1, current="")
                self._save(path, sheet, final=False)
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    self._save(path, sheet, final=True)
                    self._set(phase="error", current="", message="연속으로 실패해 멈췄습니다. 사이트 상태를 확인하세요.")
                    return
            self._save(path, sheet, final=True)
            self._set(phase="stopped" if self._stop.is_set() else "done", current="")
        except Exception as exc:  # OSError 등: 이유를 화면에 보여 준다
            self._set(phase="error", current="", message=str(exc))

    def _save(self, path: str, sheet: List[list], final: bool):
        if not sheet:
            return
        try:
            write_workbook(path, sheet)
        except PermissionError:
            if not final:
                return  # 박사님이 파일을 열어 둠: 다음 저장 때 다시 시도한다
            path = path[:-len(".xlsx")] + "_2.xlsx"
            write_workbook(path, sheet)
        self._set(file=path)
```

- [ ] **Step 4: 통과를 확인한다**

Run: `.venv/bin/python -m pytest -q tests/test_designer.py`
Expected: 22 passed

- [ ] **Step 5: 커밋한다**

```bash
git add app/designer.py tests/test_designer.py
git commit -m "feat: 서열을 하나씩 설계하는 백그라운드 작업 추가

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: 요청 경로 4개

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `Designer`, `accessions_in_folder`, `request_from_json`(Task 4·5), `PrimerBlastClient`(Task 3), `config.save`(Task 1).
- Produces: `create_app(client=None, downloader=None, designer=None)`, `app.designer`. 경로:
  - `GET /api/folder-accessions?folder=` → `{"accessions": [...]}`, 폴더가 없으면 400
  - `POST /api/design` body `{rows, common, folder}` → `{"ok": true}`. 입력 오류 400, 작업 중 409. 시작할 때 `common`과 `results_dir`를 설정에 저장
  - `GET /api/design/status` → `Designer.status()`
  - `POST /api/design/stop` → `{"ok": true}`

- [ ] **Step 1: 시험을 쓴다**

`tests/test_main.py`에서 `def make(...)` 함수 전체를 다음으로 바꾼다(바로 위에 `FakeDesigner`를 둔다).

```python
class FakeDesigner:
    def __init__(self, running=False):
        self.running = running
        self.started = []
        self.stopped = False

    def is_running(self):
        return self.running

    def start(self, req):
        self.started.append(req)

    def status(self):
        return {"phase": "idle", "total": 0, "done": 0, "current": "", "rows": [], "file": "", "message": ""}

    def stop(self):
        self.stopped = True


def make(tmp_path, monkeypatch, client=None, downloader=None, designer=None):
    monkeypatch.setattr("app.config.CONFIG_PATH", str(tmp_path / "config.json"))
    app = create_app(client=client or FakeClient(), downloader=downloader or FakeDownloader(),
                     designer=designer or FakeDesigner())
    app.testing = True
    return app
```

그리고 파일 끝에 다음을 붙인다.

```python
def test_folder_accessions(web, tmp_path):
    (tmp_path / "NM_1.1.txt").write_text(">NM_1.1 one\nACGT\n")
    r = web.get("/api/folder-accessions", query_string={"folder": str(tmp_path)})
    assert r.status_code == 200 and r.get_json() == {"accessions": ["NM_1.1"]}


def test_folder_accessions_rejects_missing_folder(web):
    assert web.get("/api/folder-accessions?folder=/definitely/not/here").status_code == 400


DESIGN_BODY = {
    "rows": [{"accession": "NM_1", "start": "", "end": "", "left": "", "right": ""}],
    "common": {"product_min": "80", "product_max": "900", "tm_min": "57", "tm_opt": "61", "tm_max": "63",
               "num_return": "5", "organism": "Mus musculus"},
    "folder": "~/primers",
}


def test_design_starts_job_and_remembers_conditions(web):
    r = web.post("/api/design", json=DESIGN_BODY)
    assert r.status_code == 200 and r.get_json() == {"ok": True}
    job = web.application.designer.started[0]
    assert job.rows[0].accession == "NM_1" and job.common.product_min == 80
    assert not job.folder.startswith("~")
    saved = web.get("/api/config").get_json()
    assert saved["product_min"] == 80 and saved["tm_opt"] == 61.0 and saved["organism"] == "Mus musculus"
    assert saved["results_dir"] == job.folder


def test_design_rejects_bad_input(web):
    r = web.post("/api/design", json={**DESIGN_BODY, "rows": []})
    assert r.status_code == 400 and "서열이 없습니다" in r.get_json()["error"]


def test_design_rejected_while_running(tmp_path, monkeypatch):
    app = make(tmp_path, monkeypatch, designer=FakeDesigner(running=True))
    assert app.test_client().post("/api/design", json=DESIGN_BODY).status_code == 409


def test_design_status_and_stop(web):
    assert web.get("/api/design/status").get_json()["phase"] == "idle"
    assert web.post("/api/design/stop").status_code == 200
    assert web.application.designer.stopped is True
```

- [ ] **Step 2: 실패를 확인한다**

Run: `.venv/bin/python -m pytest -q tests/test_main.py`
Expected: 3 failed, 8 passed, 15 errors. 오류는 `TypeError: create_app() got an unexpected keyword argument 'designer'`

- [ ] **Step 3: 구현한다**

`app/main.py`를 다음과 같이 고친다.

1. 첫 줄 docstring의 `ncbi / downloader / config 모듈을` 을 `ncbi / downloader / designer / config 모듈을` 로 바꾼다.
2. import 부분을 다음으로 바꾼다(맨 위 docstring 다음부터 `from app.ncbi import ...` 줄까지).

```python
import dataclasses
import json
import os
import socket
import subprocess
import sys
import threading
import urllib.request
import webbrowser

from flask import Flask, jsonify, request, send_from_directory

from app import config
from app.designer import Designer, accessions_in_folder, request_from_json
from app.downloader import Downloader, JobRequest
from app.ncbi import NcbiClient, NcbiError
from app.primerblast import PrimerBlastClient
```

3. `def create_app(client=None, downloader=None):` 를 `def create_app(client=None, downloader=None, designer=None):` 로 바꾸고, `app.downloader = ...` 줄 바로 아래에 다음 줄을 넣는다.

```python
    app.designer = designer or Designer(PrimerBlastClient())
```

4. `open_folder` 경로 함수 끝(`return jsonify(ok=True)`)과 `return app` 사이에 다음을 넣는다.

```python
    @app.get("/api/folder-accessions")
    def folder_accessions():
        folder = os.path.expanduser(request.args.get("folder", "").strip())
        if not os.path.isdir(folder):
            return jsonify(error="폴더가 없습니다: " + folder), 400
        return jsonify(accessions=accessions_in_folder(folder))

    @app.post("/api/design")
    def design():
        try:
            job = request_from_json(request.get_json(force=True))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        if app.designer.is_running():
            return jsonify(error="이미 설계 중입니다"), 409
        config.save({**dataclasses.asdict(job.common), "results_dir": job.folder})
        app.designer.start(job)
        return jsonify(ok=True)

    @app.get("/api/design/status")
    def design_status():
        return jsonify(app.designer.status())

    @app.post("/api/design/stop")
    def design_stop():
        app.designer.stop()
        return jsonify(ok=True)
```

- [ ] **Step 4: 통과를 확인한다**

Run: `.venv/bin/python -m pytest -q`
Expected: 115 passed, 1 skipped (건너뛰는 1개는 기존 실제 접속 시험)

- [ ] **Step 5: 커밋한다**

```bash
git add app/main.py tests/test_main.py
git commit -m "feat: 프라이머 설계 요청 경로 4개 추가

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: 2단계 화면

**Files:**
- Create: `app/static/primer.html`
- Modify: `app/static/index.html` (머리에 링크)
- Test: `tests/test_main.py` (파일 끝에 시험 하나 추가)

**Interfaces:**
- Consumes: Task 6의 경로 4개, 기존 `GET /api/config`(`downloads_dir`, `results_dir`, 공통 조건 키), 기존 `POST /api/open-folder`.
- Produces: `/primer.html` 화면. 화면 쪽 `MAX_ROWS = 50`은 서버 상수와 같은 값이다.

- [ ] **Step 1: 시험을 쓴다**

`tests/test_main.py` 끝에 다음을 붙인다.

```python
def test_primer_page_is_served(web):
    r = web.get("/primer.html")
    assert r.status_code == 200
    assert "프라이머 설계".encode() in r.data
```

- [ ] **Step 2: 실패를 확인한다**

Run: `.venv/bin/python -m pytest -q tests/test_main.py -k primer_page`
Expected: `assert 404 == 200`

- [ ] **Step 3: 화면을 만든다**

`app/static/primer.html`을 다음 내용으로 만든다.

```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>프라이머 설계</title>
<link rel="icon" href="data:,">
<style>
  body { font-family: -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif; max-width: 1100px; margin: 24px auto; padding: 0 16px; color: #222; }
  nav { display: flex; gap: 16px; margin-bottom: 12px; font-size: 14px; }
  nav a { color: #06c; }
  h1 { font-size: 20px; margin: 0; }
  h2 { font-size: 15px; margin: 0 0 8px; }
  section { margin-top: 16px; padding: 12px 16px; border: 1px solid #ddd; border-radius: 6px; }
  input[type=text] { padding: 6px 8px; font-size: 14px; }
  input.num { width: 64px; }
  #organism { width: 220px; }
  .wide { width: 70%; }
  button { padding: 6px 12px; font-size: 14px; cursor: pointer; }
  button:disabled { cursor: default; opacity: .5; }
  #error { display: none; background: #fde8e8; color: #a00; padding: 10px 14px; border-radius: 6px; margin-top: 12px; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  td, th { text-align: left; padding: 4px 6px; border-bottom: 1px solid #eee; font-size: 14px; vertical-align: top; }
  th { white-space: nowrap; }
  td input { width: 100%; box-sizing: border-box; padding: 4px 6px; font-size: 13px; }
  td input.pos { width: 72px; }
  .note { color: #666; font-size: 12px; }
  .row { margin-top: 8px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
  progress { width: 100%; height: 18px; }
  .hint { color: #666; font-size: 13px; }
</style>
</head>
<body>
<nav><a href="/">1. 서열 내려받기</a> <b>2. 프라이머 설계</b></nav>
<h1>프라이머 설계 (Primer-BLAST)</h1>
<div id="error"></div>

<section>
  <h2>서열 추가</h2>
  <div class="row">폴더에서 불러오기 <input type="text" id="src-folder" class="wide"> <button id="load-folder">불러오기</button></div>
  <div class="row">서열 번호 직접 입력 <input type="text" id="acc-input" class="wide" placeholder="예: NM_000546, NM_001126112 (쉼표·공백으로 구분)"> <button id="add-acc">추가</button></div>
</section>

<section>
  <h2>공통 조건</h2>
  <div class="row">조각 길이 최소 <input type="text" id="product_min" class="num"> 최대 <input type="text" id="product_max" class="num"></div>
  <div class="row">녹는 온도 최소 <input type="text" id="tm_min" class="num"> 적정 <input type="text" id="tm_opt" class="num"> 최대 <input type="text" id="tm_max" class="num"></div>
  <div class="row">후보 개수 <input type="text" id="num_return" class="num">
    생물종 <input type="text" id="organism" placeholder="비우면 사람(Homo sapiens)"></div>
</section>

<section>
  <div class="row" style="justify-content: space-between; margin-top: 0">
    <h2>서열 목록 (<span id="row-count">0</span> / 50)</h2>
    <button id="clear-rows">모두 지우기</button>
  </div>
  <table>
    <thead><tr><th>서열 번호</th><th>구간 시작</th><th>구간 끝</th><th>앞쪽 프라이머</th><th>뒤쪽 프라이머</th><th>상태</th><th></th></tr></thead>
    <tbody id="rows"></tbody>
  </table>
  <div class="hint">구간과 프라이머는 비워 두면 서열 전체에서 사이트가 설계합니다. 프라이머를 넣으면 그 프라이머를 검사합니다.</div>
</section>

<section>
  <div class="row">저장 폴더 <input type="text" id="folder" class="wide"></div>
  <div class="row"><button id="start">설계 시작</button> <span id="estimate" class="hint"></span></div>
  <div id="progress-box" class="row" style="display:none">
    <progress id="progress" value="0" max="1"></progress>
    <div><span id="progress-label"></span> <button id="stop">중단</button></div>
  </div>
  <div id="result-box" class="row" style="display:none">
    <span id="result-label"></span> <button id="open-folder">폴더 열기</button>
  </div>
</section>

<script>
const MAX_ROWS = 50;
const COMMON = ["product_min", "product_max", "tm_min", "tm_opt", "tm_max", "num_return", "organism"];
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const state = { rows: [], running: false, folder: "" };

async function api(path, options) {
  const resp = await fetch(path, options);
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || ("요청 실패 (HTTP " + resp.status + ")"));
  hideError();
  return data;
}
function postJson(path, body) {
  return api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}
function showError(msg) { $("error").textContent = msg; $("error").style.display = "block"; }
function hideError() { $("error").style.display = "none"; }
const report = e => showError(e.message);

// ---- 설정
async function loadConfig() {
  const c = await api("/api/config");
  COMMON.forEach(k => { $(k).value = c[k]; });
  $("src-folder").value = c.downloads_dir;
  $("folder").value = c.results_dir;
}

// ---- 서열 목록
function addAccessions(list) {
  const have = new Set(state.rows.map(r => r.accession));
  for (const acc of list) {
    if (have.has(acc)) continue;
    if (state.rows.length >= MAX_ROWS) { showError("한 번에 " + MAX_ROWS + "개까지만 설계할 수 있습니다. 나머지는 추가하지 않았습니다."); break; }
    state.rows.push({ accession: acc, start: "", end: "", left: "", right: "", status: "대기", note: "" });
    have.add(acc);
  }
  render();
}
function render() {
  const lock = state.running ? "disabled" : "";
  $("rows").innerHTML = state.rows.map((r, i) => `
    <tr><td>${esc(r.accession)}</td>
    <td><input class="pos" data-i="${i}" data-k="start" value="${esc(r.start)}" ${lock}></td>
    <td><input class="pos" data-i="${i}" data-k="end" value="${esc(r.end)}" ${lock}></td>
    <td><input data-i="${i}" data-k="left" value="${esc(r.left)}" ${lock}></td>
    <td><input data-i="${i}" data-k="right" value="${esc(r.right)}" ${lock}></td>
    <td>${esc(r.status)}${r.note ? '<div class="note">' + esc(r.note) + "</div>" : ""}</td>
    <td><button data-del="${i}" ${lock}>✕</button></td></tr>`).join("");
  $("rows").querySelectorAll("input").forEach(el => {
    el.onchange = () => { state.rows[el.dataset.i][el.dataset.k] = el.value.trim(); };
  });
  $("rows").querySelectorAll("button[data-del]").forEach(el => {
    el.onclick = () => { state.rows.splice(Number(el.dataset.del), 1); render(); };
  });
  $("row-count").textContent = state.rows.length;
  $("estimate").textContent = state.rows.length ? "예상 약 " + state.rows.length * 2 + "분 (서열 하나에 약 1~2분)" : "";
  ["load-folder", "add-acc", "clear-rows", "src-folder", "acc-input", "folder", ...COMMON].forEach(id => { $(id).disabled = state.running; });
  $("start").disabled = state.running || state.rows.length === 0;
}
$("load-folder").onclick = () => api("/api/folder-accessions?" + new URLSearchParams({ folder: $("src-folder").value.trim() }))
  .then(d => d.accessions.length ? addAccessions(d.accessions) : showError("그 폴더에서 서열 번호를 찾지 못했습니다."))
  .catch(report);
$("add-acc").onclick = () => { addAccessions($("acc-input").value.split(/[\s,]+/).filter(Boolean)); $("acc-input").value = ""; };
$("acc-input").onkeydown = e => { if (e.key === "Enter") $("add-acc").click(); };
$("clear-rows").onclick = () => { state.rows = []; render(); };

// ---- 설계 시작과 중단
$("start").onclick = () => {
  const common = {};
  COMMON.forEach(k => { common[k] = $(k).value.trim(); });
  const rows = state.rows.map(r => ({ accession: r.accession, start: r.start, end: r.end, left: r.left, right: r.right }));
  state.rows.forEach(r => { r.status = "대기"; r.note = ""; });
  $("result-box").style.display = "none";
  postJson("/api/design", { rows, common, folder: $("folder").value.trim() })
    .then(() => { state.running = true; render(); poll(); }).catch(report);
};
$("stop").onclick = () => postJson("/api/design/stop", {}).catch(report);
$("open-folder").onclick = () => postJson("/api/open-folder", { folder: state.folder }).catch(report);

// ---- 진행 상태 (2초마다 조회)
let pollTimer = null;
async function poll() {
  clearTimeout(pollTimer);
  let s;
  try { s = await api("/api/design/status"); } catch (e) { report(e); return; }
  if (s.phase !== "idle" && state.rows.length === 0) {
    // 화면을 새로 열었는데 작업이 남아 있으면 목록을 되살린다
    state.rows = s.rows.map(r => ({ accession: r.accession, start: "", end: "", left: "", right: "", status: r.status, note: r.note }));
  }
  if (s.rows.length === state.rows.length) {
    s.rows.forEach((r, i) => { state.rows[i].status = r.status; state.rows[i].note = r.note; });
  }
  state.running = s.phase === "running";
  state.folder = s.file ? s.file.replace(/[\\/][^\\/]*$/, "") : $("folder").value.trim();
  $("progress-box").style.display = state.running ? "block" : "none";
  if (state.running) {
    $("progress").max = Math.max(1, s.total);
    $("progress").value = s.done;
    $("progress-label").textContent = "진행 " + s.done + " / " + s.total + (s.current ? " · " + s.current + " 처리 중" : "");
    pollTimer = setTimeout(poll, 2000);
  } else if (s.phase !== "idle") {
    const saved = s.file ? " 결과 파일: " + s.file : " 저장된 결과가 없습니다.";
    $("result-label").textContent =
      s.phase === "done" ? "완료." + saved :
      s.phase === "stopped" ? "중단됨." + saved :
      "멈춤: " + s.message + saved;
    $("result-box").style.display = "block";
  }
  render();
}

loadConfig().then(poll).catch(report);
</script>
</body>
</html>
```

`app/static/index.html`에서 `<style>` 안의 `.hint { ... }` 줄 아래에 다음 두 줄을 넣는다.

```css
  nav { display: flex; gap: 16px; margin-bottom: 12px; font-size: 14px; }
  nav a { color: #06c; }
```

그리고 `<body>` 바로 다음, `<header>` 앞에 다음 줄을 넣는다.

```html
<nav><b>1. 서열 내려받기</b> <a href="primer.html">2. 프라이머 설계</a></nav>
```

- [ ] **Step 4: 통과를 확인한다**

Run: `.venv/bin/python -m pytest -q`
Expected: 116 passed, 1 skipped

- [ ] **Step 5: 화면을 사람이 확인한다 (사이트 접속 없음)**

가짜 클라이언트로 서버를 띄운다. 아래 스크립트를 저장소 밖 임시 파일(예: `/tmp/ui_check.py`)로 저장한다.

```python
"""화면 확인용: 가짜 클라이언트로 Designer를 돌리는 서버 (NCBI 접속 없음).
사용: python ui_check.py <저장소 경로> <임시 설정 폴더>
"""
import sys
import time

sys.path.insert(0, sys.argv[1])
from app import config  # noqa: E402
from app.designer import Designer  # noqa: E402
from app.main import create_app  # noqa: E402
from app.primerblast import Outcome, Pair, Primer, PrimerBlastError  # noqa: E402

config.CONFIG_PATH = sys.argv[2] + "/config.json"


class SlowClient:
    def design(self, row, common, should_stop):
        for _ in range(6):
            if should_stop():
                raise PrimerBlastError("중단")
            time.sleep(0.5)
        if row.accession.startswith("NM_011"):
            return Outcome(title="Mus musculus (Trp53)", note="후보 없음: No primers were found")
        p = Pair(Primer("ACCTATGG", 204, 227, 24, 57.3, 37.5), Primer("ACCATCGC", 703, 684, 20, 59.97, 55.0), 500, 4, 1)
        return Outcome(title="Homo sapiens (TP53)", pairs=[p, p], accepted=["NM_1.1"], url="http://x")


designer = Designer(SlowClient())
designer.between_jobs = 1
create_app(designer=designer).run(host="127.0.0.1", port=8799)
```

Run: `.venv/bin/python /tmp/ui_check.py "$PWD" /tmp/ui_check_cfg` (먼저 `mkdir -p /tmp/ui_check_cfg`)

브라우저로 `http://127.0.0.1:8799/primer.html`을 열고 확인한다.
- 맨 위 링크로 1단계 화면과 오갈 수 있다.
- 공통 조건 칸에 70 / 1000 / 57 / 60 / 63 / 10이 채워져 있다.
- 직접 입력 칸에 `NM_000546.6, NM_011640.3` → 추가 → 두 줄이 생긴다. 같은 번호를 다시 추가해도 줄이 늘지 않는다.
- 저장 폴더를 임시 폴더로 바꾸고 설계 시작 → 줄 상태가 `진행 중 → 완료`, 두 번째 줄은 `후보 없음`과 안내문으로 바뀌고, 끝나면 "완료. 결과 파일: …xlsx"와 폴더 열기 버튼이 보인다.
- 저장된 엑셀을 열어 첫 줄 머리글 21칸과 결과 3줄(쌍 2줄 + 후보 없음 1줄)을 확인한다.

확인이 끝나면 서버를 끄고(Ctrl+C) 임시 파일을 지운다.

- [ ] **Step 6: 커밋한다**

```bash
git add app/static/primer.html app/static/index.html tests/test_main.py
git commit -m "feat: 프라이머 설계 화면 추가

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: README와 실제 사이트 확인

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README에 2단계 사용법을 넣는다**

1. 기존 `## 4. 설정 (⚙)`부터 `## 8. 개발자용`까지 제목 번호를 하나씩 올린다(4→5, 5→6, 6→7, 7→8, 8→9).
2. `## 3. 사용법` 절의 `### 검색어 예시` 부분이 끝난 뒤(새 `## 5. 설정 (⚙)` 바로 앞)에 다음을 넣는다.

```markdown
## 4. 프라이머 설계 (2단계)

> **주의:** 이 기능은 프로그램이 NCBI Primer-BLAST 웹사이트에 대신 제출합니다. NCBI는 웹페이지에 대한 자동 접근을
> 허용하지 않으며, 그렇게 하면 접근을 제한할 수 있다고 밝히고 있습니다. 제한은 기관 IP 단위로 걸릴 수 있습니다.
> 도구는 한 번에 한 건씩만 제출하고, 15초 간격으로 결과를 확인하며, 한 번에 50개까지만 처리하도록 묶어 두었습니다.

1. 화면 맨 위의 **2. 프라이머 설계**를 누릅니다.
2. 서열을 추가합니다.
   - **폴더에서 불러오기**: 1단계에서 받은 폴더를 넣고 누르면, 그 안 파일들에 적힌 서열 번호가 목록에 들어갑니다.
   - **서열 번호 직접 입력**: `NM_000546, NM_001126112`처럼 쉼표나 공백으로 구분해 넣고 **추가**.
3. **공통 조건**을 확인합니다. 처음 값은 Primer-BLAST 웹사이트의 기본값과 같습니다.
   생물종은 `Mus musculus`처럼 학명을 넣고, 비워 두면 사람(Homo sapiens)입니다.
4. 서열마다 필요하면 **구간 시작/끝**(프라이머를 놓을 위치)과 **앞쪽/뒤쪽 프라이머**를 넣습니다.
   프라이머 칸을 비우면 사이트가 프라이머를 설계하고, 채우면 그 프라이머가 원하는 곳에만 붙는지 검사합니다.
5. 저장 폴더를 확인하고(기본값 `다운로드/primer_results`) **설계 시작**. 서열 하나에 1~2분 걸리고, 줄마다 상태가 바뀝니다.
6. 끝나면 저장 폴더에 `primers_날짜_시각.xlsx`가 생깁니다. 도중에 **중단**해도 끝난 서열의 결과는 남습니다.

### 비슷한 서열 확인 화면

웹사이트는 입력 서열과 거의 같은 서열을 찾으면 "프라이머가 붙어도 되는 서열을 골라 달라"는 화면을 보여 줍니다.
도구는 이 화면에서 **같은 유전자의 다른 판본만** 자동으로 고릅니다. 같은 유전자인지는 제목 괄호 안의 유전자 이름
(예: `TP53`)으로 판단합니다. 고른 서열은 엑셀의 "자동으로 고른 비슷한 서열" 칸에 적힙니다.

### 엑셀 파일

후보 하나가 한 줄입니다. 앞쪽·뒤쪽 프라이머의 서열, 위치, 길이, 녹는 온도, GC 비율과 만들어지는 조각 길이가 들어 있습니다.
"잘못 붙는 대상(다른 유전자)"는 다른 유전자에서도 조각이 만들어질 수 있는 곳의 수이고, 0이면 그런 곳이 보고되지 않은 후보입니다.
"잘못 붙는 대상(같은 유전자)"는 같은 유전자의 다른 판본에서 조각이 만들어지는 곳의 수입니다.
"결과 페이지 주소"는 웹사이트의 결과 화면이며, 시간이 지나면 열리지 않을 수 있습니다.
후보가 없거나 실패한 서열도 메모 칸에 이유를 적은 한 줄로 남습니다. 메모에 "결과 페이지를 읽지 못함"이 있으면
같은 폴더의 `<서열번호>_page.html` 파일을 개발자에게 보내 주세요.
```

3. `## 7. 문제 해결` 표의 마지막 줄 아래에 다음 세 줄을 넣는다.

```markdown
| "연속으로 실패해 멈췄습니다" | NCBI 사이트가 바쁘거나 접근이 막혔을 수 있습니다. 브라우저로 Primer-BLAST 웹사이트가 열리는지 확인하고 한참 뒤에 다시 시도 |
| "이미 설계 중입니다" | 진행 중인 설계가 끝나거나 중단될 때까지 기다림 |
| 엑셀 파일 이름 끝에 `_2` | 설계 중에 엑셀 파일을 열어 두어 원래 이름으로 저장하지 못한 경우. 내용은 같음 |
```

4. `## 8. 프로젝트 구조와 이후 계획` 절의 코드 블록을 다음으로 바꾸고,

```
app/
  ncbi.py         NCBI와 통신 (검색, 요약, FASTA 받기). 화면·파일과 무관
  downloader.py   받은 텍스트를 파일로 저장하고 진행 상태를 기록
  primerblast.py  Primer-BLAST 웹사이트 제출과 결과 페이지 해석. 화면·파일과 무관
  designer.py     서열을 하나씩 설계하고 결과를 엑셀로 저장
  config.py       설정 파일 읽기/쓰기
  main.py         웹 서버. 화면 요청을 받아 위 모듈들을 호출
  static/index.html   1단계 화면
  static/primer.html  2단계 화면
```

코드 블록 아래 문단("2단계를 붙일 때는 …")을 다음으로 바꾼다.

```markdown
2단계(프라이머 설계)는 이 구조에 `primerblast.py`, `designer.py`, `primer.html`을 더해 붙였습니다.
3단계(검증)도 같은 방식으로 모듈과 화면을 더하면 됩니다. 설계 문서는 `docs/superpowers/specs/` 에 있습니다.
```

5. `## 9. 개발자용`의 코드 블록에서 `.venv/bin/python -m pytest -q              # NCBI에 접속하지 않는 테스트` 줄 바로 아래에 다음 줄을 넣는다.

```bash
# Primer-BLAST 시험은 tests/fixtures/primerblast/ 의 실제 페이지 원문으로 돈다 (사이트 접속 없음)
```

- [ ] **Step 2: 시험이 그대로 통과하는지 확인한다**

Run: `.venv/bin/python -m pytest -q`
Expected: 모두 통과

- [ ] **Step 3: 커밋한다**

```bash
git add README.md
git commit -m "docs: README에 프라이머 설계(2단계) 사용법 추가

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: 실제 사이트로 한 번 확인한다 (사람이, 서열 3개)**

이 단계만 실제 Primer-BLAST에 요청을 보낸다. 사용자에게 먼저 알리고 진행한다.

1. `./run_mac.command`(또는 `.venv/bin/python -m app.main`)로 실행하고 **2. 프라이머 설계**로 간다.
2. 공통 조건은 기본값 그대로 두고, 서열 3줄을 넣는다.
   - `NM_000546`: 아무것도 넣지 않음 (사이트가 설계)
   - `NM_001126112`: 구간 시작 200, 구간 끝 900
   - `NM_000546.6`: 앞쪽 `ACCTATGGAAACTACTTCCTGAAA`, 뒤쪽 `ACCATCGCTATCTGAGCAGC` (박사님 프라이머 검사)
3. 설계 시작 → 약 5분 뒤 완료를 확인한다.
4. 같은 조건으로 브라우저에서 Primer-BLAST를 직접 돌려, 엑셀의 첫 후보 서열·위치·녹는 온도·조각 길이가 사이트 화면과 같은지 비교한다.
5. 결과를 사용자에게 보고한다. 다르면 고치기 전에 원인을 먼저 찾는다.

---

### Task 9: 용어 전환 (한국어 기본, 영어 선택)

설계 문서 14절. 전문 용어만 한국어와 Primer-BLAST 영어 사이에서 바꾸고, 설정은 `config.json`의 `terms`에 둔다. 설정 저장 경로가 이메일·API 키를 지우는 문제도 함께 고친다.

**Files:**
- Modify: `app/config.py`, `app/designer.py`, `app/main.py`, `app/static/primer.html`, `README.md`
- Test: `tests/test_config.py`, `tests/test_designer.py`, `tests/test_main.py`

**Interfaces:**
- Consumes: Task 1~8 결과 전부.
- Produces: `config.DEFAULTS["terms"] = "ko"`. `designer.HEADERS_EN`(21칸), `designer.SHEET_TITLE_EN = "Results"`, `designer.TERMS = ("ko", "en")`. `write_workbook(path, rows, terms="ko")`. `DesignRequest.terms`(기본 `"ko"`), `request_from_json`은 body의 `terms`(없으면 `"ko"`)를 검사한다. `Designer._save(path, sheet, terms, final)`. `POST /api/design` body에 `terms`. 화면: `<select id="terms">`, 용어 자리는 `data-term` 속성.

- [ ] **Step 1: 시험을 바꾼다**

아래 수정은 모두 "찾아서 바꾸기"다. 찾는 부분은 파일에 정확히 한 번 있다.

1. `tests/test_config.py`에서 다음 부분을 찾아서

```python
    assert loaded["results_dir"].endswith("primer_results")
```

   다음으로 바꾼다.

```python
    assert loaded["results_dir"].endswith("primer_results")
    assert loaded["terms"] == "ko"
```

2. `tests/test_designer.py`에서 다음 부분을 찾아서

```python
from app.designer import (
    HEADERS, MAX_ROWS, Designer, DesignRequest, accessions_in_folder, excel_rows, request_from_json,
    write_workbook,
)
```

   다음으로 바꾼다.

```python
from app.designer import (
    HEADERS, HEADERS_EN, MAX_ROWS, Designer, DesignRequest, accessions_in_folder, excel_rows, request_from_json,
    write_workbook,
)
```

3. `tests/test_designer.py`에서 다음 부분을 찾아서

```python
def test_write_workbook_roundtrip(tmp_path):
```

   다음으로 바꾼다.

```python
def test_write_workbook_in_english(tmp_path):
    path = str(tmp_path / "r.xlsx")
    write_workbook(path, excel_rows(Row("NM_1"), found(1)), "en")
    book = load_workbook(path)
    assert book.sheetnames == ["Results"]
    values = list(book["Results"].values)
    assert list(values[0]) == HEADERS_EN and len(HEADERS_EN) == len(HEADERS)
    assert values[1][3] == "AAAA"


def test_write_workbook_roundtrip(tmp_path):
```

4. `tests/test_designer.py`에서 다음 부분을 찾아서

```python
    assert not req.folder.startswith("~")


@pytest.mark.parametrize("change, message", [
```

   다음으로 바꾼다.

```python
    assert not req.folder.startswith("~")
    assert req.terms == "ko"
    assert request_from_json({**GOOD, "terms": "en"}).terms == "en"


@pytest.mark.parametrize("change, message", [
```

5. `tests/test_designer.py`에서 다음 부분을 찾아서

```python
    ({"common": {**GOOD["common"], "product_min": "70.5"}}, "조각 길이 최소"),
])
```

   다음으로 바꾼다.

```python
    ({"common": {**GOOD["common"], "product_min": "70.5"}}, "조각 길이 최소"),
    ({"terms": "fr"}, "용어 설정"),
])
```

6. `tests/test_designer.py`에서 다음 부분을 찾아서

```python
    def locked(path, rows):
        if not path.endswith("_2.xlsx"):
            raise PermissionError(path)
        real(path, rows)
```

   다음으로 바꾼다.

```python
    def locked(path, rows, terms="ko"):
        if not path.endswith("_2.xlsx"):
            raise PermissionError(path)
        real(path, rows, terms)
```

7. `tests/test_main.py`에서 다음 부분을 찾아서

```python
    assert "프라이머 설계".encode() in r.data
```

   다음으로 바꾼다.

```python
    assert "프라이머 설계".encode() in r.data
    assert b'id="terms"' in r.data and b'data-term="forward"' in r.data
```

그리고 다음을 붙인다.

`tests/test_designer.py` 끝에 다음을 붙인다(기존 내용과 빈 줄 두 개 띄움).

```python
def test_excel_headers_follow_request_terms(tmp_path):
    d = Designer(FakeClient([found()]))
    d.between_jobs = 0
    d.start(DesignRequest(rows=[Row("NM_0")], common=Common(), folder=str(tmp_path), terms="en"))
    d.wait()
    book = load_workbook(d.status()["file"])
    assert book.sheetnames == ["Results"]
    assert list(next(book["Results"].values)) == HEADERS_EN
```

`tests/test_main.py` 끝에 다음을 붙인다(기존 내용과 빈 줄 두 개 띄움).

```python
def test_saving_one_setting_keeps_client_key(web):
    web.post("/api/config", json={"email": "a@b.c", "api_key": "K", "per_item": True, "combined": False})
    assert web.post("/api/config", json={"terms": "en"}).status_code == 200
    assert web.get("/api/config").get_json()["terms"] == "en"
    assert web.application.client.email == "a@b.c" and web.application.client.api_key == "K"


def test_design_passes_terms(web):
    assert web.post("/api/design", json={**DESIGN_BODY, "terms": "en"}).status_code == 200
    assert web.application.designer.started[0].terms == "en"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `.venv/bin/python -m pytest -q`
Expected: `1 error` (`ImportError: cannot import name 'HEADERS_EN' from 'app.designer'`)

- [ ] **Step 3: 구현한다**

1. `app/config.py`에서 다음 부분을 찾아서

```python
"""config.json 읽기/쓰기. 이메일·API 키·저장 방식 체크박스 상태와 프라이머 설계 조건을 담는다."""
```

   다음으로 바꾼다.

```python
"""config.json 읽기/쓰기. 이메일·API 키·저장 방식 체크박스 상태와 프라이머 설계 조건, 용어 설정을 담는다."""
```

2. `app/config.py`에서 다음 부분을 찾아서

```python
    "results_dir": os.path.join(os.path.expanduser("~"), "Downloads", "primer_results"),
}
```

   다음으로 바꾼다.

```python
    "results_dir": os.path.join(os.path.expanduser("~"), "Downloads", "primer_results"),
    "terms": "ko",   # 2단계 화면과 엑셀의 전문 용어: ko(한국어) / en(Primer-BLAST 영어)
}
```

3. `app/designer.py`에서 다음 부분을 찾아서

```python
PAIR_COLUMNS = 16   # 후보 순번부터 잘못 붙는 대상(다른 유전자)까지
```

   다음으로 바꾼다.

```python
HEADERS_EN = [
    "Accession", "Title", "Pair",
    "Forward primer", "Forward start", "Forward stop", "Forward length", "Forward Tm", "Forward GC%",
    "Reverse primer", "Reverse start", "Reverse stop", "Reverse length", "Reverse Tm", "Reverse GC%",
    "Product length", "Unintended targets (same gene)", "Unintended targets (other gene)",
    "Accepted similar sequences", "Result URL", "Note",
]
SHEET_TITLE_EN = "Results"
TERMS = ("ko", "en")
PAIR_COLUMNS = 16   # 후보 순번부터 잘못 붙는 대상(다른 유전자)까지
```

4. `app/designer.py`에서 다음 부분을 찾아서

```python
def write_workbook(path: str, rows: List[list]):
    book = Workbook()
    sheet = book.active
    sheet.title = SHEET_TITLE
    sheet.append(HEADERS)
```

   다음으로 바꾼다.

```python
def write_workbook(path: str, rows: List[list], terms: str = "ko"):
    book = Workbook()
    sheet = book.active
    sheet.title = SHEET_TITLE_EN if terms == "en" else SHEET_TITLE
    sheet.append(HEADERS_EN if terms == "en" else HEADERS)
```

5. `app/designer.py`에서 다음 부분을 찾아서

```python
    rows: List[Row]
    common: Common
    folder: str
```

   다음으로 바꾼다.

```python
    rows: List[Row]
    common: Common
    folder: str
    terms: str = "ko"   # 엑셀 머리글 용어
```

6. `app/designer.py`에서 다음 부분을 찾아서

```python
    if not folder:
        raise ValueError("저장 폴더를 입력하세요")
```

   다음으로 바꾼다.

```python
    if not folder:
        raise ValueError("저장 폴더를 입력하세요")
    terms = body.get("terms") or "ko"
    if terms not in TERMS:
        raise ValueError("용어 설정 값이 올바르지 않습니다: %s" % terms)
```

7. `app/designer.py`에서 다음 부분을 찾아서

```python
    return DesignRequest(rows=rows, common=common, folder=os.path.expanduser(folder))
```

   다음으로 바꾼다.

```python
    return DesignRequest(rows=rows, common=common, folder=os.path.expanduser(folder), terms=terms)
```

8. `app/designer.py`에서 다음 부분을 찾아서

```python
                self._save(path, sheet, final=False)
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    self._save(path, sheet, final=True)
```

   다음으로 바꾼다.

```python
                self._save(path, sheet, request.terms, final=False)
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    self._save(path, sheet, request.terms, final=True)
```

9. `app/designer.py`에서 다음 부분을 찾아서

```python
            self._save(path, sheet, final=True)
            self._set(phase="stopped" if self._stop.is_set() else "done", current="")
```

   다음으로 바꾼다.

```python
            self._save(path, sheet, request.terms, final=True)
            self._set(phase="stopped" if self._stop.is_set() else "done", current="")
```

10. `app/designer.py`에서 다음 부분을 찾아서

```python
    def _save(self, path: str, sheet: List[list], final: bool):
        if not sheet:
            return
        try:
            write_workbook(path, sheet)
        except PermissionError:
            if not final:
                return  # 박사님이 파일을 열어 둠: 다음 저장 때 다시 시도한다
            path = path[:-len(".xlsx")] + "_2.xlsx"
            write_workbook(path, sheet)
```

   다음으로 바꾼다.

```python
    def _save(self, path: str, sheet: List[list], terms: str, final: bool):
        if not sheet:
            return
        try:
            write_workbook(path, sheet, terms)
        except PermissionError:
            if not final:
                return  # 박사님이 파일을 열어 둠: 다음 저장 때 다시 시도한다
            path = path[:-len(".xlsx")] + "_2.xlsx"
            write_workbook(path, sheet, terms)
```

11. `app/main.py`에서 다음 부분을 찾아서

```python
    def set_config():
        body = request.get_json(force=True)
        config.save(body)
        app.client.email = body.get("email", "")
        app.client.api_key = body.get("api_key", "")
        return jsonify(ok=True)
```

   다음으로 바꾼다.

```python
    def set_config():
        config.save(request.get_json(force=True))
        # 받은 값에 없는 항목(예: 용어만 저장)이 키를 지우지 않도록 저장된 값으로 맞춘다
        settings = config.load()
        app.client.email = settings["email"]
        app.client.api_key = settings["api_key"]
        return jsonify(ok=True)
```

12. `app/static/primer.html`에서 다음 부분을 찾아서

```html
  nav { display: flex; gap: 16px; margin-bottom: 12px; font-size: 14px; }
```

   다음으로 바꾼다.

```html
  nav { display: flex; gap: 16px; margin-bottom: 12px; font-size: 14px; }
  header { display: flex; justify-content: space-between; align-items: center; }
```

13. `app/static/primer.html`에서 다음 부분을 찾아서

```html
<h1>프라이머 설계 (Primer-BLAST)</h1>
```

   다음으로 바꾼다.

```html
<header>
  <h1>프라이머 설계 (Primer-BLAST)</h1>
  <label>용어 <select id="terms"><option value="ko">한국어</option><option value="en">English</option></select></label>
</header>
```

14. `app/static/primer.html`에서 다음 부분을 찾아서

```html
  <div class="row">서열 번호 직접 입력 <input type="text" id="acc-input"
```

   다음으로 바꾼다.

```html
  <div class="row"><span data-term="accession">서열 번호</span> 직접 입력 <input type="text" id="acc-input"
```

15. `app/static/primer.html`에서 다음 부분을 찾아서

```html
  <div class="row">조각 길이 최소 <input type="text" id="product_min" class="num">
```

   다음으로 바꾼다.

```html
  <div class="row"><span data-term="product_size">조각 길이</span> 최소 <input type="text" id="product_min" class="num">
```

16. `app/static/primer.html`에서 다음 부분을 찾아서

```html
  <div class="row">녹는 온도 최소 <input type="text" id="tm_min" class="num">
```

   다음으로 바꾼다.

```html
  <div class="row"><span data-term="tm">녹는 온도</span> 최소 <input type="text" id="tm_min" class="num">
```

17. `app/static/primer.html`에서 다음 부분을 찾아서

```html
  <div class="row">후보 개수 <input type="text" id="num_return" class="num">
    생물종 <input type="text" id="organism"
```

   다음으로 바꾼다.

```html
  <div class="row"><span data-term="num_return">후보 개수</span> <input type="text" id="num_return" class="num">
    <span data-term="organism">생물종</span> <input type="text" id="organism"
```

18. `app/static/primer.html`에서 다음 부분을 찾아서

```html
    <thead><tr><th>서열 번호</th><th>구간 시작</th><th>구간 끝</th><th>앞쪽 프라이머</th><th>뒤쪽 프라이머</th><th>상태</th><th></th></tr></thead>
```

   다음으로 바꾼다.

```html
    <thead><tr><th data-term="accession">서열 번호</th><th data-term="range_start">구간 시작</th><th data-term="range_end">구간 끝</th>
      <th data-term="forward">앞쪽 프라이머</th><th data-term="reverse">뒤쪽 프라이머</th><th>상태</th><th></th></tr></thead>
```

19. `app/static/primer.html`에서 다음 부분을 찾아서

```html
const COMMON = ["product_min", "product_max", "tm_min", "tm_opt", "tm_max", "num_return", "organism"];
```

   다음으로 바꾼다.

```html
const COMMON = ["product_min", "product_max", "tm_min", "tm_opt", "tm_max", "num_return", "organism"];
// 전문 용어만 바꾼다. 버튼과 안내 문장은 한국어로 둔다.
const TERMS = {
  ko: { accession: "서열 번호", range_start: "구간 시작", range_end: "구간 끝", forward: "앞쪽 프라이머",
        reverse: "뒤쪽 프라이머", product_size: "조각 길이", tm: "녹는 온도", num_return: "후보 개수", organism: "생물종" },
  en: { accession: "Accession", range_start: "Range from", range_end: "Range to", forward: "Forward primer",
        reverse: "Reverse primer", product_size: "PCR product size", tm: "Primer Tm", num_return: "# of primers to return",
        organism: "Organism" },
};
```

20. `app/static/primer.html`에서 다음 부분을 찾아서

```html
// ---- 설정
async function loadConfig() {
  const c = await api("/api/config");
  COMMON.forEach(k => { $(k).value = c[k]; });
```

   다음으로 바꾼다.

```html
// ---- 설정
function applyTerms(lang) {
  const key = lang === "en" ? "en" : "ko";
  document.querySelectorAll("[data-term]").forEach(el => { el.textContent = TERMS[key][el.dataset.term]; });
  $("terms").value = key;
}
$("terms").onchange = () => { applyTerms($("terms").value); postJson("/api/config", { terms: $("terms").value }).catch(report); };
async function loadConfig() {
  const c = await api("/api/config");
  applyTerms(c.terms);
  COMMON.forEach(k => { $(k).value = c[k]; });
```

21. `app/static/primer.html`에서 다음 부분을 찾아서

```html
  postJson("/api/design", { rows, common, folder: $("folder").value.trim() })
```

   다음으로 바꾼다.

```html
  postJson("/api/design", { rows, common, folder: $("folder").value.trim(), terms: $("terms").value })
```

- [ ] **Step 4: 통과를 확인한다**

Run: `.venv/bin/python -m pytest -q`
Expected: 121 passed, 1 skipped

- [ ] **Step 5: README에 안내를 넣는다**

1. `README.md`에서 다음 부분을 찾아서

```markdown
6. 끝나면 저장 폴더에 `primers_날짜_시각.xlsx`가 생깁니다. 도중에 **중단**해도 끝난 서열의 결과는 남습니다.
```

   다음으로 바꾼다.

```markdown
6. 끝나면 저장 폴더에 `primers_날짜_시각.xlsx`가 생깁니다. 도중에 **중단**해도 끝난 서열의 결과는 남습니다.

화면 오른쪽 위 **용어**에서 English를 고르면 전문 용어(서열 번호, 구간, 프라이머, 조각 길이, 녹는 온도, 후보 개수, 생물종)가
Primer-BLAST 웹사이트와 같은 영어(Accession, Range, Forward/Reverse primer, PCR product size, Tm 등)로 바뀌고,
엑셀 머리글과 시트 이름도 영어로 저장됩니다. 버튼과 안내 문장은 한국어 그대로이며, 고른 값은 다음에도 유지됩니다.
```

- [ ] **Step 6: 화면을 확인한다 (사이트 접속 없음)**

Task 7 Step 5의 가짜 서버로 띄우고 확인한다.
- 오른쪽 위 `용어`를 English로 바꾸면 칸 이름과 표 머리글이 Accession, Range from/to, Forward/Reverse primer, PCR product size, Primer Tm, # of primers to return, Organism으로 바뀌고, 버튼과 안내 문장은 한국어로 남는다.
- 새로고침해도 English가 유지되고, 설정 파일의 `terms`가 `"en"`이다.
- 설계 시작 → 저장된 엑셀의 시트 이름이 `Results`, 머리글이 `HEADERS_EN`과 같다. 메모 칸 내용("후보 없음" 등)은 한국어다.
- 한국어로 되돌리면 용어가 원래대로 돌아오고 `terms`가 `"ko"`로 저장된다.

- [ ] **Step 7: 커밋한다**

```bash
git add app/config.py app/designer.py app/main.py app/static/primer.html README.md tests/test_config.py tests/test_designer.py tests/test_main.py
git commit -m "feat: 2단계 화면과 엑셀의 전문 용어를 한국어/영어로 전환하는 설정 추가

설정 저장 경로가 받은 값에 없는 이메일·API 키를 지우던 문제도 함께 고침.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

