import shlex
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    interpreter = Path(sys.executable).absolute()
    checker = root / "check_comments.py"
    subprocess.run([str(interpreter), "-EsB", str(checker), "--help"], check=True,
                   stdout=subprocess.DEVNULL)
    probe = subprocess.run(["git", "hook", "list", "pre-commit"], capture_output=True)
    if probe.returncode not in (0, 1) or b"usage: git hook" in probe.stderr:
        raise SystemExit("This Git must support configurable hooks (git hook list).")
    command = shlex.join([str(interpreter), "-EsB", str(checker), "--staged"])
    for key, value in (("command", command), ("event", "pre-commit")):
        subprocess.run(["git", "config", "--global", "--replace-all",
                        f"hook.source-comment-check.{key}", value], check=True)
    result = subprocess.run(["git", "hook", "list", "pre-commit"], capture_output=True, text=True)
    if "source-comment-check" not in result.stdout.splitlines():
        raise SystemExit("The configured hook is unavailable in this checkout.")
    print("Installed the shared pre-commit check.")


if __name__ == "__main__":
    main()
