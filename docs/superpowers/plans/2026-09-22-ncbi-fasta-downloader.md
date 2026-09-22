# NCBI 서열 내려받기 도구 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 검색어로 NCBI Nucleotide를 검색해 목록에서 고르거나 상위 N건 또는 전체를 FASTA 파일로 저장하는 로컬 웹 도구를 만든다.

**Architecture:** Flask 서버(`app/main.py`)가 HTML 한 장(`app/static/index.html`)을 띄우고, JSON 요청을 받아 NCBI 통신 모듈(`app/ncbi.py`)과 백그라운드 저장 작업(`app/downloader.py`)을 호출한다. NCBI 접근은 공식 E-utilities만 쓰고 웹페이지는 절대 긁지 않는다. 설정은 저장소 루트의 `config.json`에 둔다.

**Tech Stack:** Python 3.9+, Flask ≥ 2.0, requests, pytest (개발용). 화면은 바닐라 HTML/JavaScript.

설계 문서: `docs/superpowers/specs/2026-09-22-ncbi-fasta-downloader-design.md`

## Global Constraints

- Python 3.9 이상에서 동작해야 한다 (`match` 문, `X | Y` 타입 표기 금지. `typing.Optional`, `List` 사용).
- 실행 의존성은 `flask`, `requests` 두 개뿐이다. 다른 패키지를 추가하지 않는다.
- NCBI 웹페이지(`www.ncbi.nlm.nih.gov/...`)에는 어떤 자동 요청도 보내지 않는다. `eutils.ncbi.nlm.nih.gov` 만 쓴다.
- 자동 테스트는 NCBI에 실제 접속하지 않는다. 실제 접속 테스트는 `NCBI_LIVE=1` 환경 변수일 때만 돈다.
- 모든 NCBI 요청에 `tool=primer-design-automation` 을 붙인다. 요청 간격: 키 없음 1/3초, 키 있음 1/10초.
- efetch 한 번에 번호 200개까지, esearch 한 페이지 10,000건까지.
- 포트 8765, 호스트 127.0.0.1.
- 파일 이름: 항목별 `<고유번호>.txt`, 합본 `combined.fasta`. 파일명 허용 문자 `[A-Za-z0-9._-]`, 나머지는 `_`.
- 화면과 오류 메시지는 한국어. 코드 주석과 커밋 메시지도 한국어(기존 커밋 관례).
- 파일 쓰기는 `encoding="utf-8", newline="\n"` 으로 통일한다 (Windows에서도 원문 그대로).
- 테스트 실행 명령: `.venv/bin/python -m pytest -q` (저장소 루트에서).
- 각 Task 끝에 커밋한다. 커밋 메시지 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` 줄을 붙인다.

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `requirements.txt` | 실행 의존성 |
| `requirements-dev.txt` | pytest |
| `pytest.ini` | 저장소 루트를 import 경로에 추가 |
| `.gitignore` | `.venv/`, `config.json`, `__pycache__/` |
| `app/__init__.py` | 빈 파일 (패키지 표시) |
| `app/ncbi.py` | `NcbiClient`: esearch/esummary/efetch 호출, 속도 제한, 재시도 |
| `app/downloader.py` | `split_fasta`, `safe_filename`, `JobRequest`, `Downloader`(스레드, 상태) |
| `app/config.py` | `config.json` 읽기/쓰기 |
| `app/main.py` | Flask 앱, 요청 경로 8개, 포트 확인, 브라우저 열기 |
| `app/static/index.html` | 화면 |
| `run_mac.command`, `run_windows.bat` | 더블클릭 실행 |
| `README.md` | 박사님용 안내 |
| `tests/test_ncbi.py`, `tests/test_downloader.py`, `tests/test_config.py`, `tests/test_main.py` | 자동 테스트 |

---

### Task 1: 프로젝트 골격과 NCBI 통신 모듈

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `.gitignore`, `app/__init__.py`
- Create: `app/ncbi.py`
- Test: `tests/test_ncbi.py`

**Interfaces:**
- Produces:
  - `app.ncbi.NcbiError(Exception)`
  - `app.ncbi.FETCH_BATCH = 200`, `app.ncbi.SEARCH_PAGE_MAX = 10000`
  - `app.ncbi.NcbiClient(email: str = "", api_key: str = "")`
    - 속성 `email`, `api_key` (설정 변경 시 직접 바꿔 씀), `session` (requests.Session, 테스트에서 교체), `_sleep` (time.sleep, 테스트에서 교체)
    - `search(term: str, start: int = 0, size: int = 20) -> Tuple[int, List[str]]`
    - `summaries(ids: List[str]) -> List[dict]`  각 dict: `{"uid", "accession", "title", "length"}`
    - `fetch_fasta(ids: List[str]) -> str`  (len(ids) > 200 이면 ValueError)

- [ ] **Step 1: 골격 파일 만들기**

`requirements.txt`:
```
flask>=2.0
requests>=2.25
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=7
```

`pytest.ini`:
```ini
[pytest]
pythonpath = .
testpaths = tests
```

`.gitignore`:
```
.venv/
config.json
__pycache__/
*.pyc
.pytest_cache/
```

`app/__init__.py`: 빈 파일.

개발용 가상환경 준비:
```bash
cd /Users/park/dev/primer-design-automation
python3 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt
```
Expected: 오류 없이 끝남. `.venv/bin/python -c "import flask, requests, pytest"` 가 조용히 성공.

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/test_ncbi.py`:
```python
import os

import pytest
import requests

from app.ncbi import FETCH_BATCH, NcbiClient, NcbiError


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        return self._json


class FakeSession:
    """준비된 응답을 순서대로 돌려주고, 받은 요청을 기록한다. 예외 객체가 들어 있으면 던진다."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        return self._next(url, params)

    def post(self, url, data=None, timeout=None):
        return self._next(url, data)

    def _next(self, url, params):
        self.calls.append((url, params))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_client(responses, email="", api_key=""):
    client = NcbiClient(email=email, api_key=api_key)
    client.session = FakeSession(responses)
    client.sleeps = []
    client._sleep = client.sleeps.append
    return client


SEARCH_JSON = {"esearchresult": {"count": "25497", "idlist": ["1", "2", "3"]}}


def test_search_parses_count_and_ids():
    client = make_client([FakeResponse(json_data=SEARCH_JSON)])
    assert client.search("sars-cov-2 whole genome", 0, 3) == (25497, ["1", "2", "3"])
    url, params = client.session.calls[0]
    assert url == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    assert params["db"] == "nucleotide"
    assert params["term"] == "sars-cov-2 whole genome"
    assert params["retstart"] == 0 and params["retmax"] == 3 and params["retmode"] == "json"


def test_every_request_carries_tool_email_and_key():
    client = make_client([FakeResponse(json_data=SEARCH_JSON)], email="a@b.c", api_key="KEY")
    client.search("x", 0, 1)
    params = client.session.calls[0][1]
    assert params["tool"] == "primer-design-automation"
    assert params["email"] == "a@b.c"
    assert params["api_key"] == "KEY"


def test_email_and_key_omitted_when_empty():
    client = make_client([FakeResponse(json_data=SEARCH_JSON)])
    client.search("x", 0, 1)
    params = client.session.calls[0][1]
    assert "email" not in params and "api_key" not in params


def test_search_error_field_raises():
    client = make_client([FakeResponse(json_data={"esearchresult": {"ERROR": "Empty term"}})])
    with pytest.raises(NcbiError, match="Empty term"):
        client.search("", 0, 1)


def test_summaries_parses_fields():
    data = {"result": {
        "uids": ["10", "11"],
        "10": {"uid": "10", "accessionversion": "LR881868.1", "title": "A", "slen": 29903},
        "11": {"uid": "11", "accessionversion": "MW1.1", "title": "B", "slen": 100},
    }}
    client = make_client([FakeResponse(json_data=data)])
    assert client.summaries(["10", "11"]) == [
        {"uid": "10", "accession": "LR881868.1", "title": "A", "length": 29903},
        {"uid": "11", "accession": "MW1.1", "title": "B", "length": 100},
    ]
    url, params = client.session.calls[0]
    assert url.endswith("esummary.fcgi")
    assert params["id"] == "10,11" and params["retmode"] == "json"


def test_summaries_empty_list_makes_no_request():
    client = make_client([])
    assert client.summaries([]) == []
    assert client.session.calls == []


def test_fetch_fasta_returns_text():
    client = make_client([FakeResponse(text=">A\nACGT\n")])
    assert client.fetch_fasta(["1", "2"]) == ">A\nACGT\n"
    url, params = client.session.calls[0]
    assert url.endswith("efetch.fcgi")
    assert params["id"] == "1,2"
    assert params["rettype"] == "fasta" and params["retmode"] == "text"


def test_fetch_fasta_rejects_more_than_batch():
    client = make_client([])
    with pytest.raises(ValueError):
        client.fetch_fasta(["1"] * (FETCH_BATCH + 1))


def test_retries_then_succeeds():
    client = make_client([
        FakeResponse(status_code=429),
        FakeResponse(status_code=503),
        requests.ConnectionError(),
        FakeResponse(json_data=SEARCH_JSON),
    ])
    assert client.search("x", 0, 3)[0] == 25497
    assert len(client.session.calls) == 4
    assert [s for s in client.sleeps if s >= 2] == [2, 4, 8]


def test_gives_up_after_three_retries():
    client = make_client([FakeResponse(status_code=503)] * 4)
    with pytest.raises(NcbiError, match="응답이 없습니다"):
        client.search("x", 0, 3)
    assert len(client.session.calls) == 4


def test_client_error_raises_immediately():
    client = make_client([FakeResponse(status_code=400)])
    with pytest.raises(NcbiError, match="400"):
        client.search("x", 0, 3)
    assert len(client.session.calls) == 1


def test_throttle_keeps_requests_a_third_of_a_second_apart():
    client = make_client([FakeResponse(json_data=SEARCH_JSON)] * 3)
    for _ in range(3):
        client.search("x", 0, 3)
    waits = [s for s in client.sleeps if s < 2]
    assert len(waits) == 2
    assert all(0.3 < w <= 1 / 3 for w in waits)


def test_throttle_is_a_tenth_of_a_second_with_api_key():
    client = make_client([FakeResponse(json_data=SEARCH_JSON)] * 2, api_key="KEY")
    client.search("x", 0, 3)
    client.search("x", 0, 3)
    assert len(client.sleeps) == 1
    assert 0.09 < client.sleeps[0] <= 0.1


@pytest.mark.skipif(not os.environ.get("NCBI_LIVE"), reason="NCBI_LIVE=1 일 때만 실제 접속")
def test_live_search_and_fetch():
    client = NcbiClient()
    count, ids = client.search("LR881868.1", 0, 1)
    assert count >= 1
    assert client.fetch_fasta(ids[:1]).startswith(">LR881868.1")
```

