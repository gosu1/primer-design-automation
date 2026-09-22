"""FASTA 텍스트를 파일로 저장하는 백그라운드 작업."""
import os
import re
import threading
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.ncbi import FETCH_BATCH, SEARCH_PAGE_MAX

COMBINED_NAME = "combined.fasta"


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
