"""Rendered-page contact sheet and structural QA for the high-spec PDF."""

from __future__ import annotations

from pathlib import Path
import re

import pdfplumber
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "output/pdf/PeopleMatch-Agent-Portfolio-HighSpec.pdf"
OLD = ROOT / "output/pdf/PeopleMatch-Agent-Portfolio-Final.pdf"
RENDERED = ROOT / "output/portfolio-highspec/rendered"
SHEET = ROOT / "output/portfolio-highspec/contact-sheet.png"


def main() -> None:
    pages = sorted(RENDERED.glob("page-*.png"))
    assert len(pages) == 10, f"Expected ten rendered pages, found {len(pages)}"
    thumb_w = 496
    thumb_h = 351
    gap = 20
    sheet = Image.new("RGB", (thumb_w * 2 + gap * 3, (thumb_h + 26) * 5 + gap * 6), "#E7EBE6")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 13)
    for i, path in enumerate(pages):
        with Image.open(path) as original:
            thumb = original.convert("RGB")
            thumb.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            x = gap + (i % 2) * (thumb_w + gap)
            y = gap + (i // 2) * (thumb_h + 26 + gap)
            sheet.paste(thumb, (x, y + 21))
            draw.text((x, y), f"PAGE {i + 1:02d}", fill="#153A2E", font=font)
    sheet.save(SHEET, optimize=True)

    new = PdfReader(SOURCE)
    assert len(new.pages) == 10
    if OLD.is_file():
        assert len(PdfReader(OLD).pages) == 9
    assert all(abs(float(p.mediabox.width) - 841.89) < 0.1 for p in new.pages)
    assert all(abs(float(p.mediabox.height) - 595.276) < 0.1 for p in new.pages)
    text = "\n".join(page.extract_text() or "" for page in new.pages)
    for required in (
        "rM0on",
        "Hybrid Retrieval",
        "LambdaMART",
        "Semantic Selection",
        "Deterministic Binding",
        "Grounding",
        "0.9593",
        "0.9597",
        "Synthetic sandbox",
        "post-exposure",
        "Requires Human Review",
        "3 / 3",
    ):
        assert required.lower() in text.lower(), required
    assert all(len(page.extract_text() or "") > 170 for page in new.pages)
    assert all(f"{i:02d} / 10" in (page.extract_text() or "") for i, page in enumerate(new.pages[1:], 2))
    assert "Match %" not in text
    assert "v2/v3" not in text
    assert "Narrative" in (new.pages[8].extract_text() or "")
    assert "Requires Human Review" in (new.pages[8].extract_text() or "")
    assert not re.search(r"sk-[A-Za-z0-9]{16,}|Bearer\s+[A-Za-z0-9_-]{20,}", text)
    assert SOURCE.stat().st_size < 5_000_000
    fonts = [font.get_object() for page in new.pages for font in page["/Resources"]["/Font"].get_object().values()]
    assert any(
        "Deng" in str(font.get("/BaseFont", ""))
        and bool((font.get("/FontDescriptor").get_object() if font.get("/FontDescriptor") else {}).get("/FontFile2"))
        for font in fonts
    ), "Chinese font not embedded"
    with pdfplumber.open(SOURCE) as document:
        overflow = [
            (i + 1, char.get("text"), char["x0"], char["top"])
            for i, page in enumerate(document.pages)
            for char in page.chars
            if char["x0"] < -1 or char["x1"] > page.width + 1 or char["top"] < -1 or char["bottom"] > page.height + 1
        ]
        assert not overflow, overflow[:10]
    urls = [
        annotation.get_object().get("/A", {}).get("/URI")
        for page in new.pages
        for annotation in page.get("/Annots", [])
    ]
    assert "https://github.com/rM0on/peoplematch-agent" in urls
    print(f"PASS: {len(new.pages)} A4 landscape pages; no page-edge text overflow; GitHub link; contact sheet {SHEET}")


if __name__ == "__main__":
    main()
