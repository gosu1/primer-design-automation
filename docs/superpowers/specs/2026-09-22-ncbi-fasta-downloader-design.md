# NCBI 서열 내려받기 도구 설계

작성일: 2026-09-22
상태: 승인됨 (브레인스토밍에서 항목별 확인 완료)

## 1. 목적과 배경

박사님(연구자)이 NCBI 웹사이트에서 손으로 반복하던 작업을 자동화한다.

현재 손으로 하는 흐름:
1. NCBI 홈페이지에서 검색 대상을 Nucleotide로 바꾼다.
2. 검색어(예: `sars-cov-2 whole genome`)를 입력한다.
3. 결과 항목을 하나씩 열어 FASTA 링크를 누른다.
4. 표시된 텍스트를 txt 파일로 저장한다.

이 도구는 프라이머 설계 자동화 프로젝트의 **1단계(서열 내려받기)** 다. 이후 2단계(프라이머 설계, Primer3)와 3단계(검증, BLAST+)를 붙이기 쉬운 구조로 만든다.

## 2. 핵심 결정 사항

| 결정 | 선택 | 이유 |
|---|---|---|
| NCBI 접근 방법 | 공식 E-utilities 사용. 웹페이지 스크래핑 금지 | NCBI 정책(KA-05510)이 웹페이지 스크립팅을 속도와 무관하게 금지하며, 적발 시 IP 단위(연구실 전체) 차단 가능. E-utilities는 같은 데이터를 텍스트로 돌려주는 공식 창구이며 구현도 훨씬 단순함 |
| 화면 형태 | 로컬 웹 페이지 (Flask + HTML 한 장) | 박사님이 익숙한 브라우저 화면, 설치 의존성 두 개(`flask`, `requests`)뿐, 이후 단계 화면을 추가하기 쉬움. Streamlit은 의존성이 크고 페이지 간 선택 상태 유지가 번거로워 제외 |
| 받을 범위 | 목록에서 체크 / 상위 N건 / 전체, 세 가지 모두 지원 | 사용자 요청 |
| 저장 형태 | 항목별 파일, 합본 파일을 설정 체크박스로 각각 켜고 끔 | 사용자 요청 |
| 전달 형태 | 파이썬 스크립트 + `run_mac.command` + `run_windows.bat` | 박사님 컴퓨터에 파이썬이 이미 설치되어 있음. 단일 실행 파일 포장(PyInstaller)은 필요해지면 나중에 추가 |
| 다운로드 경로 통일 | 세 가지 받기 방식 모두 "번호 목록 → 200개씩 efetch" 한 경로로 처리 | 코드 경로가 하나라서 테스트와 오류 처리가 단순함 |
| 포트 | 8765 | Flask 기본값 5000은 최근 Mac에서 AirPlay가 점유함 |

## 3. 범위

포함:
- 검색어 입력 → 결과 건수와 목록(고유번호·제목·서열 길이) 표시, 페이지 넘기기
- 체크한 항목 / 상위 N건 / 전체 받기
- 항목별 파일(`<고유번호>.txt`), 합본 파일(`combined.fasta`) 저장
- 진행률 표시, 중단, 완료 후 폴더 열기
- 설정: 이메일, NCBI API 키, 저장 방식 체크박스 상태 저장
- Mac / Windows 더블클릭 실행 파일
- README (박사님용 안내 + 확장 구조 설명)

제외:
- 프라이머 설계, 검증 (이후 단계)
- 단일 실행 파일 포장
- 검색 결과 정렬·필터 옵션 (NCBI 웹사이트 기본 순서만 따름)
- 다운로드 이력 관리

## 4. 폴더 구조

```
primer-design-automation/
├── README.md
├── requirements.txt          # flask, requests
├── requirements-dev.txt      # pytest
├── .gitignore                # .venv/, config.json, __pycache__/
├── run_mac.command
├── run_windows.bat
├── app/
│   ├── __init__.py
│   ├── main.py               # Flask 서버, 요청 경로, 브라우저 자동 열기
│   ├── ncbi.py               # E-utilities 통신 (화면·파일과 무관한 순수 파이썬)
│   ├── downloader.py         # 백그라운드 다운로드 작업, 파일 저장, 진행 상태
│   ├── config.py             # config.json 읽기/쓰기
│   └── static/
│       └── index.html        # 화면 (HTML + JavaScript, 파일 하나)
├── tests/
│   ├── test_ncbi.py
│   └── test_downloader.py
└── docs/superpowers/specs/   # 이 문서
```

