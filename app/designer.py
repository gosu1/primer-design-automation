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


def write_workbook(path: str, rows: List[list], terms: str = "ko"):
    book = Workbook()
    sheet = book.active
    sheet.title = SHEET_TITLE_EN if terms == "en" else SHEET_TITLE
    sheet.append(HEADERS_EN if terms == "en" else HEADERS)
    for values in rows:
        sheet.append(values)
    sheet.freeze_panes = "A2"
    book.save(path)


@dataclass
class DesignRequest:
    rows: List[Row]
    common: Common
    folder: str
    terms: str = "ko"   # 엑셀 머리글 용어


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
    terms = body.get("terms") or "ko"
    if terms not in TERMS:
        raise ValueError("용어 설정 값이 올바르지 않습니다: %s" % terms)
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
    return DesignRequest(rows=rows, common=common, folder=os.path.expanduser(folder), terms=terms)


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
                self._save(path, sheet, request.terms, final=False)
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    self._save(path, sheet, request.terms, final=True)
                    self._set(phase="error", current="", message="연속으로 실패해 멈췄습니다. 사이트 상태를 확인하세요.")
                    return
            self._save(path, sheet, request.terms, final=True)
            self._set(phase="stopped" if self._stop.is_set() else "done", current="")
        except Exception as exc:  # OSError 등: 이유를 화면에 보여 준다
            self._set(phase="error", current="", message=str(exc))

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
        self._set(file=path)
