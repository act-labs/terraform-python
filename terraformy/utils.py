import subprocess
from typing import Tuple

def exec(*args, **kwargs) -> Tuple[str, int]:
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
    stdout = []
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        stripped = str(line, 'utf-8').rstrip()
        print (stripped)
        stdout.append(stripped)

    proc.communicate()

    return ("\n".join(stdout), proc.returncode)