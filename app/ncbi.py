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
