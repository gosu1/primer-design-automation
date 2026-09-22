#!/bin/bash
# 더블클릭하면 서버를 띄우고 브라우저를 엽니다. 이 창을 닫으면 종료됩니다.
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "처음 실행: 필요한 구성 요소를 설치합니다 (30초쯤 걸립니다)..."
  python3 -m venv .venv || { echo "파이썬 3이 없습니다. README의 준비물 항목을 확인하세요."; read -r; exit 1; }
fi
.venv/bin/pip install -q --disable-pip-version-check -r requirements.txt
.venv/bin/python -m app.main
