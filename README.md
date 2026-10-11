# NCBI 서열 내려받기 · 프라이머 설계

NCBI 웹사이트에서 서열을 찾아 내려받고(1단계), 그 서열로 Primer-BLAST 프라이머 설계를 돌려 결과를 엑셀 파일
하나로 모으는(2단계) 도구입니다. 화면의 칸 이름은 NCBI 웹사이트와 같은 영어로 쓰고, 그 아래에 한글을 달았습니다.

1단계는 NCBI가 프로그램용으로 공식 제공하는 창구(E-utilities)만 사용합니다. 2단계는 Primer-BLAST 웹사이트에
프로그램이 대신 제출하는 방식이어서 NCBI 이용 방침상 주의할 점이 있습니다(4절 참고).

## 사용설명서 내려받기

화면 캡처를 넣어 설치부터 따라 하기 실습, 서열 받기, 프라이머 설계, 엑셀 결과 읽기까지 설명한 17쪽짜리 문서입니다.
처음 쓰신다면 1쪽짜리 빠른 시작부터 보시면 됩니다(설명서 2쪽과 같은 내용입니다).

**[사용설명서.pdf 내려받기](docs/%EC%82%AC%EC%9A%A9%EC%84%A4%EB%AA%85%EC%84%9C.pdf)** ·
**[빠른시작.pdf 내려받기](docs/%EB%B9%A0%EB%A5%B8%EC%8B%9C%EC%9E%91.pdf)**

GitHub에서는 위 링크를 누르면 문서가 화면에 펼쳐지고, 오른쪽 위의 내려받기 단추로 저장하실 수 있습니다.
아래 내용은 같은 설명을 글로만 정리한 것입니다.

<details>
<summary><b>사용설명서 17쪽 미리보기</b> — 눌러서 펼치기</summary>

<br>

| 1쪽 — 표지와 목차 | 2쪽 — 빠른 시작 |
|:--:|:--:|
| <img src="docs/preview/page-1.png" width="100%"> | <img src="docs/preview/page-2.png" width="100%"> |

| 3쪽 — 설치: 내려받기, 파이썬 | 4쪽 — 설치: 보안 허용 / 실습 시작 |
|:--:|:--:|
| <img src="docs/preview/page-3.png" width="100%"> | <img src="docs/preview/page-4.png" width="100%"> |

| 5쪽 — 실습: 검색, 받기, 2단계로 | 6쪽 — 실습: 조건 확인, Get Primers |
|:--:|:--:|
| <img src="docs/preview/page-5.png" width="100%"> | <img src="docs/preview/page-6.png" width="100%"> |

| 7쪽 — 실습: 결과 확인 | 8쪽 — 1단계 자세히: 검색, 고르기, 저장 |
|:--:|:--:|
| <img src="docs/preview/page-7.png" width="100%"> | <img src="docs/preview/page-8.png" width="100%"> |

| 9쪽 — 1단계: 진행, 받은 뒤 바로 설계 | 10쪽 — 검색어 쓰는 법 |
|:--:|:--:|
| <img src="docs/preview/page-9.png" width="100%"> | <img src="docs/preview/page-10.png" width="100%"> |

| 11쪽 — 2단계 자세히: 서열, 프라이머 조건 | 12쪽 — 2단계: 특이성, 서열 목록, 진행 상태 |
|:--:|:--:|
| <img src="docs/preview/page-11.png" width="100%"> | <img src="docs/preview/page-12.png" width="100%"> |

| 13쪽 — 엑셀 결과 읽기 | 14쪽 — 도구가 대신 판단하는 것 (1) |
|:--:|:--:|
| <img src="docs/preview/page-13.png" width="100%"> | <img src="docs/preview/page-14.png" width="100%"> |

| 15쪽 — 도구가 대신 판단하는 것 (2) | 16쪽 — 설정, 저장된 파일 |
|:--:|:--:|
| <img src="docs/preview/page-15.png" width="100%"> | <img src="docs/preview/page-16.png" width="100%"> |

| 17쪽 — 문제가 생겼을 때 |  |
|:--:|:--:|
| <img src="docs/preview/page-17.png" width="100%"> |  |

</details>

## 1. 준비물

- **파이썬 3.9 이상**. 설치 여부 확인:
  - Mac: 터미널에서 `python3 --version`
  - Windows: 명령 프롬프트에서 `py -3 --version`
  - `Python 3.9.x` 이상이 나오면 됩니다. 없으면 https://www.python.org/downloads/ 에서 설치합니다.
    Windows 설치 화면에서는 **"Add python.exe to PATH"** 를 반드시 체크합니다.
- 이 폴더 전체 (zip을 받았다면 압축을 풀어 둡니다).

## 2. 실행