- [ ] **Step 3: 테스트가 실패하는지 확인**

Run: `.venv/bin/python -m pytest tests/test_ncbi.py -q`
Expected: `ModuleNotFoundError: No module named 'app.ncbi'` 로 수집 단계에서 실패.

- [ ] **Step 4: 구현**

`app/ncbi.py`:
```python
"""NCBI E-utilities 통신. 화면과 파일 저장은 모른다.

세 함수만 제공한다: 검색어 → 번호 목록, 번호 목록 → 요약, 번호 목록 → FASTA 텍스트.
NCBI 웹페이지(www.ncbi.nlm.nih.gov)는 정책상 스크립트 접근이 금지되어 있으므로 절대 쓰지 않는다.
"""
import time
from typing import List, Tuple

import requests

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
TOOL = "primer-design-automation"
DB = "nucleotide"
FETCH_BATCH = 200        # efetch 한 번에 보낼 번호 수
SEARCH_PAGE_MAX = 10000  # esearch 한 번에 받을 수 있는 번호 수
TIMEOUT = 60
RETRY_WAITS = (2, 4, 8)  # 재시도 전 대기 초


class NcbiError(Exception):
    """사람이 읽을 메시지를 담는다."""


class NcbiClient:
    def __init__(self, email: str = "", api_key: str = ""):
        self.email = email
        self.api_key = api_key
        self.session = requests.Session()
        self._last_request = 0.0
        self._sleep = time.sleep

    @property
    def min_interval(self) -> float:
        # 키 없음: 초당 3회, 키 있음: 초당 10회
        return 0.1 if self.api_key else 1 / 3

    def search(self, term: str, start: int = 0, size: int = 20) -> Tuple[int, List[str]]:
        resp = self._request("esearch.fcgi", {
            "term": term, "retstart": start, "retmax": size, "retmode": "json",
        })
        result = resp.json()["esearchresult"]
        if "ERROR" in result:
            raise NcbiError("검색 실패: " + result["ERROR"])
        return int(result["count"]), result["idlist"]

    def summaries(self, ids: List[str]) -> List[dict]:
        if not ids:
            return []
        resp = self._request("esummary.fcgi", {"id": ",".join(ids), "retmode": "json"}, post=True)
        result = resp.json()["result"]
        return [
            {
                "uid": uid,
                "accession": result[uid]["accessionversion"],
                "title": result[uid]["title"],
                "length": result[uid]["slen"],
            }
            for uid in result["uids"]
        ]

    def fetch_fasta(self, ids: List[str]) -> str:
        if len(ids) > FETCH_BATCH:
            raise ValueError("한 번에 %d개까지만 받을 수 있습니다" % FETCH_BATCH)
        resp = self._request("efetch.fcgi", {
            "id": ",".join(ids), "rettype": "fasta", "retmode": "text",
        }, post=True)
        return resp.text

    def _request(self, endpoint: str, params: dict, post: bool = False):
        params = {"db": DB, "tool": TOOL, **params}
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        url = BASE_URL + endpoint
        for wait in RETRY_WAITS + (None,):
            self._throttle()
            try:
                if post:
                    resp = self.session.post(url, data=params, timeout=TIMEOUT)
                else:
                    resp = self.session.get(url, params=params, timeout=TIMEOUT)
            except requests.RequestException:
                resp = None
            if resp is not None:
                if resp.status_code == 200:
                    return resp
                if resp.status_code != 429 and resp.status_code < 500:
                    raise NcbiError("NCBI가 요청을 거부했습니다 (HTTP %d)" % resp.status_code)
            if wait is None:
                raise NcbiError("NCBI 응답이 없습니다. 잠시 후 다시 시도하세요.")
            self._sleep(wait)

    def _throttle(self):
        remaining = self._last_request + self.min_interval - time.monotonic()
        if remaining > 0:
            self._sleep(remaining)
        self._last_request = time.monotonic()
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_ncbi.py -q`
Expected: `13 passed, 1 skipped`

- [ ] **Step 6: 실제 접속 테스트 1회**

Run: `NCBI_LIVE=1 .venv/bin/python -m pytest tests/test_ncbi.py -q -k live`
Expected: `1 passed` (요청 2번 나감). 실패하면 응답 형식을 확인해 `search`/`fetch_fasta`를 고친다.

- [ ] **Step 7: 커밋**

