#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_wordcloud.py  (v2 — 개선판)
희토류 대시보드용 워드클라우드 생성 스크립트

개선사항:
  - n-gram 노이즈 제거 (ndfeb_ndfeb 같은 반복 bigram 제거)
  - 불용어 대폭 확장 (com, news, usa 등 URL/노이즈 단어)
  - 글자 깨짐 수정 (matplotlib 한글 폰트 적용)
  - 이미지 크기 최적화 (더 작고 선명하게)
  - max_font_size 적용 (특정 단어가 너무 크게 나오는 문제 수정)
"""

import os
import re
import json
from collections import Counter
from pathlib import Path

try:
    from wordcloud import WordCloud
except ImportError:
    raise ImportError("pip install wordcloud")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    plt.rcParams["axes.unicode_minus"] = False
except ImportError:
    raise ImportError("pip install matplotlib")

try:
    import requests
except ImportError:
    requests = None

# ── 경로 설정 ────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent.parent   # scripts/ → 프로젝트 루트
DATA_DIR     = BASE_DIR / "data"
OUTPUT_DIR   = BASE_DIR / "assets" / "images"
FONT_DIR     = BASE_DIR / "assets" / "fonts"

PAPERS_PATH  = DATA_DIR / "papers.json"
PATENTS_PATH = DATA_DIR / "patents.json"
NEWS_PATH    = DATA_DIR / "news.json"

# ── 불용어 정의 ──────────────────────────────────────────────────────────────
EN_STOPWORDS = set([
    # 일반 불용어
    "the","a","an","of","in","and","for","to","with","on","at","by",
    "is","are","was","were","be","been","being","have","has","had",
    "do","does","did","will","would","could","should","may","might",
    "from","as","this","that","these","those","it","its","we","our",
    "their","can","via","using","based","high","new","used","also",
    "two","three","one","study","show","shows","shown","result","results",
    "effect","effects","paper","article","research","method","methods",
    "approach","propose","proposed","present","presented","between",
    "which","during","after","than","more","not","all","both","while",
    "among","without","through","into","about","such","significantly",
    "however","therefore","thus","furthermore","moreover","well",
    "but","or","if","when","where","how","each","other","different",
    "various","several","many","most","first","second","large","small",
    "good","low","due","up","over","under","further","here",
    "they","them","its","was","has","been","being","here","then","than",
    # URL/뉴스 노이즈
    "com","www","http","https","html","org","net","edu",
    "news","google","reuters","bloomberg","barron","wsj","wsj",
    "investing","usa","inc","ltd","corp","co","amp",
    "deal","deals","today","say","says","said",
    "report","reports","reported","reporting",
    "get","set","make","made","take","taken","give","given",
    "plant","plants","startup","startups","elements",
    "stock","market","markets","supply","chain","chains",
    "billion","million","trillion","percent",
    "trump","china","chinese","us","eu","uk",
    "amid","amid","key","top","new","old","big",
    "year","years","month","months","week","weeks","day","days",
    "time","times","per","non","anti","pro",
])

DOMAIN_STOPWORDS = set([
    # 너무 흔한 도메인 단어
    "magnet","magnets","magnetic","rare","earth","material","materials",
    "property","properties","temperature","performance","phase","phases",
    "structure","structures","alloy","alloys","process","processing",
    "application","applications","field","energy","power","system","systems",
    "sample","samples","figure","fig","table","degree",
    "wt","vol","mpa","kj","nm","mm","cm","ghz","mhz","khz",
    "et","al","ii","iii","iv","vs","ie","eg","addition","correlation",
    # MnBi 관련 노이즈
    "permanent","hard","soft","metal","metals","oxide","oxides",
    "powder","powders","film","films","layer","layers","sub",
    "density","functional","theory","topological","insulator",
    "monolayer","structural","response","bulk",
    # 재활용 관련 노이즈  
    "facility","facilities","network","apple","theguru","hypomag",
    "today","investing","emnews",
])

KO_STOPWORDS = set([
    "의","을","를","이","가","은","는","에","에서","로","으로","와","과",
    "한","및","등","대한","통한","위한","관한","자석","자성","재료",
    "연구","특성","개발","기술","분석","제조","향상","적용","활용",
    "관련","통해","위해","대해","따른","따라","으로의","에의","에서의",
    "배터리","소재","공정","시장","산업","생산","수요","공급","가격",
    "국내","해외","글로벌","현황","동향","전망",
    "뉴스","기사","보도","관련","업체","기업","정부","중국",
    "미국","한국","세계","글로벌","올해","지난","최근","향후",
])

ALL_EN_STOPWORDS = EN_STOPWORDS | DOMAIN_STOPWORDS


# ── 한글 폰트 탐색/다운로드 ──────────────────────────────────────────────────
def get_korean_font_path():
    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/NanumGothic.ttf",
        str(FONT_DIR / "NanumGothic.ttf"),
    ]
    for path in candidates:
        if os.path.exists(path):
            print(f"  🔤 한글 폰트 발견: {path}")
            return path

    font_path = FONT_DIR / "NanumGothic.ttf"
    if not font_path.exists() and requests:
        print("  📥 NanumGothic 폰트 다운로드 중...")
        try:
            FONT_DIR.mkdir(parents=True, exist_ok=True)
            url = ("https://github.com/google/fonts/raw/main/ofl/"
                   "nanumgothic/NanumGothic-Regular.ttf")
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            font_path.write_bytes(resp.content)
            print(f"  ✅ 폰트 다운로드 완료: {font_path}")
        except Exception as e:
            print(f"  ⚠️  폰트 다운로드 실패: {e}")
            return None
    return str(font_path) if font_path.exists() else None


# ── 텍스트 전처리 ─────────────────────────────────────────────────────────────
def tokenize_en(text: str) -> list:
    """영어 텍스트 → 단어 + 의미있는 바이그램만"""
    text = text.lower()
    text = re.sub(r"[^a-z\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # 단어 필터링 (최소 3글자, 불용어 제외)
    tokens = [w for w in text.split()
              if len(w) >= 3 and w not in ALL_EN_STOPWORDS]

    result = list(tokens)

    # 바이그램: 두 단어 모두 4글자 이상, 서로 다른 단어만
    for i in range(len(tokens) - 1):
        w1, w2 = tokens[i], tokens[i + 1]
        if (len(w1) >= 4 and len(w2) >= 4   # 너무 짧은 단어 제외
                and w1 != w2                  # 동일 단어 반복 제외 (ndfeb_ndfeb 방지)
                and w1 not in ALL_EN_STOPWORDS
                and w2 not in ALL_EN_STOPWORDS):
            result.append(f"{w1}_{w2}")

    return result


def tokenize_ko(text: str) -> list:
    """한국어 텍스트 → 어절 토큰"""
    text = re.sub(r"[^\uAC00-\uD7A3\s]", " ", text)
    return [w for w in text.split()
            if len(w) >= 2 and w not in KO_STOPWORDS]


def collect_tokens(texts: list, lang: str = "en") -> Counter:
    counter = Counter()
    for text in texts:
        if not text:
            continue
        if lang == "ko":
            counter.update(tokenize_ko(text))
        else:
            counter.update(tokenize_en(text))
    return counter


def filter_freq(counter: Counter, min_count: int = 2) -> dict:
    """
    빈도 필터 + 바이그램 품질 필터:
    - 단독 단어의 빈도가 충분한 바이그램만 유지
    - 최소 빈도 미달 제거
    """
    # 단독 단어 빈도 맵
    word_freq = {w: c for w, c in counter.items() if "_" not in w}

    filtered = {}
    for word, count in counter.items():
        if count < min_count:
            continue
        if "_" in word:
            # 바이그램: 구성 단어 각각이 2회 이상 등장해야만 유지
            parts = word.split("_")
            if any(word_freq.get(p, 0) < 2 for p in parts):
                continue
        filtered[word] = count
    return filtered


# ── 데이터 로드 ──────────────────────────────────────────────────────────────
def load_json(path: Path):
    if not path.exists():
        print(f"  ⚠️  파일 없음: {path}")
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_items(data) -> list:
    if isinstance(data, list):
        return data
    return data.get("items", [])


# ── 워드클라우드 생성 ─────────────────────────────────────────────────────────
def make_wordcloud(freq: Counter, output_path: Path, colormap: str,
                   label: str, font_path: str = None, min_count: int = 2) -> bool:

    filtered = filter_freq(freq, min_count)

    if len(filtered) < 5:
        print(f"  ⏭️  [{label}] 단어 수 부족 ({len(filtered)}개) — 스킵")
        return False

    wc_kwargs = dict(
        width=800,
        height=420,
        background_color="white",
        max_words=80,
        max_font_size=100,    # ← 특정 단어가 너무 커지는 문제 방지
        min_font_size=8,
        colormap=colormap,
        prefer_horizontal=0.8,
        collocations=False,
    )
    if font_path:
        wc_kwargs["font_path"] = font_path

    wc = WordCloud(**wc_kwargs).generate_from_frequencies(filtered)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")

    # 제목: 한글 폰트 적용 or 영어 대체
    if font_path and os.path.exists(font_path):
        fp = fm.FontProperties(fname=font_path, size=13)
        ax.set_title(label, fontproperties=fp, fontweight="bold", pad=8)
    else:
        # 한글 제거 후 영어로 표시
        label_en = re.sub(r"[^\x00-\x7F]+", "", label).strip()
        ax.set_title(label_en, fontsize=13, fontweight="bold", pad=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    word_count = len(filtered)
    print(f"  ✅ [{label}] {word_count}개 단어 → {output_path.name}")
    return True


# ── 메인 ─────────────────────────────────────────────────────────────────────
def main():
    print("\n🌀 워드클라우드 생성 시작 (v2)\n")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("📂 데이터 로드 중...")
    papers_raw  = get_items(load_json(PAPERS_PATH))
    patents_raw = get_items(load_json(PATENTS_PATH))
    news_raw    = get_items(load_json(NEWS_PATH))
    print(f"   논문 {len(papers_raw)}건 / 특허 {len(patents_raw)}건 / 뉴스 {len(news_raw)}건\n")

    def get_texts(items, cat_key, fields=("title", "abstract")):
        return [
            " ".join(str(item.get(f, "")) for f in fields)
            for item in items
            if item.get("category", "") == cat_key
        ]

    korean_font = get_korean_font_path()
    print()

    results = {}

    # ① NdFeB
    print("🔵 NdFeB 워드클라우드 생성 중...")
    texts = get_texts(papers_raw, "NdFeB") + get_texts(patents_raw, "NdFeB")
    results["ndfeb"] = make_wordcloud(
        collect_tokens(texts, "en"),
        OUTPUT_DIR / "wc_ndfeb.png",
        colormap="Blues", label="NdFeB 논문+특허",
        font_path=korean_font,
    )

    # ② MnBi
    print("🟢 MnBi 워드클라우드 생성 중...")
    texts = get_texts(papers_raw, "MnBi") + get_texts(patents_raw, "MnBi")
    results["mnbi"] = make_wordcloud(
        collect_tokens(texts, "en"),
        OUTPUT_DIR / "wc_mnbi.png",
        colormap="Greens", label="MnBi 논문+특허",
        font_path=korean_font,
    )

    # ③ Recycling
    print("🟠 Recycling 워드클라우드 생성 중...")
    texts = (get_texts(papers_raw, "NdFeB_Recycling") +
             get_texts(patents_raw, "NdFeB_Recycling") +
             [n.get("title", "") for n in news_raw
              if n.get("category", "") == "NdFeB_Recycling"])
    results["recycling"] = make_wordcloud(
        collect_tokens(texts, "en"),
        OUTPUT_DIR / "wc_recycling.png",
        colormap="Oranges", label="Recycling 논문+특허+뉴스",
        font_path=korean_font,
    )

    # ④ 국내 뉴스 (한글)
    print("🟣 국내 뉴스 워드클라우드 생성 중...")
    texts = [n.get("title", "") for n in news_raw
             if n.get("source_lang", "") == "ko"]
    results["news_ko"] = make_wordcloud(
        collect_tokens(texts, "ko"),
        OUTPUT_DIR / "wc_news_ko.png",
        colormap="Purples", label="국내 뉴스 키워드",
        font_path=korean_font, min_count=1,
    )

    # ⑤ 해외 뉴스 (영어)
    print("🔵 해외 뉴스 워드클라우드 생성 중...")
    texts = [n.get("title", "") for n in news_raw
             if n.get("source_lang", "") != "ko"]
    results["news_en"] = make_wordcloud(
        collect_tokens(texts, "en"),
        OUTPUT_DIR / "wc_news_en.png",
        colormap="cool", label="Global News Keywords",
        min_count=1,
    )

    # 결과 요약
    print("\n" + "═" * 50)
    success = sum(1 for v in results.values() if v)
    print(f"✅ 워드클라우드 생성 완료! ({success}/5개 성공)")
    print(f"   📁 저장 위치: {OUTPUT_DIR.resolve()}")
    print("═" * 50 + "\n")


if __name__ == "__main__":
    main()
