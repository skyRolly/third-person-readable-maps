"""Ensure the diagnostic's client process is stopped on every exit path."""
from contextlib import contextmanager
import subprocess


@contextmanager
def managed_client(process, timeout=15):
    try:
        yield process
    finally:
        if process.poll() is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                process.wait()
