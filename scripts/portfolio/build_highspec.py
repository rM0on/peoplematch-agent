"""Build the evidence-checked PeopleMatch landscape case study.

PowerShell: run this file with the bundled Python runtime from the repository root.
Only frozen repository artifacts are read. Screenshots are cropped in the PDF, never edited.
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[2]
IMAGES = ROOT / "docs/images/portfolio-final"
EVAL = ROOT / "data/eval/phase11/runs/20260831T173246Z_test_corrected_final/report.json"
FRESH = ROOT / "backend/tests/fixtures/fresh_top3_trusted_final_20261009T0835Z.jsonl"
OUTPUT = ROOT / "output/pdf/PeopleMatch-Agent-Portfolio-HighSpec.pdf"
OLD_PDF = ROOT / "output/pdf/PeopleMatch-Agent-Portfolio-Final.pdf"
GITHUB = "https://github.com/rM0on/peoplematch-agent"
AUTHOR = "rM0on"
EVAL_SHA = "d8dee5f63405cf4b108f34eaced5c102d07db798d0e8e281da885bc6a769f971"
IMAGE_SHAS = {
    "01-recruiter-view.png": "e61f21b8eb25f8cebedbfd93814fd564ebf6cee5f61303ae7af4342b14fd2fee",
    "02-evidence-provenance.png": "4c41e9d4d73dc9d45d19a5a2f852ca87bc7c93ed61969a3663422b49a9bdd10d",
    "03-engineering-view.png": "e8b8bd4011feb64b07dbdf2319a35cb877b13f009e1458179182f8bf87dc3cfc",
    "04-agent-run.png": "e1f50e5440ac4b9b962f51650e0bced4e40180a8a4ff0c90f8ee3e8318be2db0",
    "05-eval-dashboard.png": "526dfb29ad6acaf9d400c582c10e8720e0af506836d5e60d0092a96d4fe810f9",
    "06-bad-case-review.png": "d7521746e7077079a5c8fbb40b6414d19d21cc45ec0da3a9eee9e8cd202248e1",
}


@dataclass(frozen=True)
class DS:
    # A4 landscape; 12-column editorial grid, never a transplanted website grid.
    w: float = landscape(A4)[0]
    h: float = landscape(A4)[1]
    margin: float = 38
    gutter: float = 12
    deep: colors.Color = colors.HexColor("#12362D")
    green: colors.Color = colors.HexColor("#17604D")
    sage: colors.Color = colors.HexColor("#DDEBE2")
    paper: colors.Color = colors.HexColor("#F7F6F1")
    white: colors.Color = colors.white
    ink: colors.Color = colors.HexColor("#21342C")
    muted: colors.Color = colors.HexColor("#65736B")
    hair: colors.Color = colors.HexColor("#D2DDD4")
    amber: colors.Color = colors.HexColor("#A15E31")
    amber_bg: colors.Color = colors.HexColor("#F8ECDD")

    @property
    def content(self) -> float:
        return self.w - 2 * self.margin

    @property
    def col(self) -> float:
        return (self.content - 11 * self.gutter) / 12

    def x(self, col: int) -> float:
        return self.margin + col * (self.col + self.gutter)

    def span(self, cols: int) -> float:
        return cols * self.col + (cols - 1) * self.gutter


D = DS()


def font_setup() -> None:
    directory = Path("C:/Windows/Fonts")
    missing = [name for name in ("Deng.ttf", "Dengb.ttf", "arial.ttf", "arialbd.ttf") if not (directory / name).is_file()]
    if missing:
        raise RuntimeError(f"Portfolio PDF build requires Windows DengXian/Arial fonts: {', '.join(missing)}")
    for family, filename in (
        ("Deng", "Deng.ttf"),
        ("DengBold", "Dengb.ttf"),
        ("ArialPM", "arial.ttf"),
        ("ArialPMBold", "arialbd.ttf"),
    ):
        pdfmetrics.registerFont(TTFont(family, str(directory / filename)))
    pdfmetrics.registerFontFamily("Deng", normal="Deng", bold="DengBold")


def ypos(top: float) -> float:
    return D.h - top


def rect(c: canvas.Canvas, x: float, top: float, w: float, h: float, fill: colors.Color, stroke=None, radius=0) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke or fill)
    if radius:
        c.roundRect(x, ypos(top + h), w, h, radius, fill=1, stroke=int(stroke is not None))
    else:
        c.rect(x, ypos(top + h), w, h, fill=1, stroke=int(stroke is not None))


def line(c: canvas.Canvas, x1: float, top1: float, x2: float, top2: float, color=None, width=0.8) -> None:
    c.setStrokeColor(color or D.hair)
    c.setLineWidth(width)
    c.line(x1, ypos(top1), x2, ypos(top2))


def txt(c: canvas.Canvas, text: str, x: float, top: float, size=10, color=None, bold=False, latin=False) -> None:
    c.setFillColor(color or D.ink)
    c.setFont(("ArialPMBold" if bold else "ArialPM") if latin else ("DengBold" if bold else "Deng"), size)
    c.drawString(x, ypos(top + size * 0.82), text)


def para(c: canvas.Canvas, text: str, x: float, top: float, w: float, size=9.5, leading=None, color=None, bold=False, max_h=None) -> float:
    style = ParagraphStyle(
        "pm",
        fontName="DengBold" if bold else "Deng",
        fontSize=size,
        leading=leading or size * 1.47,
        textColor=color or D.ink,
        alignment=TA_LEFT,
        wordWrap="CJK",
        splitLongWords=True,
        spaceAfter=0,
        spaceBefore=0,
    )
    p = Paragraph(text, style)
    _, h = p.wrap(w, 1000)
    if max_h is not None and h > max_h + 0.2:
        raise ValueError(f"Text exceeds reserved height: {h:.1f} > {max_h:.1f}: {text[:60]}")
    p.drawOn(c, x, ypos(top + h))
    return h


def kicker(c: canvas.Canvas, text: str, x: float, top: float, color=None) -> None:
    txt(c, text.upper(), x, top, 8.1, color or D.green, bold=True, latin=True)


def page_base(c: canvas.Canvas, page: int, section: str, dark=False) -> None:
    rect(c, 0, 0, D.w, D.h, D.deep if dark else D.paper)
    if not dark:
        line(c, D.margin, 31, D.w - D.margin, 31, D.green, 1.1)
        kicker(c, "PEOPLEMATCH / ENGINEERING CASE STUDY", D.margin, 17)
        txt(c, section.upper(), D.w - D.margin - 153, 17, 7.8, D.muted, latin=True)
        line(c, D.margin, D.h - 29, D.w - D.margin, D.h - 29)
        txt(c, "LOCAL PROTOTYPE  /  SYNTHETIC SANDBOX", D.margin, D.h - 22, 7.1, D.muted, latin=True)
        txt(c, f"{page:02d} / 10", D.w - D.margin - 38, D.h - 22, 8, D.green, bold=True, latin=True)


def page_heading(c: canvas.Canvas, page: int, section: str, title: str, sub: str) -> None:
    page_base(c, page, section)
    txt(c, title, D.margin, 51, 25.5, D.deep, bold=True)
    para(c, sub, D.margin, 88, D.content, 9.6, color=D.muted, max_h=31)


def pill(c: canvas.Canvas, text: str, x: float, top: float, w: float, fill=None, fg=None) -> None:
    rect(c, x, top, w, 24, fill or D.sage, radius=11)
    txt(c, text, x + 10, top + 6.1, 8.1, fg or D.deep, bold=True)


def arrow(c: canvas.Canvas, x1: float, top1: float, x2: float, top2: float, color=None) -> None:
    color = color or D.green
    line(c, x1, top1, x2, top2, color, 1.3)
    if abs(x2 - x1) > abs(top2 - top1):
        dx = -5 if x2 > x1 else 5
        line(c, x2 + dx, top2 - 3, x2, top2, color, 1.3)
        line(c, x2 + dx, top2 + 3, x2, top2, color, 1.3)
    else:
        dy = -5 if top2 > top1 else 5
        line(c, x2 - 3, top2 + dy, x2, top2, color, 1.3)
        line(c, x2 + 3, top2 + dy, x2, top2, color, 1.3)


def image_crop(c: canvas.Canvas, filename: str, crop: tuple[int, int, int, int], x: float, top: float, w: float, h: float, fit="cover", border=True) -> None:
    with Image.open(IMAGES / filename) as original:
        image = original.convert("RGB").crop(crop)
        iw, ih = image.size
        scale = max(w / iw, h / ih) if fit == "cover" else min(w / iw, h / ih)
        sw, sh = iw * scale, ih * scale
        if fit == "cover":
            # Crop again in source pixels so drawImage never distorts or overflows the frame.
            wanted_w, wanted_h = int(round(w / scale)), int(round(h / scale))
            l = max(0, (iw - wanted_w) // 2)
            t = max(0, (ih - wanted_h) // 2)
            image = image.crop((l, t, l + wanted_w, t + wanted_h))
            sw, sh = w, h
        data = io.BytesIO()
        image.save(data, format="PNG", optimize=True)
        data.seek(0)
        if border:
            rect(c, x - 0.5, top - 0.5, w + 1, h + 1, D.white, stroke=D.hair, radius=4)
        px = x + (w - sw) / 2
        py = top + (h - sh) / 2
        c.drawImage(ImageReader(data), px, ypos(py + sh), width=sw, height=sh)


def source(c: canvas.Canvas, text: str, x: float, top: float, width: float) -> None:
    para(c, text, x, top, width, size=7.25, leading=10, color=D.muted, max_h=22)


def rule_label(c: canvas.Canvas, n: str, heading: str, copy: str, x: float, top: float, w: float) -> None:
    txt(c, n, x, top, 9, D.green, bold=True, latin=True)
    txt(c, heading, x + 29, top - 1, 11.2, D.deep, bold=True)
    para(c, copy, x + 29, top + 20, w - 29, 9, color=D.muted, max_h=43)


def load_sources() -> tuple[dict, dict, dict]:
    assert hashlib.sha256(EVAL.read_bytes()).hexdigest() == EVAL_SHA, "Frozen evaluation changed"
    for name, expected in IMAGE_SHAS.items():
        assert hashlib.sha256((IMAGES / name).read_bytes()).hexdigest() == expected, f"Frozen screenshot changed: {name}"
    rows = [json.loads(row) for row in FRESH.read_text(encoding="utf-8").splitlines()]
    by_stage = {row["stage"]: row for row in rows if row["stage"] not in ("propositions",)}
    assert by_stage["summary"]["status"] == "TRUSTED_CHAIN_PASS"
    assert by_stage["summary"]["candidate_count"] == 3
    assert by_stage["summary"]["ranking_invariant"] is True
    assert by_stage["extraction"]["status"] == "PASS"
    assert by_stage["explanation"]["status"] == "PASS"
    assert by_stage["explanation_readback"]["status"] == "PASS"
    assert len([r for r in rows if r["stage"] == "propositions" and r["status"] == "PASS"]) == 3
    match = by_stage["match_run"]
    assert match["snapshot"]["order"] == ["cand_019", "cand_033", "cand_006"]
    assert match["run_id"] == "22326fc2-1766-4c3c-a8f0-2cc81f70849c"
    return json.loads(EVAL.read_text(encoding="utf-8")), match, by_stage


def page_1(c: canvas.Canvas) -> None:
    page_base(c, 1, "positioning", dark=True)
    # A product detail rather than a repeat of the full Recruiter View page.
    rect(c, D.w * 0.57, 0, D.w * 0.43, D.h, D.sage)
    preview_x = D.w * 0.585
    preview_w = D.w - preview_x - 15
    kicker(c, "01 / TRUSTED RECRUITER VIEW", preview_x, 96, D.green)
    image_crop(c, "01-recruiter-view.png", (607, 445, 1338, 742), preview_x, 125, preview_w, 135, fit="contain")
    image_crop(c, "01-recruiter-view.png", (632, 773, 1338, 1024), preview_x, 286, preview_w, 120, fit="contain")
    kicker(c, "FROZEN PRODUCT SURFACE / CANDIDATE 019", preview_x, 437, D.green)
    kicker(c, "AI ALGORITHM  /  LLM APPLICATION  /  PRODUCT ENGINEERING", D.margin, 41, D.sage)
    txt(c, "PeopleMatch", D.margin, 113, 39, D.white, bold=True, latin=True)
    txt(c, "Agent", D.margin, 157, 39, D.white, bold=True, latin=True)
    line(c, D.margin, 223, D.margin + 51, 223, D.sage, 3)
    txt(c, "AI Builder 人岗匹配", D.margin, 250, 21, D.white, bold=True)
    txt(c, "与推荐解释系统", D.margin, 280, 21, D.white, bold=True)
    para(c, "从候选排序到证据复核：谁值得继续看，为什么，什么仍需核实。", D.margin, 338, 405, 12, leading=20, color=D.sage, max_h=59)
    kicker(c, "HYBRID RETRIEVAL     LAMBDAMART     EVIDENCE GROUNDING", D.margin, 449, D.sage)
    kicker(c, "LLM SEMANTIC SELECTION     OFFLINE EVALUATION", D.margin, 465, D.sage)
    line(c, D.margin, 520, D.w * 0.52, 520, D.green, 1)
    txt(c, f"{AUTHOR}  /  AI Algorithm + LLM Engineering", D.margin, 534, 10, D.white, bold=True)
    txt(c, "github.com/rM0on/peoplematch-agent", D.margin, 551, 8.5, D.sage, latin=True)
    c.linkURL(GITHUB, (D.margin, ypos(560), D.margin + 290, ypos(547)), relative=0)
    c.showPage()


def page_2(c: canvas.Canvas) -> None:
    page_heading(c, 2, "problem / product", "相似度不能代替筛查判断。", "单一相似分数不能说明证据、未知和下一步。PeopleMatch 把候选排序变为有来源的人工筛查行动。")
    kicker(c, "THE SHORTCUT", D.x(0), 145, D.muted)
    txt(c, "Resume  ↔  JD", D.x(0), 182, 19, D.muted, bold=True, latin=True)
    arrow(c, D.x(0) + 168, 194, D.x(0) + 242, 194, D.muted)
    txt(c, "similarity score", D.x(0) + 257, 184, 15, D.muted, latin=True)
    line(c, D.margin, 242, D.w - D.margin, 242)
    kicker(c, "THE DECISION FRAMEWORK", D.x(0), 266)
    flow = [
        ("01", "RANK", "谁值得看", "Hybrid Retrieval + LambdaMART"),
        ("02", "EVIDENCE", "为什么", "Candidate / JD source"),
        ("03", "UNKNOWN", "缺什么证据", "Unknown ≠ deficiency"),
        ("04", "VERIFY", "先核实什么", "Human review action"),
    ]
    for i, (n, english, heading, foot) in enumerate(flow):
        x = D.x(i * 3)
        width = D.span(3)
        line(c, x, 306, x + width, 306, D.green, 2)
        txt(c, n, x, 317, 9, D.green, bold=True, latin=True)
        txt(c, english, x, 341, 13, D.deep, bold=True, latin=True)
        txt(c, heading, x, 369, 12.5, D.deep, bold=True)
        para(c, foot, x, 395, width, 8.7, color=D.muted, max_h=29)
        if i < 3:
            arrow(c, x + width - 5, 352, D.x((i + 1) * 3) - 5, 352)
    rect(c, D.margin, 461, D.content, 77, D.sage, radius=5)
    kicker(c, "PRODUCT BOUNDARY", D.margin + 18, 475)
    para(c, "面向 Candidate / AI Builder、Recruiter / Hiring Team 与 Platform Operator；输出是可复核的 decision support，不是自动录用或绝对匹配概率。", D.margin + 18, 498, D.content - 36, 11, color=D.deep, max_h=37)
    c.showPage()


def node(c: canvas.Canvas, x: float, top: float, w: float, h: float, title: str, detail: str, owner="code") -> None:
    fill = D.deep if owner == "ranking" else (D.amber_bg if owner == "llm" else D.white)
    fg = D.white if owner == "ranking" else D.deep
    sub = D.sage if owner == "ranking" else D.muted
    rect(c, x, top, w, h, fill, stroke=None if owner == "ranking" else D.hair, radius=4)
    txt(c, title, x + 9, top + 10, 9.2, fg, bold=True)
    para(c, detail, x + 9, top + 27, w - 18, 7.15, leading=9.6, color=sub, max_h=h - 31)


def page_3(c: canvas.Canvas) -> None:
    page_heading(c, 3, "system architecture", "模型选择语义，系统拥有结构。", "Immutable MatchRun 锁定排序。Provider 只选择候选范围内的语义对象，不能重写身份、证据引用或排名。")
    kicker(c, "INPUT  /  STRUCTURED EXTRACTION", D.margin, 131)
    node(c, D.x(0), 151, D.span(3), 48, "Synthetic JD", "Real structured extraction")
    node(c, D.x(3), 151, D.span(3), 48, "Candidate profiles", "Skills ≠ project evidence")
    arrow(c, D.x(3) + D.span(3) + 1, 175, D.x(6) - 2, 175)
    node(c, D.x(6), 151, D.span(6), 48, "Typed job + candidate context", "Profile contract / source records")
    kicker(c, "RANKING PATH  /  FROZEN OWNER", D.margin, 217)
    rank = [
        ("Hybrid Retrieval", "Dense + sparse / RRF"),
        ("10 Features", "Explicit pair signals"),
        ("LambdaMART", "Final rank owner"),
        ("Top-3", "cand_019 / 033 / 006"),
    ]
    for i, (a, b) in enumerate(rank):
        x = D.x(3 * i)
        node(c, x, 236, D.span(3), 52, a, b, "ranking" if i == 2 else "code")
        if i < 3:
            arrow(c, x + D.span(3) + 1, 262, D.x(3 * (i + 1)) - 2, 262)
    arrow(c, D.w / 2, 290, D.w / 2, 305)
    rect(c, D.margin, 307, D.content, 42, D.deep, radius=4)
    kicker(c, "IMMUTABLE MATCHRUN", D.margin + 14, 316, D.sage)
    txt(c, "Candidate order / LTR raw score / ranking fingerprint", D.margin + 261, 319, 9.2, D.white, latin=True)
    arrow(c, D.w / 2, 351, D.w / 2, 365)
    kicker(c, "EXPLANATION PATH  /  CANDIDATE-SCOPED", D.margin, 365)
    exp = [
        ("Evidence", "Safe projection", "code"),
        ("Option Catalog", "Verified options", "code"),
        ("Qwen Selection", "Semantic choice", "llm"),
        ("Binder", "Refs + relations", "code"),
        ("Plan + Grounding", "Fail closed", "code"),
        ("Proposition", "Trusted structure", "code"),
    ]
    for i, (a, b, owner) in enumerate(exp):
        x = D.x(i * 2)
        node(c, x, 386, D.span(2), 56, a, b, owner)
        if i < 5:
            arrow(c, x + D.span(2) + 1, 414, D.x((i + 1) * 2) - 2, 414)
    rect(c, D.margin, 459, D.content, 63, D.sage, radius=4)
    kicker(c, "OWNERSHIP RULE", D.margin + 15, 470)
    para(c, "LLM-owned: semantic selection. Code-owned: identity, rank, canonical ordering, evidence refs, provenance and Grounding. Explanation reads MatchRun; it never changes Ranking.", D.margin + 15, 490, D.content - 30, 9.5, color=D.deep, max_h=30)
    c.showPage()


def page_4(c: canvas.Canvas) -> None:
    page_heading(c, 4, "recruiter experience", "10 秒，看懂值得继续看的理由。", "截图来自已持久化的 synthetic Fresh Top-3。它呈现的是人工技术复核建议，不是招聘决定。")
    image_crop(c, "01-recruiter-view.png", (277, 286, 1383, 1024), D.margin, 132, D.span(9), 386, fit="cover")
    source(c, "SOURCE / Fresh MatchRun 22326fc2… · selected cand_019 · frozen runtime capture", D.margin, 522, D.span(9))
    x = D.x(9)
    kicker(c, "THE REVIEW LENS", x, 139)
    labels = [
        ("01", "ACTION", "优先人工技术复核"),
        ("02", "SIGNAL", "可追溯的材料信号"),
        ("03", "UNKNOWN", "核心要求证据未建立"),
        ("04", "NEXT CHECK", "先核实岗位相关证据"),
    ]
    for i, (n, h, detail) in enumerate(labels):
        top = 181 + i * 78
        line(c, x, top, x + D.span(3), top, D.hair)
        txt(c, n, x, top + 9, 8.5, D.green, bold=True, latin=True)
        kicker(c, h, x + 25, top + 9)
        para(c, detail, x + 25, top + 28, D.span(3) - 25, 9.2, color=D.deep, max_h=32)
    rect(c, x, 500, D.span(3), 42, D.amber_bg, radius=3)
    para(c, "NOT hire / match / offer probability", x + 9, 509, D.span(3) - 18, 8.2, color=D.amber, max_h=27)
    c.showPage()


def page_5(c: canvas.Canvas) -> None:
    page_heading(c, 5, "evidence / provenance", "可信判断，必须能回到材料。", "Recruiter-facing claim 不是 LLM 事实源；项目 / 技能材料与岗位要求才是可核查的来源。")
    image_crop(c, "02-evidence-provenance.png", (625, 313, 1350, 777), D.margin, 150, D.span(8), 340, fit="contain")
    source(c, "SOURCE / Frozen Evidence drill-down · claim, project source and JD requirement in one runtime view", D.margin, 502, D.span(8))
    x = D.x(8)
    kicker(c, "PROVENANCE PATH", x, 143)
    stages = [
        ("01", "RECRUITER CLAIM", "岗位关联 / 技术信号"),
        ("02", "CANDIDATE SOURCE", "当前候选人的材料"),
        ("03", "PROJECT / SKILL", "有来源的具体证据"),
        ("04", "JD REQUIREMENT", "岗位开放要求"),
    ]
    for i, (n, h, detail) in enumerate(stages):
        t = 181 + 78 * i
        line(c, x + 10, t + 25, x + 10, t + 74, D.hair, 1.2) if i < 3 else None
        rect(c, x, t, 20, 20, D.sage, radius=10)
        txt(c, n, x + 4, t + 5, 7, D.green, bold=True, latin=True)
        kicker(c, h, x + 31, t + 2)
        para(c, detail, x + 31, t + 19, D.span(4) - 31, 9.1, color=D.deep, max_h=32)
    para(c, "Unknown 表示证据未建立，而非候选人能力缺失。", x, 506, D.span(4), 9, color=D.amber, max_h=30)
    c.showPage()


def page_6(c: canvas.Canvas, match: dict) -> None:
    page_heading(c, 6, "ranking engineering", "排名来自可检验的特征链路。", "Dense + sparse 召回候选，显式特征进入 LambdaMART；Explanation 只读取结果。")
    # Three independent crops keep the actual UI numbers readable at 100%.
    image_crop(c, "03-engineering-view.png", (350, 532, 810, 634), D.margin, 145, D.span(6), 84, fit="contain")
    image_crop(c, "03-engineering-view.png", (337, 671, 825, 891), D.margin, 246, D.span(6), 183, fit="contain")
    source(c, "SOURCE / Frozen Engineering View · actual feature snapshot and Ranking Model Raw Score", D.margin, 438, D.span(6))
    x = D.x(6)
    kicker(c, "FROZEN RANKING PATH", x, 146)
    for i, (a, b) in enumerate([
        ("HYBRID RETRIEVAL", "Dense + BM25 / RRF"),
        ("FEATURE ENGINEERING", "10 explicit pair signals"),
        ("LAMBDAMART", "Final rank owner"),
    ]):
        top = 172 + 63 * i
        rect(c, x, top, D.span(6), 51, D.white, stroke=D.hair, radius=3)
        kicker(c, a, x + 11, top + 8)
        txt(c, b, x + 11, top + 25, 9.3, D.deep, latin=True)
        if i < 2:
            arrow(c, x + D.span(6) / 2, top + 52, x + D.span(6) / 2, top + 62)
    line(c, x, 375, x + D.span(6), 375, D.hair)
    score = match["results"][0]["ltr_score_raw"]
    txt(c, f"{score:.6f}", x, 388, 26, D.deep, bold=True, latin=True)
    kicker(c, "RANKING MODEL RAW SCORE", x + 159, 396)
    para(c, "cand_019：召回 #3 → 最终 #1。这个数是相对排序 margin，不是匹配率或录用概率。", x, 434, D.span(6), 9.4, color=D.muted, max_h=39)
    rect(c, x, 487, D.span(6), 45, D.sage, radius=3)
    kicker(c, "MATCHRUN / RANKING FINGERPRINT", x + 10, 495)
    txt(c, f"{match['run_id'][:8]}…   /   {match['snapshot']['ranking_fingerprint'][:20]}…", x + 10, 511, 8.4, D.deep, latin=True)
    c.showPage()


def page_7(c: canvas.Canvas) -> None:
    page_heading(c, 7, "agent / traceability", "可以追踪，但不伪造轨迹。", "Persisted AgentStep 与 Explanation 派生阶段分层呈现；前后排序快照一致。")
    image_crop(c, "04-agent-run.png", (276, 278, 1383, 970), D.margin, 151, D.span(8), 315, fit="contain")
    source(c, "SOURCE / Frozen Agent Run UI · persisted trace separated from derived metadata", D.margin, 478, D.span(8))
    x = D.x(8)
    kicker(c, "PERSISTED TRACE", x, 144)
    para(c, "Resolve inputs<br/>LambdaMART<br/>MatchRun persistence", x, 165, D.span(4), 10, leading=22, color=D.deep, max_h=73)
    line(c, x, 254, x + D.span(4), 254)
    kicker(c, "DERIVED METADATA", x, 270)
    para(c, "Evidence Build<br/>Semantic Selection<br/>Deterministic Binding<br/>Grounding<br/>RecruiterProposition", x, 292, D.span(4), 9.6, leading=20, color=D.deep, max_h=104)
    rect(c, x, 422, D.span(4), 81, D.sage, radius=3)
    kicker(c, "RANKING INVARIANCE", x + 11, 433)
    para(c, "Candidate order + LTR raw scores + fingerprint：Explanation 前后不变。", x + 11, 455, D.span(4) - 22, 9.3, color=D.deep, max_h=37)
    c.showPage()


def bar(c: canvas.Canvas, x: float, top: float, label: str, value: float, w: float, color: colors.Color) -> None:
    txt(c, label, x, top, 9.5, D.deep, bold=True, latin=True)
    rect(c, x, top + 19, w, 13, D.sage, radius=3)
    rect(c, x, top + 19, w * value, 13, color, radius=3)
    txt(c, f"{value:.4f}", x + w + 9, top + 18, 9.5, D.deep, bold=True, latin=True)


def page_8(c: canvas.Canvas, report: dict) -> None:
    page_heading(c, 8, "offline evaluation", "更复杂，不等于更好。", "冻结 Phase 11 Test 比较给出了默认策略的依据，也给出了它不能证明什么。")
    s = report["quality"]["r2"]["strategies"]
    hybrid = s["hybrid_rrf_v4"]
    ltr = s["ltr_ranker_v1"]
    ce = s["cross_encoder_experiment"]
    get = lambda v, k: v[k]["mean"]
    metrics = [
        ("NDCG@5", get(ltr, "judged_condensed_ndcg_at_5")),
        ("NDCG@10", get(ltr, "judged_condensed_ndcg_at_10")),
        ("MRR@10", get(ltr, "judged_condensed_mrr_at_10")),
        ("PAIRWISE", get(ltr, "explicit_pairwise_accuracy")),
    ]
    for i, (name, v) in enumerate(metrics):
        x = D.x(i * 3)
        line(c, x, 145, x + D.span(3), 145, D.green, 1.3)
        kicker(c, name, x, 157)
        txt(c, f"{v:.4f}", x, 179, 24.5, D.deep, bold=True, latin=True)
    kicker(c, "R2 / JUDGED-CONDENSED NDCG@5", D.margin, 249)
    bw = D.span(6) - 50
    bar(c, D.margin, 271, "Hybrid baseline", get(hybrid, "judged_condensed_ndcg_at_5"), bw, D.muted)
    bar(c, D.margin, 328, "LambdaMART / default", get(ltr, "judged_condensed_ndcg_at_5"), bw, D.green)
    bar(c, D.margin, 385, "Cross-Encoder / optional", get(ce, "judged_condensed_ndcg_at_5"), bw, D.amber)
    para(c, "CE 未优于 LTR；因此没有因模型更复杂就提升为默认最终排序。", D.margin, 452, D.span(6), 9.7, color=D.deep, max_h=37)
    x = D.x(6)
    kicker(c, "REAL PRODUCT UI / FROZEN TEST", x, 249)
    image_crop(c, "05-eval-dashboard.png", (277, 264, 1382, 844), x, 272, D.span(6), 214, fit="contain")
    source(c, "Source: Phase 11 Test / 20260831T173246Z_test_corrected_final", x, 491, D.span(6))
    rect(c, D.margin, 518, D.content, 38, D.amber_bg, radius=3)
    para(c, "Synthetic sandbox · post-exposure Test · 5 Jobs · judgment coverage 25% · 未标注 ≠ 负例 · 非生产准确率", D.margin + 10, 529, D.content - 20, 8.7, color=D.amber, max_h=18)
    c.showPage()


def page_9(c: canvas.Canvas) -> None:
    page_heading(c, 9, "bad case / decisions", "好的工程判断，也包括拒绝错误捷径。", "复核样例与真实 Provider 故障历史分别保留；失败被用来重划系统职责，而不是改写成功故事。")
    image_crop(c, "06-bad-case-review.png", (255, 204, 1019, 572), D.margin, 139, D.span(6), 176, fit="contain")
    image_crop(c, "06-bad-case-review.png", (255, 587, 1019, 1100), D.margin, 327, D.span(6), 205, fit="contain")
    source(c, "SOURCE / Independent synthetic review workflow; NOT a Fresh Top-3 or production failure", D.margin, 541, D.span(6))
    x = D.x(6)
    kicker(c, "FEEDBACK → EVIDENCE → ROOT CAUSE → ACTION", x, 142)
    decisions = [
        ("01 / MODEL CHOICE", "CE 未优于 LTR", "保留为可选实验，不取代默认排序。"),
        ("02 / PROVIDER CONTRACT", "Full-object DTO 不稳定", "改为 Semantic Selection + Deterministic Binding + Grounding。"),
        ("03 / PRODUCT TRUST", "自由 Narrative 有强度漂移", "仅作 Experimental / Requires Human Review 草稿。"),
    ]
    for i, (k, h, body) in enumerate(decisions):
        top = 178 + i * 100
        line(c, x, top, x + D.span(6), top)
        kicker(c, k, x, top + 9)
        txt(c, h, x, top + 27, 12, D.deep, bold=True)
        para(c, body, x, top + 53, D.span(6), 9, color=D.muted, max_h=39)
    rect(c, x, 491, D.span(6), 54, D.sage, radius=3)
    para(c, "这不是线上自动学习闭环：人工复核与标注、排名训练、离线评测保持独立。", x + 11, 504, D.span(6) - 22, 8.8, color=D.deep, max_h=32)
    c.showPage()


def page_10(c: canvas.Canvas, match: dict, by_stage: dict) -> None:
    page_heading(c, 10, "validation / limits", "验证到哪里，就只说到哪里。", "受控 Fresh Top-3 证明本地可信主链路可端到端运行；它不是生产招聘效果证明。")
    rect(c, D.margin, 136, D.span(5), 216, D.deep, radius=5)
    kicker(c, "CONTROLLED E2E", D.margin + 18, 155, D.sage)
    txt(c, "3 / 3", D.margin + 17, 184, 46, D.white, bold=True, latin=True)
    para(c, "Grounded Explanation<br/>Canonical RecruiterProposition<br/>Candidate isolation<br/>Persistence readback", D.margin + 18, 249, D.span(5) - 36, 10.7, leading=21, color=D.white, max_h=87)
    x = D.x(5)
    kicker(c, "WHAT WAS ACTUALLY VERIFIED", x, 143)
    facts = [
        "Real Provider structured Extraction + Qwen Semantic Selection",
        "Hybrid Retrieval → Features → LambdaMART → Fresh MatchRun",
        "ExplanationPlanV1 + Grounding + source validation",
        "Same candidate order / raw scores / fingerprint after Explanation",
    ]
    for i, fact in enumerate(facts):
        top = 172 + i * 43
        rect(c, x, top + 2, 6, 6, D.green, radius=3)
        para(c, fact, x + 17, top, D.span(7) - 17, 9.1, color=D.deep, max_h=31)
    line(c, D.margin, 378, D.w - D.margin, 378)
    kicker(c, "IMPLEMENTED STACK", D.margin, 394)
    groups = [
        ("BACKEND", "FastAPI · Pydantic · SQLAlchemy · PostgreSQL · Redis"),
        ("RANKING", "Qdrant · Dense + BM25 · RRF · LightGBM LambdaMART"),
        ("LLM / EVIDENCE", "Structured Output · Selection · Binder · Grounding"),
        ("FRONTEND / QA", "Next.js · React · TypeScript · pytest · Vitest · Playwright"),
    ]
    for i, (h, v) in enumerate(groups):
        gx = D.x((i % 2) * 6)
        gt = 415 + (i // 2) * 45
        kicker(c, h, gx, gt)
        para(c, v, gx, gt + 15, D.span(6) - 15, 8.5, color=D.muted, max_h=30)
    rect(c, D.margin, 509, D.content, 46, D.amber_bg, radius=3)
    para(c, "LIMITS  Local prototype · Synthetic sandbox · Post-exposure offline evaluation · No production traffic, QPS/SLA, online A/B, autonomous hiring or zero-hallucination claim.", D.margin + 10, 519, D.content - 20, 8.4, color=D.amber, max_h=27)
    # The author is a public repository handle; no legal name or private email is inferred.
    txt(c, f"{AUTHOR}  /  AI Algorithm + LLM Engineering", D.margin, 358, 8.8, D.deep, bold=True)
    txt(c, "github.com/rM0on/peoplematch-agent", D.x(6), 358, 8.5, D.green, latin=True)
    c.linkURL(GITHUB, (D.x(6), ypos(371), D.x(6) + 230, ypos(356)), relative=0)
    c.showPage()


def main() -> None:
    font_setup()
    report, match, by_stage = load_sources()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT), pagesize=(D.w, D.h), pageCompression=1)
    c.setTitle("PeopleMatch Agent | High-Spec Engineering Case Study")
    c.setAuthor(AUTHOR)
    c.setSubject("Local synthetic AI matching case study with controlled real-provider validation")
    c.setKeywords("PeopleMatch; Hybrid Retrieval; LambdaMART; Evidence Grounding; Synthetic Sandbox")
    page_1(c)
    page_2(c)
    page_3(c)
    page_4(c)
    page_5(c)
    page_6(c, match)
    page_7(c)
    page_8(c, report)
    page_9(c)
    page_10(c, match, by_stage)
    c.save()
    print(f"Created {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