```bash
git add requirements.txt requirements-dev.txt pytest.ini .gitignore app/__init__.py app/ncbi.py tests/test_ncbi.py
git commit -m "feat: NCBI E-utilities 통신 모듈과 프로젝트 골격

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: FASTA 쪼개기와 파일명 정리

**Files:**
- Create: `app/downloader.py` (이 Task에서는 순수 함수 두 개만)
- Test: `tests/test_downloader.py`

**Interfaces:**
- Produces:
  - `app.downloader.split_fasta(text: str) -> List[Tuple[str, str]]`  각 항목 `(고유번호, 원문)`. 원문은 항상 `\n` 하나로 끝남.
  - `app.downloader.safe_filename(name: str) -> str`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_downloader.py`:
```python
from app.downloader import safe_filename, split_fasta

TWO = ">LR881868.1 Severe acute\nGGCT\nGCAT\n>MW1.1 title\nATTA\n\n"


def test_split_fasta_two_records():
    assert split_fasta(TWO) == [
        ("LR881868.1", ">LR881868.1 Severe acute\nGGCT\nGCAT\n"),
        ("MW1.1", ">MW1.1 title\nATTA\n"),
    ]


def test_split_fasta_single_record_without_trailing_newline():
    assert split_fasta(">A x\nACGT") == [("A", ">A x\nACGT\n")]


def test_split_fasta_empty():
    assert split_fasta("") == []


def test_safe_filename():
    assert safe_filename("LR881868.1") == "LR881868.1"
    assert safe_filename("a/b:c|d e") == "a_b_c_d_e"
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `.venv/bin/python -m pytest tests/test_downloader.py -q`
Expected: `ModuleNotFoundError: No module named 'app.downloader'`

- [ ] **Step 3: 구현**

`app/downloader.py`:
```python
"""FASTA 텍스트를 파일로 저장하는 백그라운드 작업."""
import re
from typing import List, Tuple


def split_fasta(text: str) -> List[Tuple[str, str]]:
    """FASTA 텍스트를 (고유번호, 항목 원문) 목록으로 나눈다. 원문은 줄바꿈 하나로 끝난다."""
    records = []
    current = []
    for line in text.splitlines(keepends=True):
        if line.startswith(">"):
            if current:
                records.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        records.append(current)
    result = []
    for lines in records:
        body = "".join(lines).rstrip("\n") + "\n"
        accession = body[1:].split()[0]
        result.append((accession, body))
    return result


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_downloader.py -q`
Expected: `4 passed`

- [ ] **Step 5: 커밋**

```bash
git add app/downloader.py tests/test_downloader.py
git commit -m "feat: FASTA 텍스트 쪼개기와 파일명 정리 함수

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: 다운로드 작업 (스레드, 상태, 저장)

**Files:**
- Modify: `app/downloader.py` (Task 2 내용 아래에 추가)
- Test: `tests/test_downloader.py` (아래 테스트 추가)

**Interfaces:**
- Consumes: `NcbiClient.search`, `NcbiClient.fetch_fasta`, `FETCH_BATCH`, `SEARCH_PAGE_MAX` (Task 1), `split_fasta`, `safe_filename` (Task 2)
- Produces:
  - `app.downloader.COMBINED_NAME = "combined.fasta"`
  - `app.downloader.JobRequest(folder: str, per_item: bool, combined: bool, ids: Optional[List[str]] = None, term: Optional[str] = None, limit: Optional[int] = None)`
  - `app.downloader.Downloader(client)`
    - `start(request: JobRequest) -> None`  (진행 중이면 `RuntimeError`)
    - `stop() -> None`
    - `is_running() -> bool`
    - `status() -> dict`  `{"phase", "total", "done", "missing", "folder", "message"}`
    - `wait() -> None`  (테스트용, 스레드 종료 대기)

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_downloader.py` 맨 위 import를 아래로 바꾸고, 파일 끝에 테스트를 추가한다.

```python
import threading

import pytest

from app.downloader import Downloader, JobRequest, safe_filename, split_fasta
from app.ncbi import NcbiError
```

파일 끝에 추가:
```python
class FakeClient:
    """search는 준비된 페이지를 순서대로, fetch_fasta는 묶음의 첫 번호로 찾은 텍스트를 돌려준다."""

    def __init__(self, fasta_by_first_id=None, pages=None):
        self.fasta_by_first_id = fasta_by_first_id or {}
        self.pages = list(pages or [])
        self.fetched = []
        self.searched = []

    def search(self, term, start, size):
        self.searched.append((term, start, size))
        return self.pages.pop(0)

    def fetch_fasta(self, ids):
        self.fetched.append(list(ids))
        return self.fasta_by_first_id.get(ids[0], "")


def run_job(client, tmp_path, per_item=True, combined=False, **kwargs):
    d = Downloader(client)
    d.start(JobRequest(folder=str(tmp_path / "out"), per_item=per_item, combined=combined, **kwargs))
    d.wait()
    return d, tmp_path / "out"


def test_initial_status_is_idle(tmp_path):
    assert Downloader(FakeClient()).status() == {
        "phase": "idle", "total": 0, "done": 0, "missing": 0, "folder": "", "message": "",
    }


def test_per_item_files(tmp_path):
    d, out = run_job(FakeClient({"1": TWO}), tmp_path, ids=["1", "2"])
    s = d.status()
    assert s["phase"] == "done" and s["total"] == 2 and s["done"] == 2 and s["missing"] == 0
    assert s["folder"] == str(out)
    assert (out / "LR881868.1.txt").read_text() == ">LR881868.1 Severe acute\nGGCT\nGCAT\n"
    assert (out / "MW1.1.txt").read_text() == ">MW1.1 title\nATTA\n"
    assert not (out / "combined.fasta").exists()


def test_combined_file_only(tmp_path):
    d, out = run_job(FakeClient({"1": TWO}), tmp_path, ids=["1", "2"], per_item=False, combined=True)
    assert (out / "combined.fasta").read_text() == ">LR881868.1 Severe acute\nGGCT\nGCAT\n>MW1.1 title\nATTA\n"
    assert not (out / "LR881868.1.txt").exists()


def test_batches_of_200_and_missing_count(tmp_path):
    ids = [str(i) for i in range(450)]
    client = FakeClient({"0": ">A\nA\n", "200": ">B\nB\n", "400": ">C\nC\n"})
    d, out = run_job(client, tmp_path, ids=ids)
    assert [len(b) for b in client.fetched] == [200, 200, 50]
    s = d.status()
    assert s["phase"] == "done" and s["done"] == 3 and s["missing"] == 447


def test_term_mode_collects_all_ids_in_pages(tmp_path):
    client = FakeClient({"1": TWO}, pages=[(3, ["1", "2"]), (3, ["3"])])
    d, out = run_job(client, tmp_path, term="x", limit=None)
    assert client.searched == [("x", 0, 10000), ("x", 2, 10000)]
    assert client.fetched == [["1", "2", "3"]]
    s = d.status()
    assert s["phase"] == "done" and s["total"] == 3 and s["done"] == 2 and s["missing"] == 1


def test_term_mode_with_limit(tmp_path):
    client = FakeClient({"1": TWO}, pages=[(25497, ["1", "2"])])
    d, out = run_job(client, tmp_path, term="x", limit=2)
    assert client.searched == [("x", 0, 2)]
    assert d.status()["total"] == 2


def test_stop_between_batches(tmp_path):
    started = threading.Event()
    release = threading.Event()

    class SlowClient(FakeClient):
        def fetch_fasta(self, ids):
            started.set()
            release.wait(5)
            return super().fetch_fasta(ids)

    client = SlowClient({"0": ">A\nA\n", "200": ">B\nB\n"})
    d = Downloader(client)
    d.start(JobRequest(folder=str(tmp_path / "out"), per_item=True, combined=False,
                       ids=[str(i) for i in range(400)]))
    assert started.wait(5)
    assert d.is_running()
    d.stop()
    release.set()
    d.wait()
    assert d.status()["phase"] == "stopped"
    assert len(client.fetched) == 1
    assert (tmp_path / "out" / "A.txt").exists()
    assert not d.is_running()


