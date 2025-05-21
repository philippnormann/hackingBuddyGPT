import unittest
from hackingBuddyGPT.utils.llm_util import cmd_output_fixer


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

    def test_exec_command_with_sg(self):
        """Test with an exec_command that uses the sg command."""
        raw = """
I think the messagebus user might have the same password as lowpriv. Let me try to switch to the messagebus group using the sg command and provide the trustno1 password.

**Step-by-Step Explanation:**
I will use the sg command to attempt to switch to the messagebus group and provide the password trustno1. If successful, this may grant me access to the messagebus account, potentially leading to further privilege escalation.

exec_command sg messagebus
Password: trustno1
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=True), "exec_command sg messagebus")
        
    def test_plain_command_without_formatting(self):
        """Test with a command that has no formatting at all."""
        raw = """
Let me explore the system to understand its configuration.

exec_command uname -a

This will give us information about the kernel version.
"""
        self.assertEqual(cmd_output_fixer(raw, reasoning=False), "exec_command uname -a")
