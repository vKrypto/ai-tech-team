import subprocess


def git(args: list[str], cwd) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120)
    out = (r.stdout + (("\n" + r.stderr) if r.stderr else "")).strip()
    return out if r.returncode == 0 else f"git exited {r.returncode}: {out}"
