"""Resolve fixture tools from JAVA_HOME, or PATH when it is unset."""
import os
from pathlib import Path
import shutil


def which(name):
    if name not in ('java', 'javac'):
        raise ValueError('unsupported JDK tool: ' + name)
    home = os.environ.get('JAVA_HOME')
    if home:
        executable = Path(home) / 'bin' / (name + ('.exe' if os.name == 'nt' else ''))
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise FileNotFoundError('JAVA_HOME does not provide ' + name + ': ' + str(executable))
        return str(executable)
    return shutil.which(name)
