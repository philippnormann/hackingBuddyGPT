import unittest
from hackingBuddyGPT.utils.llm_util import cmd_output_fixer, remove_nonprintable


class TestCmdOutputFixer(unittest.TestCase):
    def test_exec_command_in_bold_with_reasoning(self):
        raw = """
<think>some reasoning</think>
**exec_command find / -perm -4000**
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=True), "exec_command find / -perm -4000")

    def test_exec_command_no_bold(self):
        raw = "<think>x</think>exec_command id"
        self.assertEqual(cmd_output_fixer(raw, reasoning=True), "exec_command id")

    def test_double_wrapped(self):
        raw = """
<think>blah</think>
```bash
**exec_command whoami**```
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=True), "exec_command whoami")

    def test_exec_command_buried_in_prose_bold(self):
        raw = """
<think> blah </think>
The initial step is to gather user info.
**exec_command cat /etc/passwd**
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=True), "exec_command cat /etc/passwd")

    def test_bold_exec_anywhere(self):
        raw = """
blah blah
**exec_command cat /etc/passwd**
more chatter
"""
        got = cmd_output_fixer(raw, reasoning=False)
        self.assertEqual(got, "exec_command cat /etc/passwd")

    def test_exec_command_within_boxed(self):
        raw = """
<think>blah</think>
```bash
\\boxed{exec_command whoami}
```
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=True), "exec_command whoami")

    # Additional test cases for more scenarios
    def test_multiple_commands_return_first(self):
        """Test with multiple capability commands - should return the first one."""
        raw = """
I'll perform a sequence of commands:

**exec_command id**

Then:

**exec_command whoami**
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=False), "exec_command id")

    def test_command_with_quotes(self):
        """Test with an exec_command that contains quoted arguments."""
        raw = '```bash\nexec_command echo "Hello, world!"\n```'
        self.assertEqual(cmd_output_fixer(raw, reasoning=False), 'exec_command echo "Hello, world!"')

    def test_command_with_special_chars(self):
        """Test with an exec_command that contains special characters."""
        raw = '**exec_command grep -E "password|credentials" /etc/shadow**'
        self.assertEqual(
            cmd_output_fixer(raw, reasoning=False), 'exec_command grep -E "password|credentials" /etc/shadow'
        )

    def test_double_boxed_in_code(self):
        """Test with a command in a doubly-nested boxed environment."""
        raw = """
```python
\\boxed{\\boxed{exec_command ls -la}}
```
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=False), "exec_command ls -la")

    def test_complex_markdown_format(self):
        """Test with a command in markdown format with headers, lists, etc."""
        raw = """
# Security Analysis

## Initial Reconnaissance

1. First get user information:
   * **exec_command id -a**
   * This provides complete user identity
2. Then check system details
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=False), "exec_command id -a")

    def test_test_credential_capability(self):
        """Test with test_credential capability."""
        raw = """
<think>
Let's test the credentials I found
</think>

**test_credential user:password**
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=True), "test_credential user:password")

    def test_shell_prompt_removal(self):
        """Test removing shell prompt from commands."""
        raw = """
```bash
$ exec_command cat /etc/passwd
```
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=False), "exec_command cat /etc/passwd")

    def test_triple_nested_formats(self):
        """Test with triple nested formatting: code fence + boxed + bold."""
        raw = """
```
\\boxed{**exec_command find / -name "*.conf"**}
```
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=False), 'exec_command find / -name "*.conf"')

    def test_reasoning_without_think_tags(self):
        """Test with reasoning that isn't wrapped in think tags."""
        raw = """
First I'll check the system information with:
**exec_command uname -a**
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=True), "exec_command uname -a")

    def test_bare_reasoning_without_think_tags_multiple_lines(self):
        """Test with multi-line reasoning that isn't wrapped in think tags."""
        raw = """
Let me analyze this step by step.
First, we need to understand the system.
Then I'll examine key files.

I'll start with:
exec_command id
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=True), "exec_command id")

    def test_closing_think_tag_only(self):
        """Test with just a closing think tag and no opening tag."""
        raw = """
This is my reasoning about the system.
</think>