각 모듈의 경계:
- `ncbi.py`는 파일 저장이나 화면을 모른다. 이후 단계에서 "이 번호의 서열을 가져와" 용도로 그대로 재사용한다.
- `downloader.py`는 `ncbi.py`가 돌려준 텍스트를 저장하고 진행 상태를 기록한다. HTTP를 모른다.
- `main.py`는 화면 요청을 받아 위 두 모듈을 호출한다.
- 2단계를 붙일 때는 `app/primer.py` 같은 모듈과 화면 한 장을 추가하고 `main.py`에 요청 경로를 등록한다.

## 5. NCBI 통신 모듈 (`app/ncbi.py`)

기본 주소: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`

### 5.1 클래스와 함수

```python
class NcbiError(Exception): ...          # 사람이 읽을 메시지를 담음

class NcbiClient:
    def __init__(self, email: str = "", api_key: str = "")
    def search(self, term: str, start: int, size: int) -> tuple[int, list[str]]
        # esearch.fcgi  db=nucleotide, term, retstart=start, retmax=size, retmode=json
        # 반환: (전체 건수, 이 페이지의 번호 목록)
    def summaries(self, ids: list[str]) -> list[dict]
        # esummary.fcgi  db=nucleotide, id=쉼표 목록, retmode=json  (POST)
        # 반환: [{"uid", "accession", "title", "length"}], accession은 accessionversion 필드, length는 slen
    def fetch_fasta(self, ids: list[str]) -> str
        # efetch.fcgi  db=nucleotide, id=쉼표 목록, rettype=fasta, retmode=text  (POST)
        # ids가 200개를 넘으면 ValueError
```

### 5.2 동작 규칙

- 모든 요청에 `tool=primer-design-automation` 을 붙인다. `email`, `api_key`는 값이 있을 때만 붙인다.
- 속도 제한: 요청 사이 최소 간격을 강제한다. 키 없음 1/3초, 키 있음 1/10초. 마지막 요청 시각을 기억해 부족한 만큼 `sleep`한다.
- 재시도: HTTP 429, 5xx, 연결 오류·시간 초과는 2초 → 4초 → 8초 대기 후 최대 3회 재시도. 그래도 실패하면 `NcbiError("NCBI 응답이 없습니다. 잠시 후 다시 시도하세요.")`. 그 외 4xx는 즉시 `NcbiError`.
- 요청 시간 제한(timeout): 60초.
- esearch 응답에 `ERROR` 필드가 있으면 `NcbiError`로 바꾼다.
- 정렬: esearch 기본 정렬을 쓴다. 구현 중 웹사이트 1페이지 순서와 비교해 다르면 `sort` 옵션을 웹사이트 기본과 맞춘다.
- 페이지 크기 상한: esearch `retmax` 상한(10,000)을 구현 중 실제로 확인하고, 전체 번호 수집 시 그 단위로 나눠 호출한다.

## 6. 다운로드 작업 (`app/downloader.py`)

### 6.1 작업 입력

```python
@dataclass
class JobRequest:
    folder: str                 # 저장 폴더 절대 경로 (없으면 생성)
    per_item: bool              # 항목별 파일 저장
    combined: bool              # 합본 파일 저장
    ids: list[str] | None       # 체크한 항목 모드
    term: str | None            # 상위 N건 / 전체 모드
    limit: int | None           # None이면 전체
