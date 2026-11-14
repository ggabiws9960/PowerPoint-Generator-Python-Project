"""Claude 로 덱 명세(JSON) 만들기.

사용자가 적은 주제·장 수·제목을 받아 renderer/build.js 가 읽는 명세(docs/SPEC.md)를
구조화 출력(output_config.format)으로 받는다. 모델은 .env 의 CLAUDE_MODEL, 기본 claude-opus-5-5.
"""
import json
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")

# 장 유형과 각 유형이 받는 필드 — build.js 의 R.* 와 1:1
SLIDE_TYPES = ["cover", "agenda", "section", "bullets", "cards", "stats", "table", "twoColumn", "compare", "steps", "closing"]

SYSTEM = """당신은 발표 자료 기획자다. 사용자가 준 주제와 장 수로 PowerPoint 덱의 구조화 명세(JSON)를 만든다.

원칙
- 장마다 메시지는 하나. 장 유형을 섞어 쓴다. 글머리표만 늘어놓은 장을 연달아 두지 않는다.
- 첫 장은 cover, 둘째 장은 agenda(3~4항목), 큰 주제가 바뀔 때 section, 마지막 장은 closing.
- 숫자가 있으면 stats(타일 2~4개), 둘을 견주면 twoColumn 또는 compare, 절차는 steps(3~5단계), 항목 비교는 table.
- 글은 짧게: 글머리표 한 줄 40자 안팎, 카드 한 장에 3줄 이내. 발표자 노트(notes)에 말로 할 내용을 두 문장 이내로.
- 아이콘은 react-icons Feather 이름(FiUsers, FiTool, FiCpu, FiAlertTriangle, FiFolder, FiBookOpen, FiCheckCircle, FiZap, FiClock, FiLayout, FiTrendingUp, FiTarget, FiStar)만 쓴다.
- 사용자가 준 언어로 쓴다. 사실을 지어내지 말고, 사용자가 준 내용에 없는 숫자는 만들지 않는다. 숫자가 필요한데 없으면 자리 표시 없이 그 장 유형을 피한다.
- 장 수는 cover 와 closing 을 포함해 요청한 수와 같게 맞춘다."""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "subtitle", "slides"],
    "properties": {
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "slides": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["type", "title", "section", "notes"],
                "properties": {
                    "type": {"type": "string", "enum": SLIDE_TYPES},
                    "title": {"type": "string"},
                    "section": {"type": "string", "description": "이 장이 속한 큰 주제 이름(목차 항목). cover 는 '표지'."},
                    "notes": {"type": "string"},
                    "subtitle": {"type": "string"},
                    "num": {"type": "string"},
                    "desc": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                    "callout": {"type": "object", "additionalProperties": False, "required": ["title", "text"], "properties": {"title": {"type": "string"}, "text": {"type": "string"}, "icon": {"type": "string"}}},
                    "items": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["title"], "properties": {"num": {"type": "string"}, "title": {"type": "string"}, "desc": {"type": "string"}, "icon": {"type": "string"}}}},
                    "cards": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["title", "lines"], "properties": {"tag": {"type": "string"}, "title": {"type": "string"}, "icon": {"type": "string"}, "lines": {"type": "array", "items": {"type": "string"}}}}},
                    "tiles": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["label", "value"], "properties": {"label": {"type": "string"}, "value": {"type": "string"}, "sub": {"type": "string"}, "emphasis": {"type": "boolean"}}}},
                    "chart": {"type": "object", "additionalProperties": False, "required": ["labels", "values"], "properties": {"title": {"type": "string"}, "series": {"type": "string"}, "labels": {"type": "array", "items": {"type": "string"}}, "values": {"type": "array", "items": {"type": "number"}}}},
                    "source": {"type": "string"},
                    "columns": {"type": "array", "items": {"type": "string"}},
                    "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                    "highlightRows": {"type": "array", "items": {"type": "integer"}},
                    "note": {"type": "string"},
                    "left": {"type": "object", "additionalProperties": False, "required": ["heading", "lines"], "properties": {"heading": {"type": "string"}, "lines": {"type": "array", "items": {"type": "string"}}}},
                    "right": {"type": "object", "additionalProperties": False, "required": ["heading", "lines"], "properties": {"heading": {"type": "string"}, "lines": {"type": "array", "items": {"type": "string"}}}},
                    "fromLabel": {"type": "string"},
                    "toLabel": {"type": "string"},
                    "steps": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["title"], "properties": {"title": {"type": "string"}, "desc": {"type": "string"}}}},
                },
            },
        },
    },
}


def build_user_message(topic: str, n_slides: int, title: str, presenter: str, language: str) -> str:
    return (
        f"덱 제목: {title}\n발표자: {presenter}\n장 수: {n_slides}\n언어: {language}\n\n"
        f"내용:\n{topic}\n\n"
        "위 내용으로 명세를 만들어라. 각 장의 section 은 목차 항목 이름과 같게 적어라."
    )


def generate_spec(topic: str, n_slides: int, title: str, presenter: str, language: str = "한국어") -> dict:
    """Claude 를 불러 명세 dict 를 돌려준다. 거절·오류는 RuntimeError."""
    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        messages=[{"role": "user", "content": build_user_message(topic, n_slides, title, presenter, language)}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )
    if response.stop_reason == "refusal":
        detail = getattr(response, "stop_details", None)
        raise RuntimeError(f"요청이 거절되었습니다: {getattr(detail, 'explanation', '') or getattr(detail, 'category', '')}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("응답이 잘렸습니다. 장 수를 줄이거나 내용을 짧게 해 보세요.")
    text = next(b.text for b in response.content if b.type == "text")
    spec = json.loads(text)
    spec.setdefault("title", title)
    spec["presenter"] = presenter
    return spec
