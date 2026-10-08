#!/bin/bash
# 더블클릭하면 서버를 띄우고 브라우저를 엽니다. 이 창을 닫으면 종료됩니다.
cd "$(dirname "$0")"

# 파이썬 3.9 이상을 찾는다. 새 Mac의 /usr/bin/python3는 개발자 도구가 없으면 설치 창을 띄우므로,
# 다른 위치를 먼저 보고 /usr/bin/python3는 개발자 도구가 이미 있을 때만 쓴다.
find_python() {
  for py in "$(command -v python3)" /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
            /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if [ -n "$py" ] && [ "$py" != /usr/bin/python3 ] && [ -x "$py" ] \
       && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
      echo "$py"; return
    fi
  done
  if xcode-select -p >/dev/null 2>&1 && /usr/bin/python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    echo /usr/bin/python3
  fi
}

if [ ! -d .venv ]; then
  PY="$(find_python)"
  if [ -z "$PY" ]; then
    echo "파이썬 3.9 이상을 찾지 못했습니다."
    echo "곧 열리는 python.org 페이지에서 macOS용 파이썬을 내려받아 설치한 뒤, 이 파일을 다시 더블클릭해 주세요."
    open "https://www.python.org/downloads/macos/"
    read -r -p "Enter를 누르면 이 창이 닫힙니다."
    exit 1
  fi
  echo "처음 실행: 필요한 구성 요소를 설치합니다 (30초쯤 걸립니다)..."
  "$PY" -m venv .venv || { echo "구성 요소 설치에 실패했습니다. 사용설명서의 '문제가 생겼을 때'를 확인해 주세요."; read -r; exit 1; }
fi
.venv/bin/pip install -q --disable-pip-version-check -r requirements.txt
.venv/bin/python -m app.main
