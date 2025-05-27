from typing import Optional

from .llm_util import LLM, trim_result_front, remove_think_block


class SlidingCliHistory:
    model: LLM
    maximum_target_size: int
    sliding_history: str
    last_output: str
    summarize_template: Optional[object]

    def __init__(self, used_model: LLM, summarize_template=None, reasoning=False):
        self.model = used_model
        self.maximum_target_size = used_model.context_size
        self.sliding_history = ""
        self.last_output = ""
        self.summarize_template = summarize_template
        self.reasoning = reasoning

    def _count_lines(self, text: str) -> int:
        """Count the number of lines in the text."""
        return len(text.split('\n'))

    def _summarize_output(self, cmd: str, output: str) -> str:
        """Summarize long output using the provided template."""
        if self.summarize_template is None:
            return output
        
        try:
            result = self.model.get_response(
                self.summarize_template,
                command=cmd,
                long_output=output
            )
            if self.reasoning:
                result.result = remove_think_block(result.result)
            return f"[SUMMARIZED OUTPUT]\n{result.result}"
        except Exception:
            # If summarization fails, fall back to truncating
            lines = output.split('\n')
            if len(lines) > 100:
                return '\n'.join(lines[:50] + ['...', '[OUTPUT TRUNCATED - TOO LONG]', '...'] + lines[-10:])
            return output

    def add_command(self, cmd: str, output: str):
        # Check if output is longer than 100 lines and summarize if needed
        if self._count_lines(output) > 100:
            output = self._summarize_output(cmd, output)
        
        self.sliding_history += f"$ {cmd}\n{output}"
        self.sliding_history = trim_result_front(self.model, self.maximum_target_size, self.sliding_history)

    def get_history(self, target_size: int) -> str:
        return trim_result_front(self.model, min(self.maximum_target_size, target_size), self.sliding_history)

    def add_command_only(self, cmd: str, output: str):
        self.sliding_history +=  f"$ {cmd}\n"
        self.last_output = output
        last_output_size = self.model.count_tokens(self.last_output)
        if self.maximum_target_size - last_output_size < 0:
            last_output_size = 0
            self.last_output = ''
        self.sliding_history = trim_result_front(self.model, self.maximum_target_size - last_output_size, self.sliding_history)

    def get_commands_and_last_output(self, target_size: int) -> str:
        return trim_result_front(self.model, min(self.maximum_target_size, target_size), self.sliding_history + self.last_output)