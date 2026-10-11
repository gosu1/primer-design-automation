"""사용설명서 PDF(docs/사용설명서.pdf)와 1쪽 빠른 시작(docs/빠른시작.pdf)을 만든다.

실행: .venv/bin/python docs/manual/build_manual.py   (저장소 루트에서)
필요: reportlab (requirements-dev.txt), docs/manual/fonts/ 의 Pretendard TTF(저장소에 넣지 않음, 아래 FONTS 참고).
화면 캡처는 docs/manual/images/ 에 있다. 내용을 고친 뒤 다시 실행하면 PDF와 미리보기가 함께 바뀐다.
"""
import os
import subprocess

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
IMAGES = os.path.join(HERE, "images")
OUTPUT = os.path.join(ROOT, "docs", "사용설명서.pdf")
QUICK_OUTPUT = os.path.join(ROOT, "docs", "빠른시작.pdf")
PREVIEW = os.path.join(ROOT, "docs", "preview")
TITLE = "NCBI 서열 내려받기 · 프라이머 설계"
FOOTER = "사용설명서"

# ReportLab은 OTF를 읽지 못하므로 Pretendard 배포 zip의 public/static/alternative/*.ttf 를 쓴다
FONTS = os.path.join(HERE, "fonts")
for name in ("Pretendard-Regular", "Pretendard-SemiBold"):
    path = os.path.join(FONTS, name + ".ttf")
    if not os.path.exists(path):
        raise SystemExit("글꼴이 없습니다: %s\nhttps://github.com/orioncactus/pretendard/releases 의 Pretendard-*.zip 에서 "
                         "public/static/alternative/%s.ttf 를 꺼내 넣어 주세요." % (path, name))
    pdfmetrics.registerFont(TTFont(name, path))

NAVY = colors.HexColor("#1f3b5c")
TEXT = colors.HexColor("#222222")
GRAY = colors.HexColor("#6b7280")
LINE = colors.HexColor("#d9dee7")
BLUE_BOX = colors.HexColor("#edf2fa")
HEAD_BG = colors.HexColor("#e9eff8")
WARN_BG = colors.HexColor("#fff5df")
WARN_LINE = colors.HexColor("#e5bf63")

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

S = {
    "title": ParagraphStyle("title", fontName="Pretendard-SemiBold", fontSize=25, leading=32, textColor=NAVY),
    "subtitle": ParagraphStyle("subtitle", fontName="Pretendard-Regular", fontSize=12, leading=18, textColor=GRAY, spaceAfter=14),
    "h1": ParagraphStyle("h1", fontName="Pretendard-SemiBold", fontSize=17, leading=24, textColor=NAVY, spaceBefore=14, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="Pretendard-SemiBold", fontSize=12.5, leading=18, textColor=NAVY, spaceBefore=6, spaceAfter=4),
    "body": ParagraphStyle("body", fontName="Pretendard-Regular", fontSize=9.5, leading=16, textColor=TEXT, spaceAfter=6),
    "cell": ParagraphStyle("cell", fontName="Pretendard-Regular", fontSize=9, leading=14, textColor=TEXT),
    "cellhead": ParagraphStyle("cellhead", fontName="Pretendard-SemiBold", fontSize=9, leading=14, textColor=NAVY),
    "caption": ParagraphStyle("caption", fontName="Pretendard-Regular", fontSize=8.5, leading=13, textColor=GRAY,
                              alignment=TA_CENTER, spaceBefore=3, spaceAfter=10),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=8.5, leading=13, textColor=colors.HexColor("#3b4a5c")),
    "quick": ParagraphStyle("quick", fontName="Pretendard-Regular", fontSize=10, leading=16, textColor=TEXT),
    "badge": ParagraphStyle("badge", fontName="Pretendard-SemiBold", fontSize=11, leading=14, textColor=colors.white,
                            alignment=TA_CENTER),
}


def code(text):
    # Courier에는 한글이 없으므로 영문·숫자·기호만 넣는다
    assert all(ord(ch) < 0x3000 for ch in text), text
    return '<font face="Courier" size="8.5" color="#3b4a5c">%s</font>' % text


def em(text):
    return '<font color="#1f3b5c">%s</font>' % text


def p(text, style="body"):
    return Paragraph(text, S[style])


class Heading(Paragraph):
    """목차에 쪽 번호를 기록할 장 제목."""

    def __init__(self, text):
        super().__init__(text, S["h1"])
        self.toc_text = text


def h1(text):
    return Heading(text)


# 그림·상자는 칸 하나짜리 표로 만들어 쪽 사이에서 나뉘지 않게 한다.
# KeepTogether를 겹쳐 쓰면 바깥 묶음이 높이를 무한대로 계산해 무조건 다음 쪽으로 넘기므로,
# KeepTogether는 step()의 맨 바깥에서만 쓴다.

