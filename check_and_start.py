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

run("ps aux | grep -v grep | grep -E 'python|uvicorn|jaeger|supervisor'")
run("tail -n 25 /home/student/Contour/server.log")

# If uvicorn is not running, let's start it via nohup
out, _ = run("pgrep -f 'uvicorn backend.main:app' || true")
if not out:
    print("\nStarting uvicorn backend on port 5000 in background...")
    run("cd /home/student/Contour && nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 5000 > /home/student/Contour/server.log 2>&1 &")
    time.sleep(3)
    run("ps aux | grep -v grep | grep uvicorn")

# Test local endpoints
run("curl -I http://localhost:5000/")
run("curl -I http://localhost:5000/metrics")
run("curl -s http://localhost:5000/api/telemetry/overview")

ssh.close()
