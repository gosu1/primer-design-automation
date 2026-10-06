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
