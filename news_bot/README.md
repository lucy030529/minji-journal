# 📰 일일 뉴스 텔레그램 봇

매일 아침 **07:00 (KST)** 에 전일 국내외 주요 뉴스를 수집·요약해서
텔레그램으로 보내주는 봇입니다.

- **수집**: [NewsAPI](https://newsapi.org) top-headlines (국내 `kr` + 해외 `us`)
- **요약**: Claude API (한국어 2~3문장)
- **전송**: 텔레그램 봇 — `[제목 / 요약 / 원문링크]`
- **스케줄**: GitHub Actions cron (서버 불필요, 무료)

---

## 1. 준비물 — API 키 4개 발급

### ① NewsAPI 키
1. https://newsapi.org 가입 → API Key 복사
   > 무료(Developer) 플랜은 기사 노출이 24시간 지연되지만, **'전일 뉴스'** 용도라 문제 없습니다.

### ② Anthropic (Claude) API 키
1. https://console.anthropic.com → **API Keys** 에서 키 발급
2. 결제 수단 등록 (요약 비용은 하루 몇 원 수준)

### ③ 텔레그램 봇 토큰
1. 텔레그램에서 **@BotFather** 검색 → `/newbot`
2. 봇 이름/아이디 입력 → 받은 **토큰** 복사 (예: `123456:ABC-...`)

### ④ 텔레그램 Chat ID (메시지 받을 곳)
1. 방금 만든 봇과 대화를 시작하고 아무 메시지(`/start`)나 전송
2. 브라우저에서 아래 주소 열기 (토큰 교체):
   `https://api.telegram.org/bot<봇토큰>/getUpdates`
3. 응답 JSON 의 `"chat":{"id": ...}` 숫자가 **Chat ID** 입니다.
   > 단체방으로 받으려면 봇을 그룹에 초대 후 같은 방법으로 확인하세요(보통 음수 ID).

---

## 2. GitHub Secrets 등록

저장소 → **Settings → Secrets and variables → Actions → New repository secret**
에서 아래 4개를 등록합니다.

| 이름 | 값 |
|------|-----|
| `NEWSAPI_KEY` | NewsAPI 키 |
| `ANTHROPIC_API_KEY` | Claude API 키 |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | Chat ID |

---

## 3. 동작 확인

1. 저장소 → **Actions** 탭 → **Daily News Telegram Bot** 워크플로 선택
2. **Run workflow** 버튼으로 즉시 수동 실행 → 텔레그램 메시지 도착 확인
3. 이후 매일 07:00 KST 자동 실행됩니다.

> GitHub Actions cron 은 UTC 기준이라 `0 22 * * *` (= 한국시간 07:00) 으로 설정돼 있습니다.
> 트래픽이 몰리면 수 분~수십 분 늦게 실행될 수 있습니다(정상).

---

## 4. 로컬에서 테스트하기 (선택)

```bash
cd news_bot
pip install -r requirements.txt

export NEWSAPI_KEY=...
export ANTHROPIC_API_KEY=...
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...

python news_bot.py
```

---

## 5. 커스터마이징

| 항목 | 방법 |
|------|------|
| 카테고리별 기사 수 | `ARTICLES_PER_CATEGORY` 환경변수 (기본 5) |
| 요약 모델 변경 | `CLAUDE_MODEL` 환경변수 (기본 `claude-haiku-4-5-20251001`) |
| 수집 국가/카테고리 | `news_bot.py` 의 `CATEGORIES` 리스트 수정 |
| 발송 시각 변경 | `.github/workflows/daily-news.yml` 의 `cron` 값 수정 (UTC 기준) |

특정 주제만 받고 싶으면 `CATEGORIES` 에 `{"country": "kr", "category": "business"}`
처럼 `category`(business/technology/sports 등)를 추가하면 됩니다.
