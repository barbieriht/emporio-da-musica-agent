"""Builds docs/maestro-documentation.pdf from the project's documentation.

Usage:  uv run python scripts/build_docs_pdf.py

Renders README.md, SPEC.md, docs/agents/*.md and the example conversations (appendix) with the
`markdown` package and prints them to PDF with `wkhtmltopdf` (must be installed on the system).
Emojis are dropped in the PDF (no emoji font is assumed); the source .md files are not changed.
"""
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "maestro-documentation.pdf"

PARTS = [
    ("Project README", [ROOT / "README.md"]),
    ("Specification (SPEC.md)", [ROOT / "SPEC.md"]),
    ("Development-tool configuration (docs/agents)", sorted((ROOT / "docs" / "agents").glob("*.md"))),
    ("Appendix: example conversations (Portuguese transcripts)", sorted((ROOT / "examples").glob("*.md"))),
]

CSS = """
@page { size: A4; }
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1d2433; }
h1 { font-size: 20pt; border-bottom: 2px solid #1d2433; padding-bottom: 4px; margin-top: 0; }
h2 { font-size: 14.5pt; margin-top: 22px; border-bottom: 1px solid #c9cfda; padding-bottom: 3px; }
h3 { font-size: 12pt; margin-top: 16px; }
h1, h2, h3 { page-break-after: avoid; }
p, li { orphans: 3; widows: 3; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 9pt; background: #f1f3f7; padding: 1px 3px; }
pre { background: #f1f3f7; border: 1px solid #d6dbe5; padding: 8px 10px; white-space: pre-wrap;
      word-wrap: break-word; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 8.6pt; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #c9cfda; padding: 4px 6px; vertical-align: top; font-size: 9.3pt; }
th { background: #e9edf4; text-align: left; }
blockquote { border-left: 4px solid #aab4c8; margin: 8px 0; padding: 2px 12px; color: #3b4660; background: #f7f8fb; }
.part { page-break-before: always; }
.cover { text-align: center; padding-top: 180px; }
.cover h1 { border: none; font-size: 26pt; }
.cover .sub { font-size: 12pt; color: #3b4660; }
.cover .meta { margin-top: 40px; font-size: 10pt; color: #55607a; }
.toc li { margin: 4px 0; }
.tool { margin: 6px 0 8px 14px; border-left: 3px solid #aab4c8; padding-left: 8px; page-break-inside: avoid; }
.tool-title { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.8pt; color: #3b4660; font-weight: bold; }
.tool pre { margin: 3px 0 0; }
"""

# Emoji and pictographs: no emoji font is assumed, so they would render as empty boxes.
EMOJI = re.compile("[\U0001F000-\U0001FFFF☀-➿⬀-⯿️‍]")


LIST_ITEM = re.compile(r"^\s*([-*+]|\d+\.)\s+")


def blank_line_before_lists(text: str) -> str:
    """GitHub renders a list right after a paragraph line; Python-Markdown needs a blank line first."""
    out, in_fence = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and LIST_ITEM.match(line) and out:
            previous = out[-1]
            if previous.strip() and not LIST_ITEM.match(previous) and not previous.startswith((" ", "\t")):
                out.append("")
        out.append(line)
    return "\n".join(out)


def prepare(text: str) -> str:
    text = blank_line_before_lists(text)
    # <details><summary>🔧 <code>tool(args)</code></summary> ... </details> -> always-visible block
    text = re.sub(
        r"<details><summary>\U0001F527\s*(.*?)</summary>",
        lambda m: f'<div class="tool"><div class="tool-title">Tool call: {m.group(1)}</div>',
        text,
    )
    text = text.replace("</details>", "</div>")
    text = EMOJI.sub("", text)
    # relative links and in-page anchors do not work in a PDF: keep the text, drop the link
    text = re.sub(r"\[([^\]]+)\]\((?!https?://)[^)]*\)", r"\1", text)
    return text


def render(path: Path) -> str:
    return markdown.markdown(
        prepare(path.read_text(encoding="utf-8")),
        extensions=["tables", "fenced_code", "sane_lists"],
    )


def build_html(commit: str) -> str:
    sections = []
    toc = []
    for part_index, (title, files) in enumerate(PARTS, start=1):
        if not files:
            continue
        toc.append(f"<li>{html.escape(title)}</li>")
        chunk = [f'<div class="part"><h1 style="font-size:22pt">{part_index}. {html.escape(title)}</h1></div>']
        for f in files:
            chunk.append(f'<div class="doc"><p><em>Source: <code>{f.relative_to(ROOT)}</code></em></p>{render(f)}</div>')
        sections.append("\n".join(chunk))
    cover = f"""
    <div class="cover">
      <h1>Maestro — customer-service agent<br>for Empório da Música</h1>
      <p class="sub">Project documentation: README, specification, tool configuration and example conversations</p>
      <p class="meta">Artefact AI Engineer technical challenge<br>
      Repository: https://github.com/barbieriht/emporio-da-musica-agent<br>
      Built from commit <code>{commit}</code></p>
      <div style="text-align:left; display:inline-block; margin-top:30px"><strong>Contents</strong><ol class="toc">{''.join(toc)}</ol></div>
    </div>"""
    return f"<!doctype html><html><head><meta charset='utf-8'><title>Maestro documentation</title><style>{CSS}</style></head><body>{cover}{''.join(sections)}</body></html>"


def main() -> int:
    if shutil.which("wkhtmltopdf") is None:
        print("wkhtmltopdf is not installed (apt install wkhtmltopdf)", file=sys.stderr)
        return 1
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip() or "unknown"
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", ".", ":!docs/maestro-documentation.pdf"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.strip()
    if dirty:
        commit += " + uncommitted changes"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "docs.html"
        page.write_text(build_html(commit), encoding="utf-8")
        subprocess.run(
            [
                "wkhtmltopdf", "--quiet", "--enable-local-file-access", "--encoding", "utf-8",
                "--page-size", "A4", "--margin-top", "18mm", "--margin-bottom", "18mm",
                "--margin-left", "16mm", "--margin-right", "16mm",
                str(page), str(OUT),
            ],
            check=True,
        )
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
