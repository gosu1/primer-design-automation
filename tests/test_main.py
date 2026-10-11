import logging

import pytest

from app import config, main
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


class FakeDesigner:
    def __init__(self, running=False):
        self.running = running
        self.started = []
        self.stopped = False

    def is_running(self):
        return self.running

    def start(self, req):
        self.started.append(req)

    def status(self):
        return {"phase": "idle", "total": 0, "done": 0, "current": "", "rows": [], "file": "", "message": ""}

    def stop(self):
        self.stopped = True


def make(tmp_path, monkeypatch, client=None, downloader=None, designer=None, consent=True):
    monkeypatch.setattr("app.config.CONFIG_PATH", str(tmp_path / "config.json"))
    if consent:
        config.save({"stage2_consent": True})
    app = create_app(client=client or FakeClient(), downloader=downloader or FakeDownloader(),
                     designer=designer or FakeDesigner())
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


def fake_ports(monkeypatch, taken, ours):
    """taken: 열려 있는 포트들, ours: 그중 이 도구인 포트들."""
    monkeypatch.setattr(main, "port_open", lambda p: p in taken)
    monkeypatch.setattr(main, "is_our_app", lambda p: p in ours)


def test_uses_default_port_when_free(monkeypatch):
    fake_ports(monkeypatch, taken=set(), ours=set())
    assert main.choose_port() == (8765, False)


def test_reuses_port_when_our_app_is_already_running(monkeypatch):
    fake_ports(monkeypatch, taken={8765}, ours={8765})
    assert main.choose_port() == (8765, True)


def test_skips_port_held_by_another_program(monkeypatch):
    # 8765는 남의 프로그램, 8766은 비어 있음 → 8766으로 간다
    fake_ports(monkeypatch, taken={8765}, ours=set())
    assert main.choose_port() == (8766, False)


def test_skips_several_foreign_programs(monkeypatch):
    fake_ports(monkeypatch, taken={8765, 8766, 8767}, ours=set())
    assert main.choose_port() == (8768, False)


def test_our_app_behind_a_foreign_program_is_reused(monkeypatch):
    fake_ports(monkeypatch, taken={8765, 8766}, ours={8766})
    assert main.choose_port() == (8766, True)


def test_gives_up_when_every_port_is_foreign(monkeypatch):
    fake_ports(monkeypatch, taken=set(range(8765, 8775)), ours=set())
    with pytest.raises(SystemExit):
        main.choose_port()


def test_is_our_app_rejects_a_different_server(monkeypatch):
    class OtherServer:
        def read(self):
            return b"<html><title>\xed\x94\xbc\xec\x8a\xa4\xed\x92\x80</title></html>"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(main.urllib.request, "urlopen", lambda *a, **k: OtherServer())
    assert main.is_our_app(8765) is False


def test_is_our_app_accepts_our_status_response(monkeypatch):
    class OurServer:
        def read(self):
            return b'{"phase": "idle", "total": 0, "done": 0}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(main.urllib.request, "urlopen", lambda *a, **k: OurServer())
    assert main.is_our_app(8765) is True


def test_folder_accessions(web, tmp_path):
    (tmp_path / "NM_1.1.txt").write_text(">NM_1.1 one\nACGT\n")
    r = web.get("/api/folder-accessions", query_string={"folder": str(tmp_path)})
    assert r.status_code == 200 and r.get_json() == {"accessions": ["NM_1.1"]}


def test_folder_accessions_rejects_missing_folder(web):
    assert web.get("/api/folder-accessions?folder=/definitely/not/here").status_code == 400


DESIGN_BODY = {
    "rows": [{"accession": "NM_1", "start": "", "end": "", "left": "", "right": ""}],
    "common": {"product_min": "80", "product_max": "900", "tm_min": "57", "tm_opt": "61", "tm_max": "63",
               "num_return": "5", "organism": "Mus musculus"},
    "folder": "~/primers",
}


def test_design_starts_job_and_remembers_conditions(web):
    r = web.post("/api/design", json=DESIGN_BODY)
    assert r.status_code == 200 and r.get_json() == {"ok": True}
    job = web.application.designer.started[0]
    assert job.rows[0].accession == "NM_1" and job.common.product_min == 80
    assert not job.folder.startswith("~")
    saved = web.get("/api/config").get_json()
    assert saved["product_min"] == 80 and saved["tm_opt"] == 61.0 and saved["organism"] == "Mus musculus"
    assert saved["results_dir"] == job.folder


def test_design_rejects_bad_input(web):
    r = web.post("/api/design", json={**DESIGN_BODY, "rows": []})
    assert r.status_code == 400 and "서열이 없습니다" in r.get_json()["error"]