**exec_command whoami**
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=True), "exec_command whoami")

    def test_nonsense_commands_in_think_block(self):
        """Test with nonsense commands in a think block that should be ignored."""
        raw = """
<think>
Let me think through this carefully.
First, I should try executing:
fake_command something silly
nonsense_command doing nothing
exec_command that should also be ignored
random text that looks like a command but isn't
and in the end, I test_credential user:password
but I won't execute that.
</think>

Let's execute the real command:
**exec_command ls -la /etc/passwd**
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=True), "exec_command ls -la /etc/passwd")

    def test_heavily_nested_command(self):
        """Test with a heavily nested command (code block + boxed + bold)."""
        raw = """
Here's the command I'll execute:

```python
print("Command to execute:")
my_var = "\\boxed{**exec_command find /var/log -type f -name '*.log' -mtime -1**}"
# This should find log files modified in the last day
```
"""
        self.assertEqual(
            cmd_output_fixer(raw, reasoning=False), "exec_command find /var/log -type f -name '*.log' -mtime -1"
        )

    def test_plain_command_without_formatting(self):
        """Test with a command that has no formatting at all."""
        raw = """
Let me explore the system to understand its configuration.

exec_command uname -a
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=False), "exec_command uname -a")

    def test_multiline_command_with_think_tags(self):
        """Test with a multiline command that has think tags."""
        raw = """
<think>
My overall goal is to find a method to escalate to root privileges. Currently, I have already identified some potential vectors but need to confirm their exploitability. My immediate objective is to check if the `sudo` configuration allows me to leverage `script` to spawn an interactive shell with `less`, which could potentially give me root access.

Previously, the `sudo -l` command showed that the `lowpriv` user can run `/usr/bin/less` and `/usr/bin/man` with elevated privileges. This suggests that using `script` or similar commands might exploit this configuration. Testing this scenario could be done by specifying interactive commands within `script` or piping commands through `less`.

The primary command to test is `script -q /dev/null -c "sudo /usr/bin/less /etc/passwd" << 'EOF'!whoami q EOF"` to see if it successfully escalates privileges.
The alternative approach could be manually piping commands to `less` using `echo '!whoami' | sudo /usr/bin/less /etc/passwd`, but this method hasn't shown the expected result before.

I expect either the interactive method with `script` to successfully execute `whoami` as root or give me more insight into any limitations or additional configurations needed for a successful escalation.

This step leverages the `sudo -l` output that showed `less` and `man` can be run with `sudo`, building on that knowledge to test an interactive privilege escalation method.
</think>
exec_command script -q /dev/null -c "sudo /usr/bin/less /etc/passwd" << 'EOF'
!whoami
q
EOF
"""
        self.assertEqual(
            cmd_output_fixer(raw, reasoning=True),
            "exec_command script -q /dev/null -c \"sudo /usr/bin/less /etc/passwd\" << 'EOF'\n!whoami\nq\nEOF",
        )

    def test_remove_nonprintable_characters(self):
        """Test removing non-printable characters from the command."""
        raw = "exec_command \x00cat /etc/passwd\x01"
        self.assertEqual(remove_nonprintable(raw), "exec_command cat /etc/passwd")

        raw = """/usr/bin/top
/usr/bin/atq
/usr/bin/crontab
/usr/bin/atrm
/usr/bin/newgrp
/usr/bin/su
/usr/bin/batch
/usr/bin/at
/usr/bin/quota
/usr/bin/sudo
/usr/bin/login
/usr/libexec/security_authtrampoline
/usr/libexec/authopen
/usr/sbin/traceroute6
/usr/sbin/traceroute"""
        self.assertEqual(
            remove_nonprintable(raw),
            "/usr/bin/top\n/usr/bin/atq\n/usr/bin/crontab\n/usr/bin/atrm\n/usr/bin/newgrp\n"
            "/usr/bin/su\n/usr/bin/batch\n/usr/bin/at\n/usr/bin/quota\n/usr/bin/sudo\n"
            "/usr/bin/login\n/usr/libexec/security_authtrampoline\n/usr/libexec/authopen\n"
            "/usr/sbin/traceroute6\n/usr/sbin/traceroute",
        )

        # Test with ANSI color codes (simulating a root shell prompt)
        raw_with_ansi = "\x1b[01;31mroot@server\x1b[0m:\x1b[01;34m/home/user\x1b[0m# exec_command whoami\nroot"
        self.assertEqual(
            remove_nonprintable(raw_with_ansi),
            "root@server:/home/user# exec_command whoami\nroot"
        )