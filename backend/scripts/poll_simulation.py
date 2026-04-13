#!/usr/bin/env python3
import urllib.request
import json
import time
import sys
import subprocess

sim_id = sys.argv[1] if len(sys.argv) > 1 else "sim_c83772b4f6fe"
url = f"http://localhost:5001/api/simulation/{sim_id}/run-status"
mem_log = "/Users/paulaaron/Miro Fish/MiroFish/backend/logs/memory_monitor.log"

while True:
    try:
        req = urllib.request.Request(url, headers={"Accept-Language": "en"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read()).get("data", {})
        
        status = d.get("runner_status", "unknown")
        current = d.get("current_round", 0)
        total = d.get("total_rounds", 0)
        pct = d.get("progress_percent", 0)
        actions = d.get("total_actions_count", 0)
        pid = d.get("process_pid", "?")
        
        # Get latest memory line
        try:
            result = subprocess.run(["tail", "-1", mem_log], capture_output=True, text=True, timeout=5)
            mem_line = result.stdout.strip().split("|")[-1].strip() if result.stdout else "N/A"
            python_rss = [x for x in result.stdout.strip().split() if "python_rss" in x]
            python_rss = python_rss[0] if python_rss else ""
        except:
            mem_line = "N/A"
            python_rss = ""
        
        print(f'{time.strftime("%H:%M:%S")} round={current}/{total} ({pct:.1f}%) actions={actions} status={status} pid={pid} {python_rss} | {mem_line}', flush=True)
        
        if status in ("completed", "failed", "error", "stopped"):
            print(f"\nFinal status: {status}")
            print(json.dumps(d, indent=2))
            break
    except Exception as e:
        print(f'{time.strftime("%H:%M:%S")} Error: {e}', flush=True)
    time.sleep(60)

print("SIMULATION_DONE", flush=True)