- **Mac**: `run_mac.command` 를 더블클릭합니다.
  - 처음 열 때 "열 수 없습니다" 경고가 뜨면(한 번만 하면 됩니다):
    - macOS 15(Sequoia) 이후: 경고 창의 **완료** → **시스템 설정 → 개인정보 보호 및 보안** → 아래쪽 **보안** 항목의 **그래도 열기** → **열기** → Mac 암호
    - macOS 14 이전: 파일을 **오른쪽 클릭 → 열기 → 열기**
  - 파이썬 3.9 이상이 없으면 실행 창이 알려 주고 python.org 내려받기 페이지를 엽니다.
- **Windows**: `run_windows.bat` 를 더블클릭합니다.
  - "Windows의 PC 보호" 창이 뜨면 **추가 정보 → 실행**.

처음 실행은 필요한 구성 요소를 설치하느라 30초쯤 걸립니다. 이후에는 바로 뜹니다.
검은 창이 하나 뜨고 브라우저에 화면이 열립니다. **검은 창은 그대로 두세요.** 닫으면 종료됩니다.
브라우저가 열리지 않으면 검은 창에 출력된 주소(보통 `http://127.0.0.1:8765`)를 주소창에 입력합니다.
8765번을 다른 프로그램이 쓰고 있으면 8766번처럼 다음 번호로 열리고, 검은 창에 그 주소가 출력됩니다.

## 3. 사용법

1. **Search**(검색어) 칸에 검색어를 넣고 Enter. NCBI 웹사이트의 Nucleotide 검색과 같은 결과가 같은 순서로 나옵니다.
2. 받을 항목을 정합니다. 세 가지 중 하나:
   - 목록에서 체크 → **선택한 N건 받기** (페이지를 넘겨도 체크는 유지됩니다)
   - **상위 N건 받기**: 결과 순서대로 앞에서 N건
   - **전체 받기**: 검색 결과 전부 (수만 건이면 몇 분 걸립니다)
3. 저장 폴더를 확인합니다. 기본값은 `다운로드/ncbi_fasta/<검색어>_<날짜>` 이고 바꿀 수 있습니다.
4. 저장 방식을 고릅니다 (둘 다 켤 수 있습니다):
   - **항목별 파일로 저장**: 항목마다 `LR881868.1.txt` 처럼 고유번호 이름의 파일
   - **합본 파일로 저장**: 전부를 `combined.fasta` 한 파일에 이어서
5. 받기 버튼을 누르면 진행 막대가 나옵니다. 끝나면 **폴더 열기**로 바로 볼 수 있습니다.
   도중에 **중단**을 누르면 그때까지 받은 파일은 남습니다.
6. 받은 서열로 프라이머를 설계하려면 **이 서열로 프라이머 설계**를 누릅니다(4절).

### 검색어 예시

NCBI 웹사이트 검색창에 넣을 수 있는 것은 전부 그대로 됩니다. 이 도구는 검색어를 손대지 않고 NCBI에 넘깁니다.

| 검색어 | 뜻 |
|---|---|
| `influenza A H1N1 hemagglutinin` | 단어가 제목·설명·생물명 어디든 들어 있는 항목 |
| `LR881868.1` | 고유번호 하나 |
| `LR881868.1 OR MW123456.1` | 고유번호 여러 개를 한 번에 |
| `"Severe acute respiratory syndrome coronavirus 2"[Organism] AND "complete genome"[Title]` | 생물이 SARS-CoV-2이고 제목에 "complete genome"이 있는 것만 |
| `"Severe acute respiratory syndrome coronavirus 2"[Organism] AND 29000:30000[Sequence Length] AND 2024[Publication Date]` | 위 생물 중 길이 29,000~30,000이고 2024년에 공개된 것만 |

단어 뒤의 대괄호는 "어느 칸에서 찾을지"입니다. 자주 쓰는 것:
`[Organism]` 생물 학명, `[Title]` 제목, `[Accession]` 고유번호, `[Sequence Length]` 길이 범위(`최소:최대`),
`[Publication Date]` 공개 연도(`2023:2024` 같은 범위 가능). 조건은 `AND` / `OR` / `NOT`(대문자)으로 잇습니다.

단어만 나열하면(예: `sars-cov-2 whole genome`) 설명문에 그 단어가 언급된 다른 생물의 항목까지 섞여 나옵니다.
특정 생물만 원하면 `[Organism]` 조건을 쓰는 것이 훨씬 깨끗합니다.

## 4. 프라이머 설계 (2단계)

