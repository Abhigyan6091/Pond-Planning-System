import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("10.1.75.79", port=2240, username="student", password="antar2006", timeout=15)

supervisor_content = """#!/bin/bash
cd /home/student/Contour
export PYTHONPATH=/home/student/Contour:$PYTHONPATH
export PATH=/home/student/.local/bin:$PATH

echo "[$(date)] Starting Contour + OpenTelemetry 24/7 Supervisor..." >> /home/student/Contour/supervisor.log

if ! pgrep -f "jaeger-all-in-one" > /dev/null; then
    echo "[$(date)] Starting Jaeger All-In-One..." >> /home/student/Contour/supervisor.log
    nohup /home/student/Contour/telemetry_tools/jaeger-1.60.0-linux-amd64/jaeger-all-in-one > /home/student/Contour/jaeger.log 2>&1 < /dev/null &
    sleep 2
fi

while true; do
    if ! pgrep -f "jaeger-all-in-one" > /dev/null; then
        echo "[$(date)] Respawning Jaeger..." >> /home/student/Contour/supervisor.log
        nohup /home/student/Contour/telemetry_tools/jaeger-1.60.0-linux-amd64/jaeger-all-in-one > /home/student/Contour/jaeger.log 2>&1 < /dev/null &
        sleep 1
    fi
    echo "[$(date)] Launching Uvicorn on 0.0.0.0:5000..." >> /home/student/Contour/supervisor.log
    /usr/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 5000 >> /home/student/Contour/server.log 2>&1
    EXIT_CODE=$?
    echo "[$(date)] Uvicorn exited with code $EXIT_CODE. Restarting in 2 seconds..." >> /home/student/Contour/supervisor.log
    sleep 2
done
"""

sftp = ssh.open_sftp()
with sftp.open("/home/student/Contour/supervisor.sh", "w") as f:
    f.write(supervisor_content)

stdin, stdout, stderr = ssh.exec_command("chmod +x /home/student/Contour/supervisor.sh; head -n 12 /home/student/Contour/supervisor.sh")
print(stdout.read().decode())
sftp.close()
ssh.close()
print("Supervisor successfully updated on remote container!")