def test_error_keeps_files_and_reports(tmp_path):
    class FailSecond(FakeClient):
        def fetch_fasta(self, ids):
            if self.fetched:
                raise NcbiError("NCBI 응답이 없습니다. 잠시 후 다시 시도하세요.")
            return super().fetch_fasta(ids)

    d, out = run_job(FailSecond({"0": ">A\nA\n"}), tmp_path, ids=[str(i) for i in range(300)])
    s = d.status()
    assert s["phase"] == "error" and "응답이 없습니다" in s["message"]
    assert s["done"] == 1
    assert (out / "A.txt").exists()


def test_start_while_running_raises(tmp_path):
    release = threading.Event()

    class Blocking(FakeClient):
        def fetch_fasta(self, ids):
            release.wait(5)
            return ""

    d = Downloader(Blocking())
    req = JobRequest(folder=str(tmp_path / "out"), per_item=True, combined=False, ids=["1"])
    d.start(req)
    with pytest.raises(RuntimeError):
        d.start(req)
    release.set()
    d.wait()
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `.venv/bin/python -m pytest tests/test_downloader.py -q`
Expected: `ImportError: cannot import name 'Downloader'`

- [ ] **Step 3: 구현**

`app/downloader.py`의 import 부분을 아래로 바꾸고, 파일 끝에 클래스를 추가한다.

```python
"""FASTA 텍스트를 파일로 저장하는 백그라운드 작업."""
import os
import re
import threading
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.ncbi import FETCH_BATCH, SEARCH_PAGE_MAX

COMBINED_NAME = "combined.fasta"
```

파일 끝에 추가:
```python
@dataclass
class JobRequest:
    folder: str
    per_item: bool
    combined: bool
    ids: Optional[List[str]] = None   # 체크한 항목 모드
    term: Optional[str] = None        # 상위 N건 / 전체 모드
    limit: Optional[int] = None       # None이면 전체


class Downloader:
    """한 번에 작업 하나만 돌린다. 상태는 status()로 읽는다."""

    def __init__(self, client):
        self.client = client
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._state = {"phase": "idle", "total": 0, "done": 0, "missing": 0, "folder": "", "message": ""}

    def status(self) -> dict:
        with self._lock:
            return dict(self._state)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, request: JobRequest):
        if self.is_running():
            raise RuntimeError("이미 받는 중입니다")
        self._stop.clear()
        self._set(phase="collecting" if request.ids is None else "downloading",
                  total=0, done=0, missing=0, folder=request.folder, message="")
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

    def _run(self, request: JobRequest):
        try:
            ids = request.ids if request.ids is not None else self._collect_ids(request.term, request.limit)
            self._set(phase="downloading", total=len(ids), done=0)
            self._download(ids, request)
            self._set(phase="stopped" if self._stop.is_set() else "done")
        except Exception as exc:  # NcbiError, OSError 등: 이유를 화면에 보여 준다
            self._set(phase="error", message=str(exc))

    def _collect_ids(self, term: str, limit: Optional[int]) -> List[str]:
        ids = []
        start = 0
        while True:
            size = SEARCH_PAGE_MAX if limit is None else min(SEARCH_PAGE_MAX, limit - len(ids))
            count, page = self.client.search(term, start, size)
            ids.extend(page)
            target = count if limit is None else min(count, limit)
            self._set(total=target, done=len(ids))
            start += len(page)
            if not page or len(ids) >= target or self._stop.is_set():
                return ids

    def _download(self, ids: List[str], request: JobRequest):
        os.makedirs(request.folder, exist_ok=True)
        combined = None
        if request.combined:
            combined = open(os.path.join(request.folder, COMBINED_NAME), "w", encoding="utf-8", newline="\n")
        try:
            for i in range(0, len(ids), FETCH_BATCH):
                if self._stop.is_set():
                    return
                batch = ids[i:i + FETCH_BATCH]
                records = split_fasta(self.client.fetch_fasta(batch))
                for accession, text in records:
                    if request.per_item:
                        path = os.path.join(request.folder, safe_filename(accession) + ".txt")
                        with open(path, "w", encoding="utf-8", newline="\n") as f:
                            f.write(text)
                    if combined is not None:
                        combined.write(text)
                state = self.status()
                self._set(done=state["done"] + len(records),
                          missing=state["missing"] + len(batch) - len(records))
        finally:
            if combined is not None:
                combined.close()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_downloader.py -q`
Expected: `13 passed`

- [ ] **Step 5: 커밋**

```bash
git add app/downloader.py tests/test_downloader.py
git commit -m "feat: 백그라운드 다운로드 작업과 진행 상태

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: 설정 파일 모듈

**Files:**
- Create: `app/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `app.config.CONFIG_PATH` (저장소 루트의 `config.json` 절대 경로)
  - `app.config.DEFAULTS = {"email": "", "api_key": "", "per_item": True, "combined": False}`
  - `app.config.load(path: Optional[str] = None) -> dict`
  - `app.config.save(config: dict, path: Optional[str] = None) -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_config.py`:
```python
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
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: `ImportError: cannot import name 'config' from 'app'`

- [ ] **Step 3: 구현**

`app/config.py`:
```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: `4 passed`

- [ ] **Step 5: 커밋**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: 설정 파일 읽기/쓰기

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Flask 서버