> **주의:** 이 기능은 프로그램이 NCBI Primer-BLAST 웹사이트에 대신 제출합니다. NCBI는 웹페이지에 대한 자동 접근을
> 허용하지 않으며, 그렇게 하면 접근을 제한할 수 있다고 밝히고 있습니다. 제한은 회사 전체의 인터넷 주소 단위로 걸릴 수
> 있습니다. 도구는 한 번에 한 건씩만 제출하고, 15초 간격으로 결과를 확인하며, 한 번에 50개까지만 처리하도록 묶어
> 두었습니다. 2단계를 처음 열 때 이 내용에 동의해야 쓸 수 있습니다.

**1단계에서 이어서 하기**
- 받기가 끝난 뒤 **이 서열로 프라이머 설계**를 누르면, 받은 서열이 2단계 목록에 자동으로 들어갑니다.
- 1단계에서 **받은 뒤 바로 프라이머 설계**를 체크해 두면, 받기가 끝나는 즉시 2단계에서 마지막으로 쓴 조건으로
  설계까지 이어서 진행합니다(한 번에 50개까지, 체크 상태는 기억하지 않음).

**2단계 화면** (Primer-BLAST 웹사이트와 같은 구역)
1. **PCR Template**: Enter accession(서열 번호 입력)에 `NM_000546, NM_001126112`처럼 넣고 **추가**하거나,
   **폴더에서 불러오기**로 폴더 안 파일들에 적힌 번호를 한꺼번에 넣습니다.
2. **Primer Parameters**: PCR product size(조각 길이), Primer melting temperatures(녹는 온도),
   # of primers to return(후보 개수). 처음 값은 웹사이트 기본값이고, 바꾼 값은 다음에도 남습니다.
3. **Primer Pair Specificity Checking Parameters**: Organism(생물종). `Mus musculus`처럼 학명을 넣고, 비우면 Homo sapiens.
4. **서열 목록**: 서열마다 Range From/To(구간)와 Forward/Reverse primer(프라이머)를 넣을 수 있습니다.
   프라이머를 비우면 사이트가 설계하고, 채우면 그 프라이머가 원하는 곳에만 붙는지 검사합니다.
5. **Get Primers**(설계 시작). 서열 하나에 1~2분 걸리고 줄마다 상태가 바뀝니다. 끝나면 저장 폴더
   (기본값 `다운로드/primer_results`)에 `primers_날짜_시각.xlsx`가 생깁니다. **중단**해도 끝난 서열의 결과는 남습니다.

### 비슷한 서열 확인 화면

웹사이트는 입력 서열과 거의 같은 서열을 찾으면 "프라이머가 붙어도 되는 서열을 골라 달라"는 화면을 보여 줍니다.
도구는 이 화면에서 **같은 유전자의 다른 판본만** 자동으로 고릅니다. 같은 유전자인지는 제목 괄호 안의 유전자 이름
(예: `TP53`)으로 판단합니다. 이 규칙의 한계와 도구가 대신 정하는 나머지 조건은 사용설명서 7장에 있습니다.

### 엑셀 파일

시트 이름은 `Results (결과)`이고 후보 하나가 한 줄입니다. 머리글은 `Forward primer (앞쪽 서열)`처럼 Primer-BLAST
결과 용어에 한글을 붙였습니다. `Unintended templates: other genes (잘못 붙는 대상: 다른 유전자)`가 0이면 다른 유전자에
붙는 곳이 보고되지 않은 후보입니다. `Result URL`은 웹사이트의 결과 화면이며, 시간이 지나면 열리지 않을 수 있습니다.
후보가 없거나 실패한 서열도 `Note (메모)` 칸에 이유를 적은 한 줄로 남습니다. 메모에 "결과 페이지를 읽지 못함"이 있으면
같은 폴더의 `<서열번호>_page.html` 파일을 개발자에게 보내 주세요.

## 5. 설정

1단계 화면 오른쪽 위의 **설정**을 누르면 두 칸이 나옵니다.

- **Email**(이메일): NCBI가 문제 상황에서 연락할 주소입니다. 비워도 됩니다.
- **API key**(API 키): 없어도 됩니다. 있으면 NCBI 요청 속도 제한이 초당 3회에서 10회로 늘어 큰 다운로드가 약 3배 빨라집니다. 발급은 무료이고 3분쯤 걸립니다:
  1. https://www.ncbi.nlm.nih.gov/account/ 에서 로그인 (Google, ORCID, 소속 기관 계정 등으로 로그인합니다)
  2. 오른쪽 위 사용자 이름 → **Account settings**
  3. 아래로 내려 **API Key Management** → **Create an API Key**
  4. 표시된 36자 문자열을 복사해 설정 칸에 붙여 넣고 **저장**

설정은 이 폴더의 `config.json` 에 저장됩니다. 이 파일은 남에게 보내지 마세요 (API 키가 들어 있습니다).

## 6. 저장되는 파일

