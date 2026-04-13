#!/usr/bin/env python3
import urllib.request
import json
import time
import sys

sim_id = sys.argv[1] if len(sys.argv) > 1 else "sim_c83772b4f6fe"
url = "http://localhost:5001/api/simulation/prepare/status"

while True:
    try:
        body = json.dumps({"simulation_id": sim_id}).encode()
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            "Accept-Language": "en"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read()).get("data", {})
        
        status = d.get("status", "unknown")
        progress = d.get("progress", {})
        if isinstance(progress, dict):
            profiles = progress.get("profiles_generated", 0)
            total = progress.get("total_entities", 0)
            config = progress.get("config_generated", False)
            print(f'{time.strftime("%H:%M:%S")} Status: {status} | profiles: {profiles}/{total} | config: {config}', flush=True)
        else:
            print(f'{time.strftime("%H:%M:%S")} Status: {status} | progress: {progress}', flush=True)
        
        if status in ("ready", "failed", "error"):
            print(json.dumps(d, indent=2))
            break
    except Exception as e:
        print(f'{time.strftime("%H:%M:%S")} Error: {e}', flush=True)
    time.sleep(30)

print("DONE", flush=True)
