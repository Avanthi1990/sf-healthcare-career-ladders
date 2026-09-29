"""Render a Markdown report to a print-ready PDF via headless Chrome.

Supports the subset used by the report: headings, paragraphs, lists, tables,
fenced code, blockquotes, images, and inline emphasis/code.
"""
from __future__ import annotations

import html
import re
import subprocess
import sys
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
@page { size: Letter; margin: 0.8in 0.85in; }
body { font: 10.5pt/1.55 Charter, Georgia, serif; color: #14181d; }
h1 { font-size: 21pt; line-height: 1.2; margin: 0 0 2pt; color: #14304d;
     text-wrap: balance; }
h1 + h3 { font-size: 12pt; font-weight: 400; font-style: italic; color: #4a5763;
          margin: 0 0 10pt; border: 0; }
h2 { font-size: 14pt; margin: 22pt 0 7pt; color: #14304d;
     border-bottom: 1px solid #c3d0dc; padding-bottom: 4pt; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 15pt 0 5pt; color: #22527d; page-break-after: avoid; }
h3 { color: #22527d; }
p { margin: 0 0 8pt; }
ul, ol { margin: 0 0 9pt; padding-left: 19pt; }
li { margin-bottom: 4pt; }
strong { color: #000; }
em { color: #2b3844; }
code { font: 9pt "SF Mono", Menlo, monospace; background: #eef2f6;
       padding: 1px 3.5px; border-radius: 2px; }
pre { background: #f5f7f9; border-left: 3px solid #8fa8bf; padding: 9pt 12pt;
      margin: 10pt 0; overflow-x: auto; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 8.7pt; line-height: 1.5; }
blockquote { margin: 10pt 0; padding: 8pt 12pt; background: #fbf5e8;
             border-left: 3px solid #c08b2c; }
hr { border: 0; border-top: 1px solid #d5dbe1; margin: 16pt 0; }
table { border-collapse: collapse; width: 100%; font-size: 9.3pt; margin: 10pt 0; }
th { background: #e9eff5; text-align: left; padding: 5pt 7pt; color: #14304d;
     font-weight: 700; border-bottom: 1.5px solid #8fa8bf; }
td { padding: 4pt 7pt; border-bottom: 0.5px solid #dde3e9; vertical-align: top; }
tr { page-break-inside: avoid; }
td:not(:first-child) { font-variant-numeric: tabular-nums; }
figure { margin: 12pt 0; page-break-inside: avoid; text-align: center; }
img { max-width: 100%; max-height: 4.1in; }
"""

_STOP = r"^(#{1,6}\s|>|\s*[-*]\s|\s*\d+\.\s|---+$|\||```|!\[)"


def _inline(t: str) -> str:
    t = html.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t


def to_html(md: str, title: str) -> str:
    lines, out, stack, i = md.split("\n"), [], [], 0

    def close(to=0):
        while len(stack) > to:
            out.append(f"</{stack.pop()}>")

    while i < len(lines):
        raw, s = lines[i], lines[i].strip()
        if not s:
            close(); i += 1; continue

        if s.startswith("```"):
            close(); i += 1; buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(html.escape(lines[i])); i += 1
            i += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>"); continue

        m = re.match(r"^!\[(.*?)\]\((.+?)\)$", s)
        if m:
            close()
            out.append(f'<figure><img src="{html.escape(m.group(2))}" '
                       f'alt="{html.escape(m.group(1))}"></figure>')
            i += 1; continue

        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|$", lines[i+1].strip()):
            close()
            cells = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]
            head = cells(lines[i]); i += 2; rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(cells(lines[i])); i += 1
            t = ["<table><thead><tr>"] + [f"<th>{_inline(c)}</th>" for c in head] + ["</tr></thead><tbody>"]
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>")
            out.append("".join(t) + "</tbody></table>"); continue

        if re.match(r"^---+$", s):
            close(); out.append("<hr>"); i += 1; continue

        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            close(); n = len(m.group(1))
            out.append(f"<h{n}>{_inline(m.group(2))}</h{n}>"); i += 1; continue

        if s.startswith(">"):
            close(); buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip()); i += 1
            out.append(f"<blockquote>{_inline(' '.join(buf))}</blockquote>"); continue

        matched = False
        for pattern, tag, div in ((r"^(\s*)([-*])\s+(.*)$", "ul", 2), (r"^(\s*)(\d+)\.\s+(.*)$", "ol", 3)):
            m = re.match(pattern, raw)
            if not m:
                continue
            depth = len(m.group(1)) // div + 1
            while len(stack) > depth:
                close(len(stack) - 1)
            while len(stack) < depth:
                out.append(f"<{tag}>"); stack.append(tag)
            # A list item continues onto following indented lines until a blank
            # line or the next marker. Without this every wrapped item is split
            # into a stray paragraph and the numbering restarts.
            parts, i = [m.group(3)], i + 1
            while (i < len(lines) and lines[i].strip()
                   and re.match(r"^\s+", lines[i])
                   and not re.match(r"^\s*([-*]|\d+\.)\s", lines[i])):
                parts.append(lines[i].strip()); i += 1
            out.append(f"<li>{_inline(' '.join(parts))}</li>")
            matched = True
            break
        if not matched:
            buf = []
            while i < len(lines) and lines[i].strip() and not re.match(_STOP, lines[i].strip()):
                buf.append(lines[i].strip()); i += 1
            if buf:
                close(); out.append(f"<p>{_inline(' '.join(buf))}</p>")
            else:
                i += 1
        # list branch already advanced i

    close()
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
            f"<style>{CSS}</style></head><body>{''.join(out)}</body></html>")


def main() -> None:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "report/report.md").resolve()
    pdf = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".pdf")
    tmp = src.with_suffix(".rendered.html")
    md = src.read_text()
    # PDF title = the report's first heading, not the file name.
    title = next((l[2:].strip() for l in md.splitlines() if l.startswith("# ")), src.stem)
    tmp.write_text(to_html(md, title))
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--virtual-time-budget=10000", f"--print-to-pdf={pdf}", f"file://{tmp}"],
        check=True, capture_output=True,
    )
    print(f"  wrote {pdf}  ({pdf.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
