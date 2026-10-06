import threading

import pytest
from openpyxl import load_workbook

from app import designer
from app.designer import (
    HEADERS, HEADERS_EN, MAX_ROWS, Designer, DesignRequest, accessions_in_folder, excel_rows, request_from_json,
    write_workbook,
)
from app.primerblast import Common, Outcome, Pair, Primer, PrimerBlastError, Row


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


def test_write_workbook_in_english(tmp_path):
    path = str(tmp_path / "r.xlsx")
    write_workbook(path, excel_rows(Row("NM_1"), found(1)), "en")
    book = load_workbook(path)
    assert book.sheetnames == ["Results"]
    values = list(book["Results"].values)
    assert list(values[0]) == HEADERS_EN and len(HEADERS_EN) == len(HEADERS)
    assert values[1][3] == "AAAA"


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
    assert req.terms == "ko"
    assert request_from_json({**GOOD, "terms": "en"}).terms == "en"


@pytest.mark.parametrize("change, message", [
    ({"rows": []}, "서열이 없습니다"),
    ({"rows": [{"accession": "A"}] * (MAX_ROWS + 1)}, "까지만"),
    ({"folder": " "}, "저장 폴더"),
    ({"rows": [{"accession": " "}]}, "빈 줄"),
    ({"rows": [{"accession": "NM_1", "start": "abc"}]}, "NM_1 구간 시작"),
    ({"common": {**GOOD["common"], "tm_opt": ""}}, "녹는 온도 적정"),
    ({"common": {**GOOD["common"], "product_min": "70.5"}}, "조각 길이 최소"),
    ({"terms": "fr"}, "용어 설정"),
])
def test_request_from_json_rejects(change, message):
    with pytest.raises(ValueError, match=message):
        request_from_json({**GOOD, **change})


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

    def locked(path, rows, terms="ko"):
        if not path.endswith("_2.xlsx"):
            raise PermissionError(path)
        real(path, rows, terms)

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


def test_excel_headers_follow_request_terms(tmp_path):
    d = Designer(FakeClient([found()]))
    d.between_jobs = 0
    d.start(DesignRequest(rows=[Row("NM_0")], common=Common(), folder=str(tmp_path), terms="en"))
    d.wait()
    book = load_workbook(d.status()["file"])
    assert book.sheetnames == ["Results"]
    assert list(next(book["Results"].values)) == HEADERS_EN
