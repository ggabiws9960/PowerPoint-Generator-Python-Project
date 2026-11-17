"""Claude 로 덱 명세(JSON) 만들기.

사용자가 적은 주제·장 수·제목을 받아 renderer/build.js 가 읽는 명세(docs/SPEC.md)를 만든다.
모델은 .env 의 CLAUDE_MODEL, 기본 claude-opus-5-5.

구조화 출력(output_config.format)은 쓰지 않는다. 장 유형 11종의 칸을 스키마로 적으면
API 한도에 걸린다(2026-11-17 실제 400 응답으로 확인):
  - "없어도 되는 칸"이 24개를 넘으면 거절 (처음 스키마는 30개)
  - 모든 칸을 필수로 바꾸거나 장 유형별 anyOf 로 나누면 "compiled grammar is too large"
그래서 형식을 지시문에 적고, 받은 JSON 을 validate_spec() 으로 검사해
틀리면 오류를 알려 주고 한 번 다시 쓰게 한다.
"""
import json
import os
import re

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")

# 장 유형 — build.js 의 R.* 와 1:1
SLIDE_TYPES = ["cover", "agenda", "section", "bullets", "cards", "stats", "table", "twoColumn", "compare", "steps", "closing"]

FORMAT = """출력 형식 — JSON 객체 하나만 쓴다. 앞뒤에 설명이나 코드 울타리(```)를 붙이지 않는다.
{"title": "덱 제목", "subtitle": "부제", "slides": [장, 장, ...]}

모든 장에 공통: "type", "title", "section"(이 장이 속한 목차 항목 이름, cover 는 "표지"), "notes"(발표자가 말로 할 내용, 두 문장 이내)
type 별로 더 쓰는 칸 (괄호 안은 생략 가능):
- cover: ("subtitle")
- agenda: "items": [{"num": "01", "title", "desc", "icon"}] 3~4개
- section: "num": "01", ("desc")
- bullets: "bullets": [문장], ("callout": {"title", "text", "icon"} — 옆에 둘 강조 카드)
- cards: "cards": [{"tag", "title", "icon", "lines": [문장]}] 2~4장
- stats: "tiles": [{"label", "value", ("sub"), ("emphasis": true)}] 2~4개, ("chart": {"title", "series", "labels": [..], "values": [숫자..]}), ("bullets"), ("source")
- table: "columns": [머리 칸], "rows": [[칸, ..], ..], ("highlightRows": [0부터 센 행 번호]), ("note")
- twoColumn: "left": {"heading", "lines": [..]}, "right": {"heading", "lines": [..]}
- compare: "rows": [{"from", "to", "icon", "lines": [..]}] 최대 3줄, ("fromLabel": "문제"), ("toLabel": "개선"), ("note")
- steps: "steps": [{"title", "desc"}] 3~5단계
- closing: "items": [{"title", "desc"}] 2~4개"""

SYSTEM = f"""당신은 발표 자료 기획자다. 사용자가 준 주제와 장 수로 PowerPoint 덱의 구조화 명세(JSON)를 만든다.

원칙
- 장마다 메시지는 하나. 장 유형을 섞어 쓴다. 글머리표만 늘어놓은 장을 연달아 두지 않는다.
- 첫 장은 cover, 둘째 장은 agenda(3~4항목), 큰 주제가 바뀔 때 section, 마지막 장은 closing.
- 숫자가 있으면 stats(타일 2~4개), 둘을 견주면 twoColumn 또는 compare, 절차는 steps(3~5단계), 항목 비교는 table.
- 글은 짧게: 글머리표 한 줄 40자 안팎, 카드 한 장에 3줄 이내.
- 아이콘은 react-icons Feather 이름(FiUsers, FiTool, FiCpu, FiAlertTriangle, FiFolder, FiBookOpen, FiCheckCircle, FiZap, FiClock, FiLayout, FiTrendingUp, FiTarget, FiStar)만 쓴다.
- 사용자가 준 언어로 쓴다. 사실을 지어내지 말고, 사용자가 준 내용에 없는 숫자는 만들지 않는다. 숫자가 필요한데 없으면 그 장 유형을 피한다.
- 장 수는 cover 와 closing 을 포함해 요청한 수와 같게 맞춘다.

{FORMAT}"""

