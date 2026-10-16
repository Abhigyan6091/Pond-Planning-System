import paramiko
import json
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
        safe_out = out.encode("ascii", errors="replace").decode("ascii")
        print(safe_out)
    if err:
        safe_err = err.encode("ascii", errors="replace").decode("ascii")
        print("STDERR: " + safe_err)
    return out, err

# 1. Test basic HTTP endpoints locally inside container
run("curl -s -o /dev/null -w 'GET / -> HTTP %{http_code}\n' http://localhost:5000/")
run("curl -s -o /dev/null -w 'GET /telemetry -> HTTP %{http_code}\n' http://localhost:5000/telemetry")
run("curl -s -o /dev/null -w 'GET /metrics -> HTTP %{http_code}\n' http://localhost:5000/metrics")

# 2. Check telemetry overview before contour analysis
run("curl -s http://localhost:5000/api/telemetry/overview")

# 3. Post contours_1m.kml to /api/analyzeContour
print("\n--- Submitting contours_1m.kml to /api/analyzeContour on remote container ---")
run("curl -s -X POST http://localhost:5000/api/analyzeContour -F 'file=@/home/student/Contour/contours_1m.kml' -o /home/student/Contour/last_analysis.json")
run("python3 -c \"import json; d = json.load(open('/home/student/Contour/last_analysis.json')); print('Success:', d.get('success'), '| Pond site:', d.get('pond_site', {}).get('latitude'), d.get('pond_site', {}).get('longitude'), '| Catchment m2:', d.get('catchment', {}).get('area_m2'))\"")

# 4. Check telemetry overview after contour analysis
run("curl -s http://localhost:5000/api/telemetry/overview")

# 5. Query Jaeger traces on remote container
run("python3 -c \"import requests; r = requests.get('http://localhost:16686/api/traces?service=village-pond-planning-system'); traces = r.json().get('data', []); print('Jaeger Traces Count:', len(traces)); [print('TraceID:', t['traceID'], 'spans:', len(t['spans'])) for t in traces]\"")

# 6. Check storage/opentelemetry.log on remote container
run("tail -n 15 /home/student/Contour/storage/opentelemetry.log")

ssh.close()
