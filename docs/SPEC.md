# 덱 명세(JSON) 형식

`renderer/build.js` 가 읽는 입력이다. Claude 가 이 형식으로 써 주고(`myapp/utils/claude_generate.py` 의 `SCHEMA`), 사람이 직접 써서 `/render` 로 보내도 된다. 견본: `renderer/examples/sample-ko.json`.

```json
{
  "title": "덱 제목", "subtitle": "부제", "presenter": "발표자", "date": "2026. 11. 13",
  "theme": "climath",            // renderer/themes/*.json 의 id. --theme 로 덮어쓸 수 있음
  "footer": "꼬리말 (없으면 제목 · 날짜)",
  "slides": [ { "type": "...", "title": "...", "section": "목차 항목", "notes": "발표자 노트", ... } ]
}
```

모든 장에 공통: `type`, `title`, `section`(같은 이름이 이어지면 PowerPoint 구역 하나로 묶임), `notes`(발표자 노트).

| type | 쓰임 | 고유 필드 |
| --- | --- | --- |
| `cover` | 표지 (어두운 배경) | `subtitle`, `meta`(없으면 date · presenter) |
| `agenda` | 목차 카드 2~4개 | `items[{num, title, desc, icon}]` |
| `section` | 구역 나눔 (어두운 배경) | `num`, `desc` |
| `bullets` | 글머리표 + 선택 강조 카드 | `bullets[]`, `callout{title, text, icon}` |
| `cards` | 카드 2~4개 (문제·사례·항목) | `cards[{tag, title, icon, lines[]}]` |
| `stats` | 숫자 타일 2~4개 + 선택 막대 차트/설명 | `tiles[{label, value, sub, emphasis}]`, `chart{title, series, labels[], values[]}`, `bullets[]`, `source` |
| `table` | 표 | `columns[]`, `rows[[]]`, `highlightRows[]`, `note` |
| `twoColumn` | 두 열 비교 | `left{heading, lines[]}`, `right{heading, lines[]}` |
| `compare` | 문제 → 개선 1:1 대응 (최대 3줄) | `rows[{from, to, icon, lines[]}]`, `fromLabel`, `toLabel`, `note` |
| `steps` | 단계 3~5개 | `steps[{title, desc}]` |
| `closing` | 마무리 (어두운 배경, 번호 목록) | `items[{title, desc}]` |

`icon` 은 [react-icons Feather](https://react-icons.github.io/react-icons/icons/fi/) 이름(`FiUsers`, `FiTool`, …). 모르는 이름이면 `FiCircle`.

## 테마

`renderer/themes/<id>.json`:

```json
{ "id": "climath", "label": "화면에 보일 이름", "name": "PowerPoint 테마 이름",
  "headFontFace": "NanumBarunGothic", "bodyFontFace": "NanumBarunGothic",
  "colors": { "dk1","lt1","dk2","lt2","accent1"…"accent6","hlink","folHlink" },   // 6자리 hex, # 없이
  "logo": { "dark": "assets/logo_dark.png", "white": "assets/logo_white.png", "w": 1.35, "h": 0.37 },  // 선택
  "darkContent": false }        // true 면 본문 장도 어두운 바탕
```

색은 PowerPoint 테마 색(스킴)으로 들어가므로, 만든 뒤에도 **디자인 > 색 변형**으로 한 번에 바꿀 수 있다. 로고 파일은 `renderer/assets/`(git 제외)에 두고 없으면 건너뛴다.

## 렌더 · 검사

```bash
cd renderer && npm install
node build.js examples/sample-ko.json out/sample-ko.pptx --theme climath
powershell -ExecutionPolicy Bypass -File preview.ps1 -Pptx out/sample-ko.pptx -OutDir out/png   # Windows + PowerPoint
```

`preview.ps1` 은 PowerPoint 로 열어 장마다 PNG 를 뽑는다. 열리면 파일이 온전한 것이고, 글이 넘치거나 겹치는지는 PNG 로 본다.
