"""Run ordinary publication and wrapper archival, preserving either failure."""

import subprocess
import sys


def main():
    """Attempt both phases inside the updater container."""
    failed = False
    for arguments in (["run"], ["run", "--archive"]):
        result = subprocess.run(["/app/.venv/bin/updateloop", *arguments], check=False)
        failed |= result.returncode != 0
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
