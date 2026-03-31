#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_wordcloud.py  (v3 — 뉴스 전용)
희토류 대시보드용 워드클라우드 생성 스크립트

출력 (뉴스만):
    assets/images/wc_news_ko.png   ← 국내 뉴스
    assets/images/wc_news_en.png   ← 해외 뉴스
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
BASE_DIR   = Path(__file__).parent.parent   # scripts/ → 프로젝트 루트
DATA_DIR   = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "assets" / "images"
FONT_DIR   = BASE_DIR / "assets" / "fonts"

NEWS_PATH  = DATA_DIR / "news.json"

# ── 불용어 ───────────────────────────────────────────────────────────────────
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
    "good","low","due","up","over","under","further","here","then",
    "they","them","com","www","http","https","html","org","net",
    "news","google","reuters","bloomberg","wsj","investing","usa",
    "inc","ltd","corp","co","amp","deal","deals","today","say","says",
    "said","report","reports","reported","get","set","make","made",
    "take","taken","stock","market","markets","supply","chain",
    "billion","million","trillion","percent","amid","key","top","old",
    "year","years","month","months","week","weeks","day","days",
    "time","times","per","non","anti","pro","new","big",
])

DOMAIN_STOPWORDS = set([
    "magnet","magnets","magnetic","rare","earth","material","materials",
    "property","properties","temperature","performance","phase","phases",
    "structure","structures","alloy","alloys","process","processing",
    "application","applications","field","energy","power","system","systems",
    "metal","metals","oxide","oxides","permanent","hard","soft",
])

KO_STOPWORDS = set([
    "의","을","를","이","가","은","는","에","에서","로","으로","와","과",
    "한","및","등","대한","통한","위한","관한","자석","자성","재료",
    "연구","특성","개발","기술","분석","제조","향상","적용","활용",
    "관련","통해","위해","대해","따른","따라","으로의","에의","에서의",
    "배터리","소재","공정","시장","산업","생산","수요","공급","가격",
    "국내","해외","글로벌","현황","동향","전망","뉴스","기사","보도",
    "업체","기업","정부","중국","미국","한국","세계","올해","지난","최근","향후",
])

ALL_EN_STOPWORDS = EN_STOPWORDS | DOMAIN_STOPWORDS


# ── 한글 폰트 탐색 ────────────────────────────────────────────────────────────
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
    text = text.lower()
    text = re.sub(r"[^a-z\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    tokens = [w for w in text.split()
              if len(w) >= 3 and w not in ALL_EN_STOPWORDS]
    result = list(tokens)
    for i in range(len(tokens) - 1):
        w1, w2 = tokens[i], tokens[i + 1]
        if (len(w1) >= 4 and len(w2) >= 4
                and w1 != w2
                and w1 not in ALL_EN_STOPWORDS
                and w2 not in ALL_EN_STOPWORDS):
            result.append(f"{w1}_{w2}")
    return result


def tokenize_ko(text: str) -> list:
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


def filter_freq(counter: Counter, min_count: int = 1) -> dict:
    word_freq = {w: c for w, c in counter.items() if "_" not in w}
    filtered = {}
    for word, count in counter.items():
        if count < min_count:
            continue
        if "_" in word:
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
                   label: str, font_path: str = None, min_count: int = 1) -> bool:

    filtered = filter_freq(freq, min_count)

    if len(filtered) < 5:
        print(f"  ⏭️  [{label}] 단어 수 부족 ({len(filtered)}개) — 스킵")
        return False

    wc_kwargs = dict(
        width=600,           # ← 축소 (기존 800)
        height=320,          # ← 축소 (기존 420)
        background_color="white",
        max_words=60,        # ← 축소 (기존 80)
        max_font_size=80,    # ← 축소 (기존 100)
        min_font_size=7,
        colormap=colormap,
        prefer_horizontal=0.8,
        collocations=False,
    )
    if font_path:
        wc_kwargs["font_path"] = font_path

    wc = WordCloud(**wc_kwargs).generate_from_frequencies(filtered)

    fig, ax = plt.subplots(figsize=(7, 4))   # ← 축소 (기존 9, 5)
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")

    if font_path and os.path.exists(font_path):
        fp = fm.FontProperties(fname=font_path, size=12)
        ax.set_title(label, fontproperties=fp, fontweight="bold", pad=6)
    else:
        label_en = re.sub(r"[^\x00-\x7F]+", "", label).strip()
        ax.set_title(label_en, fontsize=12, fontweight="bold", pad=6)

    plt.tight_layout()
    plt.savefig(output_path, dpi=100, bbox_inches="tight")  # ← dpi 축소 (기존 120)
    plt.close(fig)

    print(f"  ✅ [{label}] {len(filtered)}개 단어 → {output_path.name}")
    return True


# ── 메인 ─────────────────────────────────────────────────────────────────────
def main():
    print("\n🌀 워드클라우드 생성 시작 (뉴스 전용 v3)\n")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("📂 데이터 로드 중...")
    news_raw = get_items(load_json(NEWS_PATH))
    print(f"   뉴스 {len(news_raw)}건\n")

    korean_font = get_korean_font_path()
    print()

    results = {}

    # ① 국내 뉴스 (한글)
    print("🟣 국내 뉴스 워드클라우드 생성 중...")
    texts = [n.get("title", "") for n in news_raw
             if n.get("source_lang", "") == "ko"]
    results["news_ko"] = make_wordcloud(
        collect_tokens(texts, "ko"),
        OUTPUT_DIR / "wc_news_ko.png",
        colormap="Purples", label="국내 뉴스 키워드",
        font_path=korean_font, min_count=1,
    )

    # ② 해외 뉴스 (영어)
    print("🔵 해외 뉴스 워드클라우드 생성 중...")
    texts = [n.get("title", "") for n in news_raw
             if n.get("source_lang", "") != "ko"]
    results["news_en"] = make_wordcloud(
        collect_tokens(texts, "en"),
        OUTPUT_DIR / "wc_news_en.png",
        colormap="Blues", label="Global News Keywords",
        min_count=1,
    )

    # ── 결과 요약
    print("\n" + "═" * 50)
    success = sum(1 for v in results.values() if v)
    print(f"✅ 워드클라우드 생성 완료! ({success}/2개 성공)")
    print(f"   📁 저장 위치: {OUTPUT_DIR.resolve()}")
    print("═" * 50 + "\n")


if __name__ == "__main__":
    main()