**Files:**
- Create: `app/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `NcbiClient`, `NcbiError` (Task 1), `Downloader`, `JobRequest` (Task 3), `config.load/save` (Task 4)
- Produces:
  - `app.main.create_app(client=None, downloader=None) -> Flask`  (앱 객체에 `app.client`, `app.downloader` 속성)
  - `app.main.HOST = "127.0.0.1"`, `app.main.PORT = 8765`, `app.main.DOWNLOADS_DIR`
  - `app.main.main()`  (`python -m app.main` 진입점)
  - HTTP 경로: 설계 문서 7절 표와 같음

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_main.py`:
```python
import pytest

from app.main import create_app
from app.ncbi import NcbiError


class FakeClient:
    email = ""
    api_key = ""

    def search(self, term, start, size):
        return 2, ["10", "11"]

    def summaries(self, ids):
        return [{"uid": i, "accession": "A" + i, "title": "t", "length": 5} for i in ids]

    def fetch_fasta(self, ids):
        return ""


class FakeDownloader:
    def __init__(self, running=False):
        self.running = running
        self.started = []
        self.stopped = False

    def is_running(self):
        return self.running

    def start(self, req):
        self.started.append(req)

    def status(self):
        return {"phase": "idle", "total": 0, "done": 0, "missing": 0, "folder": "", "message": ""}

    def stop(self):
        self.stopped = True


def make(tmp_path, monkeypatch, client=None, downloader=None):
    monkeypatch.setattr("app.config.CONFIG_PATH", str(tmp_path / "config.json"))
    app = create_app(client=client or FakeClient(), downloader=downloader or FakeDownloader())
    app.testing = True
    return app


@pytest.fixture
def web(tmp_path, monkeypatch):
    return make(tmp_path, monkeypatch).test_client()


def test_index_serves_html(web):
    r = web.get("/")
    assert r.status_code == 200
    assert b"<html" in r.data


def test_search_returns_count_and_items(web):
    r = web.get("/api/search?term=x&start=0&size=2")
    assert r.status_code == 200
    assert r.get_json() == {"count": 2, "items": [
        {"uid": "10", "accession": "A10", "title": "t", "length": 5},
        {"uid": "11", "accession": "A11", "title": "t", "length": 5},
    ]}


def test_search_requires_term(web):
    assert web.get("/api/search?term=%20").status_code == 400


def test_download_requires_save_option(web):
    r = web.post("/api/download", json={"folder": "/x", "per_item": False, "combined": False, "ids": ["1"]})
    assert r.status_code == 400
    assert "저장 방식" in r.get_json()["error"]


def test_download_requires_folder(web):
    r = web.post("/api/download", json={"folder": "", "per_item": True, "combined": False, "ids": ["1"]})
    assert r.status_code == 400


def test_download_requires_ids_or_term(web):
    r = web.post("/api/download", json={"folder": "/x", "per_item": True, "combined": False})
    assert r.status_code == 400


def test_download_starts_job_and_expands_home(web):
    r = web.post("/api/download", json={"folder": "~/x", "per_item": True, "combined": False, "term": "q", "limit": 5})
    assert r.status_code == 200 and r.get_json() == {"ok": True}
    job = web.application.downloader.started[0]
    assert job.term == "q" and job.limit == 5 and job.ids is None
    assert job.per_item is True and job.combined is False
    assert not job.folder.startswith("~")


def test_download_rejected_while_running(tmp_path, monkeypatch):
    app = make(tmp_path, monkeypatch, downloader=FakeDownloader(running=True))
    r = app.test_client().post("/api/download", json={"folder": "/x", "per_item": True, "combined": False, "ids": ["1"]})
    assert r.status_code == 409


def test_status_and_stop(web):
    assert web.get("/api/status").get_json()["phase"] == "idle"
    assert web.post("/api/stop").status_code == 200
    assert web.application.downloader.stopped is True


def test_ncbi_error_becomes_502(tmp_path, monkeypatch):
    class Failing(FakeClient):
        def search(self, term, start, size):
            raise NcbiError("NCBI 응답이 없습니다. 잠시 후 다시 시도하세요.")

    app = make(tmp_path, monkeypatch, client=Failing())
    r = app.test_client().get("/api/search?term=x")
    assert r.status_code == 502
    assert "응답이 없습니다" in r.get_json()["error"]


def test_config_roundtrip_updates_client(web):
    r = web.post("/api/config", json={"email": "a@b.c", "api_key": "K", "per_item": False, "combined": True})
    assert r.status_code == 200
    data = web.get("/api/config").get_json()
    assert data["email"] == "a@b.c" and data["api_key"] == "K"
    assert data["per_item"] is False and data["combined"] is True
    assert data["downloads_dir"].endswith("ncbi_fasta")
    assert web.application.client.email == "a@b.c" and web.application.client.api_key == "K"


def test_open_folder_rejects_missing_folder(web):
    r = web.post("/api/open-folder", json={"folder": "/definitely/not/here"})
    assert r.status_code == 400
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `.venv/bin/python -m pytest tests/test_main.py -q`
Expected: `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: 구현**

`app/main.py`:
```python
"""로컬 웹 서버. 화면 요청을 받아 ncbi / downloader / config 모듈을 호출한다.

실행: python -m app.main  →  http://127.0.0.1:8765 가 브라우저에 열린다.
"""
import os
import socket
import subprocess
import sys
import threading
import webbrowser

from flask import Flask, jsonify, request, send_from_directory

from app import config
from app.downloader import Downloader, JobRequest
from app.ncbi import NcbiClient, NcbiError

HOST = "127.0.0.1"
PORT = 8765
DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "ncbi_fasta")


def create_app(client=None, downloader=None):
    app = Flask(__name__, static_folder="static", static_url_path="")
    settings = config.load()
    app.client = client or NcbiClient(settings["email"], settings["api_key"])
    app.downloader = downloader or Downloader(app.client)

    @app.errorhandler(NcbiError)
    def ncbi_error(exc):
        return jsonify(error=str(exc)), 502

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/search")
    def search():
        term = request.args.get("term", "").strip()
        if not term:
            return jsonify(error="검색어를 입력하세요"), 400
        start = request.args.get("start", 0, type=int)
        size = request.args.get("size", 50, type=int)
        count, ids = app.client.search(term, start, size)
        return jsonify(count=count, items=app.client.summaries(ids))

    @app.post("/api/download")
    def download():
        body = request.get_json(force=True)
        if not (body.get("per_item") or body.get("combined")):
            return jsonify(error="저장 방식을 하나 이상 선택하세요"), 400
        if not body.get("folder"):
            return jsonify(error="저장 폴더를 입력하세요"), 400
        if body.get("ids") is None and not body.get("term"):
            return jsonify(error="받을 항목이 없습니다"), 400
        if app.downloader.is_running():
            return jsonify(error="이미 받는 중입니다. 끝나거나 중단한 뒤 다시 시도하세요."), 409
        app.downloader.start(JobRequest(
            folder=os.path.expanduser(body["folder"]),
            per_item=bool(body.get("per_item")),
            combined=bool(body.get("combined")),
            ids=body.get("ids"),
            term=body.get("term"),
            limit=body.get("limit"),
        ))
        return jsonify(ok=True)

    @app.get("/api/status")
    def status():
        return jsonify(app.downloader.status())

    @app.post("/api/stop")
    def stop():
        app.downloader.stop()
        return jsonify(ok=True)

    @app.get("/api/config")
    def get_config():
        return jsonify(downloads_dir=DOWNLOADS_DIR, **config.load())

    @app.post("/api/config")
    def set_config():
        body = request.get_json(force=True)
        config.save(body)
        app.client.email = body.get("email", "")
        app.client.api_key = body.get("api_key", "")
        return jsonify(ok=True)

    @app.post("/api/open-folder")
    def open_folder():
        folder = request.get_json(force=True).get("folder", "")
        if not os.path.isdir(folder):
            return jsonify(error="폴더가 없습니다: " + folder), 400
        if sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        elif sys.platform == "win32":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder])
        return jsonify(ok=True)

    return app


def port_in_use() -> bool:
    with socket.socket() as s:
        return s.connect_ex((HOST, PORT)) == 0


def main():
    url = "http://%s:%d" % (HOST, PORT)
    if port_in_use():
        print("이미 실행 중입니다. 브라우저를 엽니다:", url)
        webbrowser.open(url)
        return
    threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    print("서버를 시작합니다:", url, " (이 창을 닫으면 종료됩니다)")
    create_app().run(host=HOST, port=PORT, debug=False)


if __name__ == "__main__":
    main()
```

`test_index_serves_html`이 통과하려면 `app/static/index.html`이 있어야 한다. 이 Task에서는 임시로 최소 파일을 만든다(Task 6에서 교체):

`app/static/index.html`:
```html
<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><title>NCBI 서열 내려받기</title></head>
<body>준비 중</body></html>
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/bin/python -m pytest -q`
Expected: `42 passed, 1 skipped` (전체 실행: ncbi 13+1skip, downloader 13, config 4, main 12)

- [ ] **Step 5: 서버가 실제로 뜨는지 확인**

Run (백그라운드로 띄우고 3초 뒤 확인):
```bash
.venv/bin/python -m app.main & sleep 3; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/; curl -s "http://127.0.0.1:8765/api/config"; kill %1
```
Expected: `200` 과 `{"api_key":"","combined":false,"downloads_dir":"/Users/.../Downloads/ncbi_fasta","email":"","per_item":true}`. 브라우저 탭이 자동으로 열린다.

- [ ] **Step 6: 커밋**

