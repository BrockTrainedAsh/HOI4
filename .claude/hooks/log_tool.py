#!/usr/bin/env python3
"""PostToolUse hook: append a one-line audit record per tool call."""
import sys, json, datetime, pathlib
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
proj = d.get("cwd") or "."
logdir = pathlib.Path(proj) / "logs"
logdir.mkdir(exist_ok=True)
tool = d.get("tool_name", "?")
ti = d.get("tool_input", {}) or {}
detail = ti.get("command") or ti.get("file_path") or ti.get("description") or ""
ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
with open(logdir / "claude-tools.log", "a", encoding="utf-8") as f:
    f.write(f"[{ts}] {tool} {str(detail)[:160]}\n")