```

`ids`와 `term` 중 하나만 채워진다. `per_item`, `combined`가 모두 거짓이면 작업을 시작하지 않는다(서버가 400으로 거부).

### 6.2 처리 순서

1. `term` 모드면 `phase=collecting`. `search`를 페이지 단위로 반복해 번호를 모은다. `limit`이 있으면 그만큼에서 끊는다. 이 동안 `done`은 모은 번호 수, `total`은 목표 수.
2. `phase=downloading`, `total`=번호 수, `done`=0.
3. 번호를 200개씩 잘라 `fetch_fasta` 호출.
4. 받은 텍스트를 `>` 줄 기준으로 항목으로 쪼갠다. 고유번호는 `>` 다음 첫 단어.
5. 항목마다: `per_item`이면 `<folder>/<고유번호>.txt`에 원문 그대로 저장(덮어쓰기). `combined`면 `<folder>/combined.fasta`에 이어 붙인다(작업 시작 때 새로 열고 끝날 때 닫음).
6. `done += 저장한 항목 수`, `missing += 요청 수 - 돌아온 수`.
7. 묶음마다 중단 요청을 확인한다. 요청이 있으면 `phase=stopped`로 끝낸다.
8. 모두 끝나면 `phase=done`.
9. 예외가 나면 `phase=error`, `message`에 이유. 저장한 파일은 남긴다.

### 6.3 상태

```python
{
  "phase": "idle" | "collecting" | "downloading" | "done" | "stopped" | "error",
  "total": int, "done": int, "missing": int,
  "folder": str, "message": str
}
```

- 작업은 `threading.Thread`에서 돈다. 동시에 하나만 허용한다.
- 중단은 `threading.Event`로 전달한다.
- 파일명은 `[A-Za-z0-9._-]` 외의 글자를 `_`로 바꾼다.
- FASTA 쪼개기와 파일명 정리는 순수 함수로 두어 단위 테스트한다.

## 7. 서버 (`app/main.py`)

| 경로 | 메서드 | 입력 | 출력 |
|---|---|---|---|
| `/` | GET | | `index.html` |
| `/api/search` | GET | `term`, `start`, `size` | `{count, items:[{uid, accession, title, length}]}` (`search` + `summaries`) |
| `/api/download` | POST | `JobRequest` JSON | `{ok: true}` / 409 진행 중 / 400 입력 오류 |
| `/api/status` | GET | | 6.3의 상태 |
| `/api/stop` | POST | | `{ok: true}` |
| `/api/config` | GET | | `{email, api_key, per_item, combined, downloads_dir}` |
| `/api/config` | POST | `{email, api_key, per_item, combined}` | `{ok: true}` |
| `/api/open-folder` | POST | `{folder}` | `{ok: true}` (Mac `open`, Windows `os.startfile`, Linux `xdg-open`) |

- `NcbiError`는 JSON `{error: "<메시지>"}` 와 502로 돌려준다. 그 밖의 예외는 500과 메시지.
- `downloads_dir`는 `~/Downloads/ncbi_fasta` 절대 경로. 화면이 여기에 `<검색어 slug>_<YYYY-MM-DD>`를 붙여 기본 저장 폴더를 만든다.
- 실행: `python -m app.main`. 시작 전에 8765 포트를 확인해 이미 열려 있으면 브라우저만 열고 종료한다. 아니면 1초 뒤 브라우저를 열고 `app.run(host="127.0.0.1", port=8765)`.
- 설정 변경 시 `NcbiClient`를 새 이메일·키로 다시 만든다.

## 8. 설정 (`app/config.py`)

- 파일: 저장소 루트의 `config.json`. git 제외.
- 필드와 기본값: `email=""`, `api_key=""`, `per_item=true`, `combined=false`.
- 파일이 없거나 깨져 있으면 기본값을 쓴다.

## 9. 화면 (`app/static/index.html`)

배치(위에서 아래로):

```
제목 · [⚙ 설정]
검색어 입력 [검색]
결과 N건 · 페이지당 [20/50/100/200] · ◀ p / P ▶
☐ 이 페이지 전체 선택
목록: ☐ 고유번호 · 제목 · 길이
[선택한 n건 받기]  상위 [N]건 [받기]  [전체 N건 받기]
저장 폴더 [경로]
☑ 항목별 파일로 저장  ☐ 합본 파일로 저장
진행 막대 · done / total · [중단]
완료 문구 · [폴더 열기]
오류 띠(빨강, 화면 상단)
설정 패널(펼침): 이메일, API 키, [저장]
```

동작:
- 검색: Enter 또는 버튼. 페이지 크기 기본 50. 페이지를 넘겨도 체크 상태는 `Set`으로 유지.
- 받기 버튼: 체크 0건이면 선택 버튼 비활성. 상위 N 기본 100, 건수 초과 시 건수로 맞춤. 두 저장 체크박스가 모두 꺼져 있으면 세 버튼 모두 비활성 + 안내 문구.
- 받기 누르면 `/api/download` 호출 후 1초마다 `/api/status` 조회. `phase`가 `collecting`/`downloading`이면 진행 막대 표시, 받기 버튼 비활성, 검색·목록은 계속 가능. 페이지를 열 때도 한 번 조회해 진행 중인 작업이 있으면 이어서 표시.
- 완료: "N건 저장됨 → 경로", `missing > 0`이면 "(m건은 NCBI에서 제공되지 않음)". [폴더 열기].
- 중단: `stopped` 표시와 저장 건수.
- 오류: `error` phase의 `message` 또는 API 오류 응답을 빨간 띠로. 다음 요청 성공 시 띠 제거.
- 설정 저장: `/api/config` POST. 저장 체크박스 변경도 즉시 저장.
- 문구는 한국어.

## 10. 실행 파일

`run_mac.command`:
```bash
#!/bin/bash
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m app.main
```

`run_windows.bat`:
```bat
@echo off
cd /d "%~dp0"
if not exist .venv py -3 -m venv .venv
.venv\Scripts\pip install -q -r requirements.txt
.venv\Scripts\python -m app.main
pause
```

- `run_mac.command`는 실행 권한(755)으로 커밋한다.
- Mac 보안 경고("확인되지 않은 개발자") 대처: 오른쪽 클릭 → 열기. README에 적는다.

## 11. 오류 처리 요약

| 상황 | 처리 |
|---|---|
| NCBI 일시 오류(429, 5xx, 네트워크) | 3회 재시도 후 `NcbiError` → 화면 빨간 띠 |
| 검색어 오류 등 4xx | 즉시 `NcbiError` |
| 폴더 생성·쓰기 실패 | 작업 `error`, 메시지에 경로와 이유 |
| 저장 체크박스 모두 꺼짐 | 화면에서 버튼 비활성, 서버는 400 |
| 작업 진행 중 새 작업 요청 | 409, 화면 안내 |
| 포트 8765 사용 중 | 브라우저만 열고 종료 |
| 요청 건수보다 적게 돌아옴 | `missing` 집계, 완료 문구에 표시 |

## 12. 테스트와 완료 판정

자동 테스트(`pytest`, NCBI에 실제 접속하지 않음. `requests.Session`을 가짜로 바꿔 응답을 흉내 냄):

- `test_ncbi.py`: 요청 파라미터에 `tool`/이메일/키가 붙는지, 요청 간격이 지켜지는지(`sleep`을 가짜로 바꿔 기록), 429·5xx 재시도 후 성공, 계속 실패 시 `NcbiError`, 4xx 즉시 `NcbiError`, `search`/`summaries` 응답 해석, `fetch_fasta` 200개 초과 거부
- `test_downloader.py`: FASTA 쪼개기(2건, 끝 빈 줄, 1건, 빈 문자열), 항목별 파일 이름·내용, 합본 파일 순서, 중단 후 `stopped`와 파일 유지, `missing` 집계, 통신 오류 시 `error`와 파일 유지, 파일명 정리
- 실제 접속 테스트 1개(`NCBI_LIVE=1` 환경 변수일 때만): 검색 1회 + `LR881868.1` 받기 1회

완료 판정 체크리스트(손으로 확인):

1. `sars-cov-2 whole genome` 검색 → 건수와 1페이지 순서가 웹사이트와 같다.
2. `LR881868.1` 하나 받기 → `LR881868.1.txt`가 웹사이트 FASTA 텍스트와 글자 단위로 같다.
3. 상위 100건 → 파일 100개, 합본 켜면 `combined.fasta`에 `>` 줄 100개.
4. 전체 받기 → 정상 완료, 걸린 시간 기록, `missing` 표시 확인.
5. 받는 도중 중단 → `stopped`, 파일 유지.
6. 네트워크 끊고 받기 → 빨간 오류 띠.
7. Mac에서 `run_mac.command` 더블클릭 → 브라우저 열림, 검색 동작.
8. Windows에서 `run_windows.bat` 더블클릭 → 같은 동작. (Windows 환경이 없어 박사님께 전달할 때 함께 확인)

## 13. README 구성

박사님이 읽는 문서. 전문용어 없이 쓴다.

1. 이 도구가 하는 일
2. 준비물: 파이썬 3.9 이상 확인 방법, 폴더 받는 방법
3. 실행: Mac / Windows 더블클릭, 보안 경고 대처, 종료 방법
4. 사용법: 검색 → 고르기 / 상위 N건 / 전체 → 저장 폴더·저장 방식 → 받기 → 폴더 열기
5. 설정: 이메일, API 키 발급 절차(NCBI 계정 → Account settings → API Key Management → Create an API Key), 키가 없어도 되는 이유(초당 3회 → 10회)
6. 저장되는 파일: 항목별 파일과 합본 파일
7. 문제 해결: 브라우저가 안 열림, NCBI 응답 없음, 파이썬 없음, 보안 경고
8. 프로젝트 구조와 이후 계획: 이 도구는 프라이머 설계 자동화의 1단계이며, 개발자의 개인적인 판단으로 이후 2단계(프라이머 설계)·3단계(검증)가 필요할 수 있다고 보고 화면·NCBI 통신·저장 작업을 분리해 다음 단계를 붙이기 쉬운 구조로 만들었다는 설명과 폴더 구조 표
9. 개발자용: 테스트 실행 방법, 모듈별 역할

## 14. 전달

개발 완료 후 GitLab `ml-study-lab/harness-engineering`에 올린다. 저장소 루트인지 하위 폴더인지는 push 직전에 확인한다. 박사님께는 저장소 링크 또는 zip으로 전달한다.
