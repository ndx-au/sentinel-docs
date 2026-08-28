#!/usr/bin/env python3
"""Rewrite old Sentinel docs filenames in fcms content to slug paths.

Reads old-filename → slug from the MAP block in sn.docs/ct/README.md
(between <!-- MAP-START --> and <!-- MAP-END -->, lines of the form
`- old.md: new-slug`). For every sn.docs/ct/*.md file, rewrites relative
Markdown links ](NN-NAME.md) and ](NN-NAME.md#anchor) to ](/slug#anchor).
](README.md) becomes ](/index) when mapped.

Link targets that look like relative .md files but are missing from the
mapping are reported; the process exits 1 if any remain.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CT_DIR = REPO / "sn.docs" / "ct"
MAP_FILE = CT_DIR / "README.md"

MAP_START = "<!-- MAP-START -->"
MAP_END = "<!-- MAP-END -->"
MAP_LINE = re.compile(r"^-\s+(\S+\.md):\s+(\S+)\s*$")
# Markdown links: ](url) or ](url "title") / ](url 'title')
LINK_RE = re.compile(r"\]\(([^)\s]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\)")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
FENCE_RE = re.compile(r"(```[\s\S]*?```)")


def load_mapping(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    start = text.find(MAP_START)
    end = text.find(MAP_END)
    if start < 0 or end < 0 or end <= start:
        raise SystemExit(f"MAP block markers missing in {path}")
    block = text[start + len(MAP_START) : end]
    mapping: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("<!--"):
            continue
        m = MAP_LINE.match(line)
        if not m:
            raise SystemExit(f"unrecognized MAP line in {path}: {line!r}")
        mapping[m.group(1)] = m.group(2)
    if not mapping:
        raise SystemExit(f"empty MAP block in {path}")
    return mapping


def is_skip_url(url: str) -> bool:
    if not url:
        return True
    if url.startswith("#"):
        return True
    if url.startswith("/") or url.startswith("//"):
        return True
    if SCHEME_RE.match(url):
        return True
    return False


def rewrite_segment(segment: str, mapping: dict[str, str], src: Path, errors: list[str]) -> str:
    def repl(m: re.Match[str]) -> str:
        url = m.group(1)
        if is_skip_url(url):
            return m.group(0)
        path, _, anchor = url.partition("#")
        if not path.endswith(".md"):
            return m.group(0)
        fname = os.path.basename(path)
        slug = mapping.get(fname)
        if slug is None:
            errors.append(f"{src.relative_to(REPO)}: {url}")
            return m.group(0)
        new = f"/{slug}"
        if anchor:
            new += f"#{anchor}"
        return m.group(0).replace(url, new, 1)

    return LINK_RE.sub(repl, segment)


def rewrite_file(path: Path, mapping: dict[str, str], errors: list[str]) -> int:
    original = path.read_text(encoding="utf-8")
    parts = FENCE_RE.split(original)
    out: list[str] = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            out.append(part)
        else:
            out.append(rewrite_segment(part, mapping, path, errors))
    updated = "".join(out)
    if updated == original:
        return 0
    path.write_text(updated, encoding="utf-8")
    old_urls = LINK_RE.findall(FENCE_RE.sub("", original))
    new_urls = LINK_RE.findall(FENCE_RE.sub("", updated))
    return sum(1 for old, new in zip(old_urls, new_urls) if old != new)


def main() -> int:
    mapping = load_mapping(MAP_FILE)
    errors: list[str] = []
    total = 0
    files = sorted(CT_DIR.glob("*.md"))
    if not files:
        print("no content files in sn.docs/ct/", file=sys.stderr)
        return 1
    for path in files:
        total += rewrite_file(path, mapping, errors)
    if errors:
        print("unresolved relative .md links (not in MAP):", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1
    print(f"rewrote {total} link(s) across {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
