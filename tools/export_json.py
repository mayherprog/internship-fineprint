#!/usr/bin/env python3
"""Write the normalized program payload — the same rows build.py embeds in
index.html — to a JSON file for the TypeScript front end.

Usage: python3 tools/export_json.py [out_path]   (default web/public/data.json)
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build  # noqa: E402

out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "web/public/data.json")
out.parent.mkdir(parents=True, exist_ok=True)
rows = build.load(pathlib.Path(__file__).resolve().parents[1] / "data")
out.write_text(json.dumps(rows, ensure_ascii=False))
print(f"{out}: {len(rows)} programs")
