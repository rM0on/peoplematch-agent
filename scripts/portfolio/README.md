# Portfolio PDF source

`build_ultimate.py` rebuilds the public 10-page A4 landscape PDF from repository-owned, frozen sources: the six images in `docs/images/portfolio-final/`, the corrected Phase 11 Test report, and the synthetic Fresh Trusted Top-3 JSONL fixture. It verifies the input hashes before authoring. `build_highspec.py` supplies the shared layout helpers and preserves the earlier design baseline; it is not the current public PDF.

This build targets Windows PowerShell and requires Python 3.12, Poppler for page rendering, and the system DengXian/Arial TrueType fonts (`C:\Windows\Fonts\Deng.ttf`, `Dengb.ttf`, `arial.ttf`, `arialbd.ttf`). Those are OS font dependencies, not repository or private-user paths. The output and its source evidence do not contain Provider credentials.

From the repository root:

```powershell
py -3.12 -m venv .venv-portfolio
.\.venv-portfolio\Scripts\python.exe -m pip install -r scripts\portfolio\requirements.txt
.\.venv-portfolio\Scripts\python.exe scripts\portfolio\build_ultimate.py
New-Item -ItemType Directory -Force output\portfolio-ultimate\final-render | Out-Null
pdftoppm -f 1 -l 10 -r 130 -png docs\portfolio\PeopleMatch-Agent-Portfolio.pdf output\portfolio-ultimate\final-render\page
.\.venv-portfolio\Scripts\python.exe scripts\portfolio\review_ultimate.py
```

The stable public artifact is `docs/portfolio/PeopleMatch-Agent-Portfolio.pdf`. Rendered pages, contact sheets, temporary PDFs and the local virtual environment belong in ignored `output/` or `.venv-portfolio/`; do not stage them. The original Final/HighSpec PDFs are local baselines, not dependencies of a fresh-clone build.
