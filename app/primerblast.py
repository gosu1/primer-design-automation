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
