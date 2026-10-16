import paramiko

def connect_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("10.1.75.79", port=2240, username="student", password="antar2006", timeout=15)
    return ssh

def run_cmd(ssh, cmd):
    print(f"\n>>> Running: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print("STDOUT:\n" + out.strip())
    if err:
        print("STDERR:\n" + err.strip())
    return out, err

if __name__ == "__main__":
    ssh = connect_ssh()
    run_cmd(ssh, "python3 -m pip list | grep -E 'opentelemetry|fastapi|uvicorn|prometheus'")
    run_cmd(ssh, "curl -I http://localhost:5000/")
    run_cmd(ssh, "which wget; which curl; which tar; which git")
    ssh.close()
