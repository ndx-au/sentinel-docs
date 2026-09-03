#!/usr/bin/env python3
"""Bundle sn.docs/ct into an OKF sidecar for NotebookLM.

Writes notebooklm/index.md and notebooklm/sentinel-docs.md only.
Never overwrites sn.docs/ct/index.md (fcms landing page) or ct/README.md (MAP).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HEADING_RE = re.compile(r"^( {0,3})(#{1,6})(\s+)(.*)$")
FENCE_OPEN_RE = re.compile(r"^( {0,3})([`~]{3,})(.*)$")
MAP_START = "<!-- MAP-START -->"
MAP_END = "<!-- MAP-END -->"
MAP_LINE = re.compile(r"^-\s+(\S+\.md):\s+(\S+)\s*$")
SKIP_NAMES = frozenset({"readme.md", "log.md"})
INDEX_TYPE_ORDER = ("Overview", "Guide", "Reference", "Playbook")

MONOLITH_TYPE = "Documentation Bundle"
MONOLITH_TITLE = "Sentinel Documentation"
MONOLITH_DESCRIPTION = (
    "Hierarchical concatenation of the sentinel-docs OKF bundle for NotebookLM."
)
MONOLITH_TAGS = ["sentinel", "documentation", "notebooklm"]


def humanize(stem: str) -> str:
    name = stem.replace("-", " ").replace("_", " ")
    name = re.sub(r"\s+", " ", name).strip()
    return name.title() if name else stem


def heading_line(level: int, title: str) -> str:
    return f"{'#' * min(max(level, 1), 6)} {title}\n"


def is_closing_fence(line: str, fence_char: str, fence_len: int) -> bool:
    m = FENCE_OPEN_RE.match(line.rstrip("\r\n"))
    if not m:
        return False
    marker = m.group(2)
    if marker[0] != fence_char or len(marker) < fence_len:
        return False
    return m.group(3).strip() == ""


def shift_headings(text: str, delta: int, warnings: list[str], source: str) -> str:
    if delta <= 0:
        return text

    lines = text.splitlines(keepends=True)
    if not lines:
        return text

    out: list[str] = []
    in_fence = False
    fence_char = ""
    fence_len = 0

    for line_no, line in enumerate(lines, start=1):
        body = line.splitlines()[0] if line.splitlines() else line
        ending = line[len(body) :]

        if in_fence:
            if is_closing_fence(body, fence_char, fence_len):
                in_fence = False
            out.append(line)
            continue

        open_fence = FENCE_OPEN_RE.match(body)
        if open_fence:
            marker = open_fence.group(2)
            in_fence = True
            fence_char = marker[0]
            fence_len = len(marker)
            out.append(line)
            continue

        heading = HEADING_RE.match(body)
        if heading:
            old_level = len(heading.group(2))
            new_level = old_level + delta
            if new_level > 6:
                warnings.append(
                    f"{source}:{line_no}: heading H{old_level} shifted to H{new_level}, clamped to H6"
                )
                new_level = 6
            out.append(
                f"{heading.group(1)}{'#' * new_level}{heading.group(3)}{heading.group(4)}{ending}"
            )
            continue

        out.append(line)

    return "".join(out)


def ensure_trailing_newline(text: str) -> str:
    if not text:
        return text
    return text if text.endswith("\n") else text + "\n"


def is_markdown(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".md"


def yaml_unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def yaml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_needs_quote(value: str) -> bool:
    if value == "" or value.strip() != value:
        return True
    if value.lower() in {"true", "false", "null", "yes", "no", "on", "off"}:
        return True
    if value[:1] in {"-", "?", ":", "&", "*", "!", "|", ">", "%", "@", "`"}:
        return True
    return any(ch in value for ch in ":#{}[]&*!|>%@`'\"\n")


def yaml_scalar(value: str) -> str:
    return yaml_quote(value) if yaml_needs_quote(value) else value


def parse_flow_yaml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith(" ") or raw.startswith("\t") or ":" not in raw:
            continue
        key, _, rest = raw.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1].strip()
            result[key] = [yaml_unquote(p.strip()) for p in inner.split(",") if p.strip()]
        elif rest:
            result[key] = yaml_unquote(rest)
        else:
            result[key] = ""
    return result


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = idx
            break
    if end is None:
        return {}, text
    return parse_flow_yaml("".join(lines[1:end])), "".join(lines[end + 1 :])


def emit_frontmatter(data: dict[str, Any]) -> str:
    lines = ["---"]
    lines.extend(_emit_mapping(data, indent=0))
    lines.append("---")
    return "\n".join(lines) + "\n"


def _emit_mapping(data: dict[str, Any], indent: int) -> list[str]:
    pad = "  " * indent
    lines: list[str] = []
    for key, value in data.items():
        lines.extend(_emit_key_value(key, value, pad, indent))
    return lines


def _emit_key_value(key: str, value: Any, pad: str, indent: int) -> list[str]:
    if isinstance(value, dict):
        return [f"{pad}{key}:"] + _emit_mapping(value, indent + 1)
    if isinstance(value, list):
        if not value:
            return [f"{pad}{key}: []"]
        if all(isinstance(item, str) for item in value):
            items = ", ".join(yaml_scalar(item) for item in value)
            return [f"{pad}{key}: [{items}]"]
        lines = [f"{pad}{key}:"]
        for item in value:
            lines.extend(_emit_list_item(item, indent + 1))
        return lines
    if isinstance(value, bool):
        return [f"{pad}{key}: {'true' if value else 'false'}"]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [f"{pad}{key}: {value}"]
    return [f"{pad}{key}: {yaml_scalar(str(value))}"]


def _emit_list_item(item: Any, indent: int) -> list[str]:
    pad = "  " * indent
    if isinstance(item, dict):
        items = list(item.items())
        if not items:
            return [f"{pad}- {{}}"]
        first_key, first_val = items[0]
        if not isinstance(first_val, (dict, list)):
            lines = [f"{pad}- {first_key}: {yaml_scalar(str(first_val))}"]
            rest = dict(items[1:])
            if rest:
                lines.extend(_emit_mapping(rest, indent + 1))
            return lines
        lines = [f"{pad}-"]
        lines.extend(_emit_mapping(item, indent + 1))
        return lines
    return [f"{pad}- {yaml_scalar(str(item))}"]


def load_map_slugs(map_file: Path) -> list[str]:
    if not map_file.is_file():
        return []
    text = map_file.read_text(encoding="utf-8")
    start = text.find(MAP_START)
    end = text.find(MAP_END)
    if start < 0 or end <= start:
        return []
    slugs: list[str] = []
    for line in text[start + len(MAP_START) : end].splitlines():
        line = line.strip()
        if not line or line.startswith("<!--"):
            continue
        m = MAP_LINE.match(line)
        if not m:
            continue
        slug = m.group(2)
        if slug != "index" and slug not in slugs:
            slugs.append(slug)
    return slugs


def rel_from(path: Path, start: Path) -> str:
    return Path(os.path.relpath(path, start)).as_posix()


def iter_concept_files(directory: Path, skip: set[Path]) -> list[Path]:
    files: list[Path] = []
    for path in directory.iterdir():
        if not is_markdown(path):
            continue
        if path.name.lower() in SKIP_NAMES:
            continue
        if path.resolve() in skip:
            continue
        files.append(path)
    return files


def child_dirs(directory: Path) -> list[Path]:
    dirs = [
        path
        for path in directory.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    ]
    dirs.sort(key=lambda p: p.name.lower())
    return dirs


def subtree_has_concepts(directory: Path, skip: set[Path]) -> bool:
    for path in directory.rglob("*"):
        if any(part.startswith(".") for part in path.relative_to(directory).parts):
            continue
        if not is_markdown(path) or path.name.lower() in SKIP_NAMES:
            continue
        if path.resolve() in skip:
            continue
        return True
    return False


@dataclass
class Concept:
    path: Path
    rel: str
    meta: dict[str, Any]
    body: str

    @property
    def concept_type(self) -> str:
        return str(self.meta.get("type", "")).strip()

    @property
    def title(self) -> str:
        title = str(self.meta.get("title", "")).strip()
        return title or humanize(self.path.stem)

    @property
    def description(self) -> str:
        return str(self.meta.get("description", "")).strip()


@dataclass
class TocNode:
    title: str
    path: str | None = None
    type: str | None = None
    children: list[TocNode] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"title": self.title}
        if self.path is not None:
            data["path"] = self.path
        if self.type is not None:
            data["type"] = self.type
        if self.children:
            data["children"] = [child.as_dict() for child in self.children]
        return data


class Bundle:
    def __init__(self, src: Path, skip: set[Path], link_root: Path) -> None:
        self.src = src
        self.skip = skip
        self.link_root = link_root
        self.parts: list[str] = []
        self.concepts: list[Concept] = []
        self.toc: list[TocNode] = []
        self.warnings: list[str] = []
        self.missing_type: list[str] = []
        self.map_slugs = load_map_slugs(src / "README.md")

    def add(self, text: str) -> None:
        text = text.strip("\n")
        if text:
            self.parts.append(text)

    def add_heading(self, level: int, title: str) -> None:
        self.add(heading_line(level, title))

    def link_path(self, path: Path) -> str:
        return rel_from(path, self.link_root)

    def load_concept(self, path: Path) -> Concept:
        rel = path.relative_to(self.src).as_posix()
        meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        concept = Concept(path=path, rel=rel, meta=meta, body=body)
        if not concept.concept_type:
            self.missing_type.append(rel)
        return concept

    def add_concept(self, concept: Concept, shift: int, toc_parent: list[TocNode]) -> None:
        self.concepts.append(concept)
        toc_parent.append(
            TocNode(
                title=concept.title,
                path=self.link_path(concept.path),
                type=concept.concept_type,
            )
        )
        self.add(shift_headings(concept.body, shift, self.warnings, concept.rel))

    def sort_others(self, files: list[Path]) -> list[Path]:
        order = {slug: i for i, slug in enumerate(self.map_slugs)}

        def key(path: Path) -> tuple[int, int | str]:
            if path.stem in order:
                return (0, order[path.stem])
            return (1, path.name.lower())

        return sorted(files, key=key)

    def walk(self, directory: Path, depth: int, toc_parent: list[TocNode]) -> None:
        files = iter_concept_files(directory, self.skip)
        intro: Path | None = None
        others: list[Path] = []
        for path in files:
            if depth == 0 and path.name.lower() == "index.md":
                intro = path
            else:
                others.append(path)
        others = self.sort_others(others)

        if intro is not None:
            self.add_concept(self.load_concept(intro), 0, toc_parent)

        for path in others:
            concept = self.load_concept(path)
            self.add_heading(depth + 1, concept.title)
            self.add_concept(concept, depth + 1, toc_parent)

        for child in child_dirs(directory):
            if not subtree_has_concepts(child, self.skip):
                continue
            node = TocNode(title=humanize(child.name))
            toc_parent.append(node)
            self.add_heading(depth + 1, node.title)
            self.walk(child, depth + 1, node.children)

    def sources(self) -> list[dict[str, str]]:
        return [
            {
                "id": concept.path.stem,
                "resource": self.link_path(concept.path),
                "title": concept.title,
            }
            for concept in self.concepts
        ]

    def render_monolith(self, generated_at: str) -> str:
        frontmatter = emit_frontmatter(
            {
                "type": MONOLITH_TYPE,
                "title": MONOLITH_TITLE,
                "description": MONOLITH_DESCRIPTION,
                "tags": MONOLITH_TAGS,
                "status": "stable",
                "generated": {"by": "process:bundle_docs", "at": generated_at},
                "sources": self.sources(),
                "toc": [node.as_dict() for node in self.toc],
            }
        )
        return frontmatter + "\n" + ensure_trailing_newline("\n\n".join(self.parts))

    def render_index(self, output_rel: str) -> str:
        groups: dict[str, list[Concept]] = {}
        for concept in self.concepts:
            groups.setdefault(concept.concept_type or "Guide", []).append(concept)

        ordered_types = [name for name in INDEX_TYPE_ORDER if name in groups]
        ordered_types.extend(
            sorted(name for name in groups if name not in INDEX_TYPE_ORDER)
        )

        lines = ["---", 'okf_version: "0.2"', "---", ""]
        for type_name in ordered_types:
            lines.append(f"# {type_name}")
            lines.append("")
            for concept in groups[type_name]:
                desc = f" - {concept.description}" if concept.description else ""
                lines.append(
                    f"* [{concept.title}]({self.link_path(concept.path)}){desc}"
                )
            lines.append("")

        lines.append("# Generated")
        lines.append("")
        lines.append(f"* [{MONOLITH_TITLE}]({output_rel}) - {MONOLITH_DESCRIPTION}")
        lines.append("")
        return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Bundle sn.docs/ct into notebooklm/ (OKF index + NotebookLM monolith)."
    )
    parser.add_argument(
        "--src",
        type=Path,
        default=repo_root / "sn.docs" / "ct",
        help="fcms content root (default: <repo>/sn.docs/ct)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root / "notebooklm" / "sentinel-docs.md",
        help="Monolith output (default: <repo>/notebooklm/sentinel-docs.md)",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=None,
        help="OKF index path (default: <output-dir>/index.md)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    src = args.src.resolve()
    output = args.output.resolve()
    index_path = args.index.resolve() if args.index else output.parent / "index.md"

    if not src.is_dir():
        print(f"error: source directory not found: {src}", file=sys.stderr)
        return 1

    skip = {output, index_path}
    bundle = Bundle(src, skip, index_path.parent)
    bundle.walk(src, 0, bundle.toc)

    if bundle.missing_type:
        for rel in bundle.missing_type:
            print(f"error: missing required frontmatter type: {rel}", file=sys.stderr)
        return 1

    if not bundle.concepts:
        print(f"error: no markdown concept files found in {src}", file=sys.stderr)
        return 1

    for warning in bundle.warnings:
        print(f"warning: {warning}", file=sys.stderr)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output.parent.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(bundle.render_monolith(generated_at), encoding="utf-8")
    index_path.write_text(bundle.render_index(output.name), encoding="utf-8")
    print(f"bundled {len(bundle.concepts)} concepts -> {index_path}")
    print(f"bundled {len(bundle.concepts)} concepts -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
