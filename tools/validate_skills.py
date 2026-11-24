#!/usr/bin/env python3
r"""Validate public Sentinel Agent Skills in skills/ for structure, YAML, links, catalog sync, and public safety.

Supported narrow YAML grammar (dependency-free):
- Mapping keys: `^[a-zA-Z0-9_.-]+:` followed by space/tab or end-of-line (never `key:value` without whitespace).
- Plain string scalars: must not start with YAML indicators, must not contain `:` followed by whitespace or
  trailing `:`, and must not be YAML boolean/null/numeric (decimal, float, hex, octal, .inf/.nan) literals.
- Double-quoted scalars: valid YAML 1.2 escapes only (`\"`, `\\`, `\/`, `\b`, `\f`, `\n`, `\r`, `\t`, `\0`,
  `\a`, `\v`, `\e`, `\ `, `\N`, `\_`, `\L`, `\P`, `\xHH`, `\uHHHH`, `\UHHHHHHHH`); no trailing non-comment text.
- Single-quoted scalars: `''` escaped single quote; no trailing non-comment text.
- Block scalars (`>`, `>-`, `|`, `|-`): space indentation >= first content line's indent; non-empty.
- Frontmatter `metadata`: must be a block mapping of string keys to string values (Agent Skills spec).
- Manifest `schema_version`: must be unquoted integer `1`.

Usage:
    python3 tools/validate_skills.py
    python3 tools/validate_skills.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
MANIFEST_PATH = SKILLS_DIR / "manifest.yaml"

SKILL_NAME_RE = re.compile(r"^(sre|sn)-[a-z0-9]+(-[a-z0-9]+)*$")
SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")
FRONTMATTER_OPEN_RE = re.compile(r"\A---[ \t]*\n")
MD_INLINE_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\r\n]+)\)")
MD_REF_DEF_RE = re.compile(r"^[ \t]{0,3}\[([^\]]+)\]:[ \t]*([^\r\n]+)$", re.MULTILINE)

# Agent Skills specification limits (https://agentskills.io/specification)
MAX_NAME_LEN = 64
MAX_DESC_LEN = 1024
MAX_SKILL_MD_LINES = 500
SUPPORTED_MANIFEST_SCHEMA_VERSION = 1

YAML_NON_STRING_LITERALS = {"true", "false", "null", "~", "yes", "no", "on", "off", ".inf", "-.inf", "+.inf", ".nan"}
YAML_NUMBER_RE = re.compile(
    r"^(?:[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?|0[xX][0-9a-fA-F]+|0[oO][0-7]+|0[0-7]+)$"
)
YAML_SIMPLE_ESCAPES = set('0abtnvfre "\\/N_LP')

# Explicitly permitted placeholder tokens for Authorization: Bearer examples.
SAFE_BEARER_PLACEHOLDERS = {
    "YOUR_API_TOKEN",
    "YOUR_TOKEN",
    "API_TOKEN",
    "EXAMPLE_TOKEN",
    "REPLACE_ME",
    "$TOKEN",
    "${TOKEN}",
    "$SENTINEL_TOKEN",
    "${SENTINEL_TOKEN}",
    "<token>",
    "<api-token>",
    "...",
}

# Variable / function-call expression allowed after `"Bearer " .. ` or `"Bearer " + `
SAFE_CODE_EXPR_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.]*(?:\([^)\r\n]*\))?")

# Matches plain-text (`Authorization: Bearer ...`), JSON (`"Authorization": "Bearer ..."`),
# and Lua (`["Authorization"] = "Bearer ..."` or `Authorization = "Bearer ..."`).
BEARER_HEADER_RE = re.compile(
    r"""(?ix)
    (?:["']Authorization["']|\[\s*["']Authorization["']\s*\]|\bAuthorization\b)
    \s*[:=]\s*
    (?P<quote>["'])?
    Bearer[ \t]+
    (?P<rest>[^\r\n}]*)
    """
)
TAILSCALE_CGNAT_RE = re.compile(
    r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b"
)
PRIVATE_RFC1918_RE = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b"
)

# Static public-safety patterns (diagnostics NEVER echo matched text).
FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private sentinel repo relative path", re.compile(r"\.\./sentinel\b")),
    ("home-dir sentinel repo path", re.compile(r"~/code/sentinel\b")),
    ("internal staging domain", re.compile(r"dwp\.solutions", re.IGNORECASE)),
    ("private maintainer LOCAL.md reference", re.compile(r"\bLOCAL\.md\b")),
    ("private ops-handover.md reference", re.compile(r"\bops-handover\.md\b")),
    ("private Go internal package path", re.compile(r"\binternal/[a-z0-9_/-]+")),
    ("private harness agent doc filename", re.compile(r"\bsre4agents\.md\b")),
    ("private Tailscale domain", re.compile(r"\b[a-z0-9-]+\.ts\.net\b", re.IGNORECASE)),
    ("private Tailscale/CGNAT IP", TAILSCALE_CGNAT_RE),
    ("private RFC1918 host IP", PRIVATE_RFC1918_RE),
    ("OpenAI-style secret key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("private key PEM block", re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY")),
]


def find_sensitive_violations(text: str) -> list[str]:
    """Return rule labels for any forbidden pattern matched in text."""
    hits: list[str] = []
    for label, pattern in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            hits.append(label)
    return hits


def is_sensitive_text(text: str) -> bool:
    return bool(find_sensitive_violations(text))


def safe_rel(path: Path, root: Path) -> str:
    """Return a safe relative display path, redacting any path containing sensitive patterns."""
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        rel = path.name
    if is_sensitive_text(rel):
        return "<redacted-path>"
    return rel


def safe_id(val: str) -> str:
    """Return val only if it is a safe bounded identifier and not sensitive, else '<redacted>'."""
    if not SAFE_ID_RE.match(val) or is_sensitive_text(val):
        return "<redacted>"
    return val


def verify_path_contained(path: Path, boundary_root: Path, root_display: Path, errors: list[str]) -> bool:
    """Verify symlinks (and dangling/looped symlinks) BEFORE reading any target. Returns True if safe."""
    rel = safe_rel(path, root_display)
    if path.is_symlink():
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            errors.append(f"{rel}: dangling, looped, or unreadable symlink rejected")
            return False
        try:
            resolved.relative_to(boundary_root.resolve())
        except ValueError:
            errors.append(f"{rel}: symlink target escapes owning package boundary")
            return False
    return True


def is_text_file(path: Path) -> bool:
    """Return True if path appears to be a UTF-8 text file (regardless of extension)."""
    try:
        raw = path.read_bytes()
    except OSError:
        return False
    if b"\x00" in raw[:8192]:
        return False
    try:
        raw.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _decode_double_quoted_yaml(
    val: str, field: str, rel_path: str, line_no: int, errors: list[str]
) -> tuple[bool, str]:
    """Parse a YAML double-quoted scalar, strictly validating escapes and termination."""
    i = 1
    out: list[str] = []
    closed = False
    while i < len(val):
        ch = val[i]
        if ch == "\\":
            if i + 1 >= len(val):
                errors.append(f"{rel_path}:{line_no}: field '{field}' has a trailing incomplete escape")
                return False, ""
            esc = val[i + 1]
            if esc in YAML_SIMPLE_ESCAPES:
                out.append(esc)
                i += 2
            elif esc == "x" and i + 3 < len(val) and re.match(r"^[0-9a-fA-F]{2}$", val[i + 2 : i + 4]):
                out.append(chr(int(val[i + 2 : i + 4], 16)))
                i += 4
            elif esc == "u" and i + 5 < len(val) and re.match(r"^[0-9a-fA-F]{4}$", val[i + 2 : i + 6]):
                out.append(chr(int(val[i + 2 : i + 6], 16)))
                i += 6
            elif esc == "U" and i + 9 < len(val) and re.match(r"^[0-9a-fA-F]{8}$", val[i + 2 : i + 10]):
                out.append(chr(int(val[i + 2 : i + 10], 16)))
                i += 10
            else:
                errors.append(f"{rel_path}:{line_no}: field '{field}' contains an invalid double-quoted YAML escape")
                return False, ""
        elif ch == '"':
            closed = True
            i += 1
            break
        else:
            out.append(ch)
            i += 1
    if not closed:
        errors.append(f"{rel_path}:{line_no}: field '{field}' has an unclosed double-quoted string")
        return False, ""
    trailing = val[i:].strip()
    if trailing and not trailing.startswith("#"):
        errors.append(f"{rel_path}:{line_no}: field '{field}' has invalid trailing characters after closing quote")
        return False, ""
    return True, "".join(out)


def parse_yaml_scalar(
    raw_val: str,
    field: str,
    rel_path: str,
    line_no: int,
    errors: list[str],
    require_string: bool = True,
) -> tuple[bool, str, bool]:
    """Strictly parse a single-line YAML scalar. Returns (ok, value, was_quoted)."""
    val = raw_val.strip()
    if not val:
        errors.append(f"{rel_path}:{line_no}: field '{field}' has empty scalar value")
        return False, "", False

    if val[0] == '"':
        ok, decoded = _decode_double_quoted_yaml(val, field, rel_path, line_no, errors)
        return ok, decoded, True

    if val[0] == "'":
        i = 1
        out: list[str] = []
        closed = False
        while i < len(val):
            ch = val[i]
            if ch == "'":
                if i + 1 < len(val) and val[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                closed = True
                i += 1
                break
            out.append(ch)
            i += 1
        if not closed:
            errors.append(f"{rel_path}:{line_no}: field '{field}' has an unclosed single-quoted string")
            return False, "", True
        trailing = val[i:].strip()
        if trailing and not trailing.startswith("#"):
            errors.append(f"{rel_path}:{line_no}: field '{field}' has invalid trailing characters after closing quote")
            return False, "", True
        return True, "".join(out), True

    # Reject YAML flow collections, anchors, tags, indicators
    if val[0] in {"[", "]", "{", "}", "*", "&", "!", "?", "|", ">", "%", "@", "`", ","}:
        errors.append(f"{rel_path}:{line_no}: field '{field}' uses unsupported or non-scalar YAML syntax")
        return False, "", False

    # Strip inline comment (whitespace followed by #)
    val = re.split(r"[ \t]+#", val, maxsplit=1)[0].rstrip()

    # Reject unquoted colon followed by whitespace (space or tab) or trailing colon
    if re.search(r":[ \t]", val) or val.endswith(":"):
        errors.append(f"{rel_path}:{line_no}: field '{field}' contains unquoted ':' mapping syntax in plain scalar")
        return False, "", False

    if require_string:
        if val.lower() in YAML_NON_STRING_LITERALS or YAML_NUMBER_RE.match(val):
            errors.append(f"{rel_path}:{line_no}: field '{field}' must be a YAML string, not a boolean/null/number literal")
            return False, "", False

    return True, val, False


def split_mapping_line(line: str) -> tuple[str, str] | None:
    """Split a YAML mapping line requiring `key:` followed by space/tab or end-of-line."""
    m = re.match(r"^([a-zA-Z0-9_.-]+):(?:[ \t]+(.*)|[ \t]*)$", line)
    if not m:
        return None
    return m.group(1), (m.group(2) or "")


def parse_strict_frontmatter(
    text: str, rel_path: str, errors: list[str]
) -> dict[str, object] | None:
    """Strictly parse SKILL.md YAML frontmatter supporting string scalars, block scalars, and optional metadata map."""
    if not FRONTMATTER_OPEN_RE.match(text):
        errors.append(f"{rel_path}:1: missing YAML frontmatter opening '---'")
        return None

    lines = text.splitlines()
    end_idx = None
    for idx in range(1, len(lines)):
        if re.match(r"^---[ \t]*$", lines[idx]):
            end_idx = idx
            break
    if end_idx is None:
        errors.append(f"{rel_path}:1: missing YAML frontmatter closing '---'")
        return None

    fm_lines = lines[1:end_idx]
    result: dict[str, object] = {}
    i = 0
    while i < len(fm_lines):
        line = fm_lines[i]
        line_no = i + 2
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if "\t" in line[: len(line) - len(line.lstrip())]:
            errors.append(f"{rel_path}:{line_no}: tab indentation is not allowed in YAML frontmatter")
            return None
        if line[0] == " ":
            errors.append(f"{rel_path}:{line_no}: unexpected indentation in frontmatter")
            return None

        kv = split_mapping_line(line)
        if kv is None:
            errors.append(f"{rel_path}:{line_no}: malformed frontmatter mapping entry (missing space after ':')")
            return None
        key, raw_val = kv
        if key in result:
            errors.append(f"{rel_path}:{line_no}: duplicate frontmatter key '{safe_id(key)}'")
            return None

        val = raw_val.strip()

        # Optional Agent Skills `metadata:` MUST be a string-to-string block mapping
        if key == "metadata":
            if val != "":
                errors.append(f"{rel_path}:{line_no}: frontmatter 'metadata' must be a YAML mapping, not a scalar")
                return None
            meta: dict[str, str] = {}
            i += 1
            meta_indent: int | None = None
            while i < len(fm_lines):
                nxt = fm_lines[i]
                nxt_no = i + 2
                if not nxt.strip() or nxt.lstrip().startswith("#"):
                    i += 1
                    continue
                if "\t" in nxt[: len(nxt) - len(nxt.lstrip())]:
                    errors.append(f"{rel_path}:{nxt_no}: tab indentation is not allowed in metadata")
                    return None
                indent = len(nxt) - len(nxt.lstrip(" "))
                if indent == 0:
                    break
                if meta_indent is None:
                    meta_indent = indent
                elif indent != meta_indent:
                    errors.append(f"{rel_path}:{nxt_no}: inconsistent indentation in metadata map")
                    return None
                mk_kv = split_mapping_line(nxt.strip())
                if mk_kv is None:
                    errors.append(f"{rel_path}:{nxt_no}: malformed metadata entry (missing space after ':')")
                    return None
                mk, mv = mk_kv
                if mk in meta:
                    errors.append(f"{rel_path}:{nxt_no}: duplicate metadata key '{safe_id(mk)}'")
                    return None
                ok, parsed_mv, _ = parse_yaml_scalar(mv, f"metadata.{safe_id(mk)}", rel_path, nxt_no, errors, require_string=True)
                if not ok:
                    return None
                meta[mk] = parsed_mv
                i += 1
            if not meta:
                errors.append(f"{rel_path}:{line_no}: metadata map must contain at least one key-value pair")
                return None
            result[key] = meta
            continue

        # Block scalars (`>`, `>-`, `|`, `|-`)
        if val in {">", ">-", "|", "|-"}:
            block_lines: list[str] = []
            i += 1
            base_indent: int | None = None
            while i < len(fm_lines):
                nxt = fm_lines[i]
                nxt_no = i + 2
                if not nxt.strip():
                    block_lines.append("")
                    i += 1
                    continue
                if "\t" in nxt[: len(nxt) - len(nxt.lstrip())]:
                    errors.append(f"{rel_path}:{nxt_no}: tab indentation is not allowed in YAML block scalar")
                    return None
                indent = len(nxt) - len(nxt.lstrip(" "))
                if indent == 0:
                    break
                if base_indent is None:
                    base_indent = indent
                elif indent < base_indent:
                    errors.append(f"{rel_path}:{nxt_no}: underindented line in block scalar '{safe_id(key)}'")
                    return None
                block_lines.append(nxt[base_indent:].rstrip())
                i += 1
            if base_indent is None or not any(p.strip() for p in block_lines):
                errors.append(f"{rel_path}:{line_no}: frontmatter block scalar '{safe_id(key)}' is empty")
                return None
            result[key] = " ".join(p.strip() for p in block_lines if p.strip()).strip()
            continue

        ok, parsed, _ = parse_yaml_scalar(val, safe_id(key), rel_path, line_no, errors, require_string=True)
        if not ok:
            return None
        result[key] = parsed
        i += 1

    return result


def parse_and_validate_manifest(
    manifest_path: Path, root_display: Path, errors: list[str]
) -> dict[str, dict[str, object]]:
    """Strictly parse and validate the full skills/manifest.yaml schema without external YAML libs."""
    rel = safe_rel(manifest_path, root_display)
    try:
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        errors.append(f"{rel}: unreadable or invalid UTF-8 manifest")
        return {}

    top_keys: dict[str, object] = {}
    entries: dict[str, dict[str, object]] = {}
    section: str | None = None
    prefixes_map: dict[str, str] = {}
    current: dict[str, object] | None = None
    in_surfaces = False
    current_start_line = 1

    def finalize_entry(item: dict[str, object], start_line: int) -> None:
        required = ("name", "prefix", "version", "status", "summary", "path")
        missing = [k for k in required if not item.get(k)]
        if missing:
            errors.append(
                f"{rel}:{start_line}: skill entry missing required fields: {', '.join(missing)}"
            )
            return
        name = str(item["name"])
        if not SKILL_NAME_RE.match(name):
            errors.append(f"{rel}:{start_line}: skill entry has invalid name format")
            return
        if name in entries:
            errors.append(f"{rel}:{start_line}: duplicate skill name '{safe_id(name)}'")
            return
        expected_prefix = name.split("-", 1)[0]
        if item["prefix"] != expected_prefix:
            errors.append(f"{rel}:{start_line}: skill '{safe_id(name)}' prefix does not match name prefix '{expected_prefix}'")
        expected_path = f"skills/{name}"
        if item["path"] != expected_path:
            errors.append(f"{rel}:{start_line}: skill '{safe_id(name)}' path must be '{expected_path}'")
        if "surfaces" in item and (not isinstance(item["surfaces"], list) or len(item["surfaces"]) == 0):
            errors.append(f"{rel}:{start_line}: skill '{safe_id(name)}' surfaces must be a non-empty YAML sequence")
        entries[name] = item

    for idx, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "\t" in line[: len(line) - len(line.lstrip())]:
            errors.append(f"{rel}:{idx}: tab indentation is not allowed in YAML")
            continue

        # Top-level key
        if not line.startswith(" "):
            if current is not None:
                finalize_entry(current, current_start_line)
                current = None
            in_surfaces = False
            section = None
            kv = split_mapping_line(line)
            if kv is None:
                errors.append(f"{rel}:{idx}: malformed top-level YAML line (missing space after ':')")
                continue
            key, raw_val = kv
            val = raw_val.strip()
            if key in top_keys:
                errors.append(f"{rel}:{idx}: duplicate top-level key '{safe_id(key)}'")
                continue

            if key == "skills":
                if val:
                    errors.append(f"{rel}:{idx}: 'skills' must be a YAML sequence, not a scalar")
                    top_keys[key] = None
                else:
                    top_keys[key] = []
                    section = "skills"
            elif key == "prefixes":
                if val:
                    errors.append(f"{rel}:{idx}: 'prefixes' must be a YAML mapping, not a scalar")
                    top_keys[key] = None
                else:
                    top_keys[key] = prefixes_map
                    section = "prefixes"
            elif key == "schema_version":
                ok, parsed, was_quoted = parse_yaml_scalar(val, key, rel, idx, errors, require_string=False)
                if ok:
                    if was_quoted or not re.match(r"^[1-9]\d*$", parsed):
                        errors.append(f"{rel}:{idx}: 'schema_version' must be an unquoted integer")
                        top_keys[key] = None
                    elif int(parsed) != SUPPORTED_MANIFEST_SCHEMA_VERSION:
                        errors.append(
                            f"{rel}:{idx}: unsupported 'schema_version' (only {SUPPORTED_MANIFEST_SCHEMA_VERSION} is supported)"
                        )
                        top_keys[key] = None
                    else:
                        top_keys[key] = int(parsed)
                else:
                    top_keys[key] = None
            else:
                ok, parsed, _ = parse_yaml_scalar(val, safe_id(key), rel, idx, errors, require_string=True)
                top_keys[key] = parsed if ok else None
            continue

        if section == "prefixes":
            if not line.startswith("  ") or line.startswith("   "):
                errors.append(f"{rel}:{idx}: invalid indentation under 'prefixes:'")
                continue
            pk_kv = split_mapping_line(line[2:])
            if pk_kv is None:
                errors.append(f"{rel}:{idx}: malformed entry under 'prefixes:'")
                continue
            pk, pv = pk_kv
            if pk in prefixes_map:
                errors.append(f"{rel}:{idx}: duplicate prefix key '{safe_id(pk)}'")
                continue
            ok, parsed, _ = parse_yaml_scalar(pv, f"prefixes.{safe_id(pk)}", rel, idx, errors, require_string=True)
            if ok:
                prefixes_map[pk] = parsed
            continue

        if section != "skills":
            errors.append(f"{rel}:{idx}: unexpected indented line outside a mapping or sequence")
            continue

        # Sequence item start under skills:
        if line.startswith("  - "):
            if current is not None:
                finalize_entry(current, current_start_line)
            in_surfaces = False
            current_start_line = idx
            item_kv = split_mapping_line(line[4:])
            if item_kv is None:
                errors.append(f"{rel}:{idx}: malformed skill list item (missing space after ':')")
                current = {}
                continue
            k, raw_v = item_kv
            ok, parsed, _ = parse_yaml_scalar(raw_v, f"skills[].{safe_id(k)}", rel, idx, errors, require_string=True)
            current = {k: parsed} if ok else {}
            continue

        if current is None:
            errors.append(f"{rel}:{idx}: unexpected content under 'skills:' before first list item")
            continue

        if in_surfaces and line.startswith("      - "):
            ok, parsed, _ = parse_yaml_scalar(line[8:], "skills[].surfaces[]", rel, idx, errors, require_string=True)
            if ok:
                cast_list = current.setdefault("surfaces", [])
                if isinstance(cast_list, list):
                    cast_list.append(parsed)
            continue

        if line.startswith("    ") and not line.startswith("     "):
            field_kv = split_mapping_line(line[4:])
            if field_kv is None:
                errors.append(f"{rel}:{idx}: malformed field in manifest skill entry (missing space after ':')")
                continue
            k, raw_v = field_kv
            if k in current:
                errors.append(f"{rel}:{idx}: duplicate field '{safe_id(k)}' in skill entry")
                continue
            if k == "surfaces":
                if raw_v.strip():
                    errors.append(f"{rel}:{idx}: field 'surfaces' must be a YAML sequence, not a scalar")
                    in_surfaces = False
                else:
                    current["surfaces"] = []
                    in_surfaces = True
                continue
            in_surfaces = False
            ok, parsed, _ = parse_yaml_scalar(raw_v, f"skills[].{safe_id(k)}", rel, idx, errors, require_string=True)
            if ok:
                current[k] = parsed
            continue

        errors.append(f"{rel}:{idx}: unexpected line in manifest skill entry")

    if current is not None:
        finalize_entry(current, current_start_line)

    if "schema_version" not in top_keys:
        errors.append(f"{rel}: missing required top-level 'schema_version'")
    if "skills" not in top_keys:
        errors.append(f"{rel}: missing required top-level 'skills:' sequence")

    return entries


def _extract_md_destination(raw: str) -> str:
    """Extract destination from inline or reference Markdown syntax, stripping <...> and optional title."""
    s = raw.strip()
    if not s:
        return ""
    if s.startswith("<"):
        end = s.find(">")
        if end != -1:
            return s[1:end].strip()
    # Destination ends at first whitespace (which introduces an optional title)
    return s.split()[0]


def check_relative_links(md_file: Path, boundary_root: Path, root_display: Path, errors: list[str]) -> None:
    rel = safe_rel(md_file, root_display)
    try:
        text = md_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"{rel}: invalid UTF-8 encoding in Markdown file")
        return
    except OSError:
        errors.append(f"{rel}: unreadable Markdown file")
        return

    cleaned = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    boundary_resolved = boundary_root.resolve()

    destinations: list[tuple[int, str]] = []
    for match in MD_INLINE_LINK_RE.finditer(cleaned):
        line_no = cleaned.count("\n", 0, match.start()) + 1
        destinations.append((line_no, _extract_md_destination(match.group(1))))
    for match in MD_REF_DEF_RE.finditer(cleaned):
        line_no = cleaned.count("\n", 0, match.start()) + 1
        destinations.append((line_no, _extract_md_destination(match.group(2))))

    for line_no, target in destinations:
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        target_path = target.split("#", 1)[0].split("?", 1)[0]
        if not target_path:
            continue
        raw_target = md_file.parent / target_path
        try:
            resolved = raw_target.resolve(strict=True)
        except OSError:
            non_strict = raw_target.resolve()
            try:
                non_strict.relative_to(boundary_resolved)
            except ValueError:
                errors.append(f"{rel}:{line_no}: relative link escapes owning package boundary")
            else:
                errors.append(f"{rel}:{line_no}: broken relative link")
            continue
        try:
            resolved.relative_to(boundary_resolved)
        except ValueError:
            errors.append(f"{rel}:{line_no}: relative link escapes owning package boundary")


def _is_safe_bearer_token(tok: str) -> bool:
    clean = tok.strip()
    if not clean:
        return True
    if clean in SAFE_BEARER_PLACEHOLDERS:
        return True
    if clean.startswith(("<", "$", "{")):
        return True
    return False


def _is_safe_bearer_rest(rest: str, quote: str | None) -> bool:
    """Return True if the remainder after 'Bearer ' is a safe placeholder or variable-backed code expression."""
    if not rest or not rest.strip():
        return True

    if quote:
        if rest.startswith(quote):
            after = rest[1:].lstrip()
            # Concatenation in Lua (`..`) or JS/Python (`+`)
            for op in ("..", "+"):
                if after.startswith(op):
                    rhs = after[len(op) :].lstrip()
                    if not rhs:
                        return False
                    # Concatenating a quoted literal is ONLY safe if that literal is an explicit placeholder
                    if rhs[0] in {'"', "'"}:
                        q2 = rhs[0]
                        end2 = rhs.find(q2, 1)
                        lit = rhs[1:end2] if end2 != -1 else rhs[1:]
                        return _is_safe_bearer_token(lit)
                    # Variable or function call expression (e.g., `token`, `ctx.secret("k")`)
                    return bool(SAFE_CODE_EXPR_RE.match(rhs))
            return True
        end_q = rest.find(quote)
        inner = rest[:end_q] if end_q != -1 else rest
        return _is_safe_bearer_token(inner)

    parts = rest.split()
    if not parts:
        return True
    inner = parts[0].rstrip("\"'`,;)}]")
    return _is_safe_bearer_token(inner)


def _scan_decoded_json_bearer(obj: object, rel: str, errors: list[str]) -> None:
    """Recursively scan decoded JSON objects so Unicode-escaped Authorization/Bearer values are caught."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() == "authorization" and isinstance(v, str):
                m = re.match(r"(?i)^Bearer[ \t]+(.*)$", v.strip())
                if m and not _is_safe_bearer_token(m.group(1)):
                    errors.append(f"{rel}: public-safety violation (hardcoded Bearer credential in JSON)")
            else:
                _scan_decoded_json_bearer(v, rel, errors)
    elif isinstance(obj, list):
        for item in obj:
            _scan_decoded_json_bearer(item, rel, errors)


def scan_public_safety(file_path: Path, root_display: Path, errors: list[str]) -> None:
    if not is_text_file(file_path):
        return
    rel = safe_rel(file_path, root_display)
    text = file_path.read_text(encoding="utf-8", errors="replace")

    for label, pattern in FORBIDDEN_PATTERNS:
        for m in pattern.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            errors.append(f"{rel}:{line_no}: public-safety violation ({label})")

    for m in BEARER_HEADER_RE.finditer(text):
        rest = m.group("rest")
        quote = m.group("quote")
        if _is_safe_bearer_rest(rest, quote):
            continue
        line_no = text.count("\n", 0, m.start()) + 1
        errors.append(f"{rel}:{line_no}: public-safety violation (hardcoded Bearer credential)")

    # Decode JSON files (or JSON-like content) to catch Unicode-escaped Bearer credentials.
    stripped = text.lstrip()
    if file_path.suffix.lower() == ".json" or stripped.startswith(("{", "[")):
        try:
            decoded = json.loads(text)
        except ValueError:
            decoded = None
        if decoded is not None:
            _scan_decoded_json_bearer(decoded, rel, errors)


def validate_skills_root(skills_dir: Path, manifest_path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    # Reject symlinked library root BEFORE walking or opening anything.
    if skills_dir.is_symlink():
        errors.append("skills root must not be a symlink")
        return errors, warnings
    if not skills_dir.is_dir():
        errors.append("skills directory not found")
        return errors, warnings

    # Check manifest containment BEFORE reading it.
    manifest_entries: dict[str, dict[str, object]] = {}
    if not manifest_path.exists() and not manifest_path.is_symlink():
        errors.append("manifest.yaml not found")
    elif verify_path_contained(manifest_path, skills_dir, skills_dir, errors):
        manifest_entries = parse_and_validate_manifest(manifest_path, skills_dir, errors)

    # Check library README containment BEFORE reading it.
    readme = skills_dir / "README.md"
    if not readme.exists() and not readme.is_symlink():
        errors.append("missing library README.md")
    elif verify_path_contained(readme, skills_dir, skills_dir, errors):
        check_relative_links(readme, skills_dir, skills_dir, errors)

    # Recursively check symlink containment AND sensitive filenames BEFORE reading/scanning.
    unsafe_paths: set[Path] = set()
    for item in sorted(skills_dir.rglob("*")):
        raw_rel = str(item.relative_to(skills_dir))
        for label in find_sensitive_violations(raw_rel):
            errors.append(f"<redacted-path>: public-safety violation in filename ({label})")
        if not verify_path_contained(item, skills_dir, skills_dir, errors):
            unsafe_paths.add(item)
            continue
        if item.is_file():
            scan_public_safety(item, skills_dir, errors)

    discovered_skills: set[str] = set()
    for entry in sorted(skills_dir.iterdir()):
        if entry in unsafe_paths:
            continue
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            errors.append(f"{safe_rel(entry, skills_dir)}: hidden directories are not allowed directly under skills/")
            continue
        discovered_skills.add(entry.name)

        if not SKILL_NAME_RE.match(entry.name):
            errors.append(
                f"{safe_id(entry.name)}: invalid skill directory name "
                "(must start with 'sre-' or 'sn-' and use lowercase kebab-case)"
            )
        elif len(entry.name) > MAX_NAME_LEN:
            errors.append(f"{safe_id(entry.name)}: skill name exceeds {MAX_NAME_LEN} characters")

        skill_md = entry / "SKILL.md"
        if not skill_md.exists() and not skill_md.is_symlink():
            errors.append(f"{safe_id(entry.name)}: missing required SKILL.md")
        elif verify_path_contained(skill_md, entry, skills_dir, errors):
            rel_skill = safe_rel(skill_md, skills_dir)
            try:
                content = skill_md.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                errors.append(f"{rel_skill}: invalid UTF-8 encoding in SKILL.md")
            except OSError:
                errors.append(f"{rel_skill}: unreadable SKILL.md")
            else:
                line_count = len(content.splitlines())
                if line_count > MAX_SKILL_MD_LINES:
                    warnings.append(
                        f"{rel_skill}: {line_count} lines exceeds progressive-disclosure target ({MAX_SKILL_MD_LINES})"
                    )
                fm = parse_strict_frontmatter(content, rel_skill, errors)
                if fm is not None:
                    fm_name = fm.get("name")
                    fm_desc = fm.get("description")
                    if not isinstance(fm_name, str) or fm_name != entry.name:
                        errors.append(f"{rel_skill}: frontmatter 'name' does not match skill directory")
                    elif len(fm_name) > MAX_NAME_LEN:
                        errors.append(f"{rel_skill}: frontmatter 'name' exceeds {MAX_NAME_LEN} characters")
                    if not isinstance(fm_desc, str) or len(fm_desc) < 20:
                        errors.append(f"{rel_skill}: frontmatter 'description' is missing or too short")
                    elif len(fm_desc) > MAX_DESC_LEN:
                        errors.append(f"{rel_skill}: frontmatter 'description' exceeds {MAX_DESC_LEN} characters")

        for file_path in sorted(entry.rglob("*")):
            if file_path in unsafe_paths:
                continue
            if not verify_path_contained(file_path, entry, skills_dir, errors):
                continue
            if file_path.is_file() and file_path.suffix.lower() == ".md":
                check_relative_links(file_path, entry, skills_dir, errors)

    manifest_names = set(manifest_entries.keys())
    for missing_in_manifest in sorted(discovered_skills - manifest_names):
        errors.append(f"skill '{safe_id(missing_in_manifest)}' exists in skills/ but is missing from manifest.yaml")
    for missing_on_disk in sorted(manifest_names - discovered_skills):
        errors.append(f"skill '{safe_id(missing_on_disk)}' listed in manifest.yaml does not exist in skills/")

    return errors, warnings


def _make_valid_fixture(root: Path) -> tuple[Path, Path]:
    skills = root / "skills"
    skills.mkdir()
    (skills / "README.md").write_text("# Library\nSee [sn-ok](./sn-ok/SKILL.md).\n", encoding="utf-8")
    manifest = skills / "manifest.yaml"
    manifest.write_text(
        "schema_version: 1\n"
        "library: sentinel-skills\n"
        "prefixes:\n"
        "  sn: \"Sentinel platform\"\n"
        "skills:\n"
        "  - name: sn-ok\n"
        "    prefix: sn\n"
        "    version: \"1.0.0\"\n"
        "    status: stable\n"
        "    summary: \"Valid test skill.\"\n"
        "    surfaces:\n"
        "      - mcp\n"
        "    path: skills/sn-ok\n",
        encoding="utf-8",
    )
    ok_dir = skills / "sn-ok"
    ok_dir.mkdir()
    (ok_dir / "ref.md").write_text("# Ref\n", encoding="utf-8")
    (ok_dir / "SKILL.md").write_text(
        "---\n"
        "name: sn-ok\n"
        "description: >-\n"
        "  Valid skill description using safe placeholders YOUR_API_TOKEN and $TOKEN.\n"
        "metadata:\n"
        "  author: sentinel\n"
        "  version: \"1.0\"\n"
        "---\n\n"
        "# Valid Skill\n"
        "Plain: `Authorization: Bearer YOUR_API_TOKEN` and `Authorization: Bearer $TOKEN`.\n"
        "JSON: `{\"Authorization\": \"Bearer YOUR_API_TOKEN\"}`.\n"
        "Lua: `[\"Authorization\"] = \"Bearer \" .. token`.\n"
        "Empty Bearer: `Authorization: Bearer   `\n"
        "Titled link: [ref](<./ref.md> \"Reference Title\")\n"
        "Example CIDR: `198.51.100.0/24` and `https://api.example.com`.\n",
        encoding="utf-8",
    )
    return skills, manifest


def run_self_test() -> int:
    """Run isolated positive and negative validator fixtures with exact assertions."""
    failures: list[str] = []

    def assert_case(
        name: str,
        setup_fn,
        expect_pass: bool,
        must_match: list[str] | None = None,
        must_not_match: list[str] | None = None,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills, manifest = _make_valid_fixture(root)
            setup_fn(root, skills, manifest)
            errors, _ = validate_skills_root(skills, manifest)
            joined = "\n".join(errors)
            if expect_pass and errors:
                failures.append(f"[{name}] expected PASS, got errors:\n{joined}")
            if not expect_pass and not errors:
                failures.append(f"[{name}] expected FAIL, got PASS")
            for sub in must_match or []:
                if sub not in joined:
                    failures.append(f"[{name}] expected error containing '{sub}', got:\n{joined}")
            for sub in must_not_match or []:
                if sub in joined:
                    failures.append(f"[{name}] diagnostic leaked forbidden text '{sub}':\n{joined}")

    # 1. Valid positive fixture (titled angle link, empty Bearer, metadata map, safe JSON/Lua Bearer)
    assert_case("valid-positive", lambda r, s, m: None, expect_pass=True)

    # 2. Missing frontmatter
    assert_case(
        "missing-frontmatter",
        lambda r, s, m: (s / "sn-ok" / "SKILL.md").write_text("# No FM\n", encoding="utf-8"),
        expect_pass=False,
        must_match=["missing YAML frontmatter"],
    )

    # 3-7. Strict YAML frontmatter grammar cases
    assert_case(
        "fm-invalid-escape",
        lambda r, s, m: (s / "sn-ok" / "SKILL.md").write_text(
            '---\nname: sn-ok\ndescription: "bad \\q escape in double quotes"\n---\n# X\n', encoding="utf-8"
        ),
        expect_pass=False,
        must_match=["invalid double-quoted YAML escape"],
    )
    assert_case(
        "fm-missing-space-after-colon",
        lambda r, s, m: (s / "sn-ok" / "SKILL.md").write_text(
            "---\nname:sn-ok\ndescription: Valid long enough description text here.\n---\n# X\n", encoding="utf-8"
        ),
        expect_pass=False,
        must_match=["missing space after ':'"],
    )
    assert_case(
        "fm-colon-tab-plain-scalar",
        lambda r, s, m: (s / "sn-ok" / "SKILL.md").write_text(
            "---\nname: sn-ok\ndescription: bad:\ttab mapping in plain scalar\n---\n# X\n", encoding="utf-8"
        ),
        expect_pass=False,
        must_match=["unquoted ':'"],
    )
    assert_case(
        "fm-scalar-metadata",
        lambda r, s, m: (s / "sn-ok" / "SKILL.md").write_text(
            "---\nname: sn-ok\ndescription: Valid long enough description text here.\nmetadata: scalar\n---\n# X\n",
            encoding="utf-8",
        ),
        expect_pass=False,
        must_match=["'metadata' must be a YAML mapping"],
    )
    assert_case(
        "fm-hex-metadata-value",
        lambda r, s, m: (s / "sn-ok" / "SKILL.md").write_text(
            "---\nname: sn-ok\ndescription: Valid long enough description text here.\nmetadata:\n  code: 0x10\n---\n# X\n",
            encoding="utf-8",
        ),
        expect_pass=False,
        must_match=["must be a YAML string"],
    )

    # 8-9. Manifest schema_version quoted & unsupported integer
    assert_case(
        "manifest-quoted-schema-version",
        lambda r, s, m: m.write_text(
            m.read_text(encoding="utf-8").replace("schema_version: 1", 'schema_version: "1"'), encoding="utf-8"
        ),
        expect_pass=False,
        must_match=["must be an unquoted integer"],
    )
    assert_case(
        "manifest-unsupported-schema-version",
        lambda r, s, m: m.write_text(
            m.read_text(encoding="utf-8").replace("schema_version: 1", "schema_version: 999"), encoding="utf-8"
        ),
        expect_pass=False,
        must_match=["unsupported 'schema_version'"],
    )

    # 10-11. Structured Bearer: Unicode-escaped JSON & Lua literal concat
    synth_bearer = "live_tok_9876543210abcdef"
    assert_case(
        "json-unicode-escaped-bearer",
        lambda r, s, m: (s / "sn-ok" / "hdr.json").write_text(
            f'{{"Authorization": "\\u0042earer {synth_bearer}"}}\n', encoding="utf-8"
        ),
        expect_pass=False,
        must_match=["hardcoded Bearer credential in JSON"],
        must_not_match=[synth_bearer],
    )
    assert_case(
        "lua-literal-concat-bearer",
        lambda r, s, m: (s / "sn-ok" / "flow.lua").write_text(
            f'headers = {{ ["Authorization"] = "Bearer " .. "{synth_bearer}" }}\n', encoding="utf-8"
        ),
        expect_pass=False,
        must_match=["hardcoded Bearer credential"],
        must_not_match=[synth_bearer],
    )

    # 12-14. Credential in valid filename, invalid-UTF8 filename, and catalog identifier — NEVER echoed!
    synth_key = "sk-proj-syntheticSECRET9988776655"
    assert_case(
        "credential-in-valid-filename",
        lambda r, s, m: (s / "sn-ok" / f"{synth_key}.md").write_text("# Note\n", encoding="utf-8"),
        expect_pass=False,
        must_match=["public-safety violation in filename"],
        must_not_match=[synth_key],
    )
    assert_case(
        "credential-in-bad-utf8-filename",
        lambda r, s, m: (s / "sn-ok" / f"{synth_key}.md").write_bytes(b"\xff\xfe\xfd"),
        expect_pass=False,
        must_match=["public-safety violation in filename", "invalid UTF-8 encoding"],
        must_not_match=[synth_key],
    )
    assert_case(
        "credential-in-catalog-id",
        lambda r, s, m: m.write_text(
            m.read_text(encoding="utf-8")
            + f"  - name: {synth_key}\n    prefix: sn\n    version: \"1.0.0\"\n    status: stable\n    summary: \"x\"\n    path: skills/x\n",
            encoding="utf-8",
        ),
        expect_pass=False,
        must_match=["invalid name format"],
        must_not_match=[synth_key],
    )

    # 15. Reference-style Markdown link to missing target
    assert_case(
        "md-missing-reference-def",
        lambda r, s, m: (s / "sn-ok" / "SKILL.md").write_text(
            (s / "sn-ok" / "SKILL.md").read_text(encoding="utf-8") + "\n[missing]: ./nope.md \"Title\"\n",
            encoding="utf-8",
        ),
        expect_pass=False,
        must_match=["broken relative link"],
    )

    # 16. Symlinked skills/ root rejected before reading
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ext = root / "external_skills"
        ext.mkdir()
        (ext / "README.md").write_text("# Ext\n", encoding="utf-8")
        (ext / "manifest.yaml").write_text("schema_version: 1\nskills: []\n", encoding="utf-8")
        link_skills = root / "skills"
        os.symlink(ext, link_skills)
        errs, _ = validate_skills_root(link_skills, link_skills / "manifest.yaml")
        if not any("must not be a symlink" in e for e in errs):
            failures.append(f"[symlinked-skills-root] expected symlink root error, got: {errs}")

    if failures:
        for f in failures:
            print(f"SELF-TEST FAILED: {f}", file=sys.stderr)
        return 1
    print("validate_skills.py self-test passed (16/16 isolated fixtures).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate public Sentinel Agent Skills.")
    parser.add_argument("--self-test", action="store_true", help="Run built-in isolated self-tests.")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    errors, warnings = validate_skills_root(SKILLS_DIR, MANIFEST_PATH)
    for w in warnings:
        print(f"WARN: {w}")
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print(f"\nValidation failed with {len(errors)} error(s).", file=sys.stderr)
        return 1

    manifest_entries = parse_and_validate_manifest(MANIFEST_PATH, SKILLS_DIR, [])
    print(f"OK: validated {len(manifest_entries)} skill(s) in {SKILLS_DIR} with 0 errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
