#!/usr/bin/env python3
"""Download theme screenshots + HTML from the Stitch results."""
import json, os, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "themes")
os.makedirs(OUT, exist_ok=True)

d = json.load(open(os.path.join(BASE, "prompts", "_results.json")))
theme_of = {
    "theme-01-default-light.md": "01-default-light",
    "theme-02-terminal-dark.md": "02-terminal-dark",
    "theme-03-blueprint.md": "03-blueprint",
    "theme-04-paper-ink.md": "04-paper-ink",
    "theme-05-high-contrast.md": "05-high-contrast",
}
for k, v in d.items():
    name = theme_of.get(k, k)
    try:
        r = json.loads(v)
        screens = r["outputComponents"][0]["design"]["screens"]
        for i, s in enumerate(screens):
            url = s.get("screenshot", {}).get("downloadUrl")
            html = s.get("htmlCode", {}).get("downloadUrl")
            if url:
                req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
                data = urllib.request.urlopen(req, timeout=60).read()
                path = os.path.join(OUT, f"{name}-{i}.png")
                open(path, "wb").write(data)
                print("saved", path, len(data), "bytes")
            if html:
                req = urllib.request.Request(html, headers={"User-Agent": "curl/8"})
                h = urllib.request.urlopen(req, timeout=60).read()
                hp = os.path.join(OUT, f"{name}-{i}.html")
                open(hp, "wb").write(h)
                print("saved", hp, len(h), "bytes")
    except Exception as e:
        print(name, "ERROR", e)