```bash
git add app/main.py app/static/index.html tests/test_main.py
git commit -m "feat: Flask 서버와 API 경로

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: 화면 (index.html)

**Files:**
- Modify: `app/static/index.html` (전체 교체)

**Interfaces:**
- Consumes: Task 5의 HTTP 경로 8개. 응답 형식은 설계 문서 7절.

자동 테스트는 없다(브라우저 화면). Step 3의 손 확인이 통과 기준이다.

- [ ] **Step 1: 화면 작성**

`app/static/index.html` 전체:
```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NCBI 서열 내려받기</title>
<style>
  body { font-family: -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif; max-width: 960px; margin: 24px auto; padding: 0 16px; color: #222; }
  header { display: flex; justify-content: space-between; align-items: center; }
  h1 { font-size: 20px; margin: 0; }
  section { margin-top: 16px; padding: 12px 16px; border: 1px solid #ddd; border-radius: 6px; }
  input[type=text], input[type=number] { padding: 6px 8px; font-size: 14px; }
  #term { width: 70%; }
  #folder { width: 85%; }
  button { padding: 6px 12px; font-size: 14px; cursor: pointer; }
  button:disabled { cursor: default; opacity: .5; }
  #error { display: none; background: #fde8e8; color: #a00; padding: 10px 14px; border-radius: 6px; margin-top: 12px; }
  #settings { display: none; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  td, th { text-align: left; padding: 4px 6px; border-bottom: 1px solid #eee; font-size: 14px; vertical-align: top; }
  td.len { text-align: right; white-space: nowrap; }
  .toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
  .actions { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; margin-top: 12px; }
  .row { margin-top: 8px; }
  progress { width: 100%; height: 18px; }
  .hint { color: #666; font-size: 13px; }
</style>
</head>
<body>
<header>
  <h1>NCBI 서열 내려받기</h1>
  <button id="toggle-settings">⚙ 설정</button>
</header>
<div id="error"></div>

<section id="settings">
  <div class="row">이메일 <input type="text" id="email" size="40" placeholder="NCBI에 알릴 연락처 (선택)"></div>
  <div class="row">API 키 <input type="text" id="api_key" size="40" placeholder="없어도 됨. 있으면 3배 빠름"></div>
  <div class="row"><button id="save-settings">저장</button> <span class="hint">발급 방법은 README에 있습니다.</span></div>
</section>

<section>
  <input type="text" id="term" placeholder="예: sars-cov-2 whole genome">
  <button id="search">검색</button>
</section>

<section id="results" style="display:none">
  <div class="toolbar">
    <span>결과 <b id="count">0</b>건</span>
    <span>페이지당
      <select id="page-size"><option>20</option><option selected>50</option><option>100</option><option>200</option></select>
      <button id="prev">◀</button> <span id="page-label">1 / 1</span> <button id="next">▶</button>
    </span>
  </div>
  <table>
    <thead><tr>
      <th><label><input type="checkbox" id="select-page"> 이 페이지 전체 선택</label></th>
      <th>고유번호</th><th>제목</th><th>길이</th>
    </tr></thead>
    <tbody id="rows"></tbody>
  </table>
  <div class="actions">
    <button id="dl-selected">선택한 0건 받기</button>
    <span>상위 <input type="number" id="top-n" value="100" min="1" style="width:80px">건 <button id="dl-top">받기</button></span>
    <button id="dl-all">전체 받기</button>
  </div>
</section>

<section>
  <div class="row">저장 폴더 <input type="text" id="folder"></div>
  <div class="row">
    <label><input type="checkbox" id="per_item"> 항목별 파일로 저장</label>
    <label style="margin-left:16px"><input type="checkbox" id="combined"> 합본 파일로 저장</label>
    <span id="save-hint" class="hint" style="margin-left:16px"></span>
  </div>
  <div id="progress-box" class="row" style="display:none">
    <progress id="progress" value="0" max="1"></progress>
    <div><span id="progress-label"></span> <button id="stop">중단</button></div>
  </div>
  <div id="result-box" class="row" style="display:none">
    <span id="result-label"></span> <button id="open-folder">폴더 열기</button>
  </div>
</section>

<script>
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const state = { term: "", count: 0, page: 0, items: [], selected: new Set(), running: false, folder: "", config: {} };

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
  state.config = await api("/api/config");
  $("email").value = state.config.email;
  $("api_key").value = state.config.api_key;
  $("per_item").checked = state.config.per_item;
  $("combined").checked = state.config.combined;
  updateButtons();
}
function saveConfig() {
  return postJson("/api/config", {
    email: $("email").value.trim(), api_key: $("api_key").value.trim(),
    per_item: $("per_item").checked, combined: $("combined").checked,
  });
}
$("toggle-settings").onclick = () => { const s = $("settings"); s.style.display = s.style.display === "block" ? "none" : "block"; };
$("save-settings").onclick = () => saveConfig().then(() => { $("settings").style.display = "none"; }).catch(report);
$("per_item").onchange = $("combined").onchange = () => { updateButtons(); saveConfig().catch(report); };

// ---- 검색과 목록
function pageSize() { return Number($("page-size").value); }
function slug(term) { return term.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 50); }
function today() { return new Date().toISOString().slice(0, 10); }

async function search() {
  const term = $("term").value.trim();
  if (!term) return;
  if (term !== state.term) { state.selected.clear(); state.page = 0; }
  state.term = term;
  await loadPage();
  $("folder").value = state.config.downloads_dir + "/" + slug(term) + "_" + today();
}
async function loadPage() {
  const size = pageSize();
  const data = await api("/api/search?" + new URLSearchParams({ term: state.term, start: state.page * size, size }));
  state.count = data.count;
  state.items = data.items;
  renderList();
}
function renderList() {
  const pages = Math.max(1, Math.ceil(state.count / pageSize()));
  $("results").style.display = "block";
  $("count").textContent = state.count.toLocaleString();
  $("page-label").textContent = (state.page + 1) + " / " + pages.toLocaleString();
  $("prev").disabled = state.page === 0;
  $("next").disabled = state.page >= pages - 1;
  $("rows").innerHTML = state.items.map(it => `
    <tr><td><input type="checkbox" data-uid="${esc(it.uid)}" ${state.selected.has(it.uid) ? "checked" : ""}></td>
    <td>${esc(it.accession)}</td><td>${esc(it.title)}</td><td class="len">${Number(it.length).toLocaleString()}</td></tr>`).join("");
  $("rows").querySelectorAll("input").forEach(cb => {
    cb.onchange = () => { cb.checked ? state.selected.add(cb.dataset.uid) : state.selected.delete(cb.dataset.uid); updateButtons(); };
  });
  $("select-page").checked = state.items.length > 0 && state.items.every(it => state.selected.has(it.uid));
  $("dl-all").textContent = "전체 " + state.count.toLocaleString() + "건 받기";
  updateButtons();
}
$("search").onclick = () => search().catch(report);
$("term").onkeydown = e => { if (e.key === "Enter") $("search").click(); };
$("page-size").onchange = () => { state.page = 0; loadPage().catch(report); };
$("prev").onclick = () => { state.page--; loadPage().catch(report); };
$("next").onclick = () => { state.page++; loadPage().catch(report); };
$("select-page").onchange = () => {
  state.items.forEach(it => $("select-page").checked ? state.selected.add(it.uid) : state.selected.delete(it.uid));
  renderList();
};

// ---- 받기
function updateButtons() {
  const canSave = $("per_item").checked || $("combined").checked;
  $("save-hint").textContent = canSave ? "" : "저장 방식을 하나 이상 선택하세요";
  const blocked = state.running || !canSave || !state.term;
  $("dl-selected").textContent = "선택한 " + state.selected.size + "건 받기";
  $("dl-selected").disabled = blocked || state.selected.size === 0;
  $("dl-top").disabled = blocked || state.count === 0;
  $("dl-all").disabled = blocked || state.count === 0;
}
function startDownload(extra) {
  const body = { folder: $("folder").value.trim(), per_item: $("per_item").checked, combined: $("combined").checked, ...extra };
  $("result-box").style.display = "none";
  postJson("/api/download", body).then(() => { state.running = true; updateButtons(); poll(); }).catch(report);
}
$("dl-selected").onclick = () => startDownload({ ids: [...state.selected] });
$("dl-top").onclick = () => {
  const n = Math.min(Math.max(1, Number($("top-n").value) || 1), state.count);
  $("top-n").value = n;
  startDownload({ term: state.term, limit: n });
};
$("dl-all").onclick = () => startDownload({ term: state.term, limit: null });
$("stop").onclick = () => postJson("/api/stop", {}).catch(report);
$("open-folder").onclick = () => postJson("/api/open-folder", { folder: state.folder }).catch(report);

// ---- 진행 상태 (1초마다 조회)
let pollTimer = null;
async function poll() {
  clearTimeout(pollTimer);
  let s;
  try { s = await api("/api/status"); } catch (e) { report(e); return; }
  state.running = s.phase === "collecting" || s.phase === "downloading";
  state.folder = s.folder;
  $("progress-box").style.display = state.running ? "block" : "none";
  if (state.running) {
    $("progress").max = Math.max(1, s.total);
    $("progress").value = s.done;
    $("progress-label").textContent = (s.phase === "collecting" ? "목록 수집 중 " : "받는 중 ")
      + s.done.toLocaleString() + " / " + s.total.toLocaleString();
    pollTimer = setTimeout(poll, 1000);
  } else if (s.phase !== "idle") {
    const saved = s.done.toLocaleString() + "건 저장됨 → " + s.folder;
    const missing = s.missing > 0 ? " (" + s.missing.toLocaleString() + "건은 NCBI에서 제공되지 않음)" : "";
    $("result-label").textContent =
      s.phase === "done" ? "완료: " + saved + missing :
      s.phase === "stopped" ? "중단됨: " + saved :
      s.done.toLocaleString() + "건까지 저장됨. 이후 실패: " + s.message;
    $("result-box").style.display = "block";
  }
  updateButtons();
}

loadConfig().then(poll).catch(report);
</script>
</body>
</html>
```

- [ ] **Step 2: 자동 테스트가 여전히 통과하는지 확인**

Run: `.venv/bin/python -m pytest -q`
Expected: `42 passed, 1 skipped`

- [ ] **Step 3: 브라우저에서 손 확인**

`.venv/bin/python -m app.main` 실행 후 열린 탭에서:

1. `sars-cov-2 whole genome` 입력 → Enter → "결과 25,497건" 안팎 표시, 50줄 목록, 저장 폴더 칸이 `.../ncbi_fasta/sars_cov_2_whole_genome_<오늘>` 로 채워짐.
2. 두 줄 체크 → ▶ 다음 페이지 → ◀ 이전 페이지 → 체크가 유지되고 버튼이 "선택한 2건 받기".
3. "항목별", "합본" 둘 다 끄면 받기 버튼 셋 다 비활성 + 안내 문구. 하나 켜면 복구.
4. `LR881868.1` 검색 → 1건 체크 → [선택한 1건 받기] → 진행 막대가 잠깐 보였다가 "완료: 1건 저장됨 → 경로" → [폴더 열기]로 Finder가 열리고 `LR881868.1.txt` 존재.
5. 상위 `100` 받기 → 완료 후 파일 100개. 합본 켜고 다시 받으면 `combined.fasta` 존재, `grep -c '^>' combined.fasta` 가 100.
6. 전체 받기 → "목록 수집 중" → "받는 중" → 몇 초 뒤 [중단] → "중단됨: N건 저장됨".
7. ⚙ 설정 → 이메일 입력 → 저장 → 서버 껐다 켜도 남아 있음 (`config.json` 생성 확인).

각 항목이 통과할 때까지 `index.html`을 고친다.

- [ ] **Step 4: 커밋**

```bash
git add app/static/index.html
git commit -m "feat: 검색·선택·받기 화면

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: 실행 파일, README, 완료 판정

**Files:**
- Create: `run_mac.command` (실행 권한 755), `run_windows.bat`, `README.md`

**Interfaces:**
- Consumes: `python -m app.main` (Task 5)

- [ ] **Step 1: 실행 파일 작성**

`run_mac.command`:
```bash
#!/bin/bash
# 더블클릭하면 서버를 띄우고 브라우저를 엽니다. 이 창을 닫으면 종료됩니다.
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "처음 실행: 필요한 구성 요소를 설치합니다 (30초쯤 걸립니다)..."
  python3 -m venv .venv || { echo "파이썬 3이 없습니다. README의 준비물 항목을 확인하세요."; read -r; exit 1; }
fi
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m app.main
```

`run_windows.bat`:
```bat
@echo off
rem 더블클릭하면 서버를 띄우고 브라우저를 엽니다. 이 창을 닫으면 종료됩니다.
cd /d "%~dp0"
if not exist .venv (
  echo 처음 실행: 필요한 구성 요소를 설치합니다 ^(30초쯤 걸립니다^)...
  py -3 -m venv .venv || python -m venv .venv || (echo 파이썬 3이 없습니다. README의 준비물 항목을 확인하세요. & pause & exit /b 1)
)
.venv\Scripts\pip install -q -r requirements.txt
.venv\Scripts\python -m app.main
pause
```

실행 권한:
```bash
chmod +x run_mac.command
git add run_mac.command && git ls-files -s run_mac.command
```
Expected: 출력 첫 열이 `100755`.

- [ ] **Step 2: Mac 실행 파일 확인**

Finder에서 `run_mac.command` 더블클릭 → 터미널 창이 뜨고 브라우저가 열림. 다시 더블클릭 → "이미 실행 중입니다" 출력 후 브라우저 탭만 열림. 터미널 창을 닫으면 서버 종료.

- [ ] **Step 3: README 작성**

`README.md`:
````markdown
# NCBI 서열 내려받기

NCBI 웹사이트에서 검색 → 항목 클릭 → FASTA → 저장을 반복하던 일을 대신해 주는 도구입니다.
검색어를 넣으면 결과 목록이 나오고, 원하는 항목을 골라서(또는 상위 N건, 전체) 한 번에 파일로 저장합니다.

이 도구는 NCBI가 프로그램용으로 공식 제공하는 창구(E-utilities)만 사용합니다. 웹사이트 화면을 자동으로
조작하지 않으므로 NCBI 이용 정책에 어긋나지 않습니다.

## 1. 준비물

- **파이썬 3.9 이상**. 설치 여부 확인:
  - Mac: 터미널에서 `python3 --version`
  - Windows: 명령 프롬프트에서 `py -3 --version`
  - `Python 3.9.x` 이상이 나오면 됩니다. 없으면 https://www.python.org/downloads/ 에서 설치합니다.
    Windows 설치 화면에서는 **"Add python.exe to PATH"** 를 반드시 체크합니다.
- 이 폴더 전체 (zip을 받았다면 압축을 풀어 둡니다).

## 2. 실행

- **Mac**: `run_mac.command` 를 더블클릭합니다.
  - 처음 열 때 "확인되지 않은 개발자" 경고가 뜨면: 파일을 **오른쪽 클릭 → 열기 → 열기**. 한 번만 하면 됩니다.
- **Windows**: `run_windows.bat` 를 더블클릭합니다.
  - "Windows의 PC 보호" 창이 뜨면 **추가 정보 → 실행**.

처음 실행은 필요한 구성 요소를 설치하느라 30초쯤 걸립니다. 이후에는 바로 뜹니다.
검은 창이 하나 뜨고 브라우저에 화면이 열립니다. **검은 창은 그대로 두세요.** 닫으면 종료됩니다.
브라우저가 열리지 않으면 주소창에 `http://127.0.0.1:8765` 를 입력합니다.

## 3. 사용법

1. 검색어를 입력하고 Enter. NCBI 웹사이트의 Nucleotide 검색과 같은 결과가 같은 순서로 나옵니다.
2. 받을 항목을 정합니다. 세 가지 중 하나:
   - 목록에서 체크 → **선택한 N건 받기** (페이지를 넘겨도 체크는 유지됩니다)
   - **상위 N건 받기**: 결과 순서대로 앞에서 N건
   - **전체 받기**: 검색 결과 전부 (수만 건이면 몇 분 걸립니다)
3. 저장 폴더를 확인합니다. 기본값은 `다운로드/ncbi_fasta/<검색어>_<날짜>` 이고 바꿀 수 있습니다.
4. 저장 방식을 고릅니다 (둘 다 켤 수 있습니다):
   - **항목별 파일로 저장**: 항목마다 `LR881868.1.txt` 처럼 고유번호 이름의 파일
   - **합본 파일로 저장**: 전부를 `combined.fasta` 한 파일에 이어서
5. 받기 버튼을 누르면 진행 막대가 나옵니다. 끝나면 **폴더 열기**로 바로 볼 수 있습니다.
   도중에 **중단**을 누르면 그때까지 받은 파일은 남습니다.

## 4. 설정 (⚙)

- **이메일**: NCBI가 문제 상황에서 연락할 주소입니다. 비워도 됩니다.
- **API 키**: 없어도 됩니다. 있으면 NCBI 요청 속도 제한이 초당 3회에서 10회로 늘어 큰 다운로드가 약 3배 빨라집니다. 발급은 무료이고 3분쯤 걸립니다:
  1. https://www.ncbi.nlm.nih.gov/account/ 에서 로그인 (Google, ORCID, 소속 기관 계정 등으로 로그인합니다)
  2. 오른쪽 위 사용자 이름 → **Account settings**
  3. 아래로 내려 **API Key Management** → **Create an API Key**
  4. 표시된 36자 문자열을 복사해 설정 칸에 붙여 넣고 **저장**

설정은 이 폴더의 `config.json` 에 저장됩니다. 이 파일은 남에게 보내지 마세요 (API 키가 들어 있습니다).

## 5. 저장되는 파일

FASTA 형식은 `>`로 시작하는 제목 줄 하나와 그 아래 서열 줄들로 된 텍스트입니다.
항목별 파일은 웹사이트에서 FASTA 링크를 눌렀을 때 보이는 내용과 같고, 합본 파일은 그것을 차례로 이어 붙인 것입니다.
NCBI가 요청한 항목 일부를 돌려주지 않는 경우(삭제·비공개 처리)가 간혹 있으며, 그때는 완료 문구에 "N건은 NCBI에서 제공되지 않음"이 표시됩니다.

## 6. 문제 해결

| 증상 | 조치 |
|---|---|
| "파이썬 3이 없습니다" | 1번 준비물대로 설치 후 다시 실행 |
| 브라우저가 안 열림 | 주소창에 `http://127.0.0.1:8765` 입력 |
| "NCBI 응답이 없습니다" | 인터넷 연결 확인 후 잠시 뒤 다시 시도. NCBI 서버가 잠시 바쁠 때도 납니다 |
| "이미 받는 중입니다" | 진행 중인 작업이 끝나거나 중단될 때까지 기다림 |
| Mac 보안 경고 | 파일 오른쪽 클릭 → 열기 |
| 폴더에 쓸 수 없음 | 저장 폴더 칸에 쓸 수 있는 다른 경로 입력 |

## 7. 프로젝트 구조와 이후 계획

이 도구는 **프라이머 설계 자동화의 1단계(서열 내려받기)** 입니다. 개발자의 개인적인 판단으로, 이후에
2단계(내려받은 서열로 프라이머 설계)와 3단계(설계한 프라이머 검증)가 필요하실 수 있다고 보고, 그때
기능을 덧붙이기 쉽도록 처음부터 역할별로 나눠 두었습니다.

```
app/
  ncbi.py        NCBI와 통신 (검색, 요약, FASTA 받기). 화면·파일과 무관해서 다음 단계에서 그대로 재사용
  downloader.py  받은 텍스트를 파일로 저장하고 진행 상태를 기록
  config.py      설정 파일 읽기/쓰기
  main.py        웹 서버. 화면 요청을 받아 위 모듈들을 호출
  static/index.html  화면
```

2단계를 붙일 때는 `app/primer.py` 같은 모듈과 화면 한 장을 추가하고 `main.py`에 요청 경로를 몇 개
등록하면 됩니다. 설계 문서는 `docs/superpowers/specs/` 에 있습니다.

## 8. 개발자용

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q              # NCBI에 접속하지 않는 테스트
NCBI_LIVE=1 .venv/bin/python -m pytest -q -k live   # 실제 접속 확인 (요청 2번)
```
````

- [ ] **Step 4: 완료 판정 체크리스트 실행**

설계 문서 12절의 체크리스트를 순서대로 수행하고 결과를 기록한다.

1. `sars-cov-2 whole genome` 검색 → 건수와 1페이지 순서가 웹사이트와 같다. **웹사이트 확인은 사람이 브라우저로 직접 한다** (프로그램으로 열지 않는다). 다르면 `app/ncbi.py`의 `search`에 `"sort"` 파라미터를 추가해 웹사이트 기본 정렬과 맞춘다.
2. `LR881868.1` 받기 → 파일 내용이 웹사이트 FASTA 텍스트와 같다: 웹에서 복사한 텍스트를 `expected.txt`로 저장한 뒤 `diff expected.txt ~/Downloads/ncbi_fasta/<폴더>/LR881868.1.txt` 가 빈 출력.
3. 상위 100건 → `ls <폴더>/*.txt | wc -l` 이 100. 합본 켜면 `grep -c '^>' <폴더>/combined.fasta` 가 100.
4. 전체 받기 → 완료. 걸린 시간과 `missing` 값을 기록.
5. 중단 → `stopped`, 파일 유지.
6. Wi-Fi 끄고 받기 → 빨간 띠에 "NCBI 응답이 없습니다".
7. `run_mac.command` 더블클릭 동작 (Step 2에서 확인).
8. Windows: 환경이 없어 박사님께 전달할 때 확인. README 2번 절차대로 안내.

- [ ] **Step 5: 커밋**

```bash
git add run_mac.command run_windows.bat README.md
git commit -m "feat: Mac/Windows 실행 파일과 README

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-Review 결과

- **설계 반영**: 2절 결정 사항(E-utilities만, Flask, 세 가지 받기, 두 저장 방식, 실행 파일, ID 경로 통일, 포트 8765) → Task 1·3·5·6·7. 5절 통신 규칙 → Task 1. 6절 작업 → Task 3. 7절 경로 8개 → Task 5. 8절 설정 → Task 4. 9절 화면 → Task 6. 10절 실행 파일, 13절 README → Task 7. 12절 테스트 → 각 Task의 테스트와 Task 7 Step 4.
- **설계와 다른 점 하나**: 설계 7절은 "설정 변경 시 `NcbiClient`를 다시 만든다"고 했으나, `Downloader`가 같은 객체를 참조하므로 다시 만들지 않고 `email`·`api_key` 속성을 바꾸는 방식으로 했다. `min_interval`을 속성(property)으로 두어 키 변경이 즉시 반영된다. 결과는 같다.
- **이름 일관성**: `NcbiClient.search/summaries/fetch_fasta`, `FETCH_BATCH`, `SEARCH_PAGE_MAX`, `split_fasta`, `safe_filename`, `JobRequest`, `Downloader.start/stop/status/is_running/wait`, `config.load/save/CONFIG_PATH`, `create_app` — 모든 Task에서 같은 이름을 쓴다. 상태 dict 키 6개(`phase,total,done,missing,folder,message`)는 Task 3·5·6에서 동일하다.
- **빈칸 없음**: 모든 코드 단계에 실제 코드가 있다.
