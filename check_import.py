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

run("cd /home/student/Contour && python3 -c 'from backend.main import app; print(\"APP LOADED SUCCESSFUL!\")'")

ssh.close()
