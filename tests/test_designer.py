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
