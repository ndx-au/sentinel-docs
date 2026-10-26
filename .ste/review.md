<!-- ndx-ste-mode: description -->

# NDX STE update record

This rewrite covers 28 public documentation pages and the repository README.
The filename map retains its existing content.
The NotebookLM index and bundle contain the revised pages.

The rewrite simplifies explanations, procedures, descriptions, and terminology.
Code blocks, inline identifiers, link destinations, and metadata structure retain their original values.
One revised heading retains an explicit anchor for its earlier wording.
Existing security material retains its draft status, assurance limits, and uncertainty about older encrypted databases.

## Validation

The bundle command completed with 28 concepts:

```bash
python3 tools/bundle_docs.py
```

Content comparisons passed for code examples, identifiers, links, metadata, and the filename map.
The sentence audit found no prose sentence above 25 words.
It examined paragraphs, list items, and table cells separately.
It counted each protected code span as one token.
The three longest prose sentences each contain 25 words under that method.
`git diff --check` passed.

## Automated lint

The same 30 source files produced 3,666 findings before the rewrite and 2,612 findings afterward.
The rate changed from 7.19 to 5.38 findings per 100 words.
The linter still exits with status 1.

| Rule | Remaining findings |
|---|---:|
| NOUNSTACK | 2024 |
| GLOSSARY | 480 |
| LENGTH | 106 |
| MODAL | 1 |
| LATIN | 1 |

The command was:

```bash
node <skill-directory>/scripts/lint.mjs README.md sn.docs/ct
```

The results need context:

- The parser includes YAML frontmatter and link destinations in its prose analysis.
- Adjacent list fragments can form one apparent sentence.
- The noun heuristic also flags verbs and technical names.
- Glossary matching ignores the domain and part of speech.
- The remaining modal appears in a quoted Docker message.
- The remaining Latin abbreviation appears in a quoted Garage placeholder.
- Reported locations can shift after fenced code blocks.

The rewrite retains these quoted UI strings.
The results do not establish a clean lint pass.
The candidates below need a decision from the glossary owner.
The approved glossary and project overlay remain outside this change.

## glossary candidates

| term | pos | meaning | do_not_write | surfaces | reason |
|---|---|---|---|---|---|
| Sentinel | noun | NDX product that runs automation from an SRE | — | sentinel-docs | No house row |
| harness | noun | Compiled Sentinel runtime that administers one SRE | — | sentinel-docs | No house row |
| SRE | noun | Sentinel Runtime Environment directory with kits and shared configuration | — | sentinel-docs | No house row |
| kit | noun | Directory with a manifest and related Sentinel components | — | sentinel-docs | No house row |
| flow | noun | Lua script that Sentinel discovers and executes | — | sentinel-docs | No house row |
| skill twin | noun | Markdown file that describes its paired code file | skill (for this file) | sentinel-docs | The house skill row describes an agent skill folder |
| content plane | noun | Content subsystem such as fcms, ccms, or wpcms | CMS (without its plane name) | sentinel-docs | No house row |
| storage point | noun | Registered S3-compatible bucket and its metadata | — | sentinel-docs | No house row |
| occupy | verb | Request or renew the lease for an active harness instance | — | sentinel-docs | No house row |
| project | noun | Sentinel automation workspace | composition (for an SRE) | sentinel-docs | The house composition row describes Remotion |
| render | verb | Produce HTML from content and a template | — | sentinel-docs | The house render row describes video production |
| format | noun | Representation of data such as JSON, text, or an archive | codec (for this meaning) | sentinel-docs | The house codec row describes media encoding |
| export | verb | Write stored records to a transferable file | render (for this meaning) | sentinel-docs | Data export differs from video production |
| specification | noun | Technical contract for behavior, interfaces, or file structures | plan (for this contract) | sentinel-docs | The house plan row describes an implementation plan |
| proxy | noun | Component that forwards requests to another service | Caddy (for every proxy) | sentinel-docs | The dashboard and signing proxy also forward requests |

Owner: Librarian <librarian@ndx.au>
