import os

import pytest
import requests

from app.primerblast import (
    BASE_URL, JOB_TIMEOUT, POLL_INTERVAL, SUBMIT_URL, Common, Hit, PrimerBlastClient, PrimerBlastError, Row,
    build_fields, error_message, gene_symbol, job_key, page_kind, parse_form_defaults, parse_results,
    parse_review, pick_same_gene,
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
