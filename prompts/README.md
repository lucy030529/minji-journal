# 이동헌 부장 스타일 실적 Q&A 생성기

기업 실적발표 스크립트를 넣으면 **신한투자증권 이동헌 부장님 어투**의 실적 리뷰
Q&A 레포트를 만들어주는 스크립트 모음입니다. (localhost:5000 사이트 연동용)

## 파일
- `leedonghun_style_prompt.md` — 핵심 딜리버러블. 이동헌 부장 프로파일 · 문체 규칙 ·
  Q&A 포맷 · few-shot 예시를 담은 **시스템 프롬프트**. 파일 하단 `` ```text `` 블록이
  실제 시스템 프롬프트 본문입니다. Claude Code / 클로드 대화창에 그대로 붙여넣어도 됩니다.
- `generate_qna.py` — 위 프롬프트를 불러와 Claude API로 레포트를 생성하는 파이썬 모듈.
  Flask 라우트 예시 포함(파일 하단 주석).

## 빠른 시작
```bash
pip install -r prompts/requirements.txt
export ANTHROPIC_API_KEY=...        # 또는: ant auth login
# 품질 우선이면 최신 Opus 계열로: export ANTHROPIC_MODEL=<opus 모델 id>

python prompts/generate_qna.py \
  --stock "한화오션" --code 042660 --quarter 4Q25 \
  --script-file transcript.txt
```

## 어투 학습 근거 (요약)
- 커버리지: 조선(한화오션·삼성중공업·HD현대중공업 등), 방산(KAI·한화에어로·현대로템·
  LIG넥스원·삼양컴텍), 기계/전력기기(LS일렉트릭·HD현대일렉트릭·효성중공업).
- 하우스뷰: '지정학발 슈퍼사이클' — LNG선 고선가, MASGA, K-방산 수출, 전력기기 공급자 우위.
- 문체: 문어체 단정형(~다체), 두괄식, 컨센 대비 상회/하회, 수주잔고·파이프라인 중시,
  2단 시그니처 제목("지정학이 쏘아 올린 슈퍼사이클 2막" 류).

자세한 규칙은 `leedonghun_style_prompt.md` 참고.
