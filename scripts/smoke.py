import os
import time
import requests

API_KEY = os.environ["AIMLAPI_KEY"]
BASE = "https://api.aimlapi.com/v2"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

print("1. Submitting Seedance Lite generation job...")
submit = requests.post(
    f"{BASE}/generate/video/bytedance/generation",
    headers=HEADERS,
    json={
        "model": "bytedance/seedance-1-0-lite-t2v",
        "prompt": "A red panda eating bamboo in a snowy forest, cinematic slow motion",
    },
    timeout=30,
)
submit.raise_for_status()
job_id = submit.json()["id"]
print(f"   Job ID: {job_id}")

print("2. Polling for completion...")
start = time.time()
while True:
    poll = requests.get(
        f"{BASE}/video/generations?generation_id={job_id}",
        headers=HEADERS,
        timeout=30,
    )
    poll.raise_for_status()
    data = poll.json()
    status = data.get("status")
    elapsed = time.time() - start
    print(f"   [{elapsed:5.1f}s] status={status}")
    if status == "completed":
        video_url = data["video"]["url"]
        print(f"3. Done. Video URL: {video_url}")
        break
    if status == "failed":
        raise SystemExit(f"Generation failed: {data}")
    if elapsed > 300:
        raise SystemExit("Timeout after 5 minutes")
    time.sleep(5)

print("4. Downloading mp4...")
mp4 = requests.get(video_url, timeout=60).content
with open("smoke_output.mp4", "wb") as f:
    f.write(mp4)
print(f"   Saved smoke_output.mp4 ({len(mp4)/1024:.1f} KB)")
print("=== OK ===")