def test_design_rejected_while_running(tmp_path, monkeypatch):
    app = make(tmp_path, monkeypatch, designer=FakeDesigner(running=True))
    assert app.test_client().post("/api/design", json=DESIGN_BODY).status_code == 409


def test_design_status_and_stop(web):
    assert web.get("/api/design/status").get_json()["phase"] == "idle"
    assert web.post("/api/design/stop").status_code == 200
    assert web.application.designer.stopped is True


def test_primer_page_is_served(web):
    r = web.get("/primer.html")
    assert r.status_code == 200
    assert "프라이머 설계".encode() in r.data
    assert b"PCR product size" in r.data and "조각 길이".encode() in r.data
    assert b'id="terms"' not in r.data


def test_index_page_shows_site_terms_with_korean(web):
    r = web.get("/")
    assert b"Accession" in r.data and "고유번호".encode() in r.data


def test_saving_one_setting_keeps_client_key(web):
    web.post("/api/config", json={"email": "a@b.c", "api_key": "K", "per_item": True, "combined": False})
    assert web.post("/api/config", json={"combined": True}).status_code == 200
    assert web.get("/api/config").get_json()["combined"] is True
    assert web.application.client.email == "a@b.c" and web.application.client.api_key == "K"



def test_design_requires_stage2_consent(tmp_path, monkeypatch):
    web = make(tmp_path, monkeypatch, consent=False).test_client()
    r = web.post("/api/design", json=DESIGN_BODY)
    assert r.status_code == 403 and "동의" in r.get_json()["error"]
    assert web.application.designer.started == []
    web.post("/api/config", json={"stage2_consent": True})
    assert web.post("/api/design", json=DESIGN_BODY).status_code == 200


def test_primer_page_has_consent_box(web):
    r = web.get("/primer.html")
    assert b'id="consent"' in r.data and b'id="consent-check"' in r.data


def test_serve_hides_dev_server_messages(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "run_simple", lambda *a, **k: calls.append((a, k)))
    werkzeug_log = logging.getLogger("werkzeug")
    monkeypatch.setattr(werkzeug_log, "level", werkzeug_log.level)
    app = object()
    main.serve(app, 8799)
    assert calls == [(("127.0.0.1", 8799, app), {"threaded": True})]
    assert werkzeug_log.level == logging.ERROR


# ---- 1단계에서 받은 뒤 바로 프라이머 설계

def test_start_design_from_uses_last_conditions(tmp_path, monkeypatch):
    app = make(tmp_path, monkeypatch)
    config.save({"product_min": 80, "organism": "Mus musculus", "results_dir": str(tmp_path / "r")})
    app.start_design_from(["NM_1.1", "NM_2.1"])
    job = app.designer.started[0]
    assert [r.accession for r in job.rows] == ["NM_1.1", "NM_2.1"]
    assert job.common.product_min == 80 and job.common.organism == "Mus musculus"
    assert job.folder == str(tmp_path / "r")


def test_start_design_from_refuses_without_consent(tmp_path, monkeypatch):
    app = make(tmp_path, monkeypatch, consent=False)
    with pytest.raises(ValueError, match="동의"):
        app.start_design_from(["NM_1.1"])


def test_start_design_from_refuses_too_many(tmp_path, monkeypatch):
    app = make(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="50"):
        app.start_design_from(["NM_%d" % i for i in range(51)])


def test_start_design_from_refuses_while_running(tmp_path, monkeypatch):
    app = make(tmp_path, monkeypatch, designer=FakeDesigner(running=True))
    with pytest.raises(RuntimeError, match="이미 설계 중"):
        app.start_design_from(["NM_1.1"])


def test_real_downloader_hands_over_to_start_design(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.CONFIG_PATH", str(tmp_path / "config.json"))
    app = create_app(client=FakeClient(), designer=FakeDesigner())
    assert app.downloader.on_done == app.start_design_from


THEN_DESIGN = {"folder": "/x", "per_item": True, "combined": False, "then_design": True}


@pytest.mark.parametrize("extra, code, message", [
    ({"ids": ["1"] * 51}, 400, "50개"),
    ({"term": "q", "limit": None}, 400, "50개"),
    ({"term": "q", "limit": 51}, 400, "50개"),
])
def test_download_then_design_is_limited(web, extra, code, message):
    r = web.post("/api/download", json={**THEN_DESIGN, **extra})
    assert r.status_code == code and message in r.get_json()["error"]


def test_download_then_design_needs_consent(tmp_path, monkeypatch):
    web = make(tmp_path, monkeypatch, consent=False).test_client()
    assert web.post("/api/download", json={**THEN_DESIGN, "ids": ["1"]}).status_code == 403


def test_download_then_design_is_passed_to_job(web):
    assert web.post("/api/download", json={**THEN_DESIGN, "term": "q", "limit": 2}).status_code == 200
    assert web.application.downloader.started[0].then_design is True
