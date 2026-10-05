# Primer-BLAST 자동 제출 도구 설계 (2단계)

작성일: 2026-10-06
상태: 승인됨 (브레인스토밍에서 항목별 확인 완료)

## 1. 목적과 배경

박사님이 NCBI Primer-BLAST 웹사이트(https://www.ncbi.nlm.nih.gov/tools/primer-blast/)에서 손으로 하던 작업을 자동화한다.

현재 손으로 하는 흐름:
1. PCR Template 칸에 서열 번호(또는 서열)를 넣는다.
2. 필요하면 구간, 직접 설계한 프라이머, 조각 길이, 녹는 온도, 생물종을 바꾼다.
3. "Get Primers"를 누르고 기다린다. 비슷한 서열 확인 화면이 나오면 허용할 서열을 고르고 다시 제출한다.
4. 결과 페이지에서 프라이머 쌍을 읽어 옮겨 적는다.

이 도구는 1단계(서열 내려받기) 화면 옆에 화면을 하나 더 붙여, 서열 여러 개에 대해 위 흐름을 차례로 돌리고 결과를 엑셀 파일 하나로 모은다.

### 1.1 NCBI 정책과의 관계

NCBI는 웹페이지에 대한 스크립트 접근을 허용하지 않으며, 그렇게 하면 접근을 제한할 수 있다고 밝힌다(NLM KB KA-05510). 제한은 IP 단위라서 기관 전체가 영향을 받을 수 있다(KA-05508). 2026-09-21에는 이 이유로 로컬 Primer3 + BLAST+ 재현을 택했으나, 2026-10-06에 사용자가 위험을 안내받은 뒤 웹사이트 자동 제출로 방향을 바꿨다. 이 설계는 그 결정을 따르되, 요청 빈도를 사람이 브라우저로 쓰는 수준에 가깝게 묶어 둔다(7절).

### 1.2 사전 확인 결과 (2026-10-06)

`NM_000546`을 기본 조건으로 실제 제출해 다음을 확인했다.

- 입력 화면을 읽고 같은 항목을 `primertool.cgi`에 multipart POST로 보내면 작업이 접수되고, 응답에 `job_key`가 들어 있다.
- `primertool.cgi?job_key=...`를 다시 요청하면 진행 상황 페이지가 온다. 약 30초 뒤 비슷한 서열 확인 화면(`userGuidedForm`)이 나왔고, 사람이 고를 때까지 넘어가지 않았다.
- 확인 화면의 숨은 항목과 고른 `USER_SEQLOC` 값을 다시 POST하면 새 `job_key`가 나오고, 약 1분 뒤 프라이머 쌍 10개가 담긴 결과 페이지가 왔다.
- 입력 화면의 기본값(조각 길이 70~1000, 녹는 온도 57/60/63 등)은 각 입력란의 `defVal` 속성에 들어 있고, 사이트의 자바스크립트가 화면에 채운다.
- 결과 페이지의 "의도하지 않은 대상"에는 확인 화면에 나오지 않았던 같은 유전자의 다른 판본도 섞여 나온다.

## 2. 핵심 결정 사항

| 결정 | 선택 | 이유 |
|---|---|---|
| 제출 방법 | 직접 요청(`requests`). 화면 없는 브라우저(Playwright)는 쓰지 않음 | 사전 확인에서 끝까지 동작함. 추가 설치가 없고 빠름. 브라우저 방식도 결과 해석은 똑같이 사이트 구조에 묶이므로 이점이 작음 |
| 서열 입력 | 1단계 폴더에서 불러오기 + 서열 번호 직접 입력, 둘 다 | 사용자 요청 |
| 제출하는 서열 형태 | 항상 서열 번호. 파일에서 불러와도 헤더의 번호만 꺼냄 | 사이트 안내: 번호를 넣어야 특이성 검사가 더 정확함 |
| 프라이머 모드 | 프라이머 칸이 비면 사이트가 설계, 채우면 박사님 프라이머 검사 | 사용자 요청 (둘 다 지원) |
| 화면에서 바꿀 수 있는 조건 | 구간, 조각 길이 최소·최대, 녹는 온도 최소·적정·최대, 후보 개수, 생물종 | 자주 바꾸는 항목만. 나머지는 사이트 기본값 |
| 서열별 값 입력 | 표 한 줄 = 서열 하나. 줄마다 구간과 프라이머 | 사용자 요청 |
| 구간 | 시작·끝 2칸. 시작 → `PRIMER5_START`, 끝 → `PRIMER3_END` | 사이트의 4칸 중 흔히 쓰는 형태. 앞쪽·뒤쪽 구간을 따로 지정할 일이 생기면 4칸으로 늘림 |
| 비슷한 서열 확인 화면 | 같은 유전자의 판본만 자동으로 고름 | 사용자 요청. 다른 유전자에 붙는 프라이머는 걸러짐 |
| 결과 형태 | 엑셀 파일 하나, 한 시트, 후보 하나가 한 줄 | 사용자 요청 |
| 엑셀 부품 | `openpyxl` | 파이썬으로만 된 작은 부품이라 Windows 설치 문제가 없음 |

## 3. 범위

포함:
- 새 화면 `primer.html`과 1단계 화면 사이를 오가는 링크
- 폴더의 서열 파일에서 서열 번호 찾기, 번호 직접 입력
- 공통 조건 입력, 서열별 구간·프라이머 입력
- 서열을 하나씩 제출하고 확인 화면 자동 처리, 결과 해석
- 진행 표시(줄마다 상태), 중단, 완료 후 폴더 열기
- 엑셀 저장 (서열 하나가 끝날 때마다 다시 저장)
- 공통 조건과 결과 폴더 기억
- README에 2단계 사용법 추가

제외:
- 사이트의 나머지 조건 항목 (엑손 경계, 데이터베이스 선택 등)
- 사이트 결과 화면을 HTML로 보관
- 사용설명서 PDF 갱신 (기능이 확정된 뒤 따로)
- 로컬 Primer3 + BLAST+ 엔진

## 4. 폴더 구조 (바뀌는 것만)

```
primer-design-automation/
├── requirements.txt          # + openpyxl
├── app/
│   ├── main.py               # 요청 경로 4개 추가
│   ├── config.py             # 기억할 항목 추가, save는 기존 값 위에 덮어씀
│   ├── primerblast.py        # 새 파일: 사이트 통신 + 페이지 해석
│   ├── designer.py           # 새 파일: 백그라운드 작업 + 엑셀 저장
│   └── static/
│       ├── index.html        # 상단에 2단계 화면 링크 추가
│       └── primer.html       # 새 파일
└── tests/
    ├── fixtures/primerblast/ # 실제 페이지 원문 (식별 값 제거)
    ├── test_primerblast.py
    └── test_designer.py
```

## 5. 사이트 통신 모듈 (`app/primerblast.py`)

화면, 파일, 엑셀을 모른다. 밖에서는 `PrimerBlastClient.design()`만 쓴다.

### 5.1 입력과 출력

```python
@dataclass
class Common:            # 모든 서열에 같은 값
    product_min: int = 70
    product_max: int = 1000
    tm_min: float = 57.0
    tm_opt: float = 60.0
    tm_max: float = 63.0
    num_return: int = 10
    organism: str = ""   # 비면 사이트 기본값

@dataclass
class Row:               # 서열 하나
    accession: str
    start: Optional[int] = None
    end: Optional[int] = None
    left: str = ""       # 박사님 앞쪽 프라이머
    right: str = ""      # 박사님 뒤쪽 프라이머

@dataclass
class Primer:
    seq: str; start: int; stop: int; length: int; tm: float; gc: float

@dataclass
class Pair:
    left: Primer
    right: Primer
    product_length: int
    unintended_same_gene: int
    unintended_other_gene: int

@dataclass
class Outcome:
    title: str = ""            # 결과 페이지의 서열 이름
    pairs: List[Pair] = field(default_factory=list)
    accepted: List[str] = field(default_factory=list)  # 확인 화면에서 고른 서열 번호
    url: str = ""              # 결과 페이지 주소
    note: str = ""             # 후보 없음, 사이트 오류 메시지 등
    raw_page: str = ""         # 해석 실패 시에만 채움

class PrimerBlastError(Exception):   # 재시도해도 안 된 통신 오류, 시간 초과, 확인 화면 반복
    ...

class PrimerBlastClient:
    def design(self, row: Row, common: Common, should_stop: Callable[[], bool]) -> Outcome: ...
```

`design()`은 사이트가 정상 응답한 경우(결과, 후보 없음, 사이트 오류 메시지, 해석 실패)에는 `Outcome`을 돌려주고, 통신이 끝내 실패하거나 시간 초과·확인 화면 반복이면 `PrimerBlastError`를 던진다.

### 5.2 페이지 해석 함수 (순수 함수, 시험 대상)

| 함수 | 하는 일 |
|---|---|
| `parse_form_defaults(html) -> List[Tuple[str, str]]` | `searchForm` 안의 항목을 읽는다. 텍스트 칸은 `value`, 비어 있으면 `defVal`. 체크박스는 `checked`일 때만 `value` 또는 `on`. 선택 상자는 `selected` 옵션, 없으면 첫 옵션. 파일 칸은 뺀다. 같은 이름이 두 번 나오면 첫 값만 쓴다 |
| `page_kind(html) -> str` | `review`(`userGuidedForm`이 있음), `results`(프라이머 쌍 또는 후보 없음 문구가 있음), `error`(사이트 오류 메시지), `waiting`(그 밖) |
| `parse_review(html) -> (fields, template_title, hits)` | 확인 화면의 숨은 항목, 입력 서열 제목, 비슷한 서열 목록(번호, 제목, `USER_SEQLOC` 값) |
| `gene_symbol(title) -> str` | 제목에서 처음 나오는 괄호 안 값. 예: `... tumor protein p53 (TP53), transcript variant 1, mRNA` → `TP53`. 없으면 빈 문자열 |
| `pick_same_gene(template_title, hits)` | 유전자 이름이 입력 서열과 같은 항목만 고른다. 입력 서열의 유전자 이름이 없으면 아무것도 고르지 않는다 |
| `parse_results(html) -> Outcome` | 서열 이름, 프라이머 쌍(앞쪽·뒤쪽 서열, 시작, 끝, 길이, 녹는 온도, GC 비율, 조각 길이), "의도하지 않은 대상" 목록을 같은 유전자와 다른 유전자로 나눠 센 값. 후보가 없으면 `note`에 사이트 안내문 |

### 5.3 처리 순서

1. 작업당 한 번 입력 화면을 GET해서 `parse_form_defaults`로 기본값을 얻는다(클라이언트가 보관).
2. 기본값에 덮어쓴다: `INPUT_SEQUENCE`=서열 번호, `PRIMER5_START`/`PRIMER3_END`=구간, `PRIMER_LEFT_INPUT`/`PRIMER_RIGHT_INPUT`=프라이머, `PRIMER_PRODUCT_MIN`/`MAX`, `PRIMER_MIN_TM`/`OPT_TM`/`MAX_TM`, `PRIMER_NUM_RETURN`, `ORGANISM`(비어 있지 않을 때만). 빈 값은 빈 채로 보낸다.
3. `primertool.cgi`에 multipart POST한다. 응답에서 `job_key`를 찾는다.
4. `POLL_INTERVAL`마다 `primertool.cgi?job_key=...`를 GET하고 `page_kind`로 판단한다.
   - `waiting`: 계속 기다린다.
   - `review`: `pick_same_gene`으로 고른 값과 숨은 항목을 POST하고 새 `job_key`로 4번을 계속한다. 한 서열에서 두 번째 `review`가 나오면 `PrimerBlastError`.
   - `results`: `parse_results`. 해석이 예외를 내면 `note="결과 페이지를 읽지 못함"`, `raw_page`=원문.
   - `error`: `note`=사이트 메시지.
5. 제출부터 `JOB_TIMEOUT`이 지나면 `PrimerBlastError("시간 초과")`.
6. 기다리는 동안 `should_stop()`이 참이 되면 바로 빠져나온다(결과 없이 `PrimerBlastError("중단")`).

통신 오류(연결 실패, 5xx)는 `RETRY_WAITS`(2, 4, 8초)만큼 쉬고 다시 시도한다. 머리글은 1단계처럼 도구 이름을 밝힌다. 기다리는 함수(`self._sleep`)는 시험에서 바꿔 끼울 수 있게 한다.

## 6. 설계 작업 (`app/designer.py`)

1단계 `Downloader`와 같은 구조: 스레드 하나, `status()`, `stop()`, `wait()`, 한 번에 작업 하나.

### 6.1 작업 입력

```python
@dataclass
class DesignRequest:
    rows: List[Row]      # 1~MAX_ROWS개
    common: Common
    folder: str          # 엑셀 저장 폴더
```

### 6.2 처리 순서

1. 폴더를 만들고 파일 이름을 정한다: `primers_YYYYMMDD_HHMM.xlsx`.
2. 줄마다 `client.design()`을 부른다. 줄 상태: `대기 → 진행 중 → 완료 / 후보 없음 / 실패`.
3. 결과를 엑셀 줄 목록에 더하고 파일 전체를 다시 저장한다.
4. `PrimerBlastError`가 연달아 `MAX_CONSECUTIVE_FAILURES`번 나면 남은 줄을 건너뛰고 `phase="error"`로 끝낸다. 메시지: "연속으로 실패해 멈췄습니다. 사이트 상태를 확인하세요."
   중단 때문에 빠져나온 경우는 실패로 세지 않는다. 그 줄은 `중단`으로 표시하고 엑셀에 남기지 않으며, 작업은 `phase="stopped"`로 끝난다.
5. 다음 줄로 가기 전에 `BETWEEN_JOBS`초 쉰다(중단 신호가 오면 바로 깸).
6. `raw_page`가 있으면 `<서열번호>_page.html`로 같은 폴더에 저장한다.

### 6.3 상태

`{"phase": idle|running|done|stopped|error, "total", "done", "current", "rows": [{"accession", "status", "note"}], "file", "message"}`

### 6.4 엑셀 (시트 이름 "결과", 후보 하나가 한 줄)

| 칸 | 내용 |
|---|---|
| 서열 번호, 서열 이름, 후보 순번 | |
| 앞쪽 서열, 앞쪽 시작, 앞쪽 끝, 앞쪽 길이, 앞쪽 녹는 온도, 앞쪽 GC% | |
| 뒤쪽 서열, 뒤쪽 시작, 뒤쪽 끝, 뒤쪽 길이, 뒤쪽 녹는 온도, 뒤쪽 GC% | |
| 조각 길이 | |
| 잘못 붙는 대상(같은 유전자), 잘못 붙는 대상(다른 유전자) | 다른 유전자 수가 박사님이 먼저 볼 값 |
| 자동으로 고른 비슷한 서열 | 쉼표로 이음 |
| 결과 페이지 주소 | |
| 메모 | 후보 없음, 실패 이유 |

후보가 없거나 실패한 서열도 한 줄(후보 칸은 비움)을 남겨 빠진 서열이 없게 한다. 저장이 `PermissionError`(박사님이 파일을 열어 둠)로 실패하면 줄 목록은 들고 있다가 다음 저장 때 다시 시도하고, 작업 끝에도 실패하면 `primers_..._2.xlsx`처럼 다른 이름으로 저장한다.

## 7. 속도 조절 상수

| 상수 | 값 | 이유 |
|---|---|---|
| `POLL_INTERVAL` | 15초 | 사람이 결과 페이지를 켜 두고 기다리는 빈도 |
| `BETWEEN_JOBS` | 10초 | 연속 제출 간격 확보 |
| `MAX_ROWS` | 50 | 한 작업의 최대 요청 양 제한. 예상 시간 약 100분 |
| `MAX_CONSECUTIVE_FAILURES` | 3 | 접근이 막혔거나 사이트에 문제가 있을 때 계속 요청하지 않음 |
| `JOB_TIMEOUT` | 600초 | 서열 하나의 최대 대기 |
| `RETRY_WAITS` | (2, 4, 8) | 1단계와 같음 |

한 번에 한 건만 제출한다. 작업이 돌고 있으면 새 작업은 거부한다(1단계 내려받기와는 따로 돈다).

## 8. 서버 (`app/main.py`)

| 경로 | 동작 |
|---|---|
| `GET /api/folder-accessions?folder=` | 폴더(하위 폴더 제외)의 `.txt`, `.fasta`, `.fa` 파일에서 `>`로 시작하는 줄의 첫 단어를 순서대로, 중복 없이 돌려준다. 폴더가 없으면 400 |
| `POST /api/design` | `{rows, common, folder}`. 줄 0개 또는 `MAX_ROWS` 초과, 숫자 칸 형식 오류, 폴더 없음은 400. 작업 중이면 409. 시작할 때 공통 조건과 폴더를 설정에 저장 |
| `GET /api/design/status` | 6.3의 상태 |
| `POST /api/design/stop` | 중단 신호 |

## 9. 설정 (`app/config.py`)

`DEFAULTS`에 `product_min`, `product_max`, `tm_min`, `tm_opt`, `tm_max`, `num_return`, `organism`, `results_dir`를 더한다. 지금의 `save()`는 받은 값에 없는 항목을 기본값으로 되돌리므로, 1단계 설정 저장이 2단계 값을 지우게 된다. `save()`는 기존 파일 값 위에 받은 항목만 덮어쓰도록 바꾼다.

`results_dir` 기본값은 `~/Downloads/primer_results`, 서열을 불러올 폴더 기본값은 1단계 `DOWNLOADS_DIR`이다.

## 10. 화면 (`app/static/primer.html`)

```
[1. 서열 내려받기]  [2. 프라이머 설계]
서열 추가
  폴더에서 불러오기 [~/Downloads/ncbi_fasta] [불러오기]
  번호 직접 입력   [NM_000546, ...        ] [추가]      (쉼표·공백·줄바꿈으로 구분)
공통 조건
  조각 길이 최소 [70] 최대 [1000] / 녹는 온도 최소 [57] 적정 [60] 최대 [63]
  후보 개수 [10] / 생물종 [ ]
서열 목록 (최대 50줄)
  서열 번호 | 구간 시작 | 구간 끝 | 앞쪽 프라이머 | 뒤쪽 프라이머 | 상태 | [x]
저장 폴더 [~/Downloads/primer_results]  [설계 시작]   예상 약 N분
진행 표시, [중단], 완료 후 파일 이름과 [폴더 열기]
```

- 상태는 2초마다 `/api/design/status`로 갱신한다(1단계와 같음).
- 생물종 칸이 비어 있으면 사이트 기본값(사람)을 쓴다. 칸 안에 그 안내를 흐린 글씨로 보여 준다.
- 서열이 `MAX_ROWS`를 넘으면 화면에서 먼저 막고 이유를 보여 준다.
- 작업 중에는 입력 칸과 버튼을 잠근다.
- 폴더 열기는 1단계의 `/api/open-folder`를 그대로 쓴다.
- `index.html` 머리에 같은 두 링크를 둔다.

## 11. 오류 처리 요약

| 상황 | 처리 |
|---|---|
| 연결 실패, 5xx | 2·4·8초 쉬고 재시도. 끝내 실패하면 그 서열 실패, 다음 서열로 |
| 사이트 오류 메시지(잘못된 번호 등) | 메모에 메시지, 다음 서열로 |
| 후보 없음 | 메모에 "후보 없음"과 사이트 안내문 |
| 10분 초과 | 실패("시간 초과"), 다음 서열로 |
| 확인 화면 반복 | 실패("확인 화면이 반복됨"), 다음 서열로 |
| 결과 페이지 해석 실패 | 메모에 "결과 페이지를 읽지 못함", 원문을 `<서열번호>_page.html`로 저장 |
| 3번 연속 실패 | 작업 전체 멈춤 |
| 엑셀 파일 잠김 | 다음 저장 때 재시도, 끝까지 안 되면 다른 이름으로 저장 |

## 12. 구현할 때 사이트에서 확인할 것

자동 시험에 넣을 페이지 원문을 얻기 위해 실제 제출이 필요한 항목이다. 한 번씩만 제출한다.

1. 후보가 없을 때의 결과 페이지 문구 (`page_kind`, `parse_results`)
2. 잘못된 서열 번호를 넣었을 때의 오류 페이지 (`page_kind`)
3. 박사님 프라이머를 넣었을 때의 결과 페이지 모양 (`parse_results`가 그대로 쓰이는지)
4. 생물종 칸에 `Homo sapiens`나 `Mus musculus`처럼 이름만 넣어도 되는지, `(taxid:...)` 형식이 필요한지
5. 결과 페이지 주소가 얼마나 오래 열리는지 (README 안내 문구용)
6. 도구 이름을 밝힌 머리글로 요청해도 사이트가 거부하지 않는지

## 13. 테스트와 완료 판정

자동 시험은 사이트에 접속하지 않는다.

- `tests/fixtures/primerblast/`: 사전 확인 때 받은 입력 화면, 확인 화면, 결과 화면과 12절에서 받을 페이지. 접속 식별 값(`MYNCBI_USER` 등)과 `job_key`는 지우고 저장한다(공개 저장소).
- `test_primerblast.py`: 5.2의 함수 전부. 가짜 세션으로 "기다림 → 확인 화면 → 기다림 → 결과" 흐름, 재시도, 시간 초과, 확인 화면 반복, 중단.
- `test_designer.py`: 가짜 클라이언트로 줄 여러 개 처리, 저장한 엑셀을 다시 열어 칸과 값 확인, 중단 시 끝난 결과 보존, 3번 연속 실패 시 멈춤, 파일 잠김 시 다른 이름 저장.
- `test_main.py`: 새 경로 4개의 정상 동작과 400/409.
- 설정: 1단계 설정 저장 뒤에도 2단계 값이 남는지.

완료 판정: 자동 시험이 모두 통과하고, 사람이 서열 3개(그대로 / 구간 지정 / 박사님 프라이머)로 실제 사이트에 한 번 돌린 엑셀이 같은 조건으로 사이트에서 직접 돌린 결과와 일치한다.