FASTA 형식은 `>`로 시작하는 제목 줄 하나와 그 아래 서열 줄들로 된 텍스트입니다.
항목별 파일은 웹사이트에서 FASTA 링크를 눌렀을 때 보이는 내용과 같고, 합본 파일은 그것을 차례로 이어 붙인 것입니다.

NCBI가 요청한 항목 일부를 돌려주지 않는 경우가 간혹 있으며, 그때는 완료 문구에 "N건은 NCBI에서 제공되지 않음"이
표시됩니다. 흔한 예는 제목이 "whole genome shotgun sequencing project"로 끝나는 항목인데, 이것은 서열이 아니라
프로젝트를 대표하는 기록이라 웹사이트에서 FASTA를 눌러도 서열이 나오지 않습니다.

## 7. 문제 해결

| 증상 | 조치 |
|---|---|
| "파이썬 3이 없습니다" / "파이썬 3.9 이상을 찾지 못했습니다" | 1번 준비물대로 설치 후 다시 실행 |
| 브라우저가 안 열림 | 검은 창에 출력된 주소(보통 `http://127.0.0.1:8765`)를 주소창에 입력 |
| "NCBI 응답이 없습니다" | 인터넷 연결 확인 후 잠시 뒤 다시 시도. NCBI 서버가 잠시 바쁠 때도 납니다 |
| "이미 받는 중입니다" | 진행 중인 작업이 끝나거나 중단될 때까지 기다림 |
| Mac "열 수 없습니다" 경고 | 2번 실행의 보안 허용 순서대로 |
| 폴더에 쓸 수 없음 | 저장 폴더 칸에 쓸 수 있는 다른 경로 입력 |
| "연속으로 실패해 멈췄습니다" | NCBI 사이트가 바쁘거나 접근이 막혔을 수 있습니다. 브라우저로 Primer-BLAST 웹사이트가 열리는지 확인하고 한참 뒤에 다시 시도 |
| "이미 설계 중입니다" | 진행 중인 설계가 끝나거나 중단될 때까지 기다림 |
| 엑셀 파일 이름 끝에 `_2` | 설계 중에 엑셀 파일을 열어 두어 원래 이름으로 저장하지 못한 경우. 내용은 같음 |
| "2단계 안내에 먼저 동의해 주세요" | 2단계 화면을 열어 안내를 읽고 동의 |
| "받은 뒤 바로 설계는 한 번에 50개까지만…" | 받을 개수를 50개 이하로 줄이거나, 체크를 끄고 받은 뒤 2단계에서 나눠서 설계 |
| "자동 설계를 시작하지 못했습니다: …" | 적힌 이유를 확인하고 2단계 화면에서 직접 Get Primers |

## 8. 프로젝트 구조와 이후 계획

이 도구는 **프라이머 설계 자동화의 1단계(서열 내려받기)와 2단계(Primer-BLAST 프라이머 설계)** 입니다.
3단계(설계한 프라이머 검증)가 필요해지면 같은 방식으로 붙일 수 있도록 역할별로 나눠 두었습니다.

```
app/
  ncbi.py         NCBI와 통신 (검색, 요약, FASTA 받기). 화면·파일과 무관
  downloader.py   받은 텍스트를 파일로 저장하고 진행 상태를 기록
  primerblast.py  Primer-BLAST 웹사이트 제출과 결과 페이지 해석. 화면·파일과 무관
  designer.py     서열을 하나씩 설계하고 결과를 엑셀로 저장
  config.py       설정 파일 읽기/쓰기
  main.py         웹 서버. 화면 요청을 받아 위 모듈들을 호출
  static/index.html   1단계 화면
  static/primer.html  2단계 화면
```

2단계(프라이머 설계)는 이 구조에 `primerblast.py`, `designer.py`, `primer.html`을 더해 붙였습니다.
3단계(검증)도 같은 방식으로 모듈과 화면을 더하면 됩니다. 설계 문서는 `docs/superpowers/specs/` 에 있습니다.

## 9. 개발자용

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q              # NCBI에 접속하지 않는 테스트
# Primer-BLAST 시험은 tests/fixtures/primerblast/ 의 실제 페이지 원문으로 돈다 (사이트 접속 없음)
.venv/bin/python docs/manual/build_manual.py   # 사용설명서·빠른 시작 PDF와 미리보기 다시 만들기 (macOS)
# 설명서 글꼴: Pretendard 배포 zip(github.com/orioncactus/pretendard/releases)의 public/static/alternative/
#   Pretendard-Regular.ttf, Pretendard-SemiBold.ttf 를 docs/manual/fonts/ 에 넣어 둔다 (저장소에는 넣지 않음)
NCBI_LIVE=1 .venv/bin/python -m pytest -q -k live   # 실제 접속 확인 (요청 2번)
```
