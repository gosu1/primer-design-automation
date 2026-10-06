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
