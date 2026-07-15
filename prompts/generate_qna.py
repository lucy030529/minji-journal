"""
이동헌 부장 스타일 실적발표 Q&A 레포트 생성 모듈.

기업 실적발표 스크립트(컨퍼런스콜 속기본 / IR 자료 / 실적 보도자료)를 입력하면
신한투자증권 이동헌 부장의 어투·포맷으로 실적 리뷰 Q&A 레포트를 생성한다.

사용 예 (단독 실행):
    export ANTHROPIC_API_KEY=...            # 또는 `ant auth login` 프로파일
    python generate_qna.py --stock "한화오션" --code 042660 --quarter 4Q25 \
        --script-file transcript.txt

Flask(localhost:5000) 연동은 파일 하단의 예시 참고.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import anthropic

# 시스템 프롬프트는 같은 폴더의 마크다운에서 <<SYSTEM_PROMPT>> 코드블록을 읽어온다.
PROMPT_FILE = Path(__file__).with_name("leedonghun_style_prompt.md")

# 품질을 최우선으로 하려면 환경변수 ANTHROPIC_MODEL 로 최신 Opus 계열 모델을 지정하세요.
# 기본값은 비용/속도 균형이 좋은 Sonnet 계열입니다.
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")


def load_system_prompt() -> str:
    """마크다운 파일에서 마지막 ```text ... ``` 블록(시스템 프롬프트 본문)을 추출한다."""
    text = PROMPT_FILE.read_text(encoding="utf-8")
    marker = "```text"
    start = text.rfind(marker)
    if start == -1:
        # 코드블록을 못 찾으면 파일 전체를 지시문으로 사용 (안전 폴백)
        return text
    start += len(marker)
    end = text.find("```", start)
    return text[start:end].strip() if end != -1 else text[start:].strip()


def build_user_message(stock: str, code: str, quarter: str, script: str) -> str:
    """실적 스크립트를 유저 메시지로 구성한다."""
    return (
        f"종목명: {stock}\n"
        f"종목코드: {code}\n"
        f"분기: {quarter}\n\n"
        f"[실적발표 스크립트 원문]\n{script.strip()}\n\n"
        "위 원문을 근거로, 이동헌 부장 스타일의 실적 리뷰 Q&A 레포트를 작성하라."
    )


def generate_report(
    stock: str,
    code: str,
    quarter: str,
    script: str,
    *,
    model: str = MODEL,
    max_tokens: int = 8000,
) -> str:
    """실적 스크립트 -> 이동헌 스타일 Q&A 레포트(마크다운 문자열)."""
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 또는 ant 프로파일에서 인증

    system_prompt = load_system_prompt()
    user_message = build_user_message(stock, code, quarter, script)

    # 큰 스크립트 입력에도 타임아웃 없이 안전하도록 스트리밍으로 받는다.
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                # 같은 시스템 프롬프트를 반복 호출하므로 프롬프트 캐싱으로 비용 절감
                "cache_control": {"type": "ephemeral"},
            }
        ],
        thinking={"type": "adaptive"},  # 실적 해석에 적당한 추론 사용
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        message = stream.get_final_message()

    return "".join(block.text for block in message.content if block.type == "text")


def _cli() -> None:
    parser = argparse.ArgumentParser(description="이동헌 스타일 실적 Q&A 레포트 생성")
    parser.add_argument("--stock", required=True, help="종목명 (예: 한화오션)")
    parser.add_argument("--code", default="", help="종목코드 (예: 042660)")
    parser.add_argument("--quarter", default="", help="분기 (예: 4Q25)")
    parser.add_argument("--script-file", help="실적 스크립트 텍스트 파일 경로")
    parser.add_argument("--script", help="실적 스크립트 원문(직접 입력)")
    args = parser.parse_args()

    if args.script_file:
        script = Path(args.script_file).read_text(encoding="utf-8")
    elif args.script:
        script = args.script
    else:  # stdin 파이프 입력 허용
        import sys

        script = sys.stdin.read()

    report = generate_report(args.stock, args.code, args.quarter, script)
    print(report)


if __name__ == "__main__":
    _cli()


# ---------------------------------------------------------------------------
# Flask(localhost:5000) 연동 예시 — app.py 등에 아래 라우트를 추가하세요.
#
#   from flask import Flask, request, jsonify
#   from generate_qna import generate_report
#
#   app = Flask(__name__)
#
#   @app.route("/api/report", methods=["POST"])
#   def report():
#       data = request.get_json(force=True)
#       md = generate_report(
#           stock=data.get("stock", ""),
#           code=data.get("code", ""),
#           quarter=data.get("quarter", ""),
#           script=data["script"],
#       )
#       return jsonify({"markdown": md})
#
#   if __name__ == "__main__":
#       app.run(host="0.0.0.0", port=5000)
# ---------------------------------------------------------------------------
