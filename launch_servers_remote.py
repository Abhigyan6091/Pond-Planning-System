import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("10.1.75.79", port=2240, username="student", password="antar2006", timeout=15)

def run(cmd):
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(out)
    if err:
        print("STDERR: " + err)
    return out, err

# 1. Kill any existing uvicorn and jaeger
run("pkill -9 -f 'uvicorn backend.main:app' || true")
run("pkill -9 -f 'jaeger-all-in-one' || true")
time.sleep(2)

# 2. Launch Jaeger All-in-One in background
print("\nStarting Jaeger All-In-One...")
run("nohup /home/student/Contour/telemetry_tools/jaeger-1.60.0-linux-amd64/jaeger-all-in-one > /home/student/Contour/jaeger.log 2>&1 < /dev/null &")
time.sleep(3)

# 3. Launch Uvicorn backend in background on port 5000
print("\nStarting Uvicorn on 0.0.0.0:5000...")
run("cd /home/student/Contour && nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 5000 > /home/student/Contour/server.log 2>&1 < /dev/null &")
time.sleep(4)

# 4. Check active processes
run("ps aux | grep -v grep | grep -E 'uvicorn|jaeger'")

# 5. Check endpoints locally
run("curl -s -o /dev/null -w 'GET / HTTP Status: %{http_code}\\n' http://localhost:5000/")
run("curl -s -o /dev/null -w 'GET /telemetry HTTP Status: %{http_code}\\n' http://localhost:5000/telemetry")
run("curl -s -o /dev/null -w 'GET /metrics HTTP Status: %{http_code}\\n' http://localhost:5000/metrics")
run("curl -s http://localhost:5000/api/telemetry/overview")

# 6. Run a real contour analysis request on the remote container to populate traces & metrics!
print("\nSubmitting contours_1m.kml to /api/analyzeContour...")
run("curl -s -X POST http://localhost:5000/api/analyzeContour -F 'file=@/home/student/Contour/contours_1m.kml' | python3 -m json.tool | head -n 25")

# 7. Check traces in Jaeger and telemetry overview
time.sleep(2)
run("curl -s http://localhost:5000/api/telemetry/overview")
run("curl -s 'http://localhost:16686/api/traces?service=village-pond-planning-system' | python3 -m json.tool | head -n 35")

ssh.close()
