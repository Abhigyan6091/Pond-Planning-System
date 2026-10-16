import paramiko
import time
import requests

REMOTE_HOST = "10.1.75.79"
REMOTE_PORT = 2240
REMOTE_USER = "student"
REMOTE_PASS = "antar2006"
REMOTE_BASE = "/home/student/Contour"
LOCAL_TELEMETRY = r"c:\Users\Abhigyan Sharma\OneDrive\Desktop\Contour\backend\telemetry.py"

print("1. Connecting SSH & SFTP...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(REMOTE_HOST, port=REMOTE_PORT, username=REMOTE_USER, password=REMOTE_PASS, timeout=20)
sftp = ssh.open_sftp()

print("2. Uploading updated backend/telemetry.py...")
sftp.put(LOCAL_TELEMETRY, f"{REMOTE_BASE}/backend/telemetry.py")
print("Upload complete.")

def run(cmd):
    print(f"\n[REMOTE] $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(out)
    if err:
        print("STDERR: " + err)
    return out, err

print("\n3. Updating supervisor.sh on remote...")
supervisor_script = """#!/bin/bash
cd /home/student/Contour
export PYTHONPATH=/home/student/Contour:$PYTHONPATH
export PATH=/home/student/.local/bin:$PATH

echo "[$(date)] Supervisor starting services..." >> /home/student/Contour/supervisor.log

if ! pgrep -f "jaeger-all-in-one" > /dev/null; then
    echo "[$(date)] Starting Jaeger All-In-One with --query.base-path=/jaeger..." >> /home/student/Contour/supervisor.log
    nohup /home/student/Contour/telemetry_tools/jaeger-1.60.0-linux-amd64/jaeger-all-in-one --query.base-path=/jaeger > /home/student/Contour/jaeger.log 2>&1 < /dev/null &
    sleep 2
fi

while true; do
    if ! pgrep -f "jaeger-all-in-one" > /dev/null; then
        echo "[$(date)] Respawning Jaeger with --query.base-path=/jaeger..." >> /home/student/Contour/supervisor.log
        nohup /home/student/Contour/telemetry_tools/jaeger-1.60.0-linux-amd64/jaeger-all-in-one --query.base-path=/jaeger > /home/student/Contour/jaeger.log 2>&1 < /dev/null &
        sleep 1
    fi
    echo "[$(date)] Launching Uvicorn on 0.0.0.0:5000..." >> /home/student/Contour/supervisor.log
    /usr/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 5000 >> /home/student/Contour/server.log 2>&1
    EXIT_CODE=$?
    echo "[$(date)] Uvicorn exited with code $EXIT_CODE. Restarting in 2s..." >> /home/student/Contour/supervisor.log
    sleep 2
done
"""
with sftp.open(f"{REMOTE_BASE}/supervisor.sh", "w") as f:
    f.write(supervisor_script)
run("chmod +x /home/student/Contour/supervisor.sh")

print("\n4. Stopping existing processes...")
run("pkill -9 -f supervisor.sh || true")
run("pkill -9 -f 'uvicorn backend.main:app' || true")
run("pkill -9 -f jaeger-all-in-one || true")
time.sleep(2)

print("\n5. Starting Jaeger All-In-One with --query.base-path=/jaeger...")
run("nohup /home/student/Contour/telemetry_tools/jaeger-1.60.0-linux-amd64/jaeger-all-in-one --query.base-path=/jaeger > /home/student/Contour/jaeger.log 2>&1 < /dev/null &")
time.sleep(3)

print("\n6. Starting Supervisor in background...")
run("nohup /home/student/Contour/supervisor.sh > /dev/null 2>&1 < /dev/null &")
time.sleep(4)

print("\n7. Verifying processes on remote...")
run("ps aux | grep -v grep | grep -E 'python|uvicorn|jaeger|supervisor'")

print("\n8. Testing internal endpoints on container...")
run("curl -s -I http://localhost:5000/jaeger/")
run("curl -s http://localhost:5000/jaeger/api/services")
run("curl -s http://localhost:5000/api/telemetry/overview")

print("\n9. Triggering contour analysis to generate fresh spans...")
run("curl -s -X POST http://localhost:5000/api/analyzeContour -F 'file=@/home/student/Contour/contours_1m.kml' -o /dev/null -w 'Analyze status: HTTP %{http_code}\\n'")
time.sleep(3)

print("\n10. Checking traces via proxied endpoint http://localhost:5000/jaeger/api/traces...")
run("curl -s 'http://localhost:5000/jaeger/api/traces?service=village-pond-planning-system' | python3 -c \"import sys, json; d=json.load(sys.stdin); traces=d.get('data', []); print('Proxied Jaeger Traces Count:', len(traces)); [print(' - TraceID:', t['traceID'], 'spans:', len(t['spans'])) for t in traces[:3]]\"")

sftp.close()
ssh.close()

print("\n11. Testing external access from this machine to http://10.1.75.79:5240/jaeger/ ...")
try:
    r_ui = requests.get("http://10.1.75.79:5240/jaeger/", timeout=10)
    print(f"External GET /jaeger/ -> HTTP {r_ui.status_code} ({len(r_ui.content)} bytes)")
    print(f"Title in HTML: {'<title>Jaeger UI</title>' in r_ui.text}")
    
    r_api = requests.get("http://10.1.75.79:5240/jaeger/api/services", timeout=10)
    print(f"External GET /jaeger/api/services -> HTTP {r_api.status_code}")
    print(f"Services JSON: {r_api.json()}")
    
    r_overview = requests.get("http://10.1.75.79:5240/api/telemetry/overview", timeout=10)
    print(f"External GET /api/telemetry/overview -> {r_overview.json()}")
    
    print("\nSUCCESS! Remote Jaeger is now fully working and accessible via port 5240!")
except Exception as e:
    print(f"External check error: {e}")
