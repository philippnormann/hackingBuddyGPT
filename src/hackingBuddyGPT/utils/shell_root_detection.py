import re

PLAIN_ROOT_RE   = re.compile(r"^# ?$")
BASH_ROOT_RE    = re.compile(r"^bash-[0-9]+(\.[0-9]+)*# ?$")
ROOT_AT_HOST_RE = re.compile(r"^root@[\w\-.]+:.*# ?$")

def got_root(_: str, output: str) -> bool:
    line = output.strip()

    if PLAIN_ROOT_RE.match(line):
        return True
    if BASH_ROOT_RE.match(line):
        return True
    if ROOT_AT_HOST_RE.match(line):
        return True
    return False