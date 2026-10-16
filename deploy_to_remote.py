import os
import glob
import time
import paramiko

REMOTE_HOST = "10.1.75.79"
REMOTE_PORT = 2240
REMOTE_USER = "student"
REMOTE_PASS = "antar2006"
REMOTE_BASE = "/home/student/Contour"

LOCAL_BASE = r"c:\Users\Abhigyan Sharma\OneDrive\Desktop\Contour"

def connect():
    print(f"Connecting to {REMOTE_USER}@{REMOTE_HOST}:{REMOTE_PORT}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(REMOTE_HOST, port=REMOTE_PORT, username=REMOTE_USER, password=REMOTE_PASS, timeout=20)
    sftp = ssh.open_sftp()
    print("SSH and SFTP connected successfully.")
    return ssh, sftp

def run_cmd(ssh, cmd):
    print(f"\n[REMOTE] $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        safe_out = out.encode("ascii", errors="replace").decode("ascii")
        print(safe_out)
    if err:
        safe_err = err.encode("ascii", errors="replace").decode("ascii")
        print(f"STDERR: {safe_err}")
    return out, err

def upload_file(sftp, local_rel, remote_rel=None):
    if remote_rel is None:
        remote_rel = local_rel.replace("\\", "/")
    
    local_path = os.path.join(LOCAL_BASE, local_rel)
    remote_path = f"{REMOTE_BASE}/{remote_rel}"
    
    # Ensure remote directory exists
    remote_dir = os.path.dirname(remote_path)
    try:
        sftp.stat(remote_dir)
    except IOError:
        pass
    
    print(f"Uploading: {local_rel} -> {remote_path}")
    sftp.put(local_path, remote_path)

def main():
    ssh, sftp = connect()

    # Step 1: Ensure remote directories
    run_cmd(ssh, f"mkdir -p {REMOTE_BASE}/telemetry_screenshots {REMOTE_BASE}/telemetry_tools {REMOTE_BASE}/storage")

    # Step 2: Upload modified code and reports
    files_to_upload = [
        "backend/telemetry.py",
        "backend/main.py",
        "backend/api/contour_analysis_routes.py",
        "backend/requirements.txt",
        "OPENTELEMETRY_REPORT.md",
        "OPENTELEMETRY_REPORT.html",
        "build_html_report.py"
    ]
    for rel in files_to_upload:
        upload_file(sftp, rel)

    # Step 3: Upload all screenshots
    screenshot_files = glob.glob(os.path.join(LOCAL_BASE, "telemetry_screenshots", "*.*"))
    for sf in screenshot_files:
        fname = os.path.basename(sf)
        upload_file(sftp, os.path.join("telemetry_screenshots", fname), f"telemetry_screenshots/{fname}")

    # Step 4: Install OpenTelemetry Python packages on the remote container
    print("\n--- Installing OpenTelemetry packages on remote container ---")
    run_cmd(ssh, "python3 -m pip install --break-system-packages opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-logging opentelemetry-exporter-otlp opentelemetry-exporter-prometheus prometheus-client markdown")

    # Step 5: Setup Jaeger on Linux
    print("\n--- Setting up Jaeger All-In-One for Linux on remote container ---")
    setup_jaeger_cmd = f"""
cd {REMOTE_BASE}/telemetry_tools
if [ ! -f jaeger-1.60.0-linux-amd64/jaeger-all-in-one ]; then
    echo "Downloading Jaeger Linux binary..."
    wget -q https://github.com/jaegertracing/jaeger/releases/download/v1.60.0/jaeger-1.60.0-linux-amd64.tar.gz -O jaeger-linux.tar.gz
    tar -xzf jaeger-linux.tar.gz
    chmod +x jaeger-1.60.0-linux-amd64/jaeger-all-in-one
    echo "Jaeger extracted."
else
    echo "Jaeger already downloaded."
fi
"""
    run_cmd(ssh, setup_jaeger_cmd)

    # Step 6: Start Jaeger in the background if not already running
    start_jaeger_cmd = f"""
if ! pgrep -f "jaeger-all-in-one" > /dev/null; then
    echo "Starting Jaeger All-in-One..."
    nohup {REMOTE_BASE}/telemetry_tools/jaeger-1.60.0-linux-amd64/jaeger-all-in-one > {REMOTE_BASE}/jaeger.log 2>&1 &
    sleep 2
    echo "Jaeger started."
else
    echo "Jaeger is already running."
fi
"""
    run_cmd(ssh, start_jaeger_cmd)

    # Step 7: Restart Uvicorn on remote so it loads the new OpenTelemetry instrumentation
    print("\n--- Restarting Uvicorn backend process on remote container ---")
    run_cmd(ssh, "pkill -f 'uvicorn backend.main:app' || true")
    time.sleep(3)

    # Check running processes
    run_cmd(ssh, "ps aux | grep -v grep | grep -E 'uvicorn|jaeger'")

    # Step 8: Verify endpoints locally on the container
    print("\n--- Verifying local endpoints on remote container ---")
    time.sleep(2)
    run_cmd(ssh, "curl -s -o /dev/null -w 'GET / status: %{http_code}\\n' http://localhost:5000/")
    run_cmd(ssh, "curl -s -o /dev/null -w 'GET /metrics status: %{http_code}\\n' http://localhost:5000/metrics")
    run_cmd(ssh, "curl -s http://localhost:5000/api/telemetry/overview")

    # Step 9: Run a test contour analysis request on the container to generate remote traces
    print("\n--- Generating test trace on remote container ---")
    run_cmd(ssh, f"curl -s -X POST 'http://localhost:5000/api/analyzeContour' -F 'file=@{REMOTE_BASE}/contours_1m.kml' | head -c 200; echo ''")

    # Step 10: Check telemetry spans and Jaeger on remote
    run_cmd(ssh, "curl -s http://localhost:5000/api/telemetry/overview")
    run_cmd(ssh, "curl -s 'http://localhost:16686/api/traces?service=village-pond-planning-system' | head -c 200; echo ''")

    sftp.close()
    ssh.close()
    print("\nDeployment to remote container COMPLETED successfully!")

if __name__ == "__main__":
    main()
