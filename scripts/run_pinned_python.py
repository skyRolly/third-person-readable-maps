#!/usr/bin/env python3
"""Launch a setup-python executable by absolute path, not PATH resolution."""
import re
import subprocess
import sys
from pathlib import Path


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 3 or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", args[1]):
        print("pinned Python: invalid executable/version/command arguments", file=sys.stderr)
        return 2
    executable, expected = Path(args[0]), args[1]
    if not executable.is_absolute() or not executable.is_file():
        print("pinned Python: absolute setup-python executable required", file=sys.stderr)
        return 2
    try:
        probe = subprocess.run([str(executable), "-c", "import sys; print(sys.version.split()[0])"],
                               capture_output=True, text=True, check=False)
        if probe.returncode != 0 or probe.stdout.strip() != expected:
            print("pinned Python: interpreter version mismatch (expected " + expected + ")", file=sys.stderr)
            return 2
        result = subprocess.run([str(executable), *args[2:]], check=False)
        return result.returncode if result.returncode >= 0 else 128 - result.returncode
    except OSError:
        print("pinned Python: executable unavailable", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
