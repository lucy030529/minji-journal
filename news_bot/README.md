# 📰 조선방산기계 데일리뉴스 봇

매일 아침 **07:00 (KST)** 에 조선/방산/기계 관련 전일 뉴스를 카테고리별로 수집·요약해
텔레그램으로 보내주는 봇입니다.

- **수집**: 구글 뉴스 RSS (무료, API 키 불필요) + 직접 RSS 피드(선택)
- **분류**: 🚢 조선 / 🛡️ 방산 / ⚙️ 기계
- **정리**: 제목의 ` - 출처`, `&nbsp;` 등 HTML 찌꺼기 자동 제거
- **요약**: Claude API — 음슴체 불렛포인트 3~4줄
- **전송**: 텔레그램 봇 (`제목 / 요약 / 원문링크`, 푸터 없음)
- **스케줄**: GitHub Actions cron (서버 불필요, 무료)

> 메인 스크립트: [`chosun_news_bot.py`](chosun_news_bot.py)
> 범용 뉴스 버전(국내·해외 일반): [`news_bot.py`](news_bot.py) — 스케줄 미설정, 참고용

---

## 1. 준비물 — API 키 / 토큰

| 항목 | 발급처 | 용도 |
|------|--------|------|
| Anthropic(Claude) API 키 | https://console.anthropic.com | 기사 요약 |
| 텔레그램 봇 토큰 | 텔레그램 **@BotFather** → `/mybots` | 발신 봇 |
| 텔레그램 Chat ID | `https://api.telegram.org/bot<토큰>/getUpdates` | 받을 곳 |

> Chat ID: 봇에게 메시지를 하나 보낸 뒤 위 주소를 브라우저에서 열면
> `"chat":{"id": ...}` 숫자가 보입니다. (`<토큰>` 자리에 실제 토큰을 괄호 없이 붙여넣기)
>
> 구글 뉴스 RSS 를 쓰므로 **NewsAPI 키는 필요 없습니다.**

## 2. GitHub Secrets 등록

저장소 → **Settings → Secrets and variables → Actions → New repository secret**

| 이름 | 값 |
|------|-----|
| `ANTHROPIC_API_KEY` | Claude API 키 |
| `TELEGRAM_BOT_TOKEN` | 조선방산기계 봇 토큰 |
| `TELEGRAM_CHAT_ID` | Chat ID |

## 3. 동작 확인

1. 저장소 → **Actions** → **Chosun Defense Machinery Daily News**
2. **Run workflow** 로 즉시 실행 → 텔레그램 도착 확인
3. 이후 매일 07:00 KST 자동 실행 (cron `0 22 * * *` = UTC)

---

## 4. 로컬 테스트 (선택)

```bash
cd news_bot
pip install -r requirements.txt

export ANTHROPIC_API_KEY=...
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...

python chosun_news_bot.py
```

---

## 5. 커스터마이징 — `chosun_news_bot.py` 의 `CATEGORIES`

카테고리/검색어/기사 수를 직접 조절할 수 있습니다.

```python
CATEGORIES = [
    {
        "label": "🚢 조선",
        "gnews": [                      # 구글 뉴스 검색어 (OR 로 키워드 묶기)
            gnews("HD현대중공업 OR 한화오션 OR 삼성중공업 OR LNG선 OR FLNG"),
            gnews("site:tradewindsnews.com"),   # 특정 사이트만 검색
            gnews("site:upstreamonline.com"),
        ],
        "feeds": [                      # 직접 RSS 피드 URL (RSS.app 등)
            # "https://rss.app/feeds/xxxx.xml",
        ],
        "limit": 8,                     # 이 카테고리 최대 기사 수
    },
    # 🛡️ 방산 / ⚙️ 기계 ...
]
```

| 하고 싶은 것 | 방법 |
|--------------|------|
| 키워드 추가/변경 | 해당 카테고리 `gnews` 의 검색어 수정 |
| 특정 매체만 보기 | `gnews("site:도메인.com 키워드")` |
| TradeWinds/Upstream RSS 직접 연결 | 그 카테고리 `feeds` 에 피드 URL 추가 |
| 카테고리별 기사 수 | `limit` 값 변경 |
| 요약 줄 수/말투 | `summarize()` 의 프롬프트 수정 |
| 요약 모델 | `CLAUDE_MODEL` 환경변수 (기본 `claude-haiku-4-5-20251001`) |
| 발송 시각 | `.github/workflows/chosun-daily-news.yml` 의 `cron` (UTC) |

> **TradeWinds / Upstream**: 두 사이트는 공개 API/무료 RSS 가 없는 유료 전문지입니다.
> 본 봇은 구글 뉴스 RSS 의 `site:` 검색으로 공개 색인된 헤드라인을 가져옵니다.
> 유료 구독을 활용하려면 해당 매체의 **이메일 뉴스레터**를 받아 처리하는 방식이
> 약관상 안전합니다(별도 구현 필요).
