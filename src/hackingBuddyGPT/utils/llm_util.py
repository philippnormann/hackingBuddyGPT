import abc
import datetime
import re
import typing
from dataclasses import dataclass

from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionFunctionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)

SAFETY_MARGIN = 128
STEP_CUT_TOKENS = 128


@dataclass
class LLMResult:
    result: typing.Any
    prompt: str
    answer: str
    duration: datetime.timedelta = datetime.timedelta(0)
    tokens_query: int = 0
    tokens_response: int = 0


class LLM(abc.ABC):
    @abc.abstractmethod
    def get_response(self, prompt, *, capabilities=None, **kwargs) -> LLMResult:
        """
        get_response prompts the LLM with the given prompt and returns the result
        The capabilities parameter is not yet in use, but will be used to pass function calling style capabilities in the
        future. Please do not use it at the moment!
        """
        pass

    @abc.abstractmethod
    def encode(self, query) -> list[int]:
        pass

    def count_tokens(self, query) -> int:
        return len(self.encode(query))


def system_message(content: str) -> ChatCompletionSystemMessageParam:
    return {"role": "system", "content": content}


def user_message(content: str) -> ChatCompletionUserMessageParam:
    return {"role": "user", "content": content}


def assistant_message(content: str) -> ChatCompletionAssistantMessageParam:
    return {"role": "assistant", "content": content}


def tool_message(content: str, tool_call_id: str) -> ChatCompletionToolMessageParam:
    return {"role": "tool", "content": content, "tool_call_id": tool_call_id}


def function_message(content: str, name: str) -> ChatCompletionFunctionMessageParam:
    return {"role": "function", "content": content, "name": name}

def remove_nonprintable(text: str) -> str:
    """
    Remove non-printable characters from the text, including ANSI escape sequences.
    This is useful to clean up command outputs that may contain control characters
    and terminal color codes.

    Args:
        text: The input text to be cleaned.

    Returns:
        Cleaned text with ANSI escape sequences and non-printable characters removed.
    """
    # First remove ANSI escape sequences (ESC followed by [ and parameters)
    ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
    text = ansi_escape.sub('', text)
    
    # Then remove other non-printable characters
    return ''.join(c for c in text if c.isprintable() or c.isspace())

def remove_wrapping_characters(cmd: str, wrappers: str) -> str:
    if len(cmd) < 2:
        return cmd
    if cmd[0] == cmd[-1] and cmd[0] in wrappers:
        print("will remove a wrapper from: " + cmd)
        return remove_wrapping_characters(cmd[1:-1], wrappers)
    return cmd


def remove_think_block(text: str) -> str:
    """
    Remove <think> tags and their content from text.
    Handles both properly closed tags and unclosed tags.

    Args:
        text: The input text that may contain think blocks

    Returns:
        Text with think blocks removed
    """
    if not text or len(text) < 2:
        return text

    # Remove properly closed think tags first
    result = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    # Handle closing tags without opening tags
    result = re.sub(r".*?</think>", "", result, flags=re.DOTALL)

    return result


# extract the next command from the LLM output
def cmd_output_fixer(cmd: str, capabilities=None, reasoning=False) -> str:
    """
    Extracts the command from the LLM output, removing unnecessary formatting and tags.

    Args:
        cmd: The command string to be processed.
        capabilities: A list of capabilities to look for in the command.
        reasoning: A boolean indicating if reasoning is enabled.

    Returns:
        The cleaned command string.
    """
    # Default capabilities if none provided
    if capabilities is None:
        capabilities = ["exec_command", "test_credential"]

    cmd = cmd.strip(" \n")
    if len(cmd) < 2:
        return cmd

    # Remove think tags and their content if reasoning is enabled
    if reasoning:
        cmd = remove_think_block(cmd)

    # Extract commands from code fence blocks (```...```)
    code_fence_pattern = re.compile(r"```.*?\n(.*?)\n```", re.DOTALL)
    result = code_fence_pattern.search(cmd)
    if result:
        cmd = result.group(1)

    # Extract commands from tilde fence blocks (~~~...~~~)
    tilde_fence_pattern = re.compile(r"~~~.*?\n(.*?)\n~~~", re.DOTALL)
    result = tilde_fence_pattern.search(cmd)
    if result:
        cmd = result.group(1)

    # Handle boxed commands
    boxed_pattern = re.compile(r"\\boxed{(.*?)}", re.DOTALL)
    while re.search(boxed_pattern, cmd):
        cmd = re.sub(boxed_pattern, r"\1", cmd)

    # Extract bold commands (**...**)
    bold_pattern = re.compile(r"\*\*(.*?)\*\*", re.DOTALL)
    # Look for all bold sections and prioritize the one that contains our command patterns
    if capabilities is not None:
        command_prefixes = "|".join(re.escape(pattern) for pattern in capabilities)
        for bold_match in bold_pattern.finditer(cmd):
            bold_content = bold_match.group(1)
            if re.search(f"({command_prefixes})\\s+", bold_content):
                cmd = bold_content
                break
    else:
        # Fall back to just using the first bold section if no capability matched
        result = bold_pattern.search(cmd)
        if result:
            cmd = result.group(1)

    # Remove shell prompt if present
    if cmd.startswith("$ "):
        cmd = cmd[2:]

    # Remove any remaining wrapping characters
    cmd = remove_wrapping_characters(cmd, "`'\"")

    # Build pattern for command detection based on provided command_patterns
    pattern_str = "|".join(f"{pattern}\\s+.*" for pattern in capabilities)
    cmd_pattern = re.compile(f"({pattern_str})", re.DOTALL)
    result = cmd_pattern.search(cmd)
    if result:
        cmd = result.group(1)

    return cmd.strip()


# this is ugly, but basically we only have an approximation how many tokens
# we are currently using. So we cannot just cut down to the desired size
# what we're doing is:
#   - take our current token count
#   - use the minimum of (current_count, desired count *2)
#     - this get's us roughly in the ballpark of the desired size
#     - as long as we assume that 2 * desired-count will always be larger
#       than the unschaerfe introduced by the string-.token conversion
#   - do a 'binary search' to cut-down to the desired size afterwards
#
# this should reduce the time needed to do the string->token conversion
# as this can be long-running if the LLM puts in a 'find /' output
def trim_result_front(model: LLM, target_size: int, result: str) -> str:
    cur_size = model.count_tokens(result)
    TARGET_SIZE_FACTOR = 3
    if cur_size > TARGET_SIZE_FACTOR * target_size:
        print(f"big step trim-down from {cur_size} to {2 * target_size}")
        result = result[: TARGET_SIZE_FACTOR * target_size]
        cur_size = model.count_tokens(result)

    while cur_size > target_size:
        print(f"need to trim down from {cur_size} to {target_size}")
        diff = cur_size - target_size
        step = int((diff + STEP_CUT_TOKENS) / 2)
        result = result[:-step]
        cur_size = model.count_tokens(result)

    return result