def box(parts, background=BLUE_BOX, border=None):
    cell = [part if not isinstance(part, str) else p(part) for part in parts]
    t = Table([[cell]], colWidths=[CONTENT_W])
    style = [("BACKGROUND", (0, 0), (-1, -1), background),
             ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
             ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if border:
        style.append(("BOX", (0, 0), (-1, -1), 0.8, border))
    t.setStyle(TableStyle(style))
    t.spaceAfter = 8
    return t


def warn(parts):
    return box(parts, WARN_BG, WARN_LINE)


def table(header, rows, widths):
    data = [[p(h, "cellhead") for h in header]] + [[p(c, "cell") for c in row] for row in rows]
    t = Table(data, colWidths=[CONTENT_W * w for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 1, NAVY),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    t.spaceAfter = 10
    return t


def figure(name, caption, width=1.0):
    path = os.path.join(IMAGES, name)
    img = Image(path)
    scale = (CONTENT_W * width - 2) / img.imageWidth   # 테두리 1pt씩을 더해도 본문 폭을 넘지 않게
    img.drawWidth, img.drawHeight = img.imageWidth * scale, img.imageHeight * scale
    framed = Table([[img]], colWidths=[img.drawWidth + 2])
    framed.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE),
                                ("LEFTPADDING", (0, 0), (-1, -1), 1), ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                                ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    t = Table([[[framed, p(caption, "caption")]]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    t.spaceAfter = 6
    return t


def step(number, title, *parts):
    badge = Table([[p(str(number), "badge")]], colWidths=[7 * mm], rowHeights=[7 * mm])
    badge.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    head = Table([[badge, p(title, "h2")]], colWidths=[9 * mm, CONTENT_W - 9 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    first = [Spacer(1, 6), head, Spacer(1, 2)]
    # 제목이 쪽 끝에 홀로 남지 않도록 첫 내용과 묶는다
    return [KeepTogether(first + [parts[0]])] + list(parts[1:])


# ---- 용어 표기: 화면과 같이 사이트 영어 용어에 한글을 단다

def t(en, ko):
    """표 안에서 쓰는 표기: 영어 용어와 그 아래 한글."""
    return '%s<br/><font size="7.5" color="#6b7280">%s</font>' % (en, ko)


def tin(en, ko):
    """본문 안에서 쓰는 표기: 영어 용어(한글)."""
    return '<font color="#1f3b5c">%s</font>(%s)' % (en, ko)


TOC = [
    "1. 설치하기 (Mac)",
    "2. 처음 15분 따라 하기",
    "3. 서열 받기 자세히 (1단계)",
    "4. 검색어 쓰는 법",
    "5. 프라이머 설계 자세히 (2단계)",
    "6. 엑셀 결과 읽기",
    "7. 도구가 대신 판단하는 것",
    "8. 설정 — Email과 API key",
    "9. 저장된 파일 살펴보기",
    "10. 문제가 생겼을 때",
]

QUICK_STEPS = [
    ("설치 (1장)", "처음 한 번만 합니다. 1장의 순서대로 도구를 내려받고, 파이썬을 설치하고, 보안 허용을 해 둡니다."),
    ("실행 (1장 3단계)", "도구 폴더의 %s를 더블클릭합니다. 검은 창(터미널)이 뜨고 잠시 뒤 브라우저에 화면이 열립니다. "
             "검은 창은 닫지 마세요." % code("run_mac.command")),
    ("검색 (3장·4장)", "%s 칸에 검색어를 넣고 %s을 누릅니다." % (tin("Search", "검색어"), tin("Search", "검색"))),
    ("받기 (3장)", "목록에서 받을 서열을 체크하고 %s를 누릅니다. 상위 N건이나 전체를 받을 수도 있습니다." % em("선택한 N건 받기")),
    ("넘어가기 (3장 4단계)", "받기가 끝나면 %s를 누릅니다. 받은 서열이 2단계 목록에 자동으로 들어갑니다." % em("이 서열로 프라이머 설계")),
    ("동의 (2장 3단계)", "처음 한 번은 NCBI 이용 방침 안내가 뜹니다. 읽고 체크한 뒤 %s를 누릅니다." % em("시작하기")),
    ("설계 (5장)", "조건(%s, %s, %s, %s)을 확인하고 %s를 누릅니다. 서열 하나에 1~2분 걸립니다."
             % (tin("PCR product size", "조각 길이"), tin("Primer melting temperatures", "녹는 온도"),
                tin("# of primers to return", "후보 개수"), tin("Organism", "생물종"), tin("Get Primers", "설계 시작"))),
    ("결과 (6장)", "끝나면 %s를 눌러 %s 파일을 엽니다. %s가 0인 후보부터 보세요."
             % (em("폴더 열기"), code("primers_") + "날짜_시각" + code(".xlsx"),
                tin("Unintended templates: other genes", "잘못 붙는 대상: 다른 유전자"))),
]


def quick_start(with_title):
    """빠른 시작 1쪽. 설명서 2쪽과 docs/빠른시작.pdf에 똑같이 들어간다."""
    out = []
    if with_title:
        out += [p(TITLE, "subtitle")]
    out += [p("빠른 시작 — 처음 쓰실 때 이 순서대로", "h1"),
            p("자세한 설명은 단계 이름 아래에 적힌 장을 보세요. 처음이라면 2장의 따라 하기 실습을 한 번 해 보시길 권합니다.")]
    rows = []
    for number, (name, text) in enumerate(QUICK_STEPS, 1):
        badge = Table([[p(str(number), "badge")]], colWidths=[7 * mm], rowHeights=[7 * mm])
        badge.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                   ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        title, _, ref = name.partition(" (")
        rows.append([badge, p('%s<br/><font size="8" color="#6b7280">%s</font>' % (title, ref.rstrip(")")), "h2"),
                     p(text, "quick")])
    steps = Table(rows, colWidths=[10 * mm, 26 * mm, CONTENT_W - 36 * mm])
    steps.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
                               ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                               ("LEFTPADDING", (0, 0), (-1, -1), 2)]))
    out += [steps, Spacer(1, 10),
            warn(["%s — 2단계는 NCBI Primer-BLAST 웹사이트에 프로그램이 대신 제출합니다. NCBI는 웹페이지에 대한 자동 "
                  "접근을 허용하지 않으며, 회사 전체의 인터넷 주소 단위로 접근을 제한할 수 있습니다. 꼭 필요한 만큼만 "
                  "사용해 주세요." % em("주의")]),
            box(["%s — 브라우저 탭을 닫는 것만으로는 종료되지 않습니다. 함께 떠 있던 검은 창을 닫으셔야 완전히 "
                 "종료됩니다." % em("끝낼 때")])]
    return out


def keep_headings(items):
    """소제목(h2)이 쪽 끝에 혼자 남지 않도록 바로 다음 내용과 묶는다. 이미 묶인 것과는 겹쳐 묶지 않는다."""
    merged, i = [], 0
    while i < len(items):
        item = items[i]
        nxt = items[i + 1] if i + 1 < len(items) else None
        if isinstance(item, Paragraph) and item.style.name == "h2" and nxt is not None \
                and not isinstance(nxt, KeepTogether):
            merged.append(KeepTogether([item, nxt]))
            i += 2
        else:
            merged.append(item)
            i += 1
    return merged


def story(toc_pages):
    out = []
    add = out.extend

    # 1쪽: 표지와 목차
    add([
        Spacer(1, 4 * mm),
        p(TITLE, "title"),
        p("서열 검색부터 프라이머 후보 엑셀까지", "subtitle"),
        box([
            "NCBI에서 서열을 찾아 내려받고, 그 서열을 Primer-BLAST에 넣어 프라이머를 설계하는 일을 이 도구가 차례로 "
            "대신합니다. %s는 검색어 한 번으로 결과 목록을 보여 주고, 고른 서열을 파일로 저장합니다. %s는 서열 목록을 "
            "Primer-BLAST에 하나씩 대신 제출하고, 나온 프라이머 후보를 엑셀 파일 하나로 모아 줍니다."
            % (em("1단계 서열 내려받기"), em("2단계 프라이머 설계")),
            "화면의 칸 이름은 NCBI 웹사이트와 같은 영어로 쓰고, 그 아래에 한글을 함께 적었습니다. 이 문서도 "
            "%s처럼 같은 방식으로 적습니다." % tin("PCR product size", "조각 길이"),
            "1단계는 NCBI가 프로그램 이용자를 위해 공식으로 제공하는 통로만 사용합니다. 2단계는 Primer-BLAST "
            "웹사이트에 프로그램이 대신 제출하는 방식이어서 NCBI 이용 방침과 관련해 주의하실 점이 있습니다. "
            "5장 첫머리의 안내를 꼭 읽어 주세요.",
        ]),
        figure("s1_first.png", "도구를 실행하면 나타나는 첫 화면입니다. 맨 위 링크로 1단계와 2단계 화면을 오갑니다.", 0.8),
        p("이 문서에서 다루는 내용", "h1"),
    ])
    toc_rows = [[p("빠른 시작", "cell"), p("2", "cell")]]
    toc_rows += [[p(name, "cell"), p(str(toc_pages.get(name, "")), "cell")] for name in TOC]
    toc = Table([[p("항목", "cellhead"), p("쪽", "cellhead")]] + toc_rows, colWidths=[CONTENT_W - 25 * mm, 25 * mm])
    toc.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG), ("LINEBELOW", (0, 0), (-1, 0), 1, NAVY),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    add([toc, PageBreak()])

    # 2쪽: 빠른 시작
    add(quick_start(with_title=False))
    add([PageBreak()])

    # 1. 설치
    add([h1(TOC[0]), p("처음 한 번만 하면 됩니다. 도구 폴더를 내려받고, 파이썬을 준비하고, macOS의 보안 허용을 합니다.")])
    add(step(1, "도구 내려받기",
             p("브라우저로 %s 에 들어가서 초록색 %s 단추를 누르고 %s를 고릅니다." % (
                 code("github.com/gosu1/primer-design-automation"), em("Code"), em("Download ZIP"))),
             figure("i_github.png", "Code → Download ZIP 을 누르면 ZIP 파일 하나가 내려받아집니다."),
             p("다운로드 폴더의 %s 을 더블클릭하면 같은 이름의 폴더가 생깁니다. 이 폴더가 도구입니다. 문서 폴더처럼 "
               "찾기 쉬운 곳으로 옮겨 두셔도 됩니다." % code("primer-design-automation-main.zip"))))
    add(step(2, "파이썬 준비하기",
             p("이 도구는 파이썬(Python) 위에서 돌아갑니다. 응용 프로그램 → 유틸리티 → 터미널을 열고 다음을 입력한 뒤 "
               "Enter를 누릅니다."),
             box([p("python3 --version", "code")]),
             p("%s 이상이 나오면 다음 단계로 넘어가세요. 나오지 않거나 숫자가 3.9보다 작으면 %s 에서 맨 위 "
               "%s 아래의 %s를 내려받습니다." % (code("Python 3.9"), code("python.org/downloads/macos"),
                                         em("Stable Releases"), em("macOS installer"))),
             figure("i_python.png", "python.org의 macOS 내려받기 화면입니다. Stable Releases의 첫 줄을 고르면 됩니다."),
             p("내려받은 %s 파일을 더블클릭하고 %s → %s → %s → %s 를 차례로 누릅니다. Mac 암호를 넣으면 설치가 끝납니다."
               % (code("python-3.x.x-macos11.pkg"), em("계속"), em("계속"), em("동의"), em("설치"))),
             box(["새 Mac에서 %s 를 입력하면 “개발자 도구를 설치하겠습니까?” 창이 뜰 수 있습니다. python.org에서 파이썬을 "
                  "설치하신다면 %s를 누르셔도 됩니다. 또 도구를 실행했을 때 파이썬이 없으면, 도구가 이유를 알려 주고 "
                  "python.org 페이지를 자동으로 엽니다." % (code("python3"), em("취소"))])))
    add(step(3, "처음 실행하고 보안 허용하기",
             p("도구 폴더의 %s 를 더블클릭합니다. 인터넷에서 받은 파일이어서 macOS가 처음 한 번은 실행을 막고 "
               "“열 수 없습니다”라는 경고를 보여 줍니다. 아래 순서로 허용해 주세요." % code("run_mac.command")),
             table(["macOS 버전", "허용하는 방법"], [
                 ["15(Sequoia) 이후", "경고 창에서 %s를 누릅니다 → %s → %s → 아래쪽 %s 항목에 나온 “run_mac.command이(가) "
                  "차단되었습니다” 옆의 %s → 다시 뜨는 창에서 %s → Mac 암호" % (
                      em("완료"), em("시스템 설정"), em("개인정보 보호 및 보안"), em("보안"), em("그래도 열기"), em("열기"))],
                 ["14 이전", "파일을 오른쪽 클릭 → %s → 다시 뜨는 창에서 %s" % (em("열기"), em("열기"))],
             ], [0.22, 0.78]),
             p("허용하면 검은 창(터미널)이 뜨고, 처음에는 “처음 실행: 필요한 구성 요소를 설치합니다”라는 문구와 함께 "
               "30초쯤 설치가 진행됩니다. 그다음 브라우저에 도구 화면이 저절로 열립니다. “터미널이 다운로드 폴더에 "
               "접근하려고 합니다” 같은 창이 뜨면 %s을 눌러 주세요." % em("허용")),
             warn(["%s 그 창이 도구를 돌리고 있습니다. 다 쓰신 뒤에 닫으면 도구가 종료됩니다." % em("검은 창은 닫지 마세요."),
                   "브라우저가 저절로 열리지 않으면 검은 창에 적힌 주소(보통 %s)를 주소창에 입력하세요. 8765번을 다른 "
                   "프로그램이 쓰고 있으면 %s 처럼 다음 번호로 열리고, 검은 창에 그 주소가 적힙니다."
                   % (code("http://127.0.0.1:8765"), code("8766"))])))
    add([CondPageBreak(110 * mm)])

    # 2. 따라 하기
    add([h1(TOC[1]),
         p("TP53 유전자의 두 판본(NM_000546, NM_001126112)으로 처음부터 엑셀 결과까지 한 번 따라 해 봅니다. 마지막에 "
           "적어 둔 값과 결과가 같으면 도구가 제대로 동작하는 것입니다. 이 실습에서 Primer-BLAST에 2건이 제출되므로, "
           "한 번만 해 보시면 충분합니다.")])
    add(step(1, "검색하기",
             p("%s 칸에 아래 검색어를 그대로 넣고 %s을 누릅니다. 고유번호 뒤에 %s 을 붙이면 고유번호 칸에서만 찾기 "
               "때문에 정확히 2건이 나옵니다." % (tin("Search", "검색어"), tin("Search", "검색"), code("[Accession]"))),
             box([p("NM_000546[Accession] OR NM_001126112[Accession]", "code")]),
             figure("t1_search.png", "%s 가 2이고, 두 서열이 목록에 나옵니다." % tin("Items", "결과 건수"))))
    add(step(2, "받기",
             p("저장 폴더는 그대로 두고 %s를 누릅니다. 몇 초 안에 끝납니다." % em("전체 2건 받기")),
             figure("t2_done.png", "받기가 끝난 화면입니다. 아래에 “이 서열로 프라이머 설계” 단추가 나타납니다.")))
    add(step(3, "2단계로 넘어가기",
             p("%s를 누릅니다. 2단계 화면으로 바뀌면서, 처음 한 번은 NCBI 이용 방침 안내가 뜹니다. 내용을 읽고 "
               "%s를 체크한 뒤 %s를 누릅니다." % (em("이 서열로 프라이머 설계"), em("위 내용을 읽고 이해했습니다"),
                                         em("시작하기"))),
             figure("t3_consent.png", "2단계를 처음 열 때 한 번만 나오는 안내입니다.", 0.7)))
    add(step(4, "조건 확인하기",
             p("받은 두 서열이 %s에 들어와 있습니다. 조건은 처음 값(웹사이트 기본값) 그대로 둡니다."
               % em("서열 목록")),
             figure("t4_loaded.png", "받은 폴더의 서열이 자동으로 들어온 2단계 화면입니다.", 0.82)))
    add(step(5, "Get Primers 누르고 기다리기",
             p("%s를 누르면 위에서부터 한 줄씩 차례로 제출합니다. 두 서열이면 4분쯤 걸립니다. 기다리는 동안 다른 일을 "
               "하셔도 됩니다." % tin("Get Primers", "설계 시작")),
             figure("t5_running.png", "첫 줄을 처리하는 중입니다. 상태가 대기 → 진행 중 → 완료로 바뀝니다."),
             figure("t6_done.png", "두 줄이 모두 완료된 화면입니다. 폴더 열기를 누르면 결과 엑셀이 있는 폴더가 열립니다.")))
    add(step(6, "결과 확인하기",
             p("엑셀 파일을 열어 각 서열의 1번 후보가 아래와 같은지 봅니다. 같으면 실습 성공입니다. NCBI 데이터베이스가 "
               "갱신되면 숫자가 조금 달라질 수 있습니다."),
             table([t("Accession", "서열 번호"), t("Forward primer", "앞쪽 프라이머"), t("Reverse primer", "뒤쪽 프라이머"),
                    t("Product", "조각 길이"), t("Unintended", "같은/다른")], [
                 ["NM_000546.6", code("ACCTATGGAAACTACTTCCTGAAA") + "<br/>204–227, Tm 57.30",
                  code("ACCATCGCTATCTGAGCAGC") + "<br/>703–684, Tm 59.97", "500", "4 / 0"],
                 ["NM_001126112.3", code("ACCTATGGAAACTACTTCCTGAAA") + "<br/>201–224, Tm 57.30",
                  code("ACCATCGCTATCTGAGCAGC") + "<br/>700–681, Tm 59.97", "500", "4 / 0"],
             ], [0.213, 0.293, 0.252, 0.105, 0.137]),   # 실제 글자 폭으로 정한 너비
             p("두 판본이 같은 프라이머 쌍을 1번 후보로 받았고, 위치만 3자리씩 다릅니다. 두 판본의 앞부분 길이가 조금 "
               "다르기 때문입니다.")))
    # 3장은 첫 캡처가 커서 제목·첫 설명·캡처가 함께 들어갈 자리가 있어야 한다
    add([CondPageBreak(160 * mm)])

    # 3. 1단계 자세히
    add([h1(TOC[2])])
    add(step(1, "검색하기",
             p("%s 칸에 찾으시는 내용을 넣고 %s을 누릅니다. NCBI 홈페이지의 Nucleotide 검색창에 넣던 것을 그대로 쓰시면 "
               "됩니다. 검색어 쓰는 법은 4장에 있습니다." % (tin("Search", "검색어"), tin("Search", "검색"))),
             figure("s1_results.png", "‘sars-cov-2 whole genome’ 으로 검색한 결과입니다. %s, %s, %s 를 보여 줍니다."
                    % (tin("Accession", "고유번호"), tin("Description", "제목"), tin("Length", "길이")))))
    add(step(2, "받을 항목 고르기 — 세 가지 방법",
             figure("s1_actions.png", "목록 아래의 받기 단추들입니다.", 0.97),
             table(["단추", "언제 쓰나요"], [
                 ["선택한 N건 받기", "목록에서 왼쪽 네모칸을 눌러 표시한 항목만 받습니다. 이전·다음으로 장을 넘겨도 표시해 둔 "
                  "항목은 그대로 유지되므로, 여러 장에 걸쳐 고르셔도 됩니다."],
                 ["상위 N건 받기", "결과 순서대로 앞에서부터 원하는 개수만큼 받습니다."],
                 ["전체 N건 받기", "검색 결과 전부를 받습니다. 수만 건이면 몇 분 걸립니다."],
             ], [0.25, 0.75])))
    add(step(3, "저장 위치와 저장 방식",
             figure("s1_save.png", "저장 구역입니다. 저장 폴더는 검색어와 날짜로 미리 채워집니다."),
             table(["저장 방식", "결과"], [
                 ["항목별 파일로 저장", "항목마다 %s 처럼 고유번호 이름의 파일이 하나씩 생깁니다." % code("LR881868.1.txt")],
                 ["합본 파일로 저장", "받은 것을 전부 %s 파일 하나에 차례로 이어 담습니다." % code("combined.fasta")],
             ], [0.25, 0.75])))
    add(step(4, "받기와 진행 상황",
             p("받기 단추를 누르면 막대가 나타나면서 진행 상황을 보여 줍니다. 도중에 %s을 누르면 멈추고, 그때까지 받은 "
               "파일은 그대로 남습니다." % em("중단")),
             figure("s1_progress.png", "받는 중에는 받은 개수와 전체 개수가 함께 표시됩니다.", 0.97),
             p("다 끝나면 저장된 개수와 폴더 위치가 나타나고, %s와 %s 단추가 함께 나옵니다. 앞의 단추는 폴더를 열고, "
               "뒤의 단추는 받은 서열을 2단계 목록에 넣은 채로 2단계 화면을 엽니다."
               % (em("폴더 열기"), em("이 서열로 프라이머 설계")))))
    add(step(5, "받은 뒤 바로 프라이머 설계",
             p("저장 구역의 %s를 체크해 두면, 받기가 끝나는 즉시 2단계 설계까지 자동으로 이어서 진행합니다. "
               "체크하면 바로 아래에 적용될 조건이 보입니다." % em("받은 뒤 바로 프라이머 설계")),
             figure("s1_then_design.png", "체크하면 2단계에서 마지막으로 쓴 조건과 저장 위치가 바로 아래에 표시됩니다."),
             table(["규칙", "내용"], [
                 ["조건", "2단계에서 마지막으로 쓴 값을 씁니다. 처음이면 웹사이트 기본값입니다. 바꾸려면 2단계 화면에서 바꿉니다."],
                 ["동의", "2단계 안내에 아직 동의하지 않았다면 처음 체크할 때 같은 안내가 뜹니다."],
                 ["개수", "한 번에 50개까지만 됩니다. 더 많이 받으려 하면 받기 단추를 누를 때 막고 이유를 알려 줍니다."],
                 ["진행", "받기가 끝나면 “프라이머 설계를 시작했습니다”와 함께 2단계 진행 화면으로 가는 링크가 나옵니다. "
                  "브라우저 탭을 닫아도 설계는 계속됩니다."],
                 ["시작 안 함", "받기를 중단했거나 오류가 났을 때, 다른 설계가 이미 돌고 있을 때는 설계를 시작하지 않고 "
                  "이유를 보여 줍니다."],
             ], [0.18, 0.82]),
             p("조건을 보지 않고 바로 제출되므로, 2단계 사용에 익숙해진 뒤에 쓰시길 권합니다. 체크 상태는 기억하지 않고 "
               "화면을 열 때마다 꺼져 있습니다.")))
    add([CondPageBreak(110 * mm)])

    # 4. 검색어
    add([
        h1(TOC[3]),
        p("NCBI 홈페이지 검색창에 넣을 수 있는 것은 전부 그대로 쓰실 수 있습니다. 이 도구는 입력하신 검색어를 고치지 "
          "않고 NCBI에 그대로 전달합니다."),
        p("단어로만 찾기", "h2"),
        table(["검색어", "찾아 주는 것"], [
            [code("influenza A H1N1 hemagglutinin"), "제목이나 설명, 생물 이름 어디든 이 단어들이 들어 있는 항목"],
            [code("LR881868.1"), "그 고유번호가 들어 있는 항목. 다른 기록의 설명에 언급된 항목까지 함께 나올 수 있습니다"],
            [code("LR881868[Accession]"), "고유번호 칸에서만 찾습니다. 그 서열 하나만 정확히 나옵니다"],
        ], [0.42, 0.58]),
        p("조건을 붙여 정확하게 찾기", "h2"),
        p("단어 뒤에 대괄호를 붙이면 ‘어느 칸에서 찾을지’를 지정할 수 있습니다. 조건은 %s, %s, %s 로 이어 붙입니다. "
          "반드시 대문자로 쓰셔야 합니다." % (code("AND"), code("OR"), code("NOT"))),
        table(["대괄호", "뜻", "예"], [
            [code("[Organism]"), "생물의 학명", code('"Severe acute respiratory syndrome coronavirus 2"[Organism]')],
            [code("[Title]"), "제목에 들어 있는 단어", code('"complete genome"[Title]')],
            [code("[Accession]"), "고유번호", code("NM_000546[Accession]")],
            [code("[Sequence Length]"), "서열 길이 범위", code("29000:30000[Sequence Length]")],
            [code("[Publication Date]"), "공개된 연도", code("2023:2024[Publication Date]")],
        ], [0.27, 0.2, 0.53]),
        box([
            "%s — 단어만 나열해서 찾으면(예: %s) 설명문에 그 단어가 언급된 다른 생물의 항목까지 섞여 나옵니다. "
            "찾으시는 생물만 골라내시려면 %s 조건을 쓰시는 편이 훨씬 깨끗합니다." % (
                em("알아두시면 좋은 점"), code("sars-cov-2 whole genome"), code("[Organism]")),
            p('"Severe acute respiratory syndrome coronavirus 2"[Organism]<br/>&nbsp;&nbsp;&nbsp;&nbsp;AND '
              '"complete genome"[Title]', "code"),
        ]),
        CondPageBreak(110 * mm),
    ])

    # 5. 2단계 자세히
    add([
        h1(TOC[4]),
        warn([
            "%s — 이 기능은 프로그램이 NCBI Primer-BLAST 웹사이트에 대신 제출합니다. NCBI는 웹페이지에 대한 자동 접근을 "
            "허용하지 않으며, 그렇게 하면 접근을 제한할 수 있다고 밝히고 있습니다. 제한은 회사 전체의 인터넷 주소 "
            "단위로 걸릴 수 있습니다." % em("먼저 읽어 주세요"),
            "도구는 한 번에 한 건씩만 제출하고, 15초 간격으로 결과를 확인하며, 한 번에 50개까지만 처리하도록 묶어 "
            "두었습니다. 그래도 위험이 없어지지는 않으므로 꼭 필요한 만큼만 사용해 주세요. 2단계를 처음 열 때 이 내용에 "
            "동의해야 쓸 수 있습니다(2장 3단계).",
        ]),
        p("2단계 화면은 Primer-BLAST 웹사이트와 같은 구역으로 나뉘어 있습니다. 위에서부터 채우고 %s를 누르시면 됩니다."
          % tin("Get Primers", "설계 시작")),
    ])
    add(step(1, "PCR Template — 서열 넣기",
             figure("s2_template.png", "%s 구역입니다." % tin("PCR Template", "서열")),
             table(["칸", "하는 일"], [
                 [t("Enter accession", "서열 번호 입력"), "%s 처럼 고유번호를 쉼표나 띄어쓰기로 구분해 넣고 %s를 누릅니다."
                  % (code("NM_000546, NM_001126112"), em("추가"))],
                 ["폴더에서 불러오기", "서열 파일이 있는 폴더를 넣고 누르면, 그 안의 파일들에 적힌 고유번호가 모두 목록에 "
                  "들어갑니다. 1단계에서 “이 서열로 프라이머 설계”로 넘어오면 이 칸이 자동으로 채워지고 불러오기까지 됩니다."],
             ], [0.25, 0.75])))
    add(step(2, "Primer Parameters — 프라이머 조건",
             figure("s2_params.png", "%s 구역입니다." % tin("Primer Parameters", "프라이머 조건")),
             table(["칸", "뜻", "처음 값"], [
                 [t("PCR product size", "조각 길이"), "두 프라이머 사이에서 만들어지는 조각 길이의 최소(Min)·최대(Max)",
                  "70 ~ 1000"],
                 [t("Primer melting temperatures (Tm)", "녹는 온도"), "프라이머 녹는 온도의 최소(Min)·적정(Opt)·최대(Max)",
                  "57 / 60 / 63"],
                 [t("# of primers to return", "후보 개수"), "받을 프라이머 쌍의 개수", "10"],
             ], [0.34, 0.46, 0.2])))
    add(step(3, "Primer Pair Specificity Checking Parameters — 특이성 검사 조건",
             figure("s2_specificity.png", "%s 구역입니다." % tin("Organism", "생물종")),
             p("%s에는 다른 곳에 잘못 붙는지 검사할 생물을 %s 처럼 학명으로 넣습니다. 비워 두면 사람(Homo sapiens)입니다. "
               "처음 값은 웹사이트 기본값과 같고, 바꾼 값은 다음에도 남아 있습니다. 화면에 없는 나머지 조건은 웹사이트 "
               "기본값을 그대로 씁니다(7장)." % (tin("Organism", "생물종"), code("Mus musculus")))))
    add(step(4, "서열 목록 — 서열마다 구간과 프라이머",
             figure("s2_list.png", "둘째 줄은 구간을 정했고, 셋째 줄은 가지고 계신 프라이머를 넣었습니다."),
             table(["칸", "쓰는 법"], [
                 [t("Range From / To", "구간 시작 / 끝"), "프라이머를 놓을 위치를 서열 안의 번호로 정합니다. 비워 두면 서열 "
                  "전체가 대상입니다."],
                 [t("Forward / Reverse primer", "앞쪽 / 뒤쪽 프라이머"), "비워 두면 사이트가 프라이머를 설계합니다. 가지고 "
                  "계신 프라이머를 넣으면, 그 프라이머가 원하는 곳에만 붙는지 검사합니다. 웹사이트의 ‘Use my own "
                  "primer’ 칸과 같습니다."],
             ], [0.3, 0.7]),
             p("한 번에 50개까지 넣을 수 있습니다. 줄 오른쪽의 %s로 하나씩 빼거나 %s로 한꺼번에 비울 수 있습니다."
               % (em("삭제"), em("모두 지우기")))))
    add(step(5, "Get Primers와 진행 상태",
             p("%s를 누르면 서열을 위에서부터 하나씩 제출합니다. 서열 하나에 1~2분 걸리고, 줄마다 상태가 바뀝니다. "
               "진행하는 동안 입력 칸은 잠깁니다." % tin("Get Primers", "설계 시작")),
             table(["상태", "뜻"], [
                 ["대기 → 진행 중 → 완료", "정상으로 끝나 프라이머 후보를 받았습니다."],
                 ["후보 없음", "조건에 맞는 프라이머가 없었습니다. 줄 아래에 사이트 설명의 앞부분이 나오고, 전체 문장은 "
                  "엑셀 메모 칸에 남습니다. 조건을 넓혀서 다시 해 보세요."],
                 ["실패", "서열 번호가 없거나 사이트가 응답하지 않은 경우입니다. 이유가 줄 아래에 나옵니다."],
                 ["중단", "%s을 눌러 멈춘 줄입니다. 그 전에 끝난 서열의 결과는 엑셀에 남습니다." % em("중단")],
             ], [0.27, 0.73]),
             p("다 끝나면 저장 폴더에 %s 파일이 생깁니다. 처음 저장 위치는 다운로드 폴더 안의 %s 입니다."
               % (code("primers_") + "날짜_시각" + code(".xlsx"), code("primer_results")))))
    add([CondPageBreak(110 * mm)])

    # 6. 엑셀
    add([
        h1(TOC[5]),
        p("시트 이름은 %s 이고, 후보 하나가 한 줄입니다. 서열 하나에서 후보가 10개 나오면 10줄이 됩니다. 후보가 없거나 "
          "실패한 서열도 메모 칸에 이유를 적은 한 줄로 남으므로, 빠진 서열이 없는지 한눈에 확인하실 수 있습니다. "
          "머리글은 Primer-BLAST 결과 화면의 용어에 한글을 괄호로 붙였습니다." % code("Results")),
        table(["머리글", "뜻"], [
            ["Accession (서열 번호), Template (서열 이름)", "넣으신 번호와 사이트가 알려 준 서열 이름"],
            ["Primer pair (후보 순번)", "사이트가 보여 준 순서"],
            ["Forward primer · start · stop · length · Tm · GC%", "앞쪽 프라이머의 서열, 위치, 길이, 녹는 온도, GC 비율입니다. "
             "위치는 입력 서열 안의 번호입니다."],
            ["Reverse primer · start · stop · length · Tm · GC%", "뒤쪽 프라이머의 정보입니다. 반대 방향으로 붙기 때문에 "
             "start 번호가 stop 번호보다 큽니다."],
            ["Product length (조각 길이)", "두 프라이머로 만들어지는 조각의 길이"],
            ["Unintended templates: same gene (잘못 붙는 대상: 같은 유전자)", "같은 유전자의 다른 판본에서도 조각이 "
             "만들어지는 곳의 수"],
            ["Unintended templates: other genes (잘못 붙는 대상: 다른 유전자)", "%s 다른 유전자에서도 조각이 만들어질 수 "
             "있는 곳의 수입니다. 0이면 그런 곳이 보고되지 않은 후보입니다." % em("먼저 보실 값입니다.")],
            ["Accepted similar sequences (자동으로 고른 비슷한 서열)", "비슷한 서열 확인 화면에서 도구가 고른 서열(7장)"],
            ["Result URL (결과 페이지 주소)", "웹사이트의 결과 화면입니다. 시간이 지나면 열리지 않을 수 있습니다."],
            ["Note (메모)", "후보 없음, 실패 이유 등"],
        ], [0.42, 0.58]),
        KeepTogether([p("실제 결과 예시", "h2"),
                      p("2장 실습에서 %s 을 설계한 결과 중 앞의 세 줄입니다." % code("NM_000546.6")),
                      table([t("Pair", "후보"), t("Forward primer", "앞쪽 프라이머"), t("Reverse primer", "뒤쪽 프라이머"),
               t("Product", "조각 길이"), t("Unintended", "같은/다른")], [
            ["1", code("ACCTATGGAAACTACTTCCTGAAA") + "<br/>204–227, Tm 57.30", code("ACCATCGCTATCTGAGCAGC") +
             "<br/>703–684, Tm 59.97", "500", "4 / 0"],
            ["2", code("ACCTATGGAAACTACTTCCTGAAA") + "<br/>204–227, Tm 57.30", code("CTTCTTTGGCTGGGGAGAGG") +
             "<br/>1102–1083, Tm 60.03", "899", "4 / 4"],
            ["3", code("ACCTATGGAAACTACTTCCTGAAA") + "<br/>204–227, Tm 57.30", code("CTGGCATTCTGGGAGCTTCA") +
             "<br/>344–325, Tm 60.03", "141", "4 / 0"],
        ], [0.1, 0.33, 0.32, 0.11, 0.14])]),
        p("2번 후보는 다른 유전자에서도 조각이 만들어질 수 있는 곳이 4곳 보고되었습니다. 1번과 3번 후보는 입력 서열 "
          "말고는 같은 유전자의 다른 판본에서만 조각이 만들어집니다."),
        box(["메모 칸에 %s이 적혀 있으면, 엑셀과 같은 폴더에 서열번호%s 파일이 함께 저장됩니다. 사이트의 화면 구성이 "
             "바뀌어 도구가 결과를 읽지 못한 경우이므로, 그 파일을 개발자에게 보내 주세요."
             % (em("결과 페이지를 읽지 못함"), code("_page.html"))]),
        CondPageBreak(110 * mm),
    ])

    # 7. 도구가 대신 판단하는 것
    add([
        h1(TOC[6]),
        p("웹사이트에서 직접 할 때는 사람이 정하던 것들을 도구가 대신 정합니다. 결과를 믿고 쓰시려면 아래 내용을 알고 "
          "계셔야 합니다."),
        p("1. 엑셀의 숫자는 사이트 결과를 옮긴 것입니다", "h2"),
        p("도구는 프라이머를 직접 계산하지 않습니다. Primer-BLAST 결과 화면의 값(서열, 위치, Tm, GC%%, 조각 길이, 잘못 "
          "붙는 대상)을 그대로 옮겨 적습니다. 의심되는 값이 있으면 %s 의 링크로 원래 결과 화면을 확인하세요."
          % tin("Result URL", "결과 페이지 주소")),
        p("2. 비슷한 서열 확인 화면에서 고르는 규칙", "h2"),
        p("웹사이트는 입력 서열과 거의 같은 서열을 찾으면 “프라이머가 붙어도 되는 서열을 골라 달라”는 화면을 보여 줍니다. "
          "도구는 이 목록에서 제목 괄호 안의 유전자 이름(예: %s)이 입력 서열과 같은 것만 고르고 제출합니다. 고른 서열은 "
          "엑셀의 %s 칸에 적힙니다." % (code("TP53"), tin("Accepted similar sequences", "자동으로 고른 비슷한 서열"))),
        table(["한계", "결과"], [
            ["유전자 이름의 표기가 다른 경우", "같은 유전자여도 고르지 않습니다."],
            ["입력 서열 제목에 괄호 유전자 이름이 없는 경우", "아무것도 고르지 않습니다. 같은 유전자의 판본도 ‘잘못 붙는 "
             "대상’으로 취급되어 후보가 줄어들 수 있습니다."],
            ["목록에 같은 유전자 이름의 다른 생물 서열이 섞인 경우", "함께 고릅니다. 생물종은 %s 조건으로 미리 좁혀 "
             "둡니다." % tin("Organism", "생물종")],
        ], [0.42, 0.58]),
        p("3. 웹사이트 기본값을 그대로 쓰는 조건", "h2"),
        p("화면에 없는 조건은 Primer-BLAST 웹사이트의 기본값으로 제출합니다. 실제 결과 화면의 Search Summary에 나온 값은 "
          "다음과 같습니다."),
        table(["조건 (웹사이트 이름)", "값"], [
            ["Database", "RefSeq mRNA (NCBI Messenger RNA Reference Sequences)"],
            ["Specificity check", "켜짐 (Enable search for primer pairs specific to the intended PCR template)"],
            ["Min total mismatches / Min 3' end mismatches", "2 / 2"],
            ["Defined 3' end region length", "5"],
            ["Mismatch threshold to ignore targets", "6"],
            ["Max target size", "4000"],
            ["Primer size (Min / Opt / Max)", "15 / 20 / 25"],
            ["Max Tm difference", "3"],
            ["Max candidate primer pairs", "500"],
            ["Repeat filter / Low complexity filter", "AUTO / Yes"],
        ], [0.45, 0.55]),
        p("4. 구간 칸이 들어가는 곳", "h2"),
        p("웹사이트의 Range 칸은 4개(Forward primer From·To, Reverse primer From·To)입니다. 도구의 %s 은 Forward primer "
          "From에, %s 는 Reverse primer To에 들어가고, 나머지 두 칸은 비워 둡니다. 즉 “프라이머 쌍이 들어갈 전체 구간”을 "
          "정하는 방식입니다." % (tin("Range From", "구간 시작"), tin("Range To", "구간 끝"))),
        p("5. 잘못 붙는 대상을 세는 방법", "h2"),
        p("결과 화면의 “Products on potentially unintended templates” 목록에 나온 서열 수를 셉니다. 제목 괄호 안의 유전자 "
          "이름이 입력 서열과 같으면 same gene, 다르면 other genes로 나눕니다. 입력 서열 제목에 유전자 이름이 없으면 "
          "모두 other genes로 셉니다."),
        p("6. 제출 속도 규칙", "h2"),
        table(["규칙", "값"], [
            ["한 번에 제출하는 서열", "1건 (위에서부터 차례로)"],
            ["결과 확인 간격", "15초"],
            ["한 번에 처리하는 최대 개수", "50개"],
            ["서열 사이 쉬는 시간", "10초"],
            ["서열 하나의 최대 대기", "10분 (넘으면 ‘시간 초과’로 실패)"],
            ["통신 오류", "2초, 4초, 8초 쉬고 다시 시도"],
            ["연속 실패", "3개가 연달아 실패하면 작업 전체를 멈춤"],
        ], [0.4, 0.6]),
        p("7. 1단계에서 바로 설계할 때의 조건", "h2"),
        p("3장 5단계의 %s를 쓰면, 조건은 2단계 화면에서 마지막으로 쓴 값이고 처음이면 웹사이트 기본값입니다."
          % em("받은 뒤 바로 프라이머 설계")),
        CondPageBreak(110 * mm),
    ])

    # 8. 설정
    add([
        h1(TOC[7]),
        p("1단계 화면 오른쪽 위의 %s을 누르면 칸 두 개가 나타납니다. 이 두 값은 1단계(서열 내려받기)에서만 쓰이며, "
          "둘 다 비워 두셔도 도구는 정상으로 작동합니다." % em("설정")),
        figure("s1_settings.png", "설정 구역입니다.", 0.97),
        p("Email (이메일)", "h2"),
        p("NCBI가 문제 상황을 발견했을 때 연락할 주소입니다. 넣어 두시면 갑자기 차단되기 전에 먼저 연락을 받으실 수 "
          "있습니다."),
        p("API key (API 키) — 넣으면 세 배 빨라집니다", "h2"),
        p("NCBI는 프로그램이 1초에 몇 번까지 요청할 수 있는지를 정해 두었습니다. 키가 없으면 1초에 3번, 키가 있으면 1초에 "
          "10번까지 허용됩니다. 발급은 무료이고 3분쯤 걸립니다."),
        table(["순서", "할 일"], [
            ["1", "%s 에 접속해 Google 계정, ORCID, 소속 기관 계정 등으로 로그인합니다." % code("ncbi.nlm.nih.gov/account")],
            ["2", "오른쪽 위의 사용자 이름을 누르고 %s로 들어갑니다." % em("Account settings")],
            ["3", "아래로 내려가 %s 항목의 %s를 누릅니다." % (em("API Key Management"), em("Create an API Key"))],
            ["4", "나타난 36자짜리 글자를 복사해 설정의 API key 칸에 붙여 넣고 %s을 누릅니다." % em("저장")],
        ], [0.1, 0.9]),
        box(["설정은 도구 폴더 안의 %s 파일에 저장되어 다음에도 그대로 쓰입니다. 2단계의 조건과 동의 기록도 같은 파일에 "
             "저장됩니다. 이 파일에는 API key가 들어 있으니 다른 사람에게 보내지 마세요." % code("config.json")]),
    ])

    # 9. 저장된 파일
    add([
        h1(TOC[8]),
        p("1단계에서 저장되는 파일은 FASTA라고 부르는 형식의 보통 텍스트입니다. %s로 시작하는 첫 줄이 그 항목의 "
          "제목이고, 그 아래 줄들이 서열입니다. 홈페이지에서 FASTA 링크를 눌렀을 때 보이던 내용과 같습니다. "
          "2단계의 결과는 엑셀 파일이며, 6장에서 설명했습니다." % code("&gt;")),
        box([p("&gt;NM_000546.6 Homo sapiens tumor protein p53 (TP53), transcript variant 1, mRNA<br/>"
               "CTCAAAAGTCTAGAGCCACCGTCCAGGGAGCAGGTAGCTGCTGGGCTCCGGGGACACTTTGCGTTCGGGC<br/>...", "code")]),
        p("받기가 끝난 뒤 %s이라는 문구가 함께 보일 때가 있습니다. 요청한 항목 중 일부를 NCBI가 돌려주지 않았다는 "
          "뜻입니다. 가장 흔한 경우는 제목이 %s로 끝나는 항목인데, 서열이 아니라 연구 과제를 대표하는 기록이어서 "
          "홈페이지에서도 서열이 나오지 않습니다. 도구의 문제가 아닙니다."
          % (em("N건은 NCBI에서 제공되지 않음"), code("whole genome shotgun sequencing project"))),
        CondPageBreak(90 * mm),
    ])

    # 10. 문제 해결
    add([
        h1(TOC[9]),
        table(["이런 화면이 보이면", "이렇게 하시면 됩니다"], [
            ["‘파이썬 3.9 이상을 찾지 못했습니다’", "열리는 python.org 페이지에서 파이썬을 설치한 뒤 다시 더블클릭해 "
             "주세요(1장 2단계)."],
            ["‘열 수 없습니다’ 경고", "1장 3단계의 보안 허용을 해 주세요."],
            ["더블클릭했는데 검은 창만 열리고 아무 글자도 나오지 않음", "그 창을 닫고 파일을 한 번 더 더블클릭해 주세요."],
            ["브라우저가 저절로 열리지 않음", "브라우저를 직접 켜고, 검은 창에 적힌 주소(보통 %s)를 입력해 주세요."
             % code("http://127.0.0.1:8765")],
            ["화면이 아예 열리지 않음", "검은 창에 %s라고 적혀 있으면 이미 켜져 있는 것입니다. 열려 있는 브라우저 탭을 "
             "확인해 주세요." % em("이미 실행 중입니다")],
            ["‘NCBI 응답이 없습니다’", "인터넷 연결을 확인하고 잠시 뒤 다시 시도해 주세요. 받던 파일은 그대로 남아 "
             "있습니다."],
            ["‘이미 받는 중입니다’ / ‘이미 설계 중입니다’", "한 번에 한 가지 작업만 합니다. 진행 중인 작업이 끝나거나 "
             "중단한 뒤에 다시 시도해 주세요."],
            ["‘저장 방식을 하나 이상 선택하세요’", "‘항목별 파일로 저장’과 ‘합본 파일로 저장’ 중 하나는 켜 두셔야 합니다."],
            ["‘폴더가 없습니다’ 또는 저장 실패", "저장 폴더 칸의 위치에 쓸 권한이 없는 경우입니다. 문서 폴더 등 다른 "
             "위치로 바꿔 주세요."],
            ["‘2단계 안내에 먼저 동의해 주세요’", "2단계 화면을 열어 안내를 읽고 동의해 주세요."],
            ["‘받은 뒤 바로 설계는 한 번에 50개까지만…’", "받을 개수를 50개 이하로 줄이거나, 체크를 끄고 받은 뒤 "
             "2단계에서 나눠서 설계해 주세요."],
            ["‘자동 설계를 시작하지 못했습니다: …’", "뒤에 적힌 이유를 확인하고, 2단계 화면에서 직접 Get Primers를 "
             "눌러 주세요."],
            ["2단계 상태가 ‘실패’, 메모에 ‘Sequence ID not found’", "서열 번호가 NCBI에 없습니다. 오타가 없는지 확인해 "
             "주세요."],
            ["‘연속으로 실패해 멈췄습니다’", "세 서열이 연달아 실패해 도구가 스스로 멈췄습니다. 브라우저로 Primer-BLAST "
             "웹사이트가 열리는지 확인하고, 한참 뒤에 다시 시도해 주세요."],
            ["엑셀 파일 이름 끝에 %s" % code("_2"), "설계하는 동안 결과 엑셀을 열어 두셔서 원래 이름으로 저장하지 못한 "
             "경우입니다. 내용은 같습니다."],
        ], [0.38, 0.62]),
    ])
    return keep_headings(out)


class ManualDoc(SimpleDocTemplate):
    def __init__(self, path, title):
        super().__init__(path, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=16 * mm,
                         bottomMargin=20 * mm, title=title, author="")
        self.toc_pages = {}

    def afterFlowable(self, flowable):
        if isinstance(flowable, Heading):
            self.toc_pages[flowable.toc_text] = self.page


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 14 * mm, PAGE_W - MARGIN, 14 * mm)
    canvas.setFont("Pretendard-Regular", 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(MARGIN, 10 * mm, TITLE + " " + FOOTER)
    canvas.drawRightString(PAGE_W - MARGIN, 10 * mm, str(doc.page))
    canvas.restoreState()


def quick_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Pretendard-Regular", 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(MARGIN, 10 * mm, "자세한 내용은 사용설명서.pdf를 보세요.")
    canvas.restoreState()


def build():
    # 목차 쪽 번호를 알기 위해 두 번 만든다
    first = ManualDoc(OUTPUT, TITLE + " " + FOOTER)
    first.build(story({}), onFirstPage=footer, onLaterPages=footer)
    final = ManualDoc(OUTPUT, TITLE + " " + FOOTER)
    final.build(story(first.toc_pages), onFirstPage=footer, onLaterPages=footer)
    assert final.toc_pages == first.toc_pages, "목차 쪽 번호가 두 번째 만들 때 바뀌었습니다"
    quick = ManualDoc(QUICK_OUTPUT, TITLE + " 빠른 시작")
    quick.build(quick_start(with_title=True), onFirstPage=quick_footer, onLaterPages=quick_footer)
    assert quick.page == 1, "빠른 시작이 1쪽을 넘었습니다"
    for old in os.listdir(PREVIEW):
        if old.startswith("page-") and old.endswith(".png"):
            os.remove(os.path.join(PREVIEW, old))
    subprocess.run(["pdftoppm", "-png", "-r", "96", OUTPUT, os.path.join(PREVIEW, "page")], check=True)
    # pdftoppm은 쪽 수에 따라 page-01.png 처럼 0을 붙이므로 page-1.png 로 맞춘다
    for name in os.listdir(PREVIEW):
        if name.startswith("page-"):
            number = int(name[len("page-"):-len(".png")])
            os.rename(os.path.join(PREVIEW, name), os.path.join(PREVIEW, "page-%d.png" % number))
    print("%s (%d쪽), %s, 미리보기 %s" % (OUTPUT, final.page, QUICK_OUTPUT, PREVIEW))
    print(final.toc_pages)


if __name__ == "__main__":
    build()
