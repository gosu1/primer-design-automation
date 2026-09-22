import threading

import pytest

from app.downloader import Downloader, JobRequest, safe_filename, split_fasta
from app.ncbi import NcbiError

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


class FakeClient:
    """search는 준비된 페이지를 순서대로, fetch_fasta는 묶음의 첫 번호로 찾은 텍스트를 돌려준다."""

    def __init__(self, fasta_by_first_id=None, pages=None):
        self.fasta_by_first_id = fasta_by_first_id or {}
        self.pages = list(pages or [])
        self.fetched = []
        self.searched = []

    def search(self, term, start, size):
        self.searched.append((term, start, size))
        return self.pages.pop(0)

    def fetch_fasta(self, ids):
        self.fetched.append(list(ids))
        return self.fasta_by_first_id.get(ids[0], "")


def run_job(client, tmp_path, per_item=True, combined=False, **kwargs):
    d = Downloader(client)
    d.start(JobRequest(folder=str(tmp_path / "out"), per_item=per_item, combined=combined, **kwargs))
    d.wait()
    return d, tmp_path / "out"


def test_initial_status_is_idle(tmp_path):
    assert Downloader(FakeClient()).status() == {
        "phase": "idle", "total": 0, "done": 0, "missing": 0, "folder": "", "message": "",
    }


def test_per_item_files(tmp_path):
    d, out = run_job(FakeClient({"1": TWO}), tmp_path, ids=["1", "2"])
    s = d.status()
    assert s["phase"] == "done" and s["total"] == 2 and s["done"] == 2 and s["missing"] == 0
    assert s["folder"] == str(out)
    assert (out / "LR881868.1.txt").read_text() == ">LR881868.1 Severe acute\nGGCT\nGCAT\n"
    assert (out / "MW1.1.txt").read_text() == ">MW1.1 title\nATTA\n"
    assert not (out / "combined.fasta").exists()


def test_combined_file_only(tmp_path):
    d, out = run_job(FakeClient({"1": TWO}), tmp_path, ids=["1", "2"], per_item=False, combined=True)
    assert (out / "combined.fasta").read_text() == ">LR881868.1 Severe acute\nGGCT\nGCAT\n>MW1.1 title\nATTA\n"
    assert not (out / "LR881868.1.txt").exists()


def test_batches_of_200_and_missing_count(tmp_path):
    ids = [str(i) for i in range(450)]
    client = FakeClient({"0": ">A\nA\n", "200": ">B\nB\n", "400": ">C\nC\n"})
    d, out = run_job(client, tmp_path, ids=ids)
    assert [len(b) for b in client.fetched] == [200, 200, 50]
    s = d.status()
    assert s["phase"] == "done" and s["done"] == 3 and s["missing"] == 447


def test_term_mode_collects_all_ids_in_pages(tmp_path):
    client = FakeClient({"1": TWO}, pages=[(3, ["1", "2"]), (3, ["3"])])
    d, out = run_job(client, tmp_path, term="x", limit=None)
    assert client.searched == [("x", 0, 10000), ("x", 2, 10000)]
    assert client.fetched == [["1", "2", "3"]]
    s = d.status()
    assert s["phase"] == "done" and s["total"] == 3 and s["done"] == 2 and s["missing"] == 1


def test_term_mode_with_limit(tmp_path):
    client = FakeClient({"1": TWO}, pages=[(25497, ["1", "2"])])
    d, out = run_job(client, tmp_path, term="x", limit=2)
    assert client.searched == [("x", 0, 2)]
    assert d.status()["total"] == 2


def test_stop_between_batches(tmp_path):
    started = threading.Event()
    release = threading.Event()

    class SlowClient(FakeClient):
        def fetch_fasta(self, ids):
            started.set()
            release.wait(5)
            return super().fetch_fasta(ids)

    client = SlowClient({"0": ">A\nA\n", "200": ">B\nB\n"})
    d = Downloader(client)
    d.start(JobRequest(folder=str(tmp_path / "out"), per_item=True, combined=False,
                       ids=[str(i) for i in range(400)]))
    assert started.wait(5)
    assert d.is_running()
    d.stop()
    release.set()
    d.wait()
    assert d.status()["phase"] == "stopped"
    assert len(client.fetched) == 1
    assert (tmp_path / "out" / "A.txt").exists()
    assert not d.is_running()


def test_error_keeps_files_and_reports(tmp_path):
    class FailSecond(FakeClient):
        def fetch_fasta(self, ids):
            if self.fetched:
                raise NcbiError("NCBI 응답이 없습니다. 잠시 후 다시 시도하세요.")
            return super().fetch_fasta(ids)

    d, out = run_job(FailSecond({"0": ">A\nA\n"}), tmp_path, ids=[str(i) for i in range(300)])
    s = d.status()
    assert s["phase"] == "error" and "응답이 없습니다" in s["message"]
    assert s["done"] == 1
    assert (out / "A.txt").exists()


def test_start_while_running_raises(tmp_path):
    release = threading.Event()

    class Blocking(FakeClient):
        def fetch_fasta(self, ids):
            release.wait(5)
            return ""

    d = Downloader(Blocking())
    req = JobRequest(folder=str(tmp_path / "out"), per_item=True, combined=False, ids=["1"])
    d.start(req)
    with pytest.raises(RuntimeError):
        d.start(req)
    release.set()
    d.wait()
