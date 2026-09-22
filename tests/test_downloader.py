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