# type 별 반드시 있어야 하는 칸과 그 모양(list/dict)
REQUIRED = {
    "agenda": {"items": list}, "section": {"num": str}, "bullets": {"bullets": list},
    "cards": {"cards": list}, "stats": {"tiles": list}, "table": {"columns": list, "rows": list},
    "twoColumn": {"left": dict, "right": dict}, "compare": {"rows": list},
    "steps": {"steps": list}, "closing": {"items": list},
}


def build_user_message(topic: str, n_slides: int, title: str, presenter: str, language: str) -> str:
    return (
        f"덱 제목: {title}\n발표자: {presenter}\n장 수: {n_slides}\n언어: {language}\n\n"
        f"내용:\n{topic}\n\n"
        "위 내용으로 명세를 만들어라. 각 장의 section 은 목차 항목 이름과 같게 적어라."
    )


def parse_json(text: str) -> dict:
    """모델 답에서 JSON 객체를 꺼낸다. 코드 울타리나 앞뒤 말이 붙어도 첫 { 부터 마지막 } 까지 읽는다."""
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j < i:
        raise ValueError("JSON 객체를 찾지 못했습니다")
    return json.loads(text[i:j + 1])


def validate_spec(spec: dict, n_slides: int) -> list[str]:
    """렌더러가 읽을 수 있는지 검사해 문제 목록을 돌려준다. 빈 목록이면 통과."""
    problems = []
    slides = spec.get("slides")
    if not isinstance(slides, list) or not slides:
        return ["slides 배열이 없습니다"]
    for k, sl in enumerate(slides, 1):
        if not isinstance(sl, dict):
            problems.append(f"{k}번째 장이 객체가 아닙니다")
            continue
        t = sl.get("type")
        if t not in SLIDE_TYPES:
            problems.append(f"{k}번째 장 type '{t}' 은 없는 유형입니다 ({', '.join(SLIDE_TYPES)} 중 하나)")
            continue
        if not isinstance(sl.get("title"), str):
            problems.append(f"{k}번째 장({t})에 title 이 없습니다")
        for field, shape in REQUIRED.get(t, {}).items():
            if not isinstance(sl.get(field), shape) or not sl.get(field):
                problems.append(f"{k}번째 장({t})에 {field} 가 없거나 비었습니다")
        if t == "stats" and isinstance(sl.get("chart"), dict):
            ch = sl["chart"]
            vals = ch.get("values") or []
            if not all(isinstance(v, (int, float)) for v in vals) or len(vals) != len(ch.get("labels") or []):
                problems.append(f"{k}번째 장(stats) chart 의 labels 와 values(숫자) 개수가 맞지 않습니다")
    if slides and slides[0].get("type") != "cover":
        problems.append("첫 장은 cover 여야 합니다")
    if abs(len(slides) - n_slides) > 1:
        problems.append(f"장 수가 {len(slides)}장입니다. {n_slides}장으로 맞춰 주세요")
    return problems


def _ask(client: anthropic.Anthropic, messages: list) -> str:
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        messages=messages,
    )
    if response.stop_reason == "refusal":
        detail = getattr(response, "stop_details", None)
        raise RuntimeError(f"요청이 거절되었습니다: {getattr(detail, 'explanation', '') or getattr(detail, 'category', '')}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("응답이 잘렸습니다. 장 수를 줄이거나 내용을 짧게 해 보세요.")
    return "".join(b.text for b in response.content if b.type == "text")


def generate_spec(topic: str, n_slides: int, title: str, presenter: str, language: str = "한국어") -> dict:
    """Claude 를 불러 명세 dict 를 돌려준다. 형식이 틀리면 한 번 고쳐 쓰게 하고, 그래도 틀리면 RuntimeError."""
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": build_user_message(topic, n_slides, title, presenter, language)}]
    problems: list[str] = []
    for attempt in range(2):
        text = _ask(client, messages)
        try:
            spec = parse_json(text)
            problems = validate_spec(spec, n_slides)
        except (ValueError, json.JSONDecodeError) as e:
            spec, problems = None, [f"JSON 으로 읽을 수 없습니다: {e}"]
        if not problems:
            spec.setdefault("title", title)
            spec["presenter"] = presenter
            return spec
        messages += [
            {"role": "assistant", "content": text},
            {"role": "user", "content": "명세에 다음 문제가 있다. 고친 명세 전체를 JSON 객체 하나로 다시 써라.\n- " + "\n- ".join(problems)},
        ]
    raise RuntimeError("명세 형식이 맞지 않습니다: " + "; ".join(problems[:5]))
