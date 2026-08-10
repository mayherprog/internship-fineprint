#!/usr/bin/env python3
"""Write the normalized program payload — the same rows build.py embeds in
index.html — to a JSON file for the TypeScript front end.

This is also where the front end's own sector labels are checked. The app
cannot read schema/program.schema.json at runtime, so it keeps a hand-written
SECTOR_LABEL of its own; this step runs immediately before `npm run build` in
CI and fails if that map has drifted from the schema or from build.py. A
sector the app has no label for would render as a raw slug in the browser
while TABLE.md rendered it correctly — the same split-brain bug the schema is
now the single source of truth to prevent.

Usage: python3 tools/export_json.py [out_path]   (default web/public/data.json)
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build  # noqa: E402
import sectors  # noqa: E402

# Python side first, so a sector missing from both maps blames the file it was
# forgotten in rather than the front end that merely mirrors it.
build.check_sector_labels()
sectors.assert_web_labels_match(build.SECTOR_LABEL)

out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "web/public/data.json")
out.parent.mkdir(parents=True, exist_ok=True)
rows = build.load(pathlib.Path(__file__).resolve().parents[1] / "data")
out.write_text(json.dumps(rows, ensure_ascii=False))
print(f"{out}: {len(rows)} programs")
