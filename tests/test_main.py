import pytest

from app.main import create_app
from app.ncbi import NcbiError


class FakeClient:
    email = ""
    api_key = ""

    def search(self, term, start, size):
        return 2, ["10", "11"]

    def summaries(self, ids):
        return [{"uid": i, "accession": "A" + i, "title": "t", "length": 5} for i in ids]

    def fetch_fasta(self, ids):
        return ""


class FakeDownloader:
    def __init__(self, running=False):
        self.running = running
        self.started = []
        self.stopped = False

    def is_running(self):
        return self.running

    def start(self, req):
        self.started.append(req)

    def status(self):
        return {"phase": "idle", "total": 0, "done": 0, "missing": 0, "folder": "", "message": ""}

    def stop(self):
        self.stopped = True


def make(tmp_path, monkeypatch, client=None, downloader=None):
    monkeypatch.setattr("app.config.CONFIG_PATH", str(tmp_path / "config.json"))
    app = create_app(client=client or FakeClient(), downloader=downloader or FakeDownloader())
    app.testing = True
    return app


@pytest.fixture
def web(tmp_path, monkeypatch):
    return make(tmp_path, monkeypatch).test_client()


def test_index_serves_html(web):
    r = web.get("/")
    assert r.status_code == 200
    assert b"<html" in r.data


def test_search_returns_count_and_items(web):
    r = web.get("/api/search?term=x&start=0&size=2")
    assert r.status_code == 200
    assert r.get_json() == {"count": 2, "items": [
        {"uid": "10", "accession": "A10", "title": "t", "length": 5},
        {"uid": "11", "accession": "A11", "title": "t", "length": 5},
    ]}


def test_search_requires_term(web):
    assert web.get("/api/search?term=%20").status_code == 400


def test_download_requires_save_option(web):
    r = web.post("/api/download", json={"folder": "/x", "per_item": False, "combined": False, "ids": ["1"]})
    assert r.status_code == 400
    assert "저장 방식" in r.get_json()["error"]


def test_download_requires_folder(web):
    r = web.post("/api/download", json={"folder": "", "per_item": True, "combined": False, "ids": ["1"]})
    assert r.status_code == 400


def test_download_requires_ids_or_term(web):
    r = web.post("/api/download", json={"folder": "/x", "per_item": True, "combined": False})
    assert r.status_code == 400


def test_download_starts_job_and_expands_home(web):
    r = web.post("/api/download", json={"folder": "~/x", "per_item": True, "combined": False, "term": "q", "limit": 5})
    assert r.status_code == 200 and r.get_json() == {"ok": True}
    job = web.application.downloader.started[0]
    assert job.term == "q" and job.limit == 5 and job.ids is None
    assert job.per_item is True and job.combined is False
    assert not job.folder.startswith("~")


def test_download_rejected_while_running(tmp_path, monkeypatch):
    app = make(tmp_path, monkeypatch, downloader=FakeDownloader(running=True))
    r = app.test_client().post("/api/download", json={"folder": "/x", "per_item": True, "combined": False, "ids": ["1"]})
    assert r.status_code == 409


def test_status_and_stop(web):
    assert web.get("/api/status").get_json()["phase"] == "idle"
    assert web.post("/api/stop").status_code == 200
    assert web.application.downloader.stopped is True


def test_ncbi_error_becomes_502(tmp_path, monkeypatch):
    class Failing(FakeClient):
        def search(self, term, start, size):
            raise NcbiError("NCBI 응답이 없습니다. 잠시 후 다시 시도하세요.")

    app = make(tmp_path, monkeypatch, client=Failing())
    r = app.test_client().get("/api/search?term=x")
    assert r.status_code == 502
    assert "응답이 없습니다" in r.get_json()["error"]


def test_config_roundtrip_updates_client(web):
    r = web.post("/api/config", json={"email": "a@b.c", "api_key": "K", "per_item": False, "combined": True})
    assert r.status_code == 200
    data = web.get("/api/config").get_json()
    assert data["email"] == "a@b.c" and data["api_key"] == "K"
    assert data["per_item"] is False and data["combined"] is True
    assert data["downloads_dir"].endswith("ncbi_fasta")
    assert web.application.client.email == "a@b.c" and web.application.client.api_key == "K"


def test_open_folder_rejects_missing_folder(web):
    r = web.post("/api/open-folder", json={"folder": "/definitely/not/here"})
    assert r.status_code == 400
