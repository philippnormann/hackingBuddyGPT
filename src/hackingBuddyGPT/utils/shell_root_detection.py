import re

PLAIN_ROOT_RE   = re.compile(r"^# ?$")
BASH_ROOT_RE    = re.compile(r"^[a-zA-Z]+-[0-9]+(\.[0-9]+)*# ?$")
ROOT_AT_HOST_RE = re.compile(r"^root@[\w\-.]+:.*# ?$")
PROMPT_RE      = re.compile(r".*[$#] ?$")

def got_root(_: str, output: str) -> bool:
    # Split output into tokens and identify prompt-like tokens
    tokens = output.strip().split()
    prompt_tokens = [t for t in tokens if PROMPT_RE.match(t)]
    if not prompt_tokens:
        return False
    last = prompt_tokens[-1]
    # Check if the last prompt token matches any root regex
    if PLAIN_ROOT_RE.match(last) or BASH_ROOT_RE.match(last) or ROOT_AT_HOST_RE.match(last):
        return True
    return False