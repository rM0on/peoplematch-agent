"""Final structural, factual and rendered-page QA for the Ultimate PDF."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pdfplumber
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
import build_highspec as base  # noqa: E402
import review_highspec as common  # noqa: E402


PDF = ROOT / "docs/portfolio/PeopleMatch-Agent-Portfolio.pdf"
PAGES = ROOT / "output/portfolio-ultimate/final-render"
SHEET = ROOT / "output/portfolio-ultimate/final-contact-sheet.png"
PRESERVED = {
    "PeopleMatch-Agent-Portfolio-Final.pdf": "0b733d3c7db921a9c3c30dddaffb4eeff3baf538c5350f8307dfd48a8706576a",
    "PeopleMatch-Agent-Portfolio-HighSpec.pdf": "5738884c7f3072bfc800edb031eb73bcb8917b60cae58c5491fbc845b15bcdb6",
}


def main() -> None:
    # The legacy visual reviewer checks page images, embedded Chinese fonts,
    # outbound URL, landscape geometry and page-edge text overflow.
    common.SOURCE = PDF
    common.RENDERED = PAGES
    common.SHEET = SHEET
    common.main()

    for filename, expected in PRESERVED.items():
        baseline = ROOT / "output/pdf" / filename
        if baseline.is_file():
            actual = hashlib.sha256(baseline.read_bytes()).hexdigest()
            assert actual == expected, f"Preserved PDF changed: {filename}"
    base.load_sources()  # frozen eval, screenshots, Fresh Trusted run

    reader = PdfReader(PDF)
    assert len(reader.pages) == 10
    metadata = reader.metadata
    assert metadata.title == "PeopleMatch Agent - AI Matching & Evidence-grounded Recommendation"
    assert metadata.author == "rM0on"
    assert metadata.subject == "AI Algorithm / LLM Engineering Portfolio Case Study"
    assert all(term in str(metadata.get("/Keywords", "")) for term in ("Hybrid Retrieval", "LambdaMART", "Grounding", "Offline Evaluation"))
    pages = [page.extract_text() or "" for page in reader.pages]
    assert "CANDIDATE 019" not in pages[0]
    assert "TRUSTED TOP-3 PRODUCT SURFACE" in pages[0]
    assert "PERSONAL PROJECT / LOCAL PROTOTYPE" in pages[0]
    assert "5 项代表性信号" in pages[5] and "10 个显式 pair features" in pages[5]
    assert "PAIRWISE ACCURACY" in pages[7]
    assert "Independent synthetic review workflow" in pages[8]
    assert "Requires Human Review" in pages[8]
    assert all(term in pages[9] for term in ("MY ROLE", "WHAT I DO NOT CLAIM", "3 / 3", "Grounded Explanation", "RecruiterProposition"))
    assert "post-exposure" in pages[7].lower() and "Synthetic sandbox" in pages[7]
    assert not re.search(r"sk-[A-Za-z0-9]{16,}|Bearer\s+[A-Za-z0-9_-]{20,}", "\n".join(pages))
    assert PDF.stat().st_size < 5_000_000

    with pdfplumber.open(PDF) as doc:
        for number, page in enumerate(doc.pages, 1):
            if number in (1, 4, 5, 6, 7, 8, 9):
                assert page.images, f"Page {number} missing frozen screenshot crop"
            for char in page.chars:
                assert -1 <= char["x0"] <= char["x1"] <= page.width + 1
                assert -1 <= char["top"] <= char["bottom"] <= page.height + 1
    print(f"ULTIMATE QA PASS: {len(pages)} pages, {PDF.stat().st_size} bytes; preserved baselines, source hashes, metadata, claims, fonts, link and overflow")


if __name__ == "__main__":
    main()
