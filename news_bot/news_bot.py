#!/usr/bin/env python3
"""
매일 아침 전일 국내외 주요 뉴스를 요약해 텔레그램으로 전송하는 봇.

흐름:
  1. NewsAPI 에서 국내(kr) + 해외(us) 주요 헤드라인을 수집
  2. Claude API 로 각 기사를 한국어 2~3줄로 요약
  3. 텔레그램 봇으로 [제목 / 요약 / 원문링크] 형식 메시지 전송

필요한 환경변수:
  NEWSAPI_KEY          - https://newsapi.org 에서 발급
  ANTHROPIC_API_KEY    - https://console.anthropic.com 에서 발급
  TELEGRAM_BOT_TOKEN   - @BotFather 로 봇 생성 시 발급
  TELEGRAM_CHAT_ID     - 메시지를 받을 채팅 ID
선택 환경변수:
  CLAUDE_MODEL         - 요약에 쓸 모델 (기본: claude-haiku-4-5-20251001)
  ARTICLES_PER_CATEGORY- 카테고리별 기사 수 (기본: 5)
"""

import html
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from anthropic import Anthropic

# ---- 설정 ---------------------------------------------------------------

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
ARTICLES_PER_CATEGORY = int(os.environ.get("ARTICLES_PER_CATEGORY", "5"))

# (카테고리 라벨, NewsAPI top-headlines 파라미터)
CATEGORIES = [
    ("🇰🇷 국내 주요 뉴스", {"country": "kr"}),
    ("🌏 해외 주요 뉴스", {"country": "us"}),
]

KST = timezone(timedelta(hours=9))


def require_env():
    missing = [
        name
        for name, val in [
            ("NEWSAPI_KEY", NEWSAPI_KEY),
            ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
            ("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN),
            ("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID),
        ]
        if not val
    ]
    if missing:
        sys.exit(f"환경변수가 설정되지 않았습니다: {', '.join(missing)}")


# ---- 1. 뉴스 수집 -------------------------------------------------------


def fetch_news(params, limit):
    """NewsAPI top-headlines 에서 기사 목록을 가져온다."""
    query = {"apiKey": NEWSAPI_KEY, "pageSize": limit, **params}
    resp = requests.get(
        "https://newsapi.org/v2/top-headlines", params=query, timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"NewsAPI 오류: {data.get('message', data)}")

    articles = []
    for a in data.get("articles", []):
        title = (a.get("title") or "").strip()
        url = (a.get("url") or "").strip()
        if not title or not url:
            continue
        articles.append(
            {
                "title": title,
                "url": url,
                "description": (a.get("description") or "").strip(),
                "content": (a.get("content") or "").strip(),
                "source": (a.get("source") or {}).get("name", ""),
            }
        )
    return articles


# ---- 2. Claude 요약 -----------------------------------------------------


def summarize(client, article):
    """기사 한 건을 한국어 2~3줄로 요약한다."""
    body = article["content"] or article["description"] or article["title"]
    prompt = (
        "다음 뉴스 기사를 한국어로 요약해줘. 규칙:\n"
        "- 핵심 내용을 2~3개의 불렛포인트로 정리\n"
        "- 각 줄은 '- ' 로 시작\n"
        "- 음슴체(예: '~함', '~됨', '~임', '~밝힘')로 작성\n"
        "- 불필요한 수식어 없이 사실 위주로\n\n"
        f"제목: {article['title']}\n"
        f"내용: {body}"
    )
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if block.type == "text").strip()


# ---- 3. 텔레그램 전송 ---------------------------------------------------


def send_telegram(text):
    """텔레그램으로 메시지를 보낸다. 4096자 제한에 맞춰 분할 전송."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chunk in split_message(text, 4000):
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
        time.sleep(0.5)  # rate limit 여유


def split_message(text, max_len):
    """긴 메시지를 줄 단위로 max_len 이하 조각으로 나눈다."""
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current.strip():
        chunks.append(current)
    return chunks


# ---- 메시지 조립 --------------------------------------------------------


def build_message(client):
    yesterday = (datetime.now(KST) - timedelta(days=1)).strftime("%Y년 %m월 %d일")
    parts = [f"<b>📅 {yesterday} 주요 뉴스 요약</b>\n"]

    for label, params in CATEGORIES:
        articles = fetch_news(params, ARTICLES_PER_CATEGORY)
        parts.append(f"\n<b>{label}</b>")
        if not articles:
            parts.append("· 수집된 기사가 없습니다.")
            continue
        for i, art in enumerate(articles, 1):
            try:
                summary = summarize(client, art)
            except Exception as e:  # 요약 실패해도 제목/링크는 보냄
                summary = art["description"] or "(요약 실패)"
                print(f"요약 실패: {e}", file=sys.stderr)
            title = html.escape(art["title"])
            summary = html.escape(summary)
            src = f" ({html.escape(art['source'])})" if art["source"] else ""
            parts.append(
                f"\n<b>{i}. {title}</b>{src}\n"
                f"{summary}\n"
                f"🔗 {html.escape(art['url'])}"
            )
    return "\n".join(parts)


def main():
    require_env()
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    message = build_message(client)
    send_telegram(message)
    print("전송 완료")


if __name__ == "__main__":
    main()
