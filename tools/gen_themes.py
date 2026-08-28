#!/usr/bin/env python3
"""Generate the 5 theme exploration screens in one Stitch session (sequential)."""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stitch_call import run_session, extract_text

PROJECT = "17232618181320525280"
DS = "assets/8406364142690308777"
PROMPTS = sorted(f for f in os.listdir(os.path.join(os.path.dirname(__file__), "prompts"))
                 if f.startswith("theme-"))
THEME_NAMES = {
    "theme-01-default-light.md": "Default Light",
    "theme-02-terminal-dark.md": "Terminal Dark",
    "theme-03-blueprint.md": "Blueprint",
    "theme-04-paper-ink.md": "Paper & Ink",
    "theme-05-high-contrast.md": "High Contrast Slate",
}

calls = []
for f in PROMPTS:
    text = open(os.path.join(os.path.dirname(__file__), "prompts", f)).read()
    name = THEME_NAMES.get(f, f)
    prompt = f"{text}\n\nShow the theme selector dropdown in the navbar open or labeled with the theme name: {name}."
    calls.append(("tools/call", {"name": "generate_screen_from_text", "arguments": {
        "projectId": PROJECT,
        "prompt": prompt,
        "deviceType": "DESKTOP",
        "designSystem": DS,
        "modelId": "GEMINI_3_FLASH",
    }}))

out, p = run_session(calls, timeout=1800)
results = {}
for i, f in enumerate(PROMPTS, start=2):
    r = out.get(i)
    print(f"\n===== {f}")
    if not r:
        print("NO RESPONSE")
        continue
    if r.get("result"):
        body = extract_text(r["result"])
        results[f] = body
        print(body[:1200])
    else:
        print("ERROR:", json.dumps(r)[:600])

with open(os.path.join(os.path.dirname(__file__), "prompts", "_results.json"), "w") as fh:
    json.dump(results, fh, indent=1)
print("\nsaved _results.json")
