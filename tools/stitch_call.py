#!/usr/bin/env python3
"""Stitch MCP driver: handshake + tool calls over stdio proxy.

Usage:
  stitch_call.py list-tools
  stitch_call.py call <tool-name> '<json-args>'
  stitch_call.py batch '<json: [[tool, args], ...]>'   # sequential, one session
"""
import json, os, subprocess, sys, time

def load_token():
    if os.environ.get("STITCH_API_KEY"):
        return
    for line in open(os.path.expanduser("~/.bashrc")):
        if line.startswith("export OP_SERVICE_ACCOUNT_TOKEN="):
            k, v = line.strip().removeprefix("export ").split("=", 1)
            os.environ[k] = v.strip('"')
            break
    r = subprocess.run(
        ["op", "read", "op://Agents Vault/NDX Stitch MCP/credential",
         "--account", "ndx-au.1password.eu"],
        capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        raise SystemExit(f"op read failed: {r.stderr[:200]}")
    os.environ["STITCH_API_KEY"] = r.stdout.strip()

def run_session(calls, timeout=600):
    """calls: list of (method, params, id) or notifications."""
    load_token()
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "hermes", "version": "1.0"}}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
    ]
    next_id = 2
    ids = []
    for method, params in calls:
        if method.startswith("notifications/"):
            lines.append(json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}}))
        else:
            lines.append(json.dumps({"jsonrpc": "2.0", "id": next_id, "method": method, "params": params or {}}))
            ids.append(next_id)
            next_id += 1
    p = subprocess.run(
        ["npx", "--yes", "@_davideast/stitch-mcp@latest", "proxy", "--debug"],
        input="\n".join(lines) + "\n", capture_output=True, text=True,
        timeout=timeout, env=os.environ.copy())
    out = {}
    for line in (p.stdout or "").splitlines():
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(m.get("id"), int) and m["id"] >= 2:
            out[m["id"]] = m
    return out, p

def extract_text(result):
    """Pull text blocks out of an MCP tool result."""
    texts = []
    for c in result.get("content", []):
        if c.get("type") == "text":
            texts.append(c["text"])
    return "\n".join(texts)

def main():
    mode = sys.argv[1]
    if mode == "list-tools":
        out, p = run_session([("tools/list", {})])
        r = out.get(2)
        if not r:
            print("NO RESP", p.stdout[-800:], p.stderr[-500:]); return
        for t in r["result"]["tools"]:
            print(f"== {t['name']}\n{t.get('description','')[:200]}\n")
    elif mode == "call":
        name, args = sys.argv[2], json.loads(sys.argv[3])
        out, p = run_session([("tools/call", {"name": name, "arguments": args})])
        r = out.get(2)
        if not r:
            print("NO RESP", p.stdout[-800:], p.stderr[-500:]); return
        if r.get("result"):
            print(extract_text(r["result"]))
        else:
            print(json.dumps(r, indent=1))
    elif mode == "batch":
        pairs = json.loads(sys.argv[2])
        calls = [("tools/call", {"name": n, "arguments": a}) for n, a in pairs]
        out, p = run_session(calls, timeout=1800)
        for i, (n, _) in enumerate(pairs, start=2):
            r = out.get(i)
            print(f"\n########## CALL {i-1}: {n}")
            if not r:
                print("NO RESP"); continue
            if r.get("result"):
                print(extract_text(r["result"])[:3000])
            else:
                print(json.dumps(r)[:800])

if __name__ == "__main__":
    main()
