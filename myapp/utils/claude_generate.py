"""Claude 로 덱 명세(JSON) 만들기.

사용자가 적은 주제·장 수·제목을 받아 renderer/build.js 가 읽는 명세(docs/SPEC.md)를 만든다.
모델은 .env 의 CLAUDE_MODEL, 기본 claude-opus-5-5.

흐름
- 12장 이하: 한 번에 전체 명세를 쓴다.
- 13장 이상(설명회처럼 100장 안팎): ① 개요(구역 → 장마다 유형·제목·핵심)를 먼저 짜고
  ② 개요를 10장씩 묶어 여러 묶음을 동시에 쓴 뒤 ③ 순서대로 이어 붙인다.
  한 번에 100장을 쓰게 하면 응답 길이 한도에 걸리고, 장끼리 내용이 겹치기 쉽다.

구조화 출력(output_config.format)은 쓰지 않는다. 장 유형 11종의 칸을 스키마로 적으면
API 한도에 걸린다(2026-11-17 실제 400 응답으로 확인): 선택 칸 24개 한도, 그리고
모든 칸 필수·유형별 anyOf 는 "compiled grammar is too large". 그래서 형식을 지시문에 적고,
받은 JSON 을 검사해 틀리면 문제 목록을 주고 한 번 다시 쓰게 한다.
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
MAX_SLIDES = 150
SINGLE_CALL_MAX = 12   # 이 장 수까지는 한 번에 쓴다
BATCH = 10             # 큰 덱을 몇 장씩 묶어 쓸지
WORKERS = 5            # 동시에 쓰는 묶음 수

# 장 유형 — build.js 의 R.* 와 1:1
SLIDE_TYPES = ["cover", "agenda", "section", "bullets", "cards", "stats", "table", "twoColumn", "compare", "steps", "closing"]

DENSITY = {
    "간결": "글은 짧게: 글머리표 3~4줄, 한 줄 30자 안팎. 카드 한 장에 2~3줄. 표는 5행 이내. 발표자 노트 두 문장 이내.",
    "보통": "글머리표 4~5줄, 한 줄 40자 안팎. 카드 한 장에 3줄. 표는 4~8행. 발표자 노트 두세 문장.",
    "자세히": ("설명회 자료처럼 화면만 읽어도 이해되게 쓴다: 글머리표 5~7줄, 한 줄 30~55자로 구체적으로. "
              "카드 한 장에 3~4줄. 표는 5~10행으로 항목을 빠짐없이. 비교는 기준을 분명히. "
              "발표자 노트는 화면에 다 못 쓴 설명과 예시를 3~5문장으로."),
}

FORMAT = """출력 형식 — JSON 객체 하나만 쓴다. 앞뒤에 설명이나 코드 울타리(```)를 붙이지 않는다.

모든 장에 공통: "type", "title", "section"(이 장이 속한 목차 항목 이름, cover 는 "표지"), "notes"(발표자 노트)
type 별로 더 쓰는 칸 (괄호 안은 생략 가능):
- cover: ("subtitle")
- agenda: "items": [{"num": "01", "title", "desc", "icon"}] 3~4개
- section: "num": "01", ("desc")
- bullets: "bullets": [문장], ("callout": {"title", "text", "icon"} — 옆에 둘 강조 카드, 이때 글머리표는 5줄 이내)
- cards: "cards": [{"tag", "title", "icon", "lines": [문장]}] 2~4장
- stats: "tiles": [{"label", "value", ("sub"), ("emphasis": true)}] 2~4개, ("chart": {"title", "series", "labels": [..], "values": [숫자..]}), ("bullets"), ("source")
- table: "columns": [머리 칸], "rows": [[칸, ..], ..], ("highlightRows": [0부터 센 행 번호]), ("note")
- twoColumn: "left": {"heading", "lines": [..]}, "right": {"heading", "lines": [..]}
- compare: "rows": [{"from", "to", "icon", "lines": [..]}] 최대 3줄(3줄이면 lines 는 2개 이내, 한 줄 35자 이내), ("fromLabel": "문제"), ("toLabel": "개선"), ("note")
- steps: "steps": [{"title", "desc"}] 3~5단계
- closing: "items": [{"title", "desc"}] 2~4개"""

PRINCIPLES = """원칙
- 장마다 메시지는 하나. 장 유형을 섞어 쓴다. 같은 유형을 세 장 넘게 연달아 두지 않는다.
- 첫 장은 cover, 둘째 장은 agenda(3~4항목), 큰 주제가 바뀔 때 section, 마지막 장은 closing.
- 숫자가 있으면 stats(타일 2~4개), 둘을 견주면 twoColumn 또는 compare, 절차는 steps(3~5단계), 여러 항목을 견주면 table.
- 아이콘은 react-icons Feather 이름(FiUsers, FiTool, FiCpu, FiAlertTriangle, FiFolder, FiBookOpen, FiCheckCircle, FiZap, FiClock, FiLayout, FiTrendingUp, FiTarget, FiStar, FiCalendar, FiAward, FiMap, FiCompass, FiBarChart2, FiList, FiSearch)만 쓴다.
- 사용자가 준 언어로 쓴다. 사실을 지어내지 않는다. 사용자가 준 내용에 없는 숫자·학교명·제도 이름은 만들지 않는다. 숫자가 필요한데 없으면 그 장 유형을 피한다.
- 사용자가 준 재료는 빠뜨리지 말고 쓴다. 재료가 장 수에 비해 적으면 같은 말을 되풀이하지 말고, 배경·이유·예시·준비 방법·자주 묻는 질문처럼 이해를 돕는 설명으로 넓힌다.
- 학교·과목·대학처럼 이름만 받은 항목은 재료에 그 항목의 구체 내용(개설 과목, 학기, 숫자 등)이 있을 때만 항목별로 장을 따로 만든다. 내용이 없으면 여러 항목을 한 장의 표나 카드로 묶고, 항목마다 같은 틀의 일반론 장을 늘어놓지 않는다."""


def system_prompt(density: str) -> str:
    return (f"당신은 발표 자료 기획자다. 사용자가 준 주제와 장 수로 PowerPoint 덱의 구조화 명세(JSON)를 만든다.\n\n"
            f"{PRINCIPLES}\n- 분량: {DENSITY.get(density, DENSITY['보통'])}\n\n{FORMAT}")


# type 별 반드시 있어야 하는 칸과 그 모양
REQUIRED = {
    "agenda": {"items": list}, "section": {"num": str}, "bullets": {"bullets": list},
    "cards": {"cards": list}, "stats": {"tiles": list}, "table": {"columns": list, "rows": list},
    "twoColumn": {"left": dict, "right": dict}, "compare": {"rows": list},
    "steps": {"steps": list}, "closing": {"items": list},
}

Progress = Optional[Callable[[str, int, int], None]]


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


def slide_problems(slides: list, offset: int = 0) -> list[str]:
    """장 목록을 렌더러가 읽을 수 있는지 검사한다. offset 은 덱 전체에서의 시작 번호(0부터)."""
    problems = []
    for k, sl in enumerate(slides, offset + 1):
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
    return problems


def validate_spec(spec: dict, n_slides: int) -> list[str]:
    slides = spec.get("slides")
    if not isinstance(slides, list) or not slides:
        return ["slides 배열이 없습니다"]
    problems = slide_problems(slides)
    if slides[0].get("type") != "cover":
        problems.append("첫 장은 cover 여야 합니다")
    if abs(len(slides) - n_slides) > 1:
        problems.append(f"장 수가 {len(slides)}장입니다. {n_slides}장으로 맞춰 주세요")
    return problems


def _ask(client: anthropic.Anthropic, system: str, messages: list, max_tokens: int = 16000) -> str:
    # 긴 응답은 스트리밍으로 받는다(요청 시간 초과 방지). 최종 메시지만 쓴다.
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=system,
        messages=messages,
    ) as stream:
        response = stream.get_final_message()
    if response.stop_reason == "refusal":
        detail = getattr(response, "stop_details", None)
        raise RuntimeError(f"요청이 거절되었습니다: {getattr(detail, 'explanation', '') or getattr(detail, 'category', '')}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("응답이 잘렸습니다. 내용을 줄이거나 분량을 '보통'으로 해 보세요.")
    return "".join(b.text for b in response.content if b.type == "text")


def _ask_json(client, system: str, first_message: str, check: Callable[[dict], list[str]], what: str,
              max_tokens: int = 16000) -> dict:
    """JSON 을 받아 check() 로 검사하고, 틀리면 문제 목록을 주고 한 번 다시 받는다."""
    messages = [{"role": "user", "content": first_message}]
    problems: list[str] = []
    for _ in range(2):
        text = _ask(client, system, messages, max_tokens)
        try:
            data = parse_json(text)
            problems = check(data)
        except (ValueError, json.JSONDecodeError) as e:
            data, problems = None, [f"JSON 으로 읽을 수 없습니다: {e}"]
        if not problems:
            return data
        messages += [
            {"role": "assistant", "content": text},
            {"role": "user", "content": "다음 문제가 있다. 고친 결과 전체를 JSON 객체 하나로 다시 써라.\n- " + "\n- ".join(problems[:20])},
        ]
    raise RuntimeError(f"{what} 형식이 맞지 않습니다: " + "; ".join(problems[:5]))


# ---------------- 큰 덱: 개요 → 묶음 ----------------

OUTLINE_FORMAT = """출력 형식 — JSON 객체 하나만 쓴다. 앞뒤 설명·코드 울타리 없이.
{"title": "덱 제목", "subtitle": "부제",
 "sections": [{"name": "구역 이름(목차 항목)", "slides": [{"type": "장 유형", "title": "장 제목", "point": "이 장에서 보여 줄 핵심, 한 문장 40자 이내"}]}]}
- 첫 구역은 이름 "표지"로 cover 한 장과 agenda 한 장을 담는다. 마지막 구역의 마지막 장은 closing.
- 큰 구역은 section 장으로 시작한다.
- 장 유형은 cover, agenda, section, bullets, cards, stats, table, twoColumn, compare, steps, closing 중에서 고른다."""


def _count(outline: dict) -> int:
    return sum(len(s.get("slides") or []) for s in outline.get("sections") or [])


def _flatten(outline: dict) -> list[dict]:
    out = []
    for sec in outline.get("sections") or []:
        for sl in sec.get("slides") or []:
            out.append({**sl, "section": sec.get("name", "")})
    return out


def plan_outline(client, topic, n, title, presenter, language, density) -> dict:
    system = (f"당신은 설명회·발표 자료 기획자다. 사용자가 준 재료로 {n}장짜리 PowerPoint 덱의 개요를 짠다.\n\n"
              f"{PRINCIPLES}\n- 분량: {DENSITY.get(density, DENSITY['보통'])}\n"
              f"- 장 수는 cover 와 closing 을 포함해 정확히 {n}장이다.\n"
              "- 구역은 재료의 흐름을 따라 4~10개로 나눈다. 장마다 다른 내용을 맡겨 겹치지 않게 한다.\n\n" + OUTLINE_FORMAT)

    def check(o):
        p = []
        if not isinstance(o.get("sections"), list) or not o["sections"]:
            return ["sections 배열이 없습니다"]
        flat = _flatten(o)
        if abs(len(flat) - n) > max(1, n // 50):
            p.append(f"장 수가 {len(flat)}장입니다. 정확히 {n}장으로 맞춰라")
        for k, sl in enumerate(flat, 1):
            if sl.get("type") not in SLIDE_TYPES:
                p.append(f"{k}번째 장 type '{sl.get('type')}' 은 없는 유형입니다")
        if flat and flat[0].get("type") != "cover":
            p.append("첫 장은 cover 여야 합니다")
        if flat and flat[-1].get("type") != "closing":
            p.append("마지막 장은 closing 이어야 합니다")
        return p

    # 100장 개요는 16k 토큰을 넘는다(2026-11-17 실제로 잘림) — 한도를 넉넉히 준다
    return _ask_json(client, system, build_user_message(topic, n, title, presenter, language), check, "개요",
                     max_tokens=32000)


def outline_text(flat: list[dict]) -> str:
    return "\n".join(f"{i}. [{sl.get('section', '')}] {sl.get('type')} — {sl.get('title')}: {sl.get('point', '')}"
                     for i, sl in enumerate(flat, 1))


def write_batch(client, topic, flat, start, end, density, language) -> list[dict]:
    """개요의 start~end-1 번째 장(0부터)을 명세로 쓴다."""
    want = flat[start:end]
    system = system_prompt(density)
    msg = (f"언어: {language}\n\n재료:\n{topic}\n\n"
           f"덱 전체 개요 ({len(flat)}장):\n{outline_text(flat)}\n\n"
           f"이번에 쓸 장은 {start + 1}~{end}번, {len(want)}장이다. 개요의 type·section 을 그대로 지키고 "
           "제목은 다듬어도 된다. 다른 번호의 장과 내용이 겹치지 않게 그 장의 핵심만 깊게 쓴다.\n"
           '출력: {"slides": [장, ...]} — 정확히 ' + f"{len(want)}장.")

    def check(d):
        sl = d.get("slides")
        if not isinstance(sl, list):
            return ["slides 배열이 없습니다"]
        p = slide_problems(sl, start)
        if len(sl) != len(want):
            p.append(f"{len(sl)}장을 썼다. 정확히 {len(want)}장({start + 1}~{end}번)을 써라")
        for k, (got, plan) in enumerate(zip(sl, want), start + 1):
            if isinstance(got, dict) and got.get("type") != plan.get("type"):
                p.append(f"{k}번째 장 type 은 개요대로 '{plan.get('type')}' 여야 한다")
        return p

    slides = _ask_json(client, system, msg, check, f"{start + 1}~{end}번 장", max_tokens=24000)["slides"]
    for got, plan in zip(slides, want):
        got["section"] = plan.get("section") or got.get("section", "")
    return slides


def generate_spec(topic: str, n_slides: int, title: str, presenter: str, language: str = "한국어",
                  density: str = "보통", progress: Progress = None) -> dict:
    """Claude 를 불러 명세 dict 를 돌려준다. progress(단계, 끝난 장 수, 전체 장 수) 로 진행을 알린다."""
    client = anthropic.Anthropic()
    tell = progress or (lambda *a: None)

    if n_slides <= SINGLE_CALL_MAX:
        tell("명세 쓰는 중", 0, n_slides)
        spec = _ask_json(client, system_prompt(density), build_user_message(topic, n_slides, title, presenter, language),
                         lambda s: validate_spec(s, n_slides), "명세")
    else:
        tell("개요 짜는 중", 0, n_slides)
        outline = plan_outline(client, topic, n_slides, title, presenter, language, density)
        flat = _flatten(outline)
        ranges = [(i, min(i + BATCH, len(flat))) for i in range(0, len(flat), BATCH)]
        done = 0
        tell("장 쓰는 중", 0, len(flat))
        parts: dict[int, list] = {}
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(write_batch, client, topic, flat, a, b, density, language): a for a, b in ranges}
            for fut in as_completed(futures):
                a = futures[fut]
                parts[a] = fut.result()          # 묶음 하나라도 실패하면 오류를 그대로 올린다
                done += len(parts[a])
                tell("장 쓰는 중", done, len(flat))
        slides = [sl for a, _ in ranges for sl in parts[a]]
        spec = {"title": outline.get("title") or title, "subtitle": outline.get("subtitle", ""), "slides": slides}

    spec.setdefault("title", title)
    spec["presenter"] = presenter
    tell("파일 만드는 중", n_slides, n_slides)
    return spec
