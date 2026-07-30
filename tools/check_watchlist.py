#!/usr/bin/env python3
"""Print watchlist rows whose re-research window covers the current month.

Exit 0 always — being due is work to schedule, not an error. The freshness
workflow folds this output into its issue report.

Usage: python3 tools/check_watchlist.py [YYYY-MM]   (month override for tests)
"""
import datetime
import json
import pathlib
import sys

here = pathlib.Path(__file__).resolve().parent
watch = json.loads((here / "watchlist.json").read_text())["watch"]
now = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().strftime("%Y-%m")

due = [w for w in watch if w["due_from"] <= now <= w["due_to"]]
if not due:
    print(f"watchlist: nothing due in {now} ({len(watch)} rows watched)")
else:
    print(f"watchlist: {len(due)} of {len(watch)} rows due for re-research in {now}\n")
    for w in due:
        print(f"  {w['firm']} — {w['program']}\n    {w['why']}")
