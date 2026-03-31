#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_wordcloud.py
희토류 대시보드용 워드클라우드 생성 스크립트

사용법:
    python generate_wordcloud.py

출력:
    assets/images/wc_ndfeb.png
    assets/images/wc_mnbi.png
    assets/images/wc_recycling.png
    assets/images/wc_news_ko.png
    assets/images/wc_news_en.png
"""

import os
import json
import re
from collections import Counter
from pathlib import Path

# ── 의존 패키지 임포트 ──────────────────────────────────────────────────────
try:
    from wordcloud import WordCloud
except ImportError:
    raise ImportError("wordcloud 패키지가 없습니다. 실행 전에: pip install wordcloud")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    raise ImportError("matplotlib 패키지가 없습니다. 실행 전에: pip install matplotlib")

try:
    import requests
except ImportError:
    requests = None  # 한글 폰트 자동 다운로드 시에만 필요

# ── 경로 설정 ───────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent.parent 
DATA_DIR      = BASE_DIR / "data"
OUTPUT_DIR    = BASE_DIR / "assets" / "images"
FONT_DIR      = BASE_DIR / "assets" / "fonts"

PAPERS_PATH   = DATA_DIR / "papers.json"
PATENTS_PATH  = DATA_DIR / "patents.json"
NEWS_PATH     = DATA_DIR / "news.json"

# ── 불용어 정의 ─────────────────────────────────────────────────────────────
EN_STOPWORDS = set([
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
    "good","low","due","up","significantly","significantly","over",
    "under","further","here","they","them","were","has","been","being"
])

DOMAIN_STOPWORDS = set([
    "magnet","magnets","magnetic","rare","earth","material","materials",
    "property","properties","temperature","performance","phase","phases",
    "structure","structures","alloy","alloys","process","processing",
    "application","applications","field","energy","power","system",
    "systems","sample","samples","figure","fig","table","degree",
    "wt","vol","mpa","kj","nm","mm","cm","ghz","mhz","khz",
    "et","al","ii","iii","iv","vs","ie","eg","addition","correlation"
])

KO_STOPWORDS = set([
    "의","을","를","이","가","은","는","에","에서","로","으로","와","과",
    "한","및","등","대한","통한","위한","관한","자석","자성","재료",
    "연구","특성","개발","기술","분석","제조","향상","적용","활용",
    "관련","통해","위해","대해","따른","따라","으로의","에의","에서의",
    "배터리","소재","공정","시장","산업","생산","수요","공급","가격",
    "국내","해외","글로벌","현황","동향","전망"
])

# 모든 불용어 통합 (소문자)
ALL_EN_STOPWORDS = EN_STOPWORDS | DOMAIN_STOPWORDS

# ── 워드클라우드별 컬러맵 및 라벨 설정 ──────────────────────────────────────
WC_CONFIG = {
    "ndfeb":    {"colormap": "Blues",   "label": "NdFeB 논문+특허"},
    "mnbi":     {"colormap": "Greens",  "label": "MnBi 논문+특허"},
    "recycling":{"colormap": "Oranges", "label": "Recycling 논문+특허+뉴스"},
    "news_ko":  {"colormap": "Purples", "label": "국내 뉴스"},
    "news_en":  {"colormap": "cool",    "label": "해외 뉴스"},
}

# ── 한글 폰트 경로 탐색/다운로드 ────────────────────────────────────────────
def get_korean_font_path() -> str | None:
    """시스템 폰트 탐색 → 없으면 NanumGothic 자동 다운로드"""
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

    # 자동 다운로드
    font_path = FONT_DIR / "NanumGothic.ttf"
    if not font_path.exists():
        if requests is None:
            print("  ⚠️  requests 패키지 없음 — 한글 폰트 자동 다운로드 불가 (pip install requests)")
            return None
        print("  📥 NanumGothic 폰트 다운로드 중...")
        try:
            FONT_DIR.mkdir(parents=True, exist_ok=True)
            url = ("https://github.com/google/fonts/raw/main/ofl/"
                   "nanumgothic/NanumGothic-Regular.ttf")
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            font_path.write_bytes(resp.content)
            print(f"  ✅ 폰트 저장 완료: {font_path}")
        except Exception as e:
            print(f"  ⚠️  폰트 다운로드 실패: {e}")
            return None
    return str(font_path)

# ── 텍스트 전처리 ────────────────────────────────────────────────────────────
def tokenize_en(text: str, use_ngrams: bool = True) -> list[str]:
    """영어 텍스트 → 단어+바이그램+트라이그램 토큰 리스트"""
    text = text.lower()
    text = re.sub(r"[^a-z\s\-]", " ", text)
    tokens = [w for w in text.split()
              if len(w) >= 3 and w not in ALL_EN_STOPWORDS]

    result = list(tokens)
    if use_ngrams:
        # 바이그램
        for i in range(len(tokens) - 1):
            bg = f"{tokens[i]}_{tokens[i+1]}"
            result.append(bg)
        # 트라이그램
        for i in range(len(tokens) - 2):
            tg = f"{tokens[i]}_{tokens[i+1]}_{tokens[i+2]}"
            result.append(tg)
    return result


def tokenize_ko(text: str) -> list[str]:
    """한국어 텍스트 → 어절/단어 토큰 리스트"""
    text = re.sub(r"[^가-힣\s]", " ", text)
    return [w for w in text.split()
            if len(w) >= 2 and w not in KO_STOPWORDS]


def collect_tokens(texts: list[str], lang: str = "en") -> Counter:
    """텍스트 리스트 → Counter(빈도)"""
    counter = Counter()
    for text in texts:
        if not text:
            continue
        if lang == "ko":
            counter.update(tokenize_ko(text))
        else:
            counter.update(tokenize_en(text))
    return counter

# ── 데이터 로드 ──────────────────────────────────────────────────────────────
def load_json(path: Path) -> dict | list:
    if not path.exists():
        print(f"  ⚠️  파일 없음: {path}")
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_items(data: dict | list) -> list:
    """papers/patents: {"items": [...]} 또는 list 형태 모두 지원"""
    if isinstance(data, list):
        return data
    return data.get("items", [])

# ── 워드클라우드 생성 ────────────────────────────────────────────────────────
def make_wordcloud(
    freq: Counter,
    output_path: Path,
    colormap: str,
    label: str,
    font_path: str | None = None,
    min_count: int = 2,
) -> bool:
    """
    Counter → 워드클라우드 PNG 저장
    Returns True on success, False on skip.
    """
    # min_count 이하 제거
    filtered = {w: c for w, c in freq.items() if c >= min_count}

    if len(filtered) < 5:
        print(f"  ⏭️  [{label}] 단어 수 부족 ({len(filtered)}개) — 스킵")
        return False

    wc_kwargs = dict(
        width=900,
        height=500,
        background_color="white",
        max_words=100,
        colormap=colormap,
        prefer_horizontal=0.85,
        collocations=False,          # 이미 n-gram 직접 처리하므로 내부 중복 방지
    )
    if font_path:
        wc_kwargs["font_path"] = font_path

    wc = WordCloud(**wc_kwargs).generate_from_frequencies(filtered)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title(label, fontsize=14, fontweight="bold", pad=10)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"  ✅ [{label}] {len(filtered)}개 단어 → {output_path.name}")
    return True

# ── 메인 로직 ────────────────────────────────────────────────────────────────
def main():
    print("\n🌀 워드클라우드 생성 시작\n")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ─ 데이터 로드
    print("📂 데이터 로드 중...")
    papers_raw  = get_items(load_json(PAPERS_PATH))
    patents_raw = get_items(load_json(PATENTS_PATH))
    news_raw    = get_items(load_json(NEWS_PATH))
    print(f"   논문 {len(papers_raw)}건 / 특허 {len(patents_raw)}건 / 뉴스 {len(news_raw)}건\n")

    # ─ 카테고리별 텍스트 분류
    CAT_MAP = {
        "ndfeb":     "NdFeB",
        "mnbi":      "MnBi",
        "recycling": "NdFeB_Recycling",
    }

    def get_texts(items, cat_key, fields=("title", "abstract")):
        return [
            " ".join(str(item.get(f, "")) for f in fields)
            for item in items
            if item.get("category", "") == cat_key
        ]

    korean_font = get_korean_font_path()
    print()

    results = {}

    # ── ① NdFeB 워드클라우드
    print("🔵 NdFeB 워드클라우드 생성 중...")
    texts_ndfeb = (get_texts(papers_raw,  "NdFeB") +
                   get_texts(patents_raw, "NdFeB"))
    freq_ndfeb = collect_tokens(texts_ndfeb, lang="en")
    results["ndfeb"] = make_wordcloud(
        freq_ndfeb,
        OUTPUT_DIR / "wc_ndfeb.png",
        colormap="Blues",
        label="NdFeB 논문+특허",
    )

    # ── ② MnBi 워드클라우드
    print("🟢 MnBi 워드클라우드 생성 중...")
    texts_mnbi = (get_texts(papers_raw,  "MnBi") +
                  get_texts(patents_raw, "MnBi"))
    freq_mnbi = collect_tokens(texts_mnbi, lang="en")
    results["mnbi"] = make_wordcloud(
        freq_mnbi,
        OUTPUT_DIR / "wc_mnbi.png",
        colormap="Greens",
        label="MnBi 논문+특허",
    )

    # ── ③ Recycling 워드클라우드
    print("🟠 Recycling 워드클라우드 생성 중...")
    texts_rec = (get_texts(papers_raw,  "NdFeB_Recycling") +
                 get_texts(patents_raw, "NdFeB_Recycling") +
                 [item.get("title", "")
                  for item in news_raw
                  if item.get("category", "") == "NdFeB_Recycling"])
    freq_rec = collect_tokens(texts_rec, lang="en")
    results["recycling"] = make_wordcloud(
        freq_rec,
        OUTPUT_DIR / "wc_recycling.png",
        colormap="Oranges",
        label="Recycling 논문+특허+뉴스",
    )

    # ── ④ 국내 뉴스 워드클라우드 (한글)
    print("🟣 국내 뉴스 워드클라우드 생성 중...")
    texts_ko = [item.get("title", "")
                for item in news_raw
                if item.get("source_lang", "") == "ko"]
    freq_ko = collect_tokens(texts_ko, lang="ko")
    results["news_ko"] = make_wordcloud(
        freq_ko,
        OUTPUT_DIR / "wc_news_ko.png",
        colormap="Purples",
        label="국내 뉴스 키워드",
        font_path=korean_font,
        min_count=1,
    )

    # ── ⑤ 해외 뉴스 워드클라우드 (영어)
    print("🔵 해외 뉴스 워드클라우드 생성 중...")
    texts_en = [item.get("title", "")
                for item in news_raw
                if item.get("source_lang", "") != "ko"]
    freq_en = collect_tokens(texts_en, lang="en")
    results["news_en"] = make_wordcloud(
        freq_en,
        OUTPUT_DIR / "wc_news_en.png",
        colormap="cool",
        label="해외 뉴스 키워드",
        min_count=1,
    )

    # ─ 최종 결과 요약
    print("\n" + "═" * 50)
    success = sum(1 for v in results.values() if v)
    print(f"✅ 워드클라우드 생성 완료! ({success}/5개 성공)")
    print(f"   📁 저장 위치: {OUTPUT_DIR.resolve()}")
    print("═" * 50 + "\n")


if __name__ == "__main__":
    main()
