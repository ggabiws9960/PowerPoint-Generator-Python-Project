// 구조화 덱 렌더러 — JSON 명세(spec) → 테마가 적용된 PPTX
//
//   node build.js <spec.json> <out.pptx> [--theme climath|bright|dark]
//   node build.js --list-themes
//
// 명세 형식은 ../docs/SPEC.md. 테마는 themes/*.json (12색 스킴 + 글꼴 + 로고).
// 만드는 방식: 테마(스킴 색) → 레이아웃(defineSlideMaster: 로고·제목 자리·쪽 번호)
// → 장 유형별 구성(카드·숫자 타일·표·비교·마무리) → writeFile → applyTheme 로 테마 색 기록.
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const Fi = require("react-icons/fi");
const { applyTheme } = require("./apply_theme.js");

const HERE = __dirname;
const W = 13.333, HGT = 7.5;
const MARGIN = 0.7;

function loadThemes() {
  const dir = path.join(HERE, "themes");
  return fs.readdirSync(dir).filter((f) => f.endsWith(".json")).map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")));
}

async function iconData(name, hex, px = 256) {
  const Comp = Fi[name] || Fi.FiCircle;
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + hex, size: px, strokeWidth: 2 }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

async function build(spec, theme, outFile) {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.theme = { headFontFace: theme.headFontFace, bodyFontFace: theme.bodyFontFace };
  pres.author = spec.author || spec.presenter || "deck-renderer";
  pres.title = spec.title || "Presentation";
  const C = pres.SchemeColor;
  const H = theme.colors;
  const dark = !!theme.darkContent; // 본문 장도 어두운 테마인가
  const logoD = theme.logo && fs.existsSync(path.join(HERE, theme.logo.dark)) ? path.join(HERE, theme.logo.dark) : null;
  const logoW = theme.logo && fs.existsSync(path.join(HERE, theme.logo.white)) ? path.join(HERE, theme.logo.white) : null;
  const lw = theme.logo ? theme.logo.w : 1.35, lh = theme.logo ? theme.logo.h : 0.37;
  const footer = spec.footer || [spec.title, spec.date].filter(Boolean).join(" · ");

  // 본문 장의 색 역할: 밝은 테마 = 흰 바탕/검정 글, 어두운 테마 = 진한 바탕/흰 글
  const BG = dark ? H.dk1 : H.lt1;          // 본문 배경
  const CARD = dark ? H.dk2 : H.lt2;        // 카드 바탕
  const CARD_ALT = dark ? "2A3570" : H.accent6; // 강조 카드 바탕
  const TXT = dark ? C.background1 : C.text1;   // 본문 글
  const SUB = C.accent5;                    // 보조 글
  const TXT_HEX = dark ? H.lt1 : H.dk1;

  // ---------- 레이아웃 ----------
  const lightObjects = [
    { placeholder: { options: { name: "title", type: "title", x: MARGIN, y: 0.35, w: 10.4, h: 0.9, fontSize: 30, bold: true, color: TXT, valign: "middle", align: "left", margin: 0 }, text: "제목" } },
    { text: { text: footer, options: { x: MARGIN, y: 6.95, w: 7, h: 0.35, fontSize: 10, color: C.accent5, valign: "middle", margin: 0 } } },
  ];
  const contentLogo = dark ? logoW : logoD;
  if (contentLogo) lightObjects.unshift({ image: { x: W - MARGIN - lw, y: 0.45, w: lw, h: lh, path: contentLogo } });
  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: BG },
    objects: lightObjects,
    slideNumber: { x: 12.2, y: 6.95, w: 0.5, h: 0.35, fontSize: 10, color: C.accent5, align: "right" },
  });
  pres.defineSlideMaster({ title: "DARKTITLE", background: { color: H.dk2 }, objects: [] });
  const darkObjects = [{ text: { text: footer, options: { x: 2.5, y: 6.55, w: 6, h: 0.44, fontSize: 10, color: C.accent5, valign: "middle", margin: 0 } } }];
  if (logoW) darkObjects.unshift({ image: { x: MARGIN, y: 6.55, w: lw * 1.2, h: lh * 1.2, path: logoW } });
  pres.defineSlideMaster({
    title: "DARK",
    background: { color: H.dk2 },
    objects: darkObjects,
    slideNumber: { x: 12.2, y: 6.55, w: 0.5, h: 0.44, fontSize: 10, color: C.accent5, align: "right" },
  });

  // ---------- 공통 부품 ----------
  function card(s, x, y, w, h, fill, name) {
    s.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: fill }, line: { color: fill, width: 0 }, rectRadius: 0.15, objectName: name });
  }
  function circleIcon(s, x, y, d, fill, data, name) {
    s.addShape(pres.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: name + " 원" });
    const pad = d * 0.26;
    s.addImage({ data, x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad, objectName: name });
  }
  function text(s, t, o) {
    s.addText(t, { margin: 0, isTextBox: true, ...o });
  }
  function bulletRuns(lines, opt = {}) {
    return lines.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < lines.length - 1, paraSpaceAfter: opt.gap ?? 8 } }));
  }
  function deco(s, x, y) {
    s.addShape(pres.ShapeType.roundRect, { x, y, w: 2.3, h: 2.3, fill: { color: H.accent1 }, line: { color: H.accent1, width: 0 }, rectRadius: 0.3, rotate: 12, objectName: "장식 1" });
    s.addShape(pres.ShapeType.roundRect, { x: x + 0.8, y: y + 0.7, w: 1.5, h: 1.5, fill: { color: H.accent2 }, line: { color: H.accent2, width: 0 }, rectRadius: 0.25, rotate: -8, objectName: "장식 2" });
  }
  const icons = {};
  async function icon(name, hex) {
    const key = name + hex;
    if (!icons[key]) icons[key] = await iconData(name, hex);
    return icons[key];
  }
  function notes(s, sl) { if (sl.notes) s.addNotes(String(sl.notes)); }

  // 섹션: 연속된 같은 section 라벨을 한 섹션으로
  let curSection = null;
  function openSlide(masterName, sl, fallbackSection) {
    const sec = sl.section || fallbackSection || curSection || spec.title || "Deck";
    if (sec !== curSection) { pres.addSection({ title: sec }); curSection = sec; }
    return pres.addSlide({ masterName, sectionTitle: sec });
  }

  // ---------- 장 유형 ----------
  const R = {};

  R.cover = async (sl) => {
    const s = openSlide("DARKTITLE", sl, "표지");
    if (logoW) s.addImage({ path: logoW, x: 0.9, y: 0.9, w: lw * 1.9, h: lh * 1.9, objectName: "로고" });
    text(s, sl.title || spec.title, { x: 0.9, y: 2.45, w: 11.5, h: 1.2, fontSize: 44, bold: true, color: C.background1, objectName: "제목" });
    const sub = sl.subtitle || spec.subtitle;
    if (sub) text(s, sub, { x: 0.9, y: 3.7, w: 11.5, h: 0.6, fontSize: 22, color: C.accent2, objectName: "부제" });
    const meta = sl.meta || [spec.date, spec.presenter].filter(Boolean).join("   |   ");
    if (meta) text(s, meta, { x: 0.9, y: 4.5, w: 11.5, h: 0.5, fontSize: 14, color: C.accent5, objectName: "날짜" });
    deco(s, 10.2, 3.9);
    notes(s, sl);
  };

  R.agenda = async (sl) => {
    const s = openSlide("CONTENT", sl, "목차");
    s.addText(sl.title || "목차", { placeholder: "title" });
    const items = (sl.items || []).slice(0, 4);
    const n = items.length || 1;
    const gap = 0.3, cw = (W - 2 * MARGIN - gap * (n - 1)) / n, y0 = 1.75, ch = 4.4;
    for (let i = 0; i < items.length; i++) {
      const it = items[i]; const x = MARGIN + i * (cw + gap);
      card(s, x, y0, cw, ch, CARD, `목차 카드 ${i + 1}`);
      circleIcon(s, x + 0.35, y0 + 0.4, 0.9, dark ? H.dk1 : H.lt1, await icon(it.icon || "FiHash", H.accent1), `목차 아이콘 ${i + 1}`);
      text(s, it.num || String(i + 1).padStart(2, "0"), { x: x + 0.35, y: y0 + 1.55, w: cw - 0.7, h: 0.7, fontSize: 36, bold: true, color: C.accent1, objectName: `목차 번호 ${i + 1}` });
      text(s, it.title, { x: x + 0.35, y: y0 + 2.3, w: cw - 0.7, h: 0.6, fontSize: 22, bold: true, color: TXT, objectName: `목차 이름 ${i + 1}` });
      if (it.desc) text(s, it.desc, { x: x + 0.35, y: y0 + 2.95, w: cw - 0.7, h: 1.2, fontSize: 13, color: SUB, valign: "top", objectName: `목차 설명 ${i + 1}` });
    }
    notes(s, sl);
  };

  R.section = async (sl) => {
    const s = openSlide("DARKTITLE", sl, sl.title);
    if (sl.num) text(s, sl.num, { x: 0.9, y: 2.0, w: 4, h: 1.0, fontSize: 54, bold: true, color: C.accent2, objectName: "섹션 번호" });
    text(s, sl.title, { x: 0.9, y: 3.0, w: 11.5, h: 1.0, fontSize: 40, bold: true, color: C.background1, objectName: "섹션 제목" });
    if (sl.desc) text(s, sl.desc, { x: 0.9, y: 4.05, w: 11.5, h: 0.8, fontSize: 18, color: C.accent5, objectName: "섹션 설명" });
    deco(s, 10.2, 3.9);
    notes(s, sl);
  };

  R.bullets = async (sl) => {
    const s = openSlide("CONTENT", sl);
    s.addText(sl.title, { placeholder: "title" });
    const lines = sl.bullets || [];
    const hasSide = !!sl.callout;
    const bw = hasSide ? 7.6 : W - 2 * MARGIN;
    card(s, MARGIN, 1.5, bw, 5.2, CARD, "본문 카드");
    text(s, bulletRuns(lines, { gap: 12 }), { x: MARGIN + 0.4, y: 1.8, w: bw - 0.8, h: 4.6, fontSize: lines.length > 6 ? 15 : 18, color: TXT, valign: "top", objectName: "글머리표" });
    if (hasSide) {
      const cx = MARGIN + bw + 0.4, cw = W - MARGIN - cx;
      card(s, cx, 1.5, cw, 5.2, H.dk2, "강조 카드");
      circleIcon(s, cx + 0.35, 1.9, 0.8, H.accent1, await icon(sl.callout.icon || "FiZap", H.lt1), "강조 아이콘");
      text(s, sl.callout.title || "핵심", { x: cx + 0.35, y: 2.9, w: cw - 0.7, h: 0.6, fontSize: 18, bold: true, color: C.accent2, objectName: "강조 제목" });
      text(s, sl.callout.text || "", { x: cx + 0.35, y: 3.5, w: cw - 0.7, h: 3.0, fontSize: 14, color: C.background1, valign: "top", objectName: "강조 글" });
    }
    notes(s, sl);
  };

  R.cards = async (sl) => {
    const s = openSlide("CONTENT", sl);
    s.addText(sl.title, { placeholder: "title" });
    const cards = (sl.cards || []).slice(0, 4);
    const n = cards.length || 1, gap = 0.4;
    const cw = (W - 2 * MARGIN - gap * (n - 1)) / n, y0 = 1.5, ch = 4.9;
    const accents = [H.accent3, H.accent4, H.accent1, H.accent2];
    for (let i = 0; i < cards.length; i++) {
      const c = cards[i]; const x = MARGIN + i * (cw + gap); const ac = accents[i % accents.length];
      card(s, x, y0, cw, ch, CARD, `카드 ${i + 1}`);
      circleIcon(s, x + 0.35, y0 + 0.35, 0.8, ac, await icon(c.icon || "FiStar", H.lt1), `카드 아이콘 ${i + 1}`);
      if (c.tag) text(s, c.tag, { x: x + 1.3, y: y0 + 0.35, w: cw - 1.6, h: 0.32, fontSize: 11, bold: true, color: ac, objectName: `카드 태그 ${i + 1}` });
      text(s, c.title, { x: x + 1.3, y: y0 + 0.65, w: cw - 1.6, h: 0.6, fontSize: n >= 3 ? 17 : 21, bold: true, color: TXT, valign: "middle", objectName: `카드 제목 ${i + 1}` });
      text(s, bulletRuns(c.lines || [], { gap: 8 }), { x: x + 0.35, y: y0 + 1.5, w: cw - 0.7, h: ch - 1.8, fontSize: n >= 3 ? 13 : 15, color: TXT, valign: "top", objectName: `카드 내용 ${i + 1}` });
    }
    notes(s, sl);
  };

  R.stats = async (sl) => {
    const s = openSlide("CONTENT", sl);
    s.addText(sl.title, { placeholder: "title" });
    const tiles = (sl.tiles || []).slice(0, 4);
    const n = tiles.length || 1, gap = 0.3;
    const tw = (W - 2 * MARGIN - gap * (n - 1)) / n, ty = 1.45, th = 1.6;
    tiles.forEach((t, i) => {
      const x = MARGIN + i * (tw + gap); const em = !!t.emphasis;
      card(s, x, ty, tw, th, em ? H.dk2 : CARD, `타일 ${i + 1}`);
      text(s, t.label, { x: x + 0.3, y: ty + 0.2, w: tw - 0.6, h: 0.35, fontSize: 13, bold: true, color: em ? C.accent2 : C.accent1, objectName: `타일 라벨 ${i + 1}` });
      text(s, String(t.value), { x: x + 0.3, y: ty + 0.5, w: tw - 0.6, h: 0.75, fontSize: 40, bold: true, color: em ? C.background1 : TXT, objectName: `타일 숫자 ${i + 1}` });
      if (t.sub) text(s, t.sub, { x: x + 0.3, y: ty + 1.2, w: tw - 0.6, h: 0.3, fontSize: 11, color: em ? C.background2 : SUB, objectName: `타일 설명 ${i + 1}` });
    });
    if (sl.chart && sl.chart.labels && sl.chart.values) {
      const base = {
        barDir: "bar", showTitle: !!sl.chart.title, title: sl.chart.title || "", titleFontSize: 13, titleColor: TXT_HEX, titleFontFace: "+mn-lt", titleBold: true,
        showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: TXT_HEX, dataLabelFontFace: "+mn-lt",
        catAxisLabelFontSize: 11, catAxisLabelColor: TXT_HEX, catAxisLabelFontFace: "+mn-lt",
        valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, catAxisLineShow: false, valAxisLineShow: false,
        showLegend: false, barGapWidthPct: 45, catAxisOrientation: "maxMin", chartColors: [H.accent1],
      };
      s.addChart(pres.ChartType.bar, [{ name: sl.chart.series || "값", labels: sl.chart.labels, values: sl.chart.values }], { ...base, x: MARGIN, y: 3.3, w: sl.bullets ? 6.2 : W - 2 * MARGIN, h: 3.4, objectName: "차트" });
      if (sl.bullets) text(s, bulletRuns(sl.bullets), { x: MARGIN + 6.6, y: 3.4, w: W - 2 * MARGIN - 6.6, h: 3.2, fontSize: 15, color: TXT, valign: "top", objectName: "설명" });
    } else if (sl.bullets) {
      text(s, bulletRuns(sl.bullets, { gap: 12 }), { x: MARGIN, y: 3.4, w: W - 2 * MARGIN, h: 3.2, fontSize: 17, color: TXT, valign: "top", objectName: "설명" });
    }
    if (sl.source) text(s, sl.source, { x: 4.5, y: 6.6, w: W - MARGIN - 4.5, h: 0.3, fontSize: 9, color: SUB, align: "right", valign: "middle", objectName: "출처" });
    notes(s, sl);
  };

  R.table = async (sl) => {
    const s = openSlide("CONTENT", sl);
    s.addText(sl.title, { placeholder: "title" });
    const cols = sl.columns || [];
    const rows = sl.rows || [];
    const ncol = Math.max(cols.length, ...rows.map((r) => r.length), 1);
    const hl = new Set(sl.highlightRows || []);
    const head = cols.map((c, i) => ({ text: String(c), options: { bold: true, fontSize: 12, color: H.lt1, fill: { color: H.dk2 }, align: i === 0 ? "left" : "center", valign: "middle" } }));
    const body = rows.map((r, ri) => r.map((cell, ci) => ({ text: String(cell ?? ""), options: { fontSize: rows.length > 10 ? 10 : 12, bold: ci === 0 || hl.has(ri), color: TXT_HEX, fill: { color: hl.has(ri) ? CARD_ALT : ci === 0 ? CARD : BG }, align: ci === 0 ? "left" : "center", valign: "middle" } })));
    const tw = W - 2 * MARGIN;
    const colW = [tw * 0.28, ...Array(ncol - 1).fill((tw * 0.72) / Math.max(ncol - 1, 1))];
    const rowH = Math.min(0.6, 4.9 / (rows.length + 1));
    s.addTable([head, ...body], { x: MARGIN, y: 1.5, w: tw, colW, rowH: [rowH, ...Array(rows.length).fill(rowH)], fontFace: theme.bodyFontFace, border: { type: "solid", color: dark ? H.dk1 : "FFFFFF", pt: 1 }, margin: 0.05, objectName: "표" });
    if (sl.note) text(s, sl.note, { x: MARGIN, y: 6.55, w: W - 2 * MARGIN, h: 0.35, fontSize: 11, italic: true, color: SUB, valign: "middle", objectName: "표 비고" });
    notes(s, sl);
  };

  R.twoColumn = async (sl) => {
    const s = openSlide("CONTENT", sl);
    s.addText(sl.title, { placeholder: "title" });
    const cols = [sl.left || {}, sl.right || {}];
    const gap = 0.4, cw = (W - 2 * MARGIN - gap) / 2;
    for (let i = 0; i < 2; i++) {
      const c = cols[i]; const x = MARGIN + i * (cw + gap); const ac = i === 0 ? H.accent1 : H.accent4;
      card(s, x, 1.5, cw, 5.2, i === 0 ? CARD : CARD_ALT, `열 ${i + 1}`);
      s.addShape(pres.ShapeType.rect, { x: x + 0.4, y: 1.85, w: 0.12, h: 0.5, fill: { color: ac }, line: { color: ac, width: 0 }, objectName: `열 띠 ${i + 1}` });
      text(s, c.heading || "", { x: x + 0.7, y: 1.8, w: cw - 1.1, h: 0.6, fontSize: 20, bold: true, color: TXT, valign: "middle", objectName: `열 제목 ${i + 1}` });
      text(s, bulletRuns(c.lines || [], { gap: 10 }), { x: x + 0.4, y: 2.6, w: cw - 0.8, h: 3.9, fontSize: 15, color: TXT, valign: "top", objectName: `열 내용 ${i + 1}` });
    }
    notes(s, sl);
  };

  R.compare = async (sl) => {
    const s = openSlide("CONTENT", sl);
    s.addText(sl.title, { placeholder: "title" });
    const rows = (sl.rows || []).slice(0, 3);
    const y0 = 1.5, avail = 5.2, rg = 0.3;
    const rh = (avail - rg * (rows.length - 1)) / Math.max(rows.length, 1);
    const arrow = await icon("FiArrowRight", H.accent5);
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i]; const y = y0 + i * (rh + rg);
      card(s, MARGIN, y, 3.6, rh, CARD, `비교 왼쪽 ${i + 1}`);
      text(s, sl.fromLabel || "문제", { x: MARGIN + 0.3, y: y + 0.25, w: 3, h: 0.3, fontSize: 12, bold: true, color: C.accent3, objectName: `비교 왼쪽 태그 ${i + 1}` });
      text(s, r.from, { x: MARGIN + 0.3, y: y + 0.6, w: 3.0, h: rh - 0.8, fontSize: 17, bold: true, color: TXT, valign: "top", objectName: `비교 왼쪽 글 ${i + 1}` });
      s.addImage({ data: arrow, x: MARGIN + 3.8, y: y + rh / 2 - 0.3, w: 0.6, h: 0.6, objectName: `화살표 ${i + 1}` });
      const rx = MARGIN + 4.6, rw = W - MARGIN - rx;
      card(s, rx, y, rw, rh, CARD_ALT, `비교 오른쪽 ${i + 1}`);
      circleIcon(s, rx + 0.35, y + 0.3, 0.8, H.accent4, await icon(r.icon || "FiCheckCircle", H.lt1), `비교 아이콘 ${i + 1}`);
      text(s, sl.toLabel || "개선", { x: rx + 1.4, y: y + 0.25, w: 3, h: 0.3, fontSize: 12, bold: true, color: C.accent4, objectName: `비교 오른쪽 태그 ${i + 1}` });
      text(s, r.to, { x: rx + 1.4, y: y + 0.55, w: rw - 1.7, h: 0.5, fontSize: 19, bold: true, color: TXT, objectName: `비교 오른쪽 제목 ${i + 1}` });
      text(s, bulletRuns(r.lines || [], { gap: 4 }), { x: rx + 1.4, y: y + 1.1, w: rw - 1.7, h: rh - 1.3, fontSize: 13, color: TXT, valign: "top", objectName: `비교 오른쪽 내용 ${i + 1}` });
    }
    if (sl.note) text(s, sl.note, { x: MARGIN, y: 6.55, w: 9, h: 0.35, fontSize: 12, italic: true, color: SUB, objectName: "비교 안내" });
    notes(s, sl);
  };

  R.steps = async (sl) => {
    const s = openSlide("CONTENT", sl);
    s.addText(sl.title, { placeholder: "title" });
    const steps = (sl.steps || []).slice(0, 5);
    const n = steps.length || 1, gap = 0.25;
    const sw = (W - 2 * MARGIN - gap * (n - 1)) / n, y0 = 1.8, sh = 4.3;
    for (let i = 0; i < steps.length; i++) {
      const st = steps[i]; const x = MARGIN + i * (sw + gap);
      card(s, x, y0, sw, sh, i === steps.length - 1 ? CARD_ALT : CARD, `단계 ${i + 1}`);
      s.addShape(pres.ShapeType.ellipse, { x: x + 0.3, y: y0 + 0.3, w: 0.7, h: 0.7, fill: { color: H.accent1 }, line: { color: H.accent1, width: 0 }, objectName: `단계 번호 원 ${i + 1}` });
      text(s, String(i + 1), { x: x + 0.3, y: y0 + 0.3, w: 0.7, h: 0.7, fontSize: 20, bold: true, color: C.background1, align: "center", valign: "middle", objectName: `단계 번호 ${i + 1}` });
      text(s, st.title, { x: x + 0.3, y: y0 + 1.2, w: sw - 0.6, h: 0.8, fontSize: n >= 4 ? 16 : 20, bold: true, color: TXT, valign: "top", objectName: `단계 제목 ${i + 1}` });
      text(s, st.desc || "", { x: x + 0.3, y: y0 + 2.05, w: sw - 0.6, h: sh - 2.3, fontSize: n >= 4 ? 12 : 14, color: SUB, valign: "top", objectName: `단계 설명 ${i + 1}` });
    }
    notes(s, sl);
  };

  R.closing = async (sl) => {
    const s = openSlide("DARK", sl, "마무리");
    text(s, sl.title || "오늘 정할 것", { x: 0.9, y: 0.7, w: 11, h: 0.9, fontSize: 34, bold: true, color: C.background1, objectName: "마무리 제목" });
    const items = (sl.items || []).slice(0, 4);
    items.forEach((it, i) => {
      const y = 2.0 + i * (items.length > 3 ? 1.05 : 1.35);
      s.addShape(pres.ShapeType.ellipse, { x: 0.9, y, w: 0.8, h: 0.8, fill: { color: H.accent2 }, line: { color: H.accent2, width: 0 }, objectName: `결정 번호 원 ${i + 1}` });
      text(s, String(i + 1), { x: 0.9, y, w: 0.8, h: 0.8, fontSize: 22, bold: true, color: C.text2, align: "center", valign: "middle", objectName: `결정 번호 ${i + 1}` });
      text(s, it.title, { x: 2.0, y: y - 0.02, w: 8.5, h: 0.45, fontSize: 22, bold: true, color: C.background1, objectName: `결정 제목 ${i + 1}` });
      if (it.desc) text(s, it.desc, { x: 2.0, y: y + 0.42, w: 8.5, h: 0.4, fontSize: 15, color: C.accent5, objectName: `결정 설명 ${i + 1}` });
    });
    deco(s, 10.3, 2.3);
    notes(s, sl);
  };

  // ---------- 생성 ----------
  const slides = Array.isArray(spec.slides) ? spec.slides : [];
  if (!slides.length || slides[0].type !== "cover") slides.unshift({ type: "cover", title: spec.title, subtitle: spec.subtitle });
  for (const sl of slides) {
    const fn = R[sl.type];
    if (!fn) { console.warn(`알 수 없는 장 유형: ${sl.type} → bullets 로 처리`); await R.bullets({ ...sl, bullets: sl.bullets || sl.lines || [] }); continue; }
    await fn(sl);
  }
  fs.mkdirSync(path.dirname(path.resolve(outFile)), { recursive: true });
  await pres.writeFile({ fileName: outFile });
  await applyTheme(outFile, { name: theme.name, colors: theme.colors });
  return slides.length;
}

(async () => {
  const args = process.argv.slice(2);
  if (args.includes("--list-themes")) {
    console.log(JSON.stringify(loadThemes().map((t) => ({ id: t.id, label: t.label }))));
    return;
  }
  const [specFile, outFile] = args.filter((a) => !a.startsWith("--"));
  if (!specFile || !outFile) { console.error("usage: node build.js <spec.json> <out.pptx> [--theme id]"); process.exit(2); }
  const spec = JSON.parse(fs.readFileSync(specFile, "utf8"));
  const ti = args.indexOf("--theme");
  const themeId = ti >= 0 ? args[ti + 1] : spec.theme || "climath";
  const theme = loadThemes().find((t) => t.id === themeId);
  if (!theme) { console.error(`테마 없음: ${themeId}`); process.exit(2); }
  const n = await build(spec, theme, outFile);
  console.log(JSON.stringify({ ok: true, out: path.resolve(outFile), slides: n, theme: theme.id }));
})().catch((e) => { console.error(e); process.exit(1); });
