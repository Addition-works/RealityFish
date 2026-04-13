#!/usr/bin/env python3
import urllib.request
import json
import time
import sys

report_id = sys.argv[1] if len(sys.argv) > 1 else "report_7b8ef3d1f6fa"
url = f"http://localhost:5001/api/report/{report_id}/progress"

while True:
    try:
        req = urllib.request.Request(url, headers={"Accept-Language": "en"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read()).get("data", {})
        
        status = d.get("status", "unknown")
        pct = d.get("progress", 0)
        current = d.get("current_section", "?")
        total = d.get("total_sections", "?")
        
        print(f'{time.strftime("%H:%M:%S")} Report: {pct}% | section {current}/{total} | status: {status}', flush=True)
        
        if status in ("completed", "failed", "error"):
            print(f"\nFinal: {status}")
            print(json.dumps(d, indent=2))
            break
    except Exception as e:
        print(f'{time.strftime("%H:%M:%S")} Error: {e}', flush=True)
    time.sleep(30)

print("REPORT_DONE", flush=True)
