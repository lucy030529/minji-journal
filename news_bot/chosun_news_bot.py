#!/usr/bin/env python3
"""
조선방산기계 데일리뉴스 봇.

매일 아침 조선/방산/기계 관련 뉴스를 카테고리별로 수집해
Claude 로 음슴체 불렛 요약 후 텔레그램으로 전송한다.

특징:
  - 구글 뉴스 RSS(무료, API 키 불필요)로 카테고리별 검색 수집
  - 소스별로 수집 기간(hours)·개수 제한(limit)을 따로 지정 가능
  - TradeWinds / Upstream 은 최근 24시간 기사를 제한 없이 전부 수집
  - 제목의 " - 출처", &nbsp; 등 HTML 찌꺼기 자동 정리
  - 카테고리(🚢조선 / 🛡️방산 / ⚙️기계)로 구분
  - 푸터('총 N건 ...') 없음

환경변수:
  ANTHROPIC_API_KEY   - Claude API 키 (요약용)
  TELEGRAM_BOT_TOKEN  - 조선방산기계 데일리뉴스 봇 토큰
  TELEGRAM_CHAT_ID    - 받을 채팅 ID
선택:
  CLAUDE_MODEL        - 기본 claude-haiku-4-5-20251001
"""

import html
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests
from anthropic import Anthropic

# ---- 설정 ---------------------------------------------------------------

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

KST = timezone(timedelta(hours=9))
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

# 소스에 "hours" 가 없을 때 적용할 기본 수집 기간(시간).
DEFAULT_HOURS = 36


def gnews(query):
    """구글 뉴스 RSS 검색 URL 생성 (한국어/한국 기준)."""
    return (
        f"https://news.google.com/rss/search?q={quote(query)}"
        "&hl=ko&gl=KR&ceid=KR:ko"
    )


# 카테고리별 수집 설정.
#   label    : 카테고리 제목
#   sources  : 소스 목록. 각 소스는 아래 키를 가짐
#       - "gnews": 구글 뉴스 검색어  또는  "feed": 직접 RSS 피드 URL (둘 중 하나)
#       - "limit": 보낼 최대 기사 수 (None = 무제한, 기간 내 전부 수집)
#       - "hours": 수집 기간(시간). 생략 시 DEFAULT_HOURS
#
# ※ TradeWinds / Upstream 은 최근 24시간 기사를 limit 없이 전부 수집하도록 설정함.
CATEGORIES = [
    {
        "label": "🚢 조선",
        "sources": [
            {
                "gnews": (
                    "조선소 OR HD현대중공업 OR 한화오션 OR 삼성중공업 OR HD현대미포 "
                    "OR LNG선 OR FLNG OR 컨테이너선 OR 선박 수주"
                ),
                "limit": 8,
            },
            # TradeWinds: 최근 24시간 기사 전부 (개수 제한 없음)
            {"gnews": "site:tradewindsnews.com", "limit": None, "hours": 24},
            # Upstream: 최근 24시간 기사 전부 (개수 제한 없음)
            {"gnews": "site:upstreamonline.com", "limit": None, "hours": 24},
        ],
    },
    {
        "label": "🛡️ 방산",
        "sources": [
            {
                "gnews": (
                    "방위산업 OR 한화에어로스페이스 OR 한국항공우주산업 OR LIG넥스원 "
                    "OR 현대로템 OR K9 자주포 OR K2 전차 OR 무기 수출"
                ),
                "limit": 5,
            },
        ],
    },
    {
        "label": "⚙️ 기계",
        "sources": [
            {
                "gnews": (
                    "두산에너빌리티 OR 변압기 OR 가스터빈 OR 발전설비 OR HD현대인프라코어 "
                    "OR 건설기계 OR 원전 기자재 OR 플랜트 기자재"
                ),
                "limit": 5,
            },
        ],
    },
]


