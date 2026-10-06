"""로컬 웹 서버. 화면 요청을 받아 ncbi / downloader / designer / config 모듈을 호출한다.

실행: python -m app.main  →  http://127.0.0.1:8765 가 브라우저에 열린다.
"""
import dataclasses
import json
import os
import socket
import subprocess
import sys
import threading
import urllib.request
import webbrowser

from flask import Flask, jsonify, request, send_from_directory

from app import config
from app.designer import Designer, accessions_in_folder, request_from_json
from app.downloader import Downloader, JobRequest
from app.ncbi import NcbiClient, NcbiError
from app.primerblast import PrimerBlastClient

HOST = "127.0.0.1"
PORT = 8765
DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "ncbi_fasta")


def create_app(client=None, downloader=None, designer=None):
    app = Flask(__name__, static_folder="static", static_url_path="")
    settings = config.load()
    app.client = client or NcbiClient(settings["email"], settings["api_key"])
    app.downloader = downloader or Downloader(app.client)
    app.designer = designer or Designer(PrimerBlastClient())

    @app.errorhandler(NcbiError)
    def ncbi_error(exc):
        return jsonify(error=str(exc)), 502

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/search")
    def search():
        term = request.args.get("term", "").strip()
        if not term:
            return jsonify(error="검색어를 입력하세요"), 400
        start = request.args.get("start", 0, type=int)
        size = request.args.get("size", 50, type=int)
        count, ids = app.client.search(term, start, size)
        return jsonify(count=count, items=app.client.summaries(ids))

    @app.post("/api/download")
    def download():
        body = request.get_json(force=True)
        if not (body.get("per_item") or body.get("combined")):
            return jsonify(error="저장 방식을 하나 이상 선택하세요"), 400
        if not body.get("folder"):
            return jsonify(error="저장 폴더를 입력하세요"), 400
        if body.get("ids") is None and not body.get("term"):
            return jsonify(error="받을 항목이 없습니다"), 400
        if app.downloader.is_running():
            return jsonify(error="이미 받는 중입니다. 끝나거나 중단한 뒤 다시 시도하세요."), 409
        app.downloader.start(JobRequest(
            folder=os.path.expanduser(body["folder"]),
            per_item=bool(body.get("per_item")),
            combined=bool(body.get("combined")),
            ids=body.get("ids"),
            term=body.get("term"),
            limit=body.get("limit"),
        ))
        return jsonify(ok=True)

    @app.get("/api/status")
    def status():
        return jsonify(app.downloader.status())

    @app.post("/api/stop")
    def stop():
        app.downloader.stop()
        return jsonify(ok=True)

    @app.get("/api/config")
    def get_config():
        return jsonify(downloads_dir=DOWNLOADS_DIR, **config.load())

    @app.post("/api/config")
    def set_config():
        config.save(request.get_json(force=True))
        # 받은 값에 없는 항목(예: 용어만 저장)이 키를 지우지 않도록 저장된 값으로 맞춘다
        settings = config.load()
        app.client.email = settings["email"]
        app.client.api_key = settings["api_key"]
        return jsonify(ok=True)

    @app.post("/api/open-folder")
    def open_folder():
        folder = request.get_json(force=True).get("folder", "")
        if not os.path.isdir(folder):
            return jsonify(error="폴더가 없습니다: " + folder), 400
        if sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        elif sys.platform == "win32":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder])
        return jsonify(ok=True)

    @app.get("/api/folder-accessions")
    def folder_accessions():
        folder = os.path.expanduser(request.args.get("folder", "").strip())
        if not os.path.isdir(folder):
            return jsonify(error="폴더가 없습니다: " + folder), 400
        return jsonify(accessions=accessions_in_folder(folder))

    @app.post("/api/design")
    def design():
        try:
            job = request_from_json(request.get_json(force=True))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        if app.designer.is_running():
            return jsonify(error="이미 설계 중입니다"), 409
        config.save({**dataclasses.asdict(job.common), "results_dir": job.folder})
        app.designer.start(job)
        return jsonify(ok=True)

    @app.get("/api/design/status")
    def design_status():
        return jsonify(app.designer.status())

    @app.post("/api/design/stop")
    def design_stop():
        app.designer.stop()
        return jsonify(ok=True)

    return app


PORT_TRIES = 10


def port_open(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex((HOST, port)) == 0


def is_our_app(port: int) -> bool:
    """그 포트에 떠 있는 것이 이 도구인지 확인한다. 다른 프로그램이면 False."""
    try:
        with urllib.request.urlopen("http://%s:%d/api/status" % (HOST, port), timeout=1) as resp:
            return "phase" in json.load(resp)
    except Exception:
        return False


def choose_port():
    """(쓸 포트, 이미 실행 중인지)를 돌려준다. 다른 프로그램이 쓰는 포트는 건너뛴다."""
    for port in range(PORT, PORT + PORT_TRIES):
        if not port_open(port):
            return port, False
        if is_our_app(port):
            return port, True
    raise SystemExit(
        "%d~%d 포트를 모두 다른 프로그램이 쓰고 있어 실행할 수 없습니다."
        % (PORT, PORT + PORT_TRIES - 1))


def main():
    port, already_running = choose_port()
    url = "http://%s:%d" % (HOST, port)
    if already_running:
        print("이미 실행 중입니다. 브라우저를 엽니다:", url)
        webbrowser.open(url)
        return
    if port != PORT:
        print("%d번 자리는 다른 프로그램이 쓰고 있어 %d번으로 엽니다." % (PORT, port))
    threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    print("서버를 시작합니다:", url, " (이 창을 닫으면 종료됩니다)")
    create_app().run(host=HOST, port=port, debug=False)


if __name__ == "__main__":
    main()
