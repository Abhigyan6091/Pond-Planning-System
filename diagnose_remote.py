import paramiko

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

run("ps aux | grep -v grep | grep -E 'python|uvicorn|jaeger'")
run("tail -n 30 /home/student/Contour/server.log")
run("tail -n 30 /home/student/Contour/jaeger.log")

ssh.close()