def require_env():
    missing = [
        n
        for n, v in [
            ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
            ("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN),
            ("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID),
        ]
        if not v
    ]
    if missing:
        sys.exit(f"환경변수가 설정되지 않았습니다: {', '.join(missing)}")


# ---- 1. 수집 + 정리 -----------------------------------------------------


def clean_text(text):
    """&nbsp; 등 HTML 엔티티/태그 제거 및 공백 정리."""
    if not text:
        return ""
    text = html.unescape(text)            # &nbsp; &lt; &amp; 등 먼저 해제
    text = re.sub(r"<[^>]+>", " ", text)  # 그 다음 HTML 태그 제거
    text = text.replace("\xa0", " ")      # nbsp -> 일반 공백
    return re.sub(r"\s+", " ", text).strip()


def clean_title(title, source):
    """제목 끝의 ' - 출처명' 제거."""
    title = clean_text(title)
    if source:
        # "제목 - 출처" 또는 "제목 출처" 형태 모두 정리
        title = re.sub(rf"\s*[-–]\s*{re.escape(source)}\s*$", "", title)
        if title.endswith(source):
            title = title[: -len(source)].rstrip(" -–")
    return title.strip()


def parse_pubdate(text):
    """RSS pubDate 문자열을 UTC datetime 으로. 실패 시 None."""
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def parse_feed(url, since):
    """RSS 한 개를 표준 라이브러리로 파싱해 기사 목록으로 변환. since 이후만."""
    resp = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ChosunNewsBot/1.0)"},
        timeout=30,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    articles = []
    for item in root.findall(".//item"):
        src_el = item.find("source")
        source = (src_el.text or "").strip() if src_el is not None else ""
        title = clean_title(item.findtext("title", ""), source)
        link = (item.findtext("link", "") or "").strip()
        if not title or not link:
            continue
        published = parse_pubdate(item.findtext("pubDate", ""))
        if published and published < since:
            continue
        articles.append(
            {
                "title": title,
                "link": link,
                "summary_src": clean_text(item.findtext("description", "")),
                "source": source,
                "published": published,
            }
        )
    return articles


def collect(category, now):
    """카테고리의 모든 소스를 모아 중복 제거 후 반환.

    소스마다 자체 수집 기간(hours)·개수 제한(limit)을 적용한다.
    limit 이 None 이면 기간 내 기사를 전부 가져온다(TradeWinds/Upstream 용).
    """
    seen, out = set(), []
    for src in category["sources"]:
        hours = src.get("hours", DEFAULT_HOURS)
        since = now - timedelta(hours=hours)
        url = gnews(src["gnews"]) if "gnews" in src else src["feed"]
        try:
            arts = parse_feed(url, since)
        except Exception as e:
            print(f"피드 수집 실패 ({url[:60]}...): {e}", file=sys.stderr)
            continue
        # 소스 내 최신순 정렬 후, limit 이 있으면 그만큼만
        arts.sort(
            key=lambda a: a["published"] or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        if src.get("limit") is not None:
            arts = arts[: src["limit"]]
        # 카테고리 전체 기준 중복 제거
        for art in arts:
            key = re.sub(r"\W+", "", art["title"])[:40]
            if key in seen:
                continue
            seen.add(key)
            out.append(art)
    return out


# ---- 2. Claude 요약 (음슴체 불렛 3~4줄) ----------------------------------


def summarize(client, article):
    body = article["summary_src"] or article["title"]
    prompt = (
        "다음 뉴스를 한국어로 요약해줘. 규칙:\n"
        "- 핵심 내용을 3~4개의 불렛포인트로 정리\n"
        "- 각 줄은 '- ' 로 시작\n"
        "- 음슴체로 작성 (예: '~함', '~됨', '~임', '~밝힘', '~전망')\n"
        "- 사실 위주, 불필요한 수식어 없이\n"
        "- 영어 기사면 한국어로 번역해 요약\n\n"
        f"제목: {article['title']}\n"
        f"내용: {body}"
    )
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    # 혹시 불렛이 아니면 줄마다 '- ' 붙이기
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    fixed = [ln if ln.startswith(("-", "•", "·")) else f"- {ln}" for ln in lines]
    return "\n".join(f"- {ln.lstrip('-•· ').strip()}" for ln in fixed)


# ---- 3. 메시지 조립 + 전송 ----------------------------------------------


def build_message(client):
    now = datetime.now(KST)
    header = f"📅 {now:%Y.%m.%d} ({WEEKDAYS[now.weekday()]}) 조선/방산/기계 Daily News"
    parts = [f"<b>{header}</b>"]

    now_utc = datetime.now(timezone.utc)
    for cat in CATEGORIES:
        articles = collect(cat, now_utc)
        parts.append(f"\n\n<b>{cat['label']}</b>")
        if not articles:
            parts.append("\n· 새 기사 없음")
            continue
        for i, art in enumerate(articles, 1):
            try:
                summary = summarize(client, art)
            except Exception as e:
                summary = f"- {art['summary_src'] or '요약 실패'}"
                print(f"요약 실패: {e}", file=sys.stderr)
            title = html.escape(art["title"])
            src = f" ({html.escape(art['source'])})" if art["source"] else ""
            summary = html.escape(summary)
            link = html.escape(art["link"])
            parts.append(
                f"\n\n<b>{i}. {title}</b>{src}\n{summary}\n🔗 {link}"
            )
    return "".join(parts)


def split_message(text, max_len=4000):
    chunks, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > max_len:
            chunks.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur)
    return chunks


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chunk in split_message(text):
        resp = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"텔레그램 전송 실패: {resp.status_code} {resp.text}")
        time.sleep(0.5)


def main():
    require_env()
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    message = build_message(client)
    send_telegram(message)
    print("전송 완료")


if __name__ == "__main__":
    main()